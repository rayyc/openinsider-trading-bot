# src/risk_manager.py - UPDATED WITH DUAL-MODE LOGIC
import structlog
from src.config import config
import logging

logger = structlog.get_logger()
logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, trade_executor):
        self.executor = trade_executor
        self.api = trade_executor.api
    
    def get_portfolio_summary(self):
        """Get current portfolio state."""
        try:
            account = self.api.get_account()
            positions = self.executor.get_positions()
            
            portfolio_value = float(account.portfolio_value)
            cash = float(account.cash)
            buying_power = float(account.buying_power)
            
            # Calculate position values
            position_values = {}
            total_position_value = 0
            
            for pos in positions:
                value = pos['current_value']
                position_values[pos['ticker']] = value
                total_position_value += value
            
            return {
                'portfolio_value': portfolio_value,
                'cash': cash,
                'buying_power': buying_power,
                'positions': position_values,
                'total_positions': total_position_value,
                'position_count': len(positions)
            }
        except Exception as e:
            logger.error(f"Failed to get portfolio summary: {e}")
            return None
    
    def calculate_position_size(self, portfolio_value, current_price):
        """Calculate exact share quantity based on risk parameters."""
        # Risk a fixed % of portfolio per trade
        risk_capital = portfolio_value * config.MAX_PORTFOLIO_RISK_PCT
        
        # Calculate max shares
        max_shares = int(risk_capital / current_price)
        
        # Ensure minimum 1 share
        if max_shares < 1:
            max_shares = 1
        
        # Calculate actual order value
        order_value = max_shares * current_price
        
        logger.debug(
            f"Position sizing: Portfolio=${portfolio_value:.2f}, "
            f"RiskCapital=${risk_capital:.2f}, Price=${current_price:.2f}, "
            f"Shares={max_shares}, OrderValue=${order_value:.2f}"
        )
        
        return max_shares, order_value
    
    def check_position_limits(self, ticker):
        """Check if we can open a new position."""
        summary = self.get_portfolio_summary()
        if not summary:
            return False
        
        # Check 1: Already holding this ticker
        if ticker in summary['positions']:
            logger.warning(f"Already holding {ticker}, skipping duplicate position")
            return False
        
        # Check 2: Maximum concurrent positions
        if summary['position_count'] >= config.MAX_CONCURRENT_POSITIONS:
            logger.warning(
                f"Maximum positions reached ({summary['position_count']}/"
                f"{config.MAX_CONCURRENT_POSITIONS}), skipping {ticker}"
            )
            return False
        
        # Check 3: Sufficient buying power (for cash accounts)
        if summary['buying_power'] <= 0:
            logger.warning(f"Insufficient buying power: ${summary['buying_power']:.2f}")
            return False
        
        return True

    def check_trade_risk(self, position_size, current_pnl):
        """
        Check per-trade stop loss / take profit.
        position_size: dollar value of the trade (e.g. $10,000)
        current_pnl: profit/loss of the trade in dollars
        """
        if config.USE_PERCENTAGE_MODE_TRADES:
            stop_loss_limit = position_size * config.STOP_LOSS_PCT
            take_profit_limit = position_size * config.TAKE_PROFIT_PCT
        else:
            stop_loss_limit = config.STOP_LOSS_USD
            take_profit_limit = config.TAKE_PROFIT_USD

        logger.debug(
            f"Trade risk check: Position=${position_size:.2f}, "
            f"PnL=${current_pnl:.2f}, StopLoss=${stop_loss_limit:.2f}, "
            f"TakeProfit=${take_profit_limit:.2f}"
        )

        if current_pnl <= -stop_loss_limit:
            logger.warning(
                f"STOP LOSS triggered: PnL=${current_pnl:.2f}, Limit=${stop_loss_limit:.2f}"
            )
            return "STOP LOSS TRIGGERED"
        elif current_pnl >= take_profit_limit:
            logger.info(
                f"TAKE PROFIT triggered: PnL=${current_pnl:.2f}, Limit=${take_profit_limit:.2f}"
            )
            return "TAKE PROFIT TRIGGERED"
        else:
            return "HOLD POSITION"