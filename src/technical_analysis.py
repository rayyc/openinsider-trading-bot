#src/technical_analysis.py
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import logging
from src.config import config

logger = logging.getLogger(__name__)

class TechnicalAnalyzer:
    """Technical analysis using Yahoo Finance market data (FREE - no API key needed)"""
    
    def __init__(self):
        # No API client needed for yfinance - it's completely free
        # yfinance automatically handles:
        # - Data fetching from Yahoo Finance
        # - Rate limiting
        # - Retries
        logger.info("Technical Analyzer initialized with Yahoo Finance (free, no subscription)")
    
    def analyze_ticker(self, ticker):
        """
        Perform technical analysis using Yahoo Finance data
        Returns: dict with technical indicators and pass/fail
        """
        try:
            # Get 200 days of data from Yahoo Finance (free, no subscription needed)
            # This is sufficient for 200-day MA calculation
            stock = yf.Ticker(ticker)
            
            # Use .history() method which is more reliable than .download()
            df = stock.history(period="200d")
            
            if df.empty or len(df) < 50:
                logger.warning(f"Insufficient data for {ticker} (got {len(df)} days, need 50+)")
                # ✅ FIXED: Return None instead of neutral result
                # This will properly exclude the stock from trading
                return None
            
            # Calculate indicators
            # Note: Yahoo Finance returns 'Close' not 'close' (capitalized)
            current_price = df['Close'].iloc[-1]
            sma_50 = df['Close'].rolling(window=50).mean().iloc[-1]
            sma_200 = df['Close'].rolling(window=200).mean().iloc[-1] if len(df) >= 200 else None
            volume_avg_20d = df['Volume'].rolling(window=20).mean().iloc[-1]
            
            # Calculate RSI
            rsi = self._calculate_rsi(df['Close'], period=14)
            
            # Build result - convert numpy types to Python types for JSON serialization
            result = {
                'ticker': ticker,
                'current_price': float(current_price),
                'sma_50': float(sma_50) if pd.notna(sma_50) else None,
                'sma_200': float(sma_200) if sma_200 is not None and pd.notna(sma_200) else None,
                'above_50ma': bool(current_price > sma_50) if pd.notna(sma_50) else False,
                'above_200ma': bool(current_price > sma_200) if sma_200 is not None and pd.notna(sma_200) else None,
                'volume_20d_avg': float(volume_avg_20d) if pd.notna(volume_avg_20d) else 0,
                'rsi': float(rsi) if rsi is not None else None,
                'passed': True,
                'warnings': [],
                'data_source': 'yahoo_finance'  # Track where data came from
            }
            
            # Apply filters
            if config.REQUIRE_PRICE_ABOVE_50MA and not result['above_50ma']:
                result['passed'] = False
                result['warnings'].append(f"Price ${current_price:.2f} below 50-MA ${sma_50:.2f}")
            
            if config.REQUIRE_PRICE_ABOVE_200MA and sma_200 and pd.notna(sma_200):
                if current_price < sma_200:
                    result['passed'] = False
                    result['warnings'].append(f"Price ${current_price:.2f} below 200-MA ${sma_200:.2f}")
            
            if volume_avg_20d < config.MIN_VOLUME_20D_AVG:
                result['passed'] = False
                result['warnings'].append(f"Low volume: {volume_avg_20d:,.0f} < {config.MIN_VOLUME_20D_AVG:,}")
            
            if rsi and rsi > config.MAX_RSI:
                result['passed'] = False
                result['warnings'].append(f"Overbought RSI: {rsi:.1f} > {config.MAX_RSI}")
                # Note:  failing on overbought
            
            if rsi and rsi < config.MIN_RSI:
                result['passed'] = False
                result['warnings'].append(f"Oversold RSI: {rsi:.1f} < {config.MIN_RSI}")
            
            # Log result
            rsi_str = f"{rsi:.1f}" if rsi else 'N/A'
            logger.info(f"Technical analysis for {ticker}: "
                       f"Price=${current_price:.2f}, 50MA=${sma_50:.2f}, "
                       f"RSI={rsi_str}, Volume={volume_avg_20d:,.0f}, "
                       f"Passed={result['passed']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Technical analysis failed for {ticker}: {e}")
            # ✅ FIXED: Return None on errors too
            return None
    
    def _calculate_rsi(self, prices, period=14):
        """
        Calculate Relative Strength Index (RSI)
        RSI = 100 - (100 / (1 + RS))
        Where RS = Average Gain / Average Loss over period
        """
        try:
            # Calculate price changes
            delta = prices.diff()
            
            # Separate gains and losses
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            # Calculate RS and RSI
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            # Get the most recent RSI value
            latest_rsi = rsi.iloc[-1]
            
            # Return as Python float, or None if invalid
            return float(latest_rsi) if pd.notna(latest_rsi) else None
            
        except Exception as e:
            logger.debug(f"RSI calculation failed: {e}")
            return None
    
    def batch_analyze(self, tickers):
        """
        Analyze multiple tickers in batch
        Returns only tickers that pass technical analysis
        """
        results = []
        passed_count = 0
        failed_count = 0
        
        for ticker in tickers:
            try:
                result = self.analyze_ticker(ticker)
                
                # ✅ FIXED: Skip if result is None (insufficient data or error)
                if result is None:
                    failed_count += 1
                    logger.debug(f"{ticker} failed technical analysis: Insufficient data or error")
                    continue
                
                if result['passed']:
                    results.append(result)
                    passed_count += 1
                else:
                    failed_count += 1
                    logger.debug(f"{ticker} failed technical analysis: {result['warnings']}")
                    
            except Exception as e:
                logger.error(f"Failed to analyze {ticker}: {e}")
                failed_count += 1
                # Don't add to results if completely failed
        
        logger.info(f"Technical analysis batch complete: "
                   f"{passed_count} passed, {failed_count} failed out of {len(tickers)} total")
        
        return results
    
    def get_current_price(self, ticker):
        """
        Get current price for a ticker using Yahoo Finance
        This is a utility method for other modules that need real-time prices
        """
        try:
            stock = yf.Ticker(ticker)
            # Get most recent price from 1-day history
            hist = stock.history(period="1d")
            
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                return float(current_price)
            else:
                logger.warning(f"No price data available for {ticker}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get current price for {ticker}: {e}")
            return None