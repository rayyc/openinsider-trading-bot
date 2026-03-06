#src/trade_execution.py
import alpaca_trade_api as tradeapi
from datetime import datetime
import time
import structlog
from src.config import config
import logging

logger = structlog.get_logger()
logger = logging.getLogger(__name__)

class TradeExecutor:
    def __init__(self):
        self.api = tradeapi.REST(
            config.ALPACA_API_KEY,
            config.ALPACA_SECRET_KEY,
            config.ALPACA_BASE_URL,
            api_version='v2'
        )
        self.positions = {}

    def execute_trades(self, signals, portfolio_value=None, max_capital_per_trade=None):
        """Execute trades with position limits and fill verification."""
        if not portfolio_value:
            portfolio_value = self._get_portfolio_value()

        if not max_capital_per_trade:
            # Default to 2% if not specified
            max_capital_per_trade = portfolio_value * 0.02

        executed_trades = []

        for signal in signals:
            ticker = signal['ticker']

            try:
                # Get current price
                current_price = self._get_current_price(ticker)
                if not current_price or current_price <= 0:
                    logger.warning(f"Invalid price for {ticker}: ${current_price}")
                    continue

                # Calculate shares based on max_capital_per_trade
                max_shares = int(max_capital_per_trade / current_price)
                shares_to_buy = max(1, max_shares)

                # Check actual buying power
                account = self.api.get_account()
                buying_power = float(account.buying_power)
                order_value = shares_to_buy * current_price

                if order_value > buying_power:
                    shares_to_buy = int(buying_power / current_price)
                    if shares_to_buy <= 0:
                        logger.warning(f"Insufficient buying power for {ticker}")
                        continue

                # --- SAFE STOP LOSS / TAKE PROFIT CALCULATION ---
                if config.USE_PERCENTAGE_MODE_TRADES:
                    stop_price = current_price * (1 - config.STOP_LOSS_PCT)
                    take_profit_price = current_price * (1 + config.TAKE_PROFIT_PCT)
                else:
                    stop_price = current_price - config.STOP_LOSS_USD
                    take_profit_price = current_price + config.TAKE_PROFIT_USD

                # Enforce Alpaca’s rules
                stop_price = min(stop_price, current_price - 0.01)
                stop_price = max(0.01, round(stop_price, 2))  # must be > 0
                stop_limit_price = max(0.01, round(stop_price - 0.01, 2))
                take_profit_price = max(0.01, round(take_profit_price, 2))

                # Debug log for calculated values
                logger.info(
                    f"Calculated risk params for {ticker}: "
                    f"Stop={stop_price}, StopLimit={stop_limit_price}, TakeProfit={take_profit_price}"
                )

                # Place bracket order
                order = self.api.submit_order(
                    symbol=ticker,
                    qty=shares_to_buy,
                    side='buy',
                    type='market',
                    time_in_force='day',
                    order_class='bracket',
                    take_profit={'limit_price': take_profit_price},
                    stop_loss={'stop_price': stop_price, 'limit_price': stop_limit_price}
                )

                # ===== VERIFY ORDER FILL =====
                order_filled = False
                avg_fill_price = current_price
                order_status = None

                for attempt in range(30):
                    order_status = self.api.get_order(order.id)
                    if order_status.status == 'filled':
                        order_filled = True
                        avg_fill_price = float(order_status.filled_avg_price) if order_status.filled_avg_price else current_price
                        logger.info(f"ORDER FILLED: {ticker} - {shares_to_buy} shares @ ${avg_fill_price:.2f}")
                        break
                    elif order_status.status in ('rejected', 'canceled', 'expired'):
                        logger.error(f"ORDER FAILED: {ticker} - Final Status: {order_status.status}")
                        executed_trades.append({
                            'ticker': ticker,
                            'shares': shares_to_buy,
                            'price': current_price,
                            'value': order_value,
                            'status': 'failed',
                            'reason': order_status.status,
                            'order_id': order.id,
                            'timestamp': datetime.now().isoformat()
                        })
                        break
                    time.sleep(1)
                else:
                    if order_status and order_status.status not in ('rejected', 'canceled', 'expired'):
                        logger.warning(f"ORDER NOT FILLED: {ticker} - Order stuck as '{order_status.status}' after 30 seconds.")
                        try:
                            self.api.cancel_order(order.id)
                            logger.info(f"Cancelled unfilled order for {ticker}")
                        except Exception as cancel_error:
                            logger.warning(f"Could not cancel order for {ticker}: {cancel_error}")
                    continue

                if not order_filled:
                    continue
                # ===== END VERIFICATION =====

                actual_filled_value = shares_to_buy * avg_fill_price
                trade_record = {
                    'ticker': ticker,
                    'shares': shares_to_buy,
                    'price': avg_fill_price,
                    'value': actual_filled_value,
                    'max_allowed': max_capital_per_trade,
                    'order_id': order.id,
                    'timestamp': datetime.now().isoformat(),
                    'signal_score': signal.get('conviction_score', 0),
                    'fundamental_score': signal.get('score', 0),
                    'status': 'filled'
                }

                executed_trades.append(trade_record)
                logger.info(
                    f"LIVE TRADE EXECUTED: {ticker} - {shares_to_buy} shares @ ${avg_fill_price:.2f} "
                    f"(Value: ${actual_filled_value:.2f}, Max Allowed: ${max_capital_per_trade:.2f})"
                )

                time.sleep(1)

            except Exception as e:
                logger.error(f"Failed to execute trade for {ticker}: {e}", exc_info=True)

        return executed_trades

    def _get_portfolio_value(self):
        try:
            account = self.api.get_account()
            return float(account.portfolio_value)
        except Exception as e:
            logger.error(f"Failed to get portfolio value: {e}")
            return 10000

    def _has_position(self, ticker):
        try:
            position = self.api.get_position(ticker)
            return position is not None
        except:
            return False

    def _get_current_price(self, ticker):
        try:
            bars = self.api.get_bars(ticker, '1Min', limit=1).df
            if not bars.empty:
                return float(bars.iloc[-1]['close'])
        except Exception as e:
            logger.error(f"Failed to get price for {ticker}: {e}")
        return None

    def get_positions(self):
        """Get current positions with profit details"""
        try:
            positions = self.api.list_positions()
            return [{
                'ticker': p.symbol,
                'qty': int(p.qty),
                'avg_price': float(p.avg_entry_price),
                'current_price': float(p.current_price),
                'current_value': float(p.market_value),
                'unrealized_pl': float(p.unrealized_pl),       # $ profit/loss
                'unrealized_plpc': float(p.unrealized_plpc)    # % profit/loss
            } for p in positions]
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []

    def log_positions_summary(self):
        """Log a summary of all open positions with profit/loss details"""
        try:
            positions = self.get_positions()
            if not positions:
                logger.info("No open positions.")
                return

            logger.info("=== CURRENT PORTFOLIO POSITIONS ===")
            total_unrealized = 0.0
            for p in positions:
                total_unrealized += p['unrealized_pl']
                logger.info(
                    f"{p['ticker']}: {p['qty']} shares | "
                    f"Entry=${p['avg_price']:.2f} | Current=${p['current_price']:.2f} | "
                    f"Value=${p['current_value']:.2f} | "
                    f"Unrealized=${p['unrealized_pl']:.2f} ({p['unrealized_plpc']*100:.2f}%)"
                )
            logger.info(f"--- TOTAL UNREALIZED P&L: ${total_unrealized:.2f} ---")
            logger.info("===================================")

        except Exception as e:
            logger.error(f"Failed to log positions summary: {e}")

    def log_realized_profit(self):
        """Log realized profit/loss from closed trades (daily)"""
        try:
            account = self.api.get_account()
            # Alpaca tracks today's realized P&L in account attributes
            realized_pl = float(account.equity) - float(account.last_equity)
            logger.info(f"--- REALIZED P&L TODAY: ${realized_pl:.2f} ---")
            
        except Exception as e:
            logger.error(f"Failed to fetch realized P&L: {e}")