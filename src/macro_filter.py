#src/macro_filter.py
import yfinance as yf
import logging
import time
from typing import Tuple

logger = logging.getLogger(__name__)

class MacroFilter:
    """
    Check macro market conditions before trading.
    Enhanced with retry logic, caching, and graceful degradation.
    """
    
    def __init__(self):
        self.cache = {}
        self.cache_duration = 300  # 5 minutes in seconds
        self.max_retries = 3
        self.retry_delay = 2
    
    def _get_price_data(self, ticker: str) -> dict:
        """
        Get current price and 50-day MA using historical data (more reliable than .info)
        
        Args:
            ticker: Stock ticker (e.g., 'SPY', '^VIX')
        
        Returns:
            dict with 'current_price' and 'sma_50', or None if failed
        """
        # Check cache first
        cache_key = ticker
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if time.time() - cached_time < self.cache_duration:
                logger.debug(f"Using cached data for {ticker}")
                return cached_data
        
        # Fetch with retries
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Fetching {ticker} data (attempt {attempt + 1}/{self.max_retries})")
                
                # Use history instead of .info (more reliable)
                stock = yf.Ticker(ticker)
                hist = stock.history(period="3mo")  # 3 months for 50-day MA
                
                if hist.empty:
                    logger.warning(f"No data for {ticker} on attempt {attempt + 1}")
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delay * (2 ** attempt)
                        time.sleep(delay)
                        continue
                    return None
                
                # Get current price (most recent close)
                current_price = float(hist['Close'].iloc[-1])
                
                # Calculate 50-day moving average
                if len(hist) >= 50:
                    sma_50 = float(hist['Close'].tail(50).mean())
                else:
                    # Use all available data if less than 50 days
                    sma_50 = float(hist['Close'].mean())
                    logger.debug(f"{ticker}: Only {len(hist)} days available")
                
                result = {
                    'current_price': current_price,
                    'sma_50': sma_50,
                    'data_points': len(hist)
                }
                
                # Cache the result
                self.cache[cache_key] = (time.time(), result)
                
                logger.debug(f"{ticker}: Price=${current_price:.2f}, 50MA=${sma_50:.2f}")
                return result
                
            except Exception as e:
                logger.warning(f"{ticker} fetch attempt {attempt + 1}/{self.max_retries} failed: {str(e)[:100]}")
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.debug(f"Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"All retry attempts failed for {ticker}")
                    return None
        
        return None
    
    def is_safe_to_trade(self) -> Tuple[bool, str]:
        """
        Returns (is_safe, reason) tuple.
        
        Checks:
        1. VIX level (volatility)
        2. SPY trend (market direction)
        
        Uses graceful degradation - continues trading if data fetch fails.
        """
        from src.config import config
        
        warnings = []
        
        # === CHECK 1: VIX (Volatility) ===
        try:
            vix_data = self._get_price_data("^VIX")
            
            if vix_data:
                vix_current = vix_data['current_price']
                
                if vix_current > config.MAX_VIX_THRESHOLD:
                    logger.warning(f"⚠️  High volatility: VIX={vix_current:.1f} > {config.MAX_VIX_THRESHOLD}")
                    return False, f"VIX too high: {vix_current:.1f} > {config.MAX_VIX_THRESHOLD}"
                
                logger.info(f"✓ VIX check passed: {vix_current:.1f} < {config.MAX_VIX_THRESHOLD}")
            else:
                warnings.append("VIX data unavailable")
                logger.warning("Could not fetch VIX data - proceeding with caution")
                
        except Exception as e:
            warnings.append(f"VIX check error: {str(e)[:50]}")
            logger.error(f"VIX check exception: {e}")
        
        # === CHECK 2: SPY Market Trend ===
        if config.CHECK_MARKET_TREND:
            try:
                spy_data = self._get_price_data("SPY")
                
                if spy_data:
                    spy_price = spy_data['current_price']
                    spy_50ma = spy_data['sma_50']
                    
                    if spy_price < spy_50ma:
                        diff_pct = ((spy_price / spy_50ma) - 1) * 100
                        logger.warning(f"Market downtrend: SPY ${spy_price:.2f} < 50MA ${spy_50ma:.2f} ({diff_pct:+.2f}%)")
                        return False, f"Market downtrend: SPY ${spy_price:.2f} < 50MA ${spy_50ma:.2f}"
                    
                    diff_pct = ((spy_price / spy_50ma) - 1) * 100
                    logger.info(f"✓ Market uptrend: SPY ${spy_price:.2f} > 50MA ${spy_50ma:.2f} ({diff_pct:+.2f}%)")
                else:
                    warnings.append("SPY data unavailable")
                    logger.warning("Could not fetch SPY data - proceeding with caution")
                    
            except Exception as e:
                warnings.append(f"SPY check error: {str(e)[:50]}")
                logger.error(f"SPY check exception: {e}")
        
        # === FINAL DECISION ===
        if warnings:
            # Had issues but no hard failures - proceed with warnings
            reason = f"Proceeding with warnings: {'; '.join(warnings)}"
            logger.info(f"⚠️  {reason}")
            return True, reason
        
        # All checks passed
        logger.info("✓ All macro conditions favorable")
        return True, "Favorable conditions"
    
    def get_market_status(self) -> dict:
        """
        Get detailed market status for dashboards/logging.
        
        Returns:
            dict with VIX, SPY price, SPY 50MA, safety status
        """
        from src.config import config
        
        status = {
            'timestamp': time.time(),
            'vix': None,
            'spy_price': None,
            'spy_50ma': None,
            'is_safe': False,
            'reason': 'Unknown'
        }
        
        try:
            # Get VIX
            vix_data = self._get_price_data("^VIX")
            if vix_data:
                status['vix'] = vix_data['current_price']
            
            # Get SPY
            spy_data = self._get_price_data("SPY")
            if spy_data:
                status['spy_price'] = spy_data['current_price']
                status['spy_50ma'] = spy_data['sma_50']
            
            # Get safety determination
            is_safe, reason = self.is_safe_to_trade()
            status['is_safe'] = is_safe
            status['reason'] = reason
            
        except Exception as e:
            logger.error(f"Error getting market status: {e}")
            status['reason'] = f"Error: {str(e)[:50]}"
        
        return status
    
    def clear_cache(self):
        """Clear cached data - useful for testing or manual refresh"""
        self.cache = {}
        logger.info("Macro filter cache cleared")


if __name__ == "__main__":
    # Test the macro filter
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*60)
    print("MACRO FILTER TEST")
    print("="*60 + "\n")
    
    macro = MacroFilter()
    
    print("Testing market conditions...\n")
    is_safe, reason = macro.is_safe_to_trade()
    
    print(f"Result: {'✓ SAFE TO TRADE' if is_safe else '✗ NOT SAFE'}")
    print(f"Reason: {reason}\n")
    
    print("Getting detailed status...\n")
    status = macro.get_market_status()
    
    print(f"VIX Level: {status.get('vix', 'N/A')}")
    print(f"SPY Price: ${status.get('spy_price', 0):.2f}")
    print(f"SPY 50-Day MA: ${status.get('spy_50ma', 0):.2f}")
    print(f"Safe to Trade: {status.get('is_safe', False)}")
    print(f"Status: {status.get('reason', 'Unknown')}")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
