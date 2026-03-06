#src/main.py
import sys
import io
import schedule
import time as time_module
import pytz
import logging
from datetime import datetime, time as dt_time
import structlog
from src.data_collection import OpenInsiderScraper
from src.signal_filtering import SignalFilter
from src.fundamental_analysis import FundamentalAnalyzer
from src.technical_analysis import TechnicalAnalyzer
from src.macro_filter import MacroFilter
from src.trade_execution import TradeExecutor
from src.config import config

# Force UTF-8 encoding for Windows console to support emojis
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logger = structlog.get_logger()
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/trading_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class InsiderTradingPipeline:
    def __init__(self):
        self.scraper = OpenInsiderScraper()
        self.filter = SignalFilter()
        self.analyzer = FundamentalAnalyzer()
        self.technical = TechnicalAnalyzer()  # NEW: Technical analysis
        self.macro_filter = MacroFilter()      # NEW: Macro environment filter
        self.executor = TradeExecutor()
        self.last_run = None
        
        # Timezone setup
        self.eat_tz = pytz.timezone('Africa/Nairobi')
        
    def is_market_hours(self) -> bool:
        """Check if current time is within trading hours."""
        now_eat = datetime.now(self.eat_tz)
        
        # Check day of week (0=Monday, 6=Sunday)
        if now_eat.weekday() not in config.TRADING_DAYS:
            return False
        
        # Check time of day
        market_open = dt_time(16, 30)  # 4:30 PM EAT
        market_close = dt_time(23, 00)  # 11:00 PM EAT
        current_time = now_eat.time()
        
        return market_open <= current_time <= market_close
        
    def run_pipeline(self):
        """Execute the complete pipeline with risk management and new filters."""
        logger.info("=== STARTING ENHANCED PIPELINE WITH MULTI-LAYER FILTERING ===")
        start_time = datetime.now()
        
        try:
            # === STEP 0: Initialize Safety Modules ===
            from src.risk_manager import RiskManager
            from src.circuit_breaker import CircuitBreaker
            
            risk_manager = RiskManager(self.executor)
            circuit_breaker = CircuitBreaker(self.executor)
            
            # === NEW STEP 0.5: Macro Environment Check ===
            logger.info("Step 0.5: Checking macro environment")
            is_safe, reason = self.macro_filter.is_safe_to_trade()
            
            if not is_safe:
                logger.warning(f"⚠️  Trading PAUSED due to macro conditions: {reason}")
                logger.warning("Pipeline halted to protect capital during unfavorable market conditions")
                return
            
            logger.info(f"✓ Macro conditions favorable: {reason}")
            
            # === STEP 1: Circuit Breaker Check ===
            if not circuit_breaker.check_daily_limits():
                logger.error("❌ Trading halted by circuit breaker. Pipeline stopped.")
                return
            
            # === STEP 2: Data Collection ===
            logger.info("Step 1: Scraping OpenInsider")
            raw_data = self.scraper.scrape_prebuilt_screen("cluster")
            
            if raw_data.empty:
                logger.warning("No data scraped, exiting pipeline")
                return
            
            logger.info(f"✓ Found {len(raw_data)} raw insider purchases")
            
            # === STEP 3: Signal Filtering ===
            logger.info("Step 2: Filtering insider signals")
            filtered_signals = self.filter.filter_high_conviction(raw_data)
            
            if filtered_signals.empty:
                logger.info("No high-conviction signals found after filtering")
                return
            
            logger.info(f"✓ {len(filtered_signals)} signals passed conviction filters")
            
            # === STEP 4: Fundamental Analysis ===
            logger.info("Step 3: Analyzing fundamentals")
            tickers = filtered_signals['ticker'].unique().tolist()
            logger.info(f"Analyzing {len(tickers)} unique tickers: {', '.join(tickers)}")
            
            # LOWERED min_score from 85 to 70 since we now have technical + macro filters
            fundamental_results = self.analyzer.batch_analyze(tickers, min_score=70)
            
            if not fundamental_results:
                logger.info("❌ No tickers passed fundamental analysis (min_score=70)")
                return
            
            logger.info(f"✓ {len(fundamental_results)} tickers passed fundamental analysis")
            for result in fundamental_results:
                logger.info(f"   {result['ticker']}: Score={result['score']}, "
                           f"Source={result.get('data_source', 'unknown')}, "
                           f"Warnings={len(result['warnings'])}")
            
            # === NEW STEP 4.5: Technical Analysis ===
            logger.info("Step 3.5: Analyzing technicals")
            fundamental_tickers = [r['ticker'] for r in fundamental_results]
            technical_results = self.technical.batch_analyze(fundamental_tickers)
            
            if not technical_results:
                logger.info("❌ No tickers passed technical analysis")
                return
            
            logger.info(f"✓ {len(technical_results)} tickers passed technical analysis")
            for result in technical_results:
                # Safe formatting - handle None values properly
                current_price = result.get('current_price')
                sma_50 = result.get('sma_50')
                rsi = result.get('rsi')
                
                price_str = f"${current_price:.2f}" if current_price else "N/A"
                sma_str = f"${sma_50:.2f}" if sma_50 else "N/A"
                rsi_str = f"{rsi:.1f}" if rsi else "N/A"
                
                logger.info(f"   {result['ticker']}: Price={price_str}, "
                           f"50MA={sma_str}, RSI={rsi_str}")
            
            # Merge fundamental and technical results
            technical_tickers = {r['ticker'] for r in technical_results}
            final_candidates = [r for r in fundamental_results if r['ticker'] in technical_tickers]
            
            logger.info(f"✓ After all filters: {len(final_candidates)} final candidates")
            
            if not final_candidates:
                logger.info("No candidates remaining after technical filter")
                return
            
            # === STEP 5: Apply Risk Checks & Position Sizing ===
            logger.info("Step 4: Applying risk management")
            
            # Get portfolio summary for position sizing
            portfolio_summary = risk_manager.get_portfolio_summary()
            if not portfolio_summary:
                logger.error("Failed to get portfolio summary. Pipeline stopped.")
                return
            
            portfolio_value = portfolio_summary['portfolio_value']
            logger.info(f"Portfolio Value: ${portfolio_value:.2f}")
            
            # Prepare final trade list with calculated position sizes
            final_trades = []
            for result in final_candidates:
                ticker = result['ticker']
                
                # Risk Check 1: Position limits
                if not risk_manager.check_position_limits(ticker):
                    continue
                
                # Get current price for this ticker
                current_price = self.executor._get_current_price(ticker)
                if not current_price or current_price <= 0:
                    logger.warning(f"Could not get valid price for {ticker}")
                    continue
                
                # Risk Check 2: Calculate position size
                shares_to_buy, order_value = risk_manager.calculate_position_size(
                    portfolio_value, current_price
                )
                
                # Risk Check 3: Ensure sufficient buying power
                if order_value > portfolio_summary['buying_power']:
                    logger.warning(
                        f"Insufficient buying power for {ticker}: "
                        f"Needed=${order_value:.2f}, Available=${portfolio_summary['buying_power']:.2f}"
                    )
                    continue
                
                # Combine all data
                trade_data = result.copy()
                trade_data['shares_to_buy'] = shares_to_buy
                trade_data['order_value'] = order_value
                trade_data['current_price'] = current_price
                
                # Get the best signal for this ticker
                ticker_signals = filtered_signals[filtered_signals['ticker'] == ticker]
                if not ticker_signals.empty:
                    best_signal = ticker_signals.iloc[0].to_dict()
                    trade_data.update(best_signal)
                
                final_trades.append(trade_data)
                logger.info(
                    f"✓ Approved {ticker}: {shares_to_buy} shares @ ${current_price:.2f} "
                    f"(Value: ${order_value:.2f}, Fund Score: {result['score']})"
                )
            
            # === STEP 6: Execute Trades ===
            if final_trades:
                logger.info(f"Step 5: Executing {len(final_trades)} approved trades")
                
                # Prepare signals for execution
                execution_signals = []
                for trade in final_trades:
                    execution_signals.append({
                        'ticker': trade['ticker'],
                        'conviction_score': trade.get('conviction_score', 0),
                        'score': trade.get('score', 0),
                        'shares': trade['shares_to_buy'],
                        'calculated_value': trade['order_value']
                    })
                
                # Execute with position limits
                max_capital_per_trade = portfolio_value * config.MAX_PORTFOLIO_RISK_PCT
                executed = self.executor.execute_trades(
                    execution_signals,
                    portfolio_value=portfolio_value,
                    max_capital_per_trade=max_capital_per_trade
                )
                
                if executed:
                    logger.info(f"✓ Successfully executed {len(executed)} trades")
                    
                    # Log detailed execution summary
                    total_executed_value = sum(t['value'] for t in executed)
                    logger.info(
                        f"Execution Summary: {len(executed)} trades, "
                        f"Total Value: ${total_executed_value:.2f}, "
                        f"Portfolio Impact: {total_executed_value/portfolio_value:.2%}"
                    )
                else:
                    logger.info("No trades were executed")
            else:
                logger.info("No trades approved after risk checks")
            
            # === FINAL STEP: Log Completion ===
            duration = (datetime.now() - start_time).total_seconds()
            self.last_run = datetime.now()
            
            logger.info(f"=== PIPELINE COMPLETED IN {duration:.2f} SECONDS ===")
            
            # Log portfolio snapshot
            final_summary = risk_manager.get_portfolio_summary()
            if final_summary:
                logger.info(
                    f"Portfolio Snapshot: "
                    f"Value=${final_summary['portfolio_value']:.2f}, "
                    f"Positions={final_summary['position_count']}, "
                    f"Cash=${final_summary['cash']:.2f}"
                )
            
            # Log detailed positions summary
            self.executor.log_positions_summary()
            
            # Log realized profit/loss
            self.executor.log_realized_profit()

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
    
    def run_once(self):
        """Run one complete cycle of the pipeline - checks market hours first."""
        try:
            current_time = datetime.now(self.eat_tz)
            
            # Check if market is open
            if not self.is_market_hours():
                logger.info(f"Market is CLOSED at {current_time.strftime('%H:%M:%S')} EAT - skipping pipeline run")
                return
            
            # Market is open - run the pipeline
            logger.info(f"Market is OPEN at {current_time.strftime('%H:%M:%S')} EAT - running pipeline")
            self.run_pipeline()
            
            logger.info("Cycle complete\n")
            
        except Exception as e:
            logger.error(f"Error in run cycle: {e}", exc_info=True)
    
    def run(self):
        """
        Main run loop - continuously monitors and trades using schedule library.
        This is the recommended way to run the bot in production.
        """
        logger.info("\n" + "="*80)
        logger.info("STARTING RAY CHARLES' ENHANCED SYSTEM - CONTINUOUS MODE")
        logger.info("="*80)
        logger.info(f"Market Hours: {config.MARKET_OPEN_EAT} to {config.MARKET_CLOSE_EAT} EAT")
        logger.info(f"Trading Days: Monday-Friday")
        logger.info(f"Check Interval: {config.RUN_INTERVAL_MINUTES} minutes")
        logger.info("\n🆕 NEW FEATURES:")
        logger.info("  ✓ Financial Modeling Prep (FMP) integration for better data coverage")
        logger.info("  ✓ Technical analysis using Yahoo Finance market data")
        logger.info("  ✓ Macro environment filter (VIX + SPY trend)")
        logger.info("  ✓ Multi-layer filtering for higher accuracy")
        logger.info("="*80 + "\n")
        
        # Run immediately on startup
        logger.info("Running initial pipeline check...")
        self.run_once()
        
        # Schedule periodic runs using schedule library
        interval_minutes = config.RUN_INTERVAL_MINUTES
        schedule.every(interval_minutes).minutes.do(self.run_once)
        
        logger.info(f"Scheduled to run every {interval_minutes} minutes")
        logger.info("Press Ctrl+C to stop\n")
        
        # Main loop - more efficient than long sleeps
        try:
            while True:
                schedule.run_pending()
                time_module.sleep(60)  # Check every minute for scheduled tasks
                
        except KeyboardInterrupt:
            logger.info("\n" + "="*80)
            logger.info("SYSTEM STOPPED BY USER")
            logger.info("="*80)
            
            # Log final status
            if self.last_run:
                logger.info(f"Last successful run: {self.last_run.strftime('%Y-%m-%d %H:%M:%S')}")
            
            logger.info("Shutdown complete. Goodbye!")

def main():
    """Main entry point"""
    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )
    
    # Create and run pipeline
    pipeline = InsiderTradingPipeline()
    
    # Run in continuous mode with schedule-based execution
    pipeline.run()

if __name__ == "__main__":
    main()