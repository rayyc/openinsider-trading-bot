import os
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass
class Config:
    # OpenInsider Configuration
    OPENINSIDER_URL = "http://openinsider.com/screener"
    
    # Alpaca API Configuration (for trade execution only - NOT for market data)
    ALPACA_API_KEY = os.getenv('ALPACA_API_KEY', '')
    ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY', '')
    ALPACA_BASE_URL = "https://paper-api.alpaca.markets"  # Use paper trading!
    
    # Financial Modeling Prep API (FREE - Get key from financialmodelingprep.com)
    FMP_API_KEY = os.getenv('FMP_API_KEY', '')
    USE_FMP_FALLBACK = False  # Use FMP when yfinance fails
    
    # Market Data Source Configuration
    # ================================
    # IMPORTANT: All market data (prices, volume, technical indicators) comes from Yahoo Finance
    # Yahoo Finance is FREE and does NOT require:
    # - API keys
    # - Subscriptions
    # - Authentication
    # 
    # What Yahoo Finance provides:
    # - Historical OHLCV data (Open, High, Low, Close, Volume)
    # - Current prices
    # - Moving averages (calculated from historical data)
    # - Volume data for RSI and other indicators
    # 
    # Alpaca is ONLY used for:
    # - Trade execution (buying/selling stocks)
    # - Portfolio management
    # - Account information
    # 
    # This avoids the "subscription does not permit querying recent SIP data" error
    
    # Trading Parameters
    MAX_PORTFOLIO_RISK_PCT = 0.02  # Risk 2% of portfolio per trade
    MIN_TRADE_VALUE = 20000  # Minimum insider purchase value to consider
    REQUIRED_TITLES = ['CEO', 'CFO', 'Director','Dir', 'President', 'Pres']
    MAX_POSITION_SIZE = 0.02
    MAX_CONCURRENT_POSITIONS = 5   # Maximum open positions

    # Fundamental Analysis Thresholds
    MIN_CURRENT_RATIO = 1.5
    MAX_DEBT_TO_EQUITY = 2.0
    MIN_PROFIT_MARGIN = 0.45
    MAX_PE_RATIO = 50
    
    # Technical Analysis Filters (using Yahoo Finance data)
    REQUIRE_PRICE_ABOVE_50MA = True  # Only trade stocks above 50-day moving average
    REQUIRE_PRICE_ABOVE_200MA = False  # Less strict - 200-day MA check
    MIN_VOLUME_20D_AVG = 100000  # Minimum average daily volume (100k shares)
    MAX_RSI = 70  # Avoid overbought stocks (RSI > 70)
    MIN_RSI = 30  # Avoid oversold/weak stocks (RSI < 30)
    
    # Macro Environment Filters (using Yahoo Finance for VIX and SPY data)
    MAX_VIX_THRESHOLD = 30  # Pause trading if VIX (volatility) > 30
    CHECK_MARKET_TREND = True  # Only trade when SPY is above its 50-day MA

    # --- Circuit Breaker ---
    # Toggle between percentage-based or fixed-dollar daily limits
    USE_PERCENTAGE_MODE = False        # True = % of equity, False = fixed $

    # Percentage-based thresholds
    MAX_DAILY_LOSS_PCT = 0.005        # 0.5% of equity
    MAX_DAILY_PROFIT_PCT = 0.02       # 2% of equity

    # Fixed-dollar thresholds
    MAX_DAILY_LOSS_USD = 500          # $500 daily loss cap
    MAX_DAILY_PROFIT_USD = 250        # $250 daily profit cap

    # --- Risk Management (per trade) ---
    # Toggle between percentage-based or fixed-dollar per-trade limits
    USE_PERCENTAGE_MODE_TRADES = False # True = % of trade size, False = fixed $

    # Percentage-based thresholds
    STOP_LOSS_PCT = 0.005             # 0.5% stop loss per trade
    TAKE_PROFIT_PCT = 0.01            # 1% take profit per trade

    # Fixed-dollar thresholds
    STOP_LOSS_USD = 100               # $100 stop loss per trade
    TAKE_PROFIT_USD = 250             # $250 take profit per trade

    # System
    LOG_LEVEL = "INFO"
    
    # ===== SCHEDULING CONFIGURATION =====
    RUN_INTERVAL_MINUTES = 5  # Run every 5 minutes (adjust as needed)
    
    # Market Hours in EAT (East Africa Time, UTC+3)
    MARKET_OPEN_EAT = "16:30"  # 4:30 PM EAT
    MARKET_CLOSE_EAT = "23:00"  # 11:00 PM EAT
    
    # Days to trade (0=Monday, 1=Tuesday, ... 4=Friday)
    TRADING_DAYS = [0, 1, 2, 3, 4]  # Monday through Friday
    
config = Config()
