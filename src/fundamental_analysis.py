#src/fundamental_analysis.py
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import structlog
from src.config import config
import logging

logger = structlog.get_logger()
logger = logging.getLogger(__name__)

# Only import FMP if fallback is enabled
if config.USE_FMP_FALLBACK:
    try:
        from src.fmp_analyzer import FMPAnalyzer
    except ImportError:
        logger.warning("FMP analyzer not available despite USE_FMP_FALLBACK=True")
        config.USE_FMP_FALLBACK = False

class FundamentalAnalyzer:
    def __init__(self):
        self.cache = {}
        self.cache_duration = timedelta(hours=6)
        
        # Only initialize FMP if enabled
        if config.USE_FMP_FALLBACK:
            try:
                self.fmp = FMPAnalyzer()
                logger.info("FMP fallback enabled")
            except:
                self.fmp = None
                logger.warning("FMP initialization failed, using yfinance only")
        else:
            self.fmp = None
            logger.info("FMP fallback disabled - using yfinance only")
        
    def analyze_ticker(self, ticker):
        """Comprehensive fundamental analysis with optional FMP fallback."""
        # Check cache first
        if ticker in self.cache:
            cache_time, result = self.cache[ticker]
            if datetime.now() - cache_time < self.cache_duration:
                return result
        
        try:
            # Try yfinance first
            stock = yf.Ticker(ticker)
            info = stock.info
            
            analysis = {
                'ticker': ticker,
                'passed': False,
                'score': 0,
                'metrics': {},
                'warnings': [],
                'failed_reasons': [],
                'data_source': 'yfinance'
            }
            
            # If yfinance fails AND FMP is enabled, try FMP
            if (not info or len(info) < 5) and config.USE_FMP_FALLBACK and self.fmp:
                logger.info(f"yfinance data insufficient for {ticker}, trying FMP...")
                return self._analyze_with_fmp(ticker, analysis)
            elif not info or len(info) < 5:
                # No FMP fallback, return neutral
                logger.warning(f"yfinance data insufficient for {ticker}, no FMP fallback available")
                return self._create_neutral_analysis(ticker, "Insufficient data from yfinance")
            
            # ===== COLLECT AND STORE ALL METRICS FROM YFINANCE =====
            # Profitability
            profit_margin = info.get('profitMargins')
            analysis['metrics']['profit_margin'] = profit_margin if profit_margin is not None else 0
            
            # Liquidity
            current_ratio = info.get('currentRatio')
            analysis['metrics']['current_ratio'] = current_ratio if current_ratio is not None else 0
            
            # Solvency
            debt_to_equity = info.get('debtToEquity')
            analysis['metrics']['debt_to_equity'] = debt_to_equity if debt_to_equity is not None else 0
            
            # Valuation
            pe_ratio = info.get('trailingPE')
            analysis['metrics']['pe_ratio'] = pe_ratio if pe_ratio is not None else 0
            
            # Growth
            revenue_growth = info.get('revenueGrowth')
            analysis['metrics']['revenue_growth'] = revenue_growth if revenue_growth is not None else 0
            
            # Market Cap
            market_cap = info.get('marketCap', 0)
            analysis['metrics']['market_cap'] = market_cap
            
            # Technical - Price relative to moving averages
            fifty_day_avg = info.get('fiftyDayAverage', 0)
            two_hundred_day_avg = info.get('twoHundredDayAverage', 0)
            current_price = info.get('regularMarketPrice', 0)
            
            above_50ma = 0
            if current_price and fifty_day_avg and fifty_day_avg > 0:
                above_50ma = ((current_price / fifty_day_avg) - 1) * 100
                analysis['metrics']['above_50ma'] = above_50ma
                
                if current_price < two_hundred_day_avg * 0.8:
                    analysis['warnings'].append(f"Price ${current_price:.2f} below 200-day MA (${two_hundred_day_avg:.2f})")
            
            # ===== GENERATE WARNINGS FOR SUB-OPTIMAL METRICS =====
            if profit_margin is not None and profit_margin < config.MIN_PROFIT_MARGIN:
                analysis['warnings'].append(f"Low profit margin: {profit_margin:.2%}")
            
            if current_ratio is not None and current_ratio < config.MIN_CURRENT_RATIO:
                analysis['warnings'].append(f"Low current ratio: {current_ratio:.2f}")
            
            if debt_to_equity is not None and debt_to_equity > config.MAX_DEBT_TO_EQUITY:
                analysis['warnings'].append(f"High debt-to-equity: {debt_to_equity:.2f}")
            
            if pe_ratio is not None and pe_ratio > config.MAX_PE_RATIO:
                analysis['warnings'].append(f"High P/E ratio: {pe_ratio:.2f}")
            
            if revenue_growth is not None and revenue_growth < 0:
                analysis['warnings'].append(f"Negative revenue growth: {revenue_growth:.2%}")
            
            if market_cap < 100_000_000:  # $100M minimum
                analysis['warnings'].append(f"Small market cap: ${market_cap/1_000_000:.1f}M")
            
            # ===== CALCULATE THE FINAL SCORE =====
            analysis['score'] = self._calculate_fundamental_score(analysis)
            analysis['passed'] = True  # batch_analyze will filter by score
            
            # Cache the results
            self.cache[ticker] = (datetime.now(), analysis)
            
            logger.info(f"Analyzed {ticker} (yfinance): Score={analysis['score']:.1f}, Warnings={len(analysis['warnings'])}")
            
            return analysis
            
        except Exception as e:
            # Only try FMP if enabled
            if config.USE_FMP_FALLBACK and self.fmp:
                logger.debug(f"yfinance failed for {ticker}: {e}")
                return self._analyze_with_fmp(ticker, analysis if 'analysis' in locals() else {})
            else:
                logger.warning(f"Analysis failed for {ticker}: {e}")
                return self._create_neutral_analysis(ticker, f"Analysis error: {str(e)}")
    
    def _analyze_with_fmp(self, ticker, analysis):
        """Use FMP as data source when yfinance fails - only if enabled"""
        if not config.USE_FMP_FALLBACK or not self.fmp:
            return self._create_neutral_analysis(ticker, "FMP fallback disabled")
            
        try:
            # Get data from FMP
            key_metrics = self.fmp.get_key_metrics(ticker)
            ratios = self.fmp.get_financial_ratios(ticker)
            growth = self.fmp.get_growth_metrics(ticker)
            
            if not any([key_metrics, ratios, growth]):
                return self._create_neutral_analysis(ticker, "No data from FMP")
            
            analysis = {
                'ticker': ticker,
                'passed': False,
                'score': 0,
                'metrics': {},
                'warnings': [],
                'failed_reasons': [],
                'data_source': 'fmp'
            }
            
            # Populate metrics from FMP data
            if key_metrics:
                analysis['metrics']['pe_ratio'] = key_metrics.get('pe_ratio')
                analysis['metrics']['debt_to_equity'] = key_metrics.get('debt_to_equity')
                analysis['metrics']['current_ratio'] = key_metrics.get('current_ratio')
                analysis['metrics']['market_cap'] = key_metrics.get('market_cap')
                analysis['metrics']['roe'] = key_metrics.get('roe')
            
            if ratios:
                analysis['metrics']['profit_margin'] = ratios.get('profit_margin')
                analysis['metrics']['operating_margin'] = ratios.get('operating_margin')
            
            if growth:
                analysis['metrics']['revenue_growth'] = growth.get('revenue_growth')
                analysis['metrics']['eps_growth'] = growth.get('eps_growth')
            
            # Generate warnings based on thresholds
            self._generate_warnings(analysis)
            
            # Calculate score
            analysis['score'] = self._calculate_fundamental_score(analysis)
            analysis['passed'] = True
            
            self.cache[ticker] = (datetime.now(), analysis)
            
            logger.info(f"Analyzed {ticker} (FMP): Score={analysis['score']:.1f}, Warnings={len(analysis['warnings'])}")
            
            return analysis
            
        except Exception as e:
            logger.debug(f"FMP analysis failed for {ticker}: {e}")
            return self._create_neutral_analysis(ticker, f"FMP error: {str(e)}")
    
    def _generate_warnings(self, analysis):
        """Generate warnings based on metrics"""
        metrics = analysis['metrics']
        
        profit_margin = metrics.get('profit_margin', 0)
        if profit_margin and profit_margin < config.MIN_PROFIT_MARGIN:
            analysis['warnings'].append(f"Low profit margin: {profit_margin:.2%}")
        
        current_ratio = metrics.get('current_ratio', 0)
        if current_ratio and current_ratio < config.MIN_CURRENT_RATIO:
            analysis['warnings'].append(f"Low current ratio: {current_ratio:.2f}")
        
        debt_to_equity = metrics.get('debt_to_equity', 0)
        if debt_to_equity and debt_to_equity > config.MAX_DEBT_TO_EQUITY:
            analysis['warnings'].append(f"High debt: {debt_to_equity:.2f}")
        
        pe_ratio = metrics.get('pe_ratio', 0)
        if pe_ratio and pe_ratio > config.MAX_PE_RATIO:
            analysis['warnings'].append(f"High P/E: {pe_ratio:.2f}")
        
        revenue_growth = metrics.get('revenue_growth', 0)
        if revenue_growth and revenue_growth < 0:
            analysis['warnings'].append(f"Negative revenue growth: {revenue_growth:.2%}")
        
        market_cap = metrics.get('market_cap', 0)
        if market_cap and market_cap < 100_000_000:
            analysis['warnings'].append(f"Small market cap: ${market_cap/1_000_000:.1f}M")
    
    def _create_neutral_analysis(self, ticker, reason):
        """Create a neutral analysis result for stocks with insufficient data or errors."""
        return {
            'ticker': ticker,
            'passed': True,
            'score': 40,
            'metrics': {},
            'warnings': [reason],
            'failed_reasons': [],
            'data_source': 'none'
        }
    
    def _calculate_fundamental_score(self, analysis):
        """
        Calculate a fundamental health score (0-100).
        All rules are now point deductions/additions, not pass/fail gates.
        """
        score = 65  # Start with a slightly positive bias
        
        metrics = analysis['metrics']
        
        # 1. Profitability (Max +15 / Min -20)
        profit_margin = metrics.get('profit_margin', 0)
        if profit_margin is not None:
            if profit_margin > 0.20:  # Excellent
                score += 15
            elif profit_margin > 0.10:  # Good
                score += 10
            elif profit_margin > 0.05:  # Acceptable
                score += 5
            elif profit_margin > 0:     # Marginal
                score += 0
            else:                       # Negative
                score -= min(20, abs(profit_margin * 100))
        
        # 2. Solvency - Debt-to-Equity (Max +10 / Min -25)
        debt_to_equity = metrics.get('debt_to_equity', 0)
        if debt_to_equity is not None:
            if debt_to_equity < 0.5:   # Very low debt
                score += 10
            elif debt_to_equity < 1.0: # Low debt
                score += 5
            elif debt_to_equity < 2.0: # Moderate
                score += 0
            elif debt_to_equity < 4.0: # High
                score -= 10
            else:                      # Very high
                score -= 25
        
        # 3. Growth - Revenue Growth (Max +20 / Min -10)
        revenue_growth = metrics.get('revenue_growth', 0)
        if revenue_growth is not None:
            if revenue_growth > 0.55:  # Strong growth
                score += 20
            elif revenue_growth > 0.50: # Good growth
                score += 15
            elif revenue_growth > 0.45: # Moderate growth
                score += 10
            elif revenue_growth > 0.25:    # Slow growth
                score += 5
            else:                       # Negative growth
                score -= 10
        
        # 4. Liquidity - Current Ratio (Max +10 / Min -10)
        current_ratio = metrics.get('current_ratio', 0)
        if current_ratio is not None:
            if current_ratio > 3.0:   # Very strong
                score += 10
            elif current_ratio > 2.0: # Strong
                score += 7
            elif current_ratio > 1.5: # Acceptable
                score += 3
            elif current_ratio > 1.0: # Minimal
                score += 0
            else:                     # Potential liquidity issue
                score -= 10
        
        # 5. Valuation - P/E Ratio (Max +5 / Min -15)
        pe_ratio = metrics.get('pe_ratio', 0)
        if pe_ratio is not None and pe_ratio > 0:
            if pe_ratio < 15:    # Undervalued
                score += 5
            elif pe_ratio < 25:  # Fairly valued
                score += 2
            elif pe_ratio < 50:  # Overvalued
                score -= 5
            else:                # Highly overvalued
                score -= 15
        
        # 6. Technical - Above 50-day MA (Max +10 / Min -5)
        above_50ma = metrics.get('above_50ma', 0)
        if above_50ma > 10:   # Strong uptrend
            score += 10
        elif above_50ma > 5:  # Mild uptrend
            score += 5
        elif above_50ma > -5: # Neutral
            score += 0
        else:                 # Downtrend
            score -= 5
        
        # 7. Market Cap Penalty for very small companies (Min -20)
        market_cap = metrics.get('market_cap', 0)
        if market_cap < 50_000_000:   # Micro-cap (<$50M)
            score -= 20
        elif market_cap < 100_000_000: # Very small cap
            score -= 10
        elif market_cap < 300_000_000: # Small cap
            score -= 5
        
        # Ensure score stays within bounds
        return max(0, min(100, int(score)))
    
    def batch_analyze(self, tickers, min_score=70):
        """
        Analyze multiple tickers and return those meeting the minimum score.
        LOWERED from 85 to 70 since we now have technical + macro filters.
        """
        results = []
        for ticker in tickers:
            analysis = self.analyze_ticker(ticker)
            
            # Pass/Fail determined solely by score
            if analysis['score'] >= min_score:
                results.append(analysis)
        
        # Sort by fundamental score (highest first)
        results.sort(key=lambda x: x['score'], reverse=True)
        
        if results:
            logger.info(f"Batch analysis: {len(results)} of {len(tickers)} tickers passed with score >= {min_score}")
        
        return results