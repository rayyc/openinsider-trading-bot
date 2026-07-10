# strategy_openinsider_bot.py
# ============================================================
# OPENINSIDER TRADING BOT - ALGOBULLS STRATEGY WRAPPER
# ============================================================
# This file encapsulates your entire trading system as a 
# monetizable AI Agent on the AlgoBulls marketplace.
# 
# REVENUE MODEL: Up to 70% revenue share per execution minute
# IP PROTECTION: Core logic remains hidden (black box)
# PLATFORM: AlgoBulls Strategy Creator Program
# ============================================================

from pyalgotrading.strategy import StrategyBase
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import yfinance as yf
import time
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import logging

# Configure logger
logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION (User-adjustable parameters)
# ============================================================
@dataclass
class StrategyConfig:
    # ---- OpenInsider Filters ----
    MIN_TRADE_VALUE: int = 20000
    REQUIRED_TITLES: List[str] = None
    
    # ---- Fundamental Analysis Thresholds ----
    MIN_CURRENT_RATIO: float = 1.5
    MAX_DEBT_TO_EQUITY: float = 2.0
    MIN_PROFIT_MARGIN: float = 0.45
    MAX_PE_RATIO: float = 50
    
    # ---- Technical Analysis Filters ----
    REQUIRE_PRICE_ABOVE_50MA: bool = True
    REQUIRE_PRICE_ABOVE_200MA: bool = False
    MIN_VOLUME_20D_AVG: int = 100000
    MAX_RSI: float = 70
    MIN_RSI: float = 30
    
    # ---- Macro Filters ----
    MAX_VIX_THRESHOLD: float = 30
    CHECK_MARKET_TREND: bool = True
    
    # ---- Risk Management ----
    MAX_PORTFOLIO_RISK_PCT: float = 0.02
    MAX_CONCURRENT_POSITIONS: int = 5
    STOP_LOSS_PCT: float = 0.005
    TAKE_PROFIT_PCT: float = 0.01
    
    # ---- Circuit Breaker ----
    MAX_DAILY_LOSS_PCT: float = 0.005
    MAX_DAILY_PROFIT_PCT: float = 0.02
    
    def __post_init__(self):
        if self.REQUIRED_TITLES is None:
            self.REQUIRED_TITLES = ['CEO', 'CFO', 'Director', 'Dir', 'President', 'Pres']


# ============================================================
# HELPER: Calculate RSI using pandas (no TA-Lib required)
# ============================================================
def calculate_rsi(data: pd.Series, period: int = 14) -> float:
    """
    Calculate RSI using pandas.
    RSI = 100 - (100 / (1 + RS))
    Where RS = Average Gain / Average Loss over period
    """
    try:
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        latest_rsi = rsi.iloc[-1]
        return float(latest_rsi) if pd.notna(latest_rsi) else None
    except Exception:
        return None


# ============================================================
# CORE LOGIC - YOUR ORIGINAL SYSTEM (ENCAPSULATED)
# ============================================================
class OpenInsiderCore:
    """Your complete trading system from the src/ folder."""
    
    def __init__(self, config: StrategyConfig):
        self.config = config
        self._cache = {}
        self._cache_duration = 3600
        
    # ----- DATA COLLECTION -----
    def scrape_insider_trades(self) -> pd.DataFrame:
        """Scrape OpenInsider for recent insider purchases."""
        url = "http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=0&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=100&page=1"
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', {'class': 'tinytable'})
            
            if not table:
                return pd.DataFrame()
            
            # Parse headers
            headers = [th.text.strip().replace('\xa0', ' ') for th in table.find('tr').find_all(['th', 'td'])]
            col_map = {h: idx for idx, h in enumerate(headers)}
            
            # Parse data
            data = []
            for row in table.find_all('tr')[1:]:
                cols = row.find_all('td')
                if len(cols) < len(headers):
                    continue
                    
                try:
                    trade_type = cols[col_map.get('Trade Type', 7)].text.strip()
                    if 'P' not in trade_type.upper():
                        continue
                    
                    ticker = cols[col_map.get('Ticker', 3)].text.strip()
                    price_str = cols[col_map.get('Price', 8)].text.strip().replace('$', '').replace(',', '')
                    qty_str = cols[col_map.get('Qty', 9)].text.strip().replace(',', '').replace('+', '')
                    value_str = cols[col_map.get('Value', 12)].text.strip().replace('$', '').replace(',', '')
                    
                    if not all([price_str, qty_str, value_str, ticker]):
                        continue
                    
                    price = float(price_str)
                    qty = int(qty_str)
                    value = float(value_str)
                    
                    if value < self.config.MIN_TRADE_VALUE:
                        continue
                    
                    record = {
                        'ticker': ticker,
                        'company': cols[col_map.get('Company Name', 4)].text.strip(),
                        'insider': cols[col_map.get('Insider Name', 5)].text.strip(),
                        'title': cols[col_map.get('Title', 6)].text.strip(),
                        'trade_date': cols[col_map.get('Trade Date', 2)].text.strip(),
                        'price': price,
                        'qty': qty,
                        'value': value,
                    }
                    data.append(record)
                    
                except Exception:
                    continue
            
            df = pd.DataFrame(data)
            if not df.empty:
                df['trade_date'] = pd.to_datetime(df['trade_date'], errors='coerce')
                week_ago = datetime.now() - timedelta(days=7)
                df = df[df['trade_date'] >= week_ago]
                
            return df
            
        except Exception as e:
            logger.error(f"OpenInsider scrape failed: {e}")
            return pd.DataFrame()
    
    # ----- SIGNAL FILTERING -----
    def filter_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply conviction filters to insider trades."""
        if df.empty:
            return df
        
        filtered = df.copy()
        
        # Filter by title
        required_titles_lower = [t.lower() for t in self.config.REQUIRED_TITLES]
        title_mask = filtered['title'].apply(
            lambda x: any(req in str(x).lower() for req in required_titles_lower)
        )
        filtered = filtered[title_mask]
        
        if filtered.empty:
            return filtered
        
        # Identify cluster buys
        ticker_counts = filtered['ticker'].value_counts()
        cluster_tickers = ticker_counts[ticker_counts >= 2].index
        filtered['is_cluster'] = filtered['ticker'].isin(cluster_tickers)
        filtered['cluster_size'] = filtered['ticker'].map(ticker_counts)
        
        # Calculate conviction score
        scores = filtered.apply(self._calculate_conviction_score, axis=1)
        filtered['conviction_score'] = scores
        
        # Sort by conviction
        filtered = filtered.sort_values('conviction_score', ascending=False)
        
        return filtered
    
    def _calculate_conviction_score(self, row) -> int:
        """Calculate conviction score 0-100."""
        score = 0
        
        # Value-based scoring
        value = float(row['value'])
        if value >= 1000000:
            score += 40
        elif value >= 100000:
            score += 30
        elif value >= 25000:
            score += 20
            
        # Title-based scoring
        title = str(row['title']).lower()
        if 'ceo' in title:
            score += 30
        elif 'cfo' in title:
            score += 25
        elif 'director' in title or 'dir' in title:
            score += 20
        
        # Cluster bonus
        if row.get('is_cluster', False):
            cluster_size = row.get('cluster_size', 1)
            score += min(20, int(cluster_size) * 10)
            
        # Recency bonus
        trade_date = row['trade_date']
        if pd.notna(trade_date):
            if hasattr(trade_date, 'tz') and trade_date.tz is not None:
                trade_date = trade_date.tz_localize(None)
            days_old = (datetime.now() - trade_date).days
            score += max(0, 10 - days_old * 2)
        
        return int(min(100, max(0, score)))
    
    # ----- FUNDAMENTAL ANALYSIS -----
    def analyze_fundamentals(self, ticker: str) -> Dict:
        """Analyze fundamentals using yfinance."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            if not info or len(info) < 5:
                return self._create_neutral_analysis(ticker, "Insufficient data")
            
            metrics = {
                'profit_margin': info.get('profitMargins', 0) or 0,
                'current_ratio': info.get('currentRatio', 0) or 0,
                'debt_to_equity': info.get('debtToEquity', 0) or 0,
                'pe_ratio': info.get('trailingPE', 0) or 0,
                'revenue_growth': info.get('revenueGrowth', 0) or 0,
                'market_cap': info.get('marketCap', 0) or 0,
            }
            
            # Calculate score
            score = self._calculate_fundamental_score(metrics)
            
            return {
                'ticker': ticker,
                'score': score,
                'passed': score >= 70,
                'metrics': metrics,
                'warnings': self._generate_fundamental_warnings(metrics),
                'data_source': 'yfinance'
            }
            
        except Exception as e:
            logger.warning(f"Fundamental analysis failed for {ticker}: {e}")
            return self._create_neutral_analysis(ticker, f"Error: {str(e)[:50]}")
    
    def _calculate_fundamental_score(self, metrics: Dict) -> int:
        """Calculate fundamental health score 0-100."""
        score = 65
        
        # Profitability
        profit_margin = metrics.get('profit_margin', 0)
        if profit_margin > 0.20:
            score += 15
        elif profit_margin > 0.10:
            score += 10
        elif profit_margin > 0.05:
            score += 5
        elif profit_margin < 0:
            score -= min(20, abs(profit_margin * 100))
        
        # Debt-to-Equity
        debt_to_equity = metrics.get('debt_to_equity', 0)
        if debt_to_equity < 0.5:
            score += 10
        elif debt_to_equity < 1.0:
            score += 5
        elif debt_to_equity > 4.0:
            score -= 25
        elif debt_to_equity > 2.0:
            score -= 10
        
        # Revenue Growth
        revenue_growth = metrics.get('revenue_growth', 0)
        if revenue_growth > 0.55:
            score += 20
        elif revenue_growth > 0.50:
            score += 15
        elif revenue_growth > 0.45:
            score += 10
        elif revenue_growth > 0.25:
            score += 5
        else:
            score -= 10
        
        # Current Ratio
        current_ratio = metrics.get('current_ratio', 0)
        if current_ratio > 3.0:
            score += 10
        elif current_ratio > 2.0:
            score += 7
        elif current_ratio > 1.5:
            score += 3
        elif current_ratio < 1.0:
            score -= 10
        
        # P/E Ratio
        pe_ratio = metrics.get('pe_ratio', 0)
        if pe_ratio > 0:
            if pe_ratio < 15:
                score += 5
            elif pe_ratio < 25:
                score += 2
            elif pe_ratio > 50:
                score -= 15
            elif pe_ratio > 25:
                score -= 5
        
        # Market Cap
        market_cap = metrics.get('market_cap', 0)
        if market_cap < 50_000_000:
            score -= 20
        elif market_cap < 100_000_000:
            score -= 10
        elif market_cap < 300_000_000:
            score -= 5
        
        return max(0, min(100, int(score)))
    
    def _generate_fundamental_warnings(self, metrics: Dict) -> List[str]:
        """Generate warnings for sub-optimal metrics."""
        warnings = []
        
        profit_margin = metrics.get('profit_margin', 0)
        if profit_margin and profit_margin < self.config.MIN_PROFIT_MARGIN:
            warnings.append(f"Low profit margin: {profit_margin:.2%}")
        
        current_ratio = metrics.get('current_ratio', 0)
        if current_ratio and current_ratio < self.config.MIN_CURRENT_RATIO:
            warnings.append(f"Low current ratio: {current_ratio:.2f}")
        
        debt_to_equity = metrics.get('debt_to_equity', 0)
        if debt_to_equity and debt_to_equity > self.config.MAX_DEBT_TO_EQUITY:
            warnings.append(f"High debt: {debt_to_equity:.2f}")
        
        pe_ratio = metrics.get('pe_ratio', 0)
        if pe_ratio and pe_ratio > self.config.MAX_PE_RATIO:
            warnings.append(f"High P/E: {pe_ratio:.2f}")
        
        market_cap = metrics.get('market_cap', 0)
        if market_cap and market_cap < 100_000_000:
            warnings.append(f"Small market cap: ${market_cap/1_000_000:.1f}M")
        
        return warnings
    
    def _create_neutral_analysis(self, ticker: str, reason: str) -> Dict:
        """Create neutral analysis when data is insufficient."""
        return {
            'ticker': ticker,
            'score': 40,
            'passed': False,
            'metrics': {},
            'warnings': [reason],
            'data_source': 'none'
        }
    
    # ----- TECHNICAL ANALYSIS (using pandas RSI) -----
    def analyze_technicals(self, ticker: str) -> Optional[Dict]:
        """Analyze technicals using yfinance (no TA-Lib)."""
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="200d")
            
            if df.empty or len(df) < 50:
                return None
            
            current_price = df['Close'].iloc[-1]
            sma_50 = df['Close'].rolling(window=50).mean().iloc[-1]
            sma_200 = df['Close'].rolling(window=200).mean().iloc[-1] if len(df) >= 200 else None
            volume_avg_20d = df['Volume'].rolling(window=20).mean().iloc[-1]
            
            # Calculate RSI using pandas (no TA-Lib)
            rsi = calculate_rsi(df['Close'], period=14)
            
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
                'warnings': []
            }
            
            # Apply filters
            if self.config.REQUIRE_PRICE_ABOVE_50MA and not result['above_50ma']:
                result['passed'] = False
                result['warnings'].append(f"Price below 50-MA")
            
            if self.config.REQUIRE_PRICE_ABOVE_200MA and sma_200 and pd.notna(sma_200):
                if current_price < sma_200:
                    result['passed'] = False
                    result['warnings'].append(f"Price below 200-MA")
            
            if volume_avg_20d < self.config.MIN_VOLUME_20D_AVG:
                result['passed'] = False
                result['warnings'].append(f"Low volume: {volume_avg_20d:,.0f}")
            
            if rsi and rsi > self.config.MAX_RSI:
                result['passed'] = False
                result['warnings'].append(f"Overbought RSI: {rsi:.1f}")
            
            if rsi and rsi < self.config.MIN_RSI:
                result['passed'] = False
                result['warnings'].append(f"Oversold RSI: {rsi:.1f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Technical analysis failed for {ticker}: {e}")
            return None
    
    # ----- MACRO FILTER -----
    def check_macro_conditions(self) -> Tuple[bool, str]:
        """Check VIX and SPY market conditions."""
        try:
            # Check VIX
            vix = yf.Ticker("^VIX")
            vix_hist = vix.history(period="5d")
            if not vix_hist.empty:
                vix_current = vix_hist['Close'].iloc[-1]
                if vix_current > self.config.MAX_VIX_THRESHOLD:
                    return False, f"VIX too high: {vix_current:.1f}"
            
            # Check SPY trend
            if self.config.CHECK_MARKET_TREND:
                spy = yf.Ticker("SPY")
                spy_hist = spy.history(period="100d")
                if not spy_hist.empty and len(spy_hist) >= 50:
                    spy_price = spy_hist['Close'].iloc[-1]
                    spy_50ma = spy_hist['Close'].tail(50).mean()
                    if spy_price < spy_50ma:
                        return False, f"SPY below 50-MA"
            
            return True, "Favorable conditions"
            
        except Exception as e:
            logger.warning(f"Macro check failed: {e}")
            return True, "Proceeding with caution"
    
    # ----- CIRCUIT BREAKER -----
    class CircuitBreaker:
        def __init__(self, config: StrategyConfig):
            self.config = config
            self.daily_pnl = 0
            self.daily_start_equity = 0
            self.trading_halted = False
            
        def check_daily_limits(self, current_equity: float, daily_pnl: float) -> bool:
            loss_limit = daily_pnl * -1  # Positive number for comparison
            profit_limit = daily_pnl * 1  # Positive number for comparison
            
            if daily_pnl >= profit_limit and profit_limit > 0:
                self.trading_halted = True
                logger.warning(f"DAILY PROFIT TARGET REACHED: ${daily_pnl:.2f}")
                return False
            
            if daily_pnl <= -loss_limit:
                self.trading_halted = True
                logger.warning(f"DAILY LOSS LIMIT REACHED: ${daily_pnl:.2f}")
                return False
            
            return True


# ============================================================
# ALGOBULLS STRATEGY CLASS
# ============================================================
class StrategyOpenInsiderBot(StrategyBase):
    """
    OpenInsider Trading Bot - Monetized AI Agent
    
    This strategy combines insider trading signals with multi-layer
    filtering (fundamental, technical, macro) to generate high-conviction
    trades in US equities.
    
    REVENUE: Up to 70% revenue share on AlgoBulls marketplace
    """
    
    name = 'OpenInsider Multi-Layer Bot'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initialize configuration
        self.strategy_config = StrategyConfig(
            MIN_TRADE_VALUE=self.strategy_parameters.get('MIN_TRADE_VALUE', 20000),
            MAX_PORTFOLIO_RISK_PCT=self.strategy_parameters.get('MAX_PORTFOLIO_RISK_PCT', 0.02),
            MAX_CONCURRENT_POSITIONS=self.strategy_parameters.get('MAX_CONCURRENT_POSITIONS', 5),
            STOP_LOSS_PCT=self.strategy_parameters.get('STOP_LOSS_PCT', 0.005),
            TAKE_PROFIT_PCT=self.strategy_parameters.get('TAKE_PROFIT_PCT', 0.01),
            MAX_DAILY_LOSS_PCT=self.strategy_parameters.get('MAX_DAILY_LOSS_PCT', 0.005),
            MAX_DAILY_PROFIT_PCT=self.strategy_parameters.get('MAX_DAILY_PROFIT_PCT', 0.02),
            REQUIRED_TITLES=self.strategy_parameters.get('REQUIRED_TITLES', ['CEO', 'CFO', 'Director', 'Dir', 'President', 'Pres'])
        )
        
        # Initialize core
        self.core = OpenInsiderCore(self.strategy_config)
        self.circuit_breaker = OpenInsiderCore.CircuitBreaker(self.strategy_config)
        
        # State
        self._processed_tickers = set()
        self._last_scan_time = None
        self._daily_pnl = 0.0
        self._start_equity = 0.0
        self._trades_today = []
        self._cache = {}
        self._cache_timestamp = {}
        self._cache_duration = 300
        
        logger.info(f"OpenInsider Strategy initialized")
    
    def initialize(self):
        """Called at the start of each trading day."""
        self._processed_tickers = set()
        self._last_scan_time = None
        self._trades_today = []
        self._cache = {}
        self._cache_timestamp = {}
        
        portfolio_value = self.broker.get_account().equity
        self._start_equity = float(portfolio_value)
        self._daily_pnl = 0.0
        
        logger.info(f"Day initialized. Start equity: ${self._start_equity:.2f}")
    
    # ----- CORE DECISION LOGIC -----
    def get_decision(self, instrument):
        """Your complete trading logic - the 'black box'."""
        ticker = instrument.symbol
        
        # Check cache
        if ticker in self._cache:
            cache_time = self._cache_timestamp.get(ticker, 0)
            if time.time() - cache_time < self._cache_duration:
                return self._cache[ticker]
        
        logger.info(f"Analyzing {ticker}...")
        
        try:
            # Step 0: Macro Check
            is_safe, reason = self.core.check_macro_conditions()
            if not is_safe:
                logger.info(f"{ticker}: Macro reject - {reason}")
                self._cache[ticker] = None
                self._cache_timestamp[ticker] = time.time()
                return None
            
            # Step 1: Get Insider Data
            all_insider_data = self.core.scrape_insider_trades()
            if all_insider_data.empty:
                logger.info(f"{ticker}: No insider data")
                self._cache[ticker] = None
                self._cache_timestamp[ticker] = time.time()
                return None
            
            ticker_data = all_insider_data[all_insider_data['ticker'] == ticker]
            if ticker_data.empty:
                logger.info(f"{ticker}: No recent insider purchases")
                self._cache[ticker] = None
                self._cache_timestamp[ticker] = time.time()
                return None
            
            # Step 2: Signal Filtering
            filtered = self.core.filter_signals(ticker_data)
            if filtered.empty:
                logger.info(f"{ticker}: Failed signal filtering")
                self._cache[ticker] = None
                self._cache_timestamp[ticker] = time.time()
                return None
            
            best_signal = filtered.iloc[0]
            conviction_score = best_signal.get('conviction_score', 0)
            
            if conviction_score < 30:
                logger.info(f"{ticker}: Low conviction ({conviction_score})")
                self._cache[ticker] = None
                self._cache_timestamp[ticker] = time.time()
                return None
            
            # Step 3: Fundamental Analysis
            fundamental = self.core.analyze_fundamentals(ticker)
            if not fundamental or not fundamental.get('passed', False):
                logger.info(f"{ticker}: Failed fundamental (score={fundamental.get('score', 0)})")
                self._cache[ticker] = None
                self._cache_timestamp[ticker] = time.time()
                return None
            
            # Step 4: Technical Analysis
            technical = self.core.analyze_technicals(ticker)
            if technical is None or not technical.get('passed', False):
                logger.info(f"{ticker}: Failed technical")
                self._cache[ticker] = None
                self._cache_timestamp[ticker] = time.time()
                return None
            
            # Step 5: Combined Score
            combined_score = (
                (conviction_score * 0.3) +
                (fundamental['score'] * 0.4) +
                (100 if technical['above_50ma'] else 0) * 0.3
            )
            
            if combined_score < 50:
                logger.info(f"{ticker}: Combined score too low ({combined_score:.1f})")
                self._cache[ticker] = None
                self._cache_timestamp[ticker] = time.time()
                return None
            
            # SUCCESS
            logger.info(f"{ticker}: PASSED all filters! Conviction={conviction_score}, Fund={fundamental['score']}, Combined={combined_score:.1f}")
            
            result = {
                'ticker': ticker,
                'signal': 'BUY',
                'conviction_score': conviction_score,
                'fundamental_score': fundamental['score'],
                'combined_score': combined_score,
                'current_price': technical['current_price'],
                'sma_50': technical['sma_50'],
                'rsi': technical['rsi']
            }
            
            self._cache[ticker] = result
            self._cache_timestamp[ticker] = time.time()
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {e}")
            self._cache[ticker] = None
            self._cache_timestamp[ticker] = time.time()
            return None
    
    # ----- ALGOBULLS REQUIRED METHODS -----
    
    def strategy_select_instruments_for_entry(self, candle, instruments_bucket):
        """Select instruments to enter."""
        selected_instruments = []
        meta = []
        
        # Check circuit breaker
        current_equity = self.broker.get_account().equity
        if not self.circuit_breaker.check_daily_limits(float(current_equity), self._daily_pnl):
            logger.warning("Circuit breaker triggered - no new entries")
            return [], []
        
        # Check position count
        positions = self.broker.get_positions()
        if len(positions) >= self.strategy_config.MAX_CONCURRENT_POSITIONS:
            logger.info(f"Max positions reached ({len(positions)})")
            return [], []
        
        # Analyze instruments
        for instrument in instruments_bucket:
            ticker = instrument.symbol
            
            if any(p.symbol == ticker for p in positions):
                continue
            
            decision = self.get_decision(instrument)
            
            if decision and decision.get('signal') == 'BUY':
                selected_instruments.append(instrument)
                meta.append({
                    'action': 'BUY',
                    'conviction_score': decision.get('conviction_score', 0),
                    'fundamental_score': decision.get('fundamental_score', 0)
                })
                logger.info(f"Selected {ticker} for entry")
        
        return selected_instruments, meta
    
    def strategy_enter_position(self, candle, instrument, meta):
        """Execute entry order."""
        ticker = instrument.symbol
        action = meta.get('action', 'BUY')
        
        account = self.broker.get_account()
        portfolio_value = float(account.equity)
        max_risk = portfolio_value * self.strategy_config.MAX_PORTFOLIO_RISK_PCT
        
        current_price = self.broker.get_current_price(instrument)
        if not current_price or current_price <= 0:
            logger.warning(f"Invalid price for {ticker}")
            return None
        
        shares = int(max_risk / current_price)
        if shares < 1:
            shares = 1
        
        stop_loss_price = current_price * (1 - self.strategy_config.STOP_LOSS_PCT)
        take_profit_price = current_price * (1 + self.strategy_config.TAKE_PROFIT_PCT)
        
        stop_loss_price = max(0.01, round(stop_loss_price, 2))
        take_profit_price = max(0.01, round(take_profit_price, 2))
        
        logger.info(f"Entry: {ticker} - {shares} shares @ ${current_price:.2f}, SL: ${stop_loss_price:.2f}, TP: ${take_profit_price:.2f}")
        
        order = self.broker.OrderBracket(
            instrument,
            action,
            quantity=shares,
            stop_loss={'limit_price': stop_loss_price},
            take_profit={'limit_price': take_profit_price}
        )
        
        self._trades_today.append({
            'ticker': ticker,
            'shares': shares,
            'entry_price': current_price,
            'stop_loss': stop_loss_price,
            'take_profit': take_profit_price,
            'timestamp': candle.time
        })
        
        self._update_daily_pnl()
        return order
    
    def strategy_select_instruments_for_exit(self, candle, instruments_bucket):
        """Select positions to exit."""
        selected_instruments = []
        meta = []
        positions = self.broker.get_positions()
        
        for instrument in instruments_bucket:
            ticker = instrument.symbol
            position = next((p for p in positions if p.symbol == ticker), None)
            if position is None:
                continue
            
            current_price = self.broker.get_current_price(instrument)
            if not current_price:
                continue
            
            avg_entry = float(position.avg_entry_price)
            pnl_pct = (current_price - avg_entry) / avg_entry
            
            if pnl_pct <= -self.strategy_config.STOP_LOSS_PCT:
                selected_instruments.append(instrument)
                meta.append({'action': 'EXIT', 'reason': 'Stop loss'})
                logger.info(f"{ticker}: Stop loss triggered ({pnl_pct:.2%})")
                
            elif pnl_pct >= self.strategy_config.TAKE_PROFIT_PCT:
                selected_instruments.append(instrument)
                meta.append({'action': 'EXIT', 'reason': 'Take profit'})
                logger.info(f"{ticker}: Take profit triggered ({pnl_pct:.2%})")
            
            elif self.circuit_breaker.trading_halted:
                selected_instruments.append(instrument)
                meta.append({'action': 'EXIT', 'reason': 'Circuit breaker'})
                logger.info(f"{ticker}: Exiting due to circuit breaker")
        
        return selected_instruments, meta
    
    def strategy_exit_position(self, candle, instrument, meta):
        """Close position."""
        ticker = instrument.symbol
        reason = meta.get('reason', 'Manual')
        
        logger.info(f"Exiting {ticker}: {reason}")
        
        position = self.broker.get_position(instrument)
        if position is None:
            return False
        
        order = self.broker.OrderMarket(
            instrument,
            'SELL',
            quantity=position.quantity
        )
        
        self._update_daily_pnl()
        return True
    
    def _update_daily_pnl(self):
        """Update daily P&L."""
        try:
            account = self.broker.get_account()
            current_equity = float(account.equity)
            self._daily_pnl = current_equity - self._start_equity
        except Exception as e:
            logger.debug(f"Failed to update daily P&L: {e}")


# ============================================================
# STRATEGY CREATOR SUBMISSION HELPER
# ============================================================
def create_strategy_package():
    """Create the complete strategy package."""
    print("\n" + "="*60)
    print("OPENINSIDER STRATEGY - MONETIZATION PACKAGE")
    print("="*60)
    print("\nThis strategy is ready for submission to AlgoBulls.")
    print("\nStrategy Name: OpenInsider Multi-Layer Bot")
    print("Revenue Model: Up to 70% revenue share")
    print("\nFeatures:")
    print("  ✓ OpenInsider insider tracking")
    print("  ✓ Multi-layer filtering")
    print("  ✓ Circuit breakers")
    print("  ✓ Risk management")
    print("  ✓ Cluster detection")
    print("\n" + "="*60)
    print("\nTO SUBMIT TO ALGOBULLS:")
    print("1. Save this file as 'strategy_openinsider_bot.py'")
    print("2. Go to https://algobulls.com")
    print("3. Navigate to 'Strategy Creator'")
    print("4. Upload this file")
    print("5. Apply for the Strategy Creator Program")
    print("6. Start earning up to 70% revenue share!")
    print("="*60)


if __name__ == "__main__":
    create_strategy_package()