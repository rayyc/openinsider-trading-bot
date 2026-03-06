# 📊 OpenInsider Trading Bot

Algorithmic trading system that executes trades on Alpaca based on insider trading signals from OpenInsider.com, enhanced with multi-layer fundamental and technical analysis.

## 🎯 Overview

This bot continuously monitors OpenInsider for high-conviction insider purchases (cluster buys by CEOs, CFOs, and Directors), filters them through rigorous fundamental and technical analysis, and automatically executes trades on Alpaca's paper or live trading platform.

## ✨ Key Features

### **📰 Intelligent Signal Generation**
- **OpenInsider Integration** - Automated real-time data collection
- **Cluster Buy Detection** - Identifies coordinated insider purchases
- **Executive-Level Filtering** - Focuses on C-suite and board member trades
- **Value Thresholds** - Minimum transaction size requirements
- **Real-time Monitoring** - Continuous scanning during market hours

### **🔬 Multi-Layer Analysis Pipeline**

#### **1. Fundamental Analysis**
- Current ratio & liquidity assessment
- Debt-to-equity ratio screening
- Profit margin evaluation
- P/E ratio filtering
- Financial health scoring
- Optional FMP API integration for enhanced metrics

#### **2. Technical Analysis**
- 50-day & 200-day moving average confirmation
- RSI (Relative Strength Index) boundaries (30-70)
- Volume analysis (20-day average threshold)
- Trend momentum verification
- Multi-timeframe confluence

#### **3. Macro Market Filters**
- VIX (Volatility Index) threshold monitoring
- SPY (S&P 500) trend analysis via 50-day MA
- Market hours verification (East Africa Time - EAT)
- Risk-off condition detection
- Circuit breaker integration

### **🛡️ Advanced Risk Management**

- **Circuit Breaker System**
  - Automatic trading halt on daily loss limits
  - Profit target protection
  - Configurable USD or percentage-based limits
  - State persistence across restarts

- **Position Sizing**
  - Percentage-based risk allocation (default 2%)
  - Maximum portfolio exposure limits
  - Dynamic position sizing based on account equity

- **Stop Loss / Take Profit**
  - Configurable exit levels (% or fixed USD)
  - Automatic order protection
  - Risk-reward ratio optimization

- **Position Limits**
  - Maximum concurrent positions cap
  - Per-symbol exposure control
  - Diversification enforcement

### **⚡ Execution & Monitoring**

- **Alpaca Integration**
  - Paper trading support (free virtual trading)
  - Live trading capability
  - REST API & WebSocket support
  - Real-time order status tracking

- **Scheduling & Automation**
  - APScheduler for reliable task execution
  - Market hours awareness (EAT timezone)
  - Configurable check intervals (default: 5 minutes)
  - Graceful error handling & recovery

- **Dashboard (Optional)**
  - Streamlit web interface
  - Real-time P&L tracking
  - Position monitoring
  - Trade history visualization
  - Interactive charts with Plotly

- **Logging & Monitoring**
  - Structured logging with structlog
  - System resource monitoring (psutil)
  - Trade execution audit trail
  - Error tracking & debugging

## 🛠️ Installation

### **Prerequisites**
- Python 3.8 or higher
- Alpaca brokerage account (paper or live)
- Internet connection for data fetching

### **Step 1: Clone Repository**
```bash
git clone https://github.com/YOUR_USERNAME/openinsider_trading_bot.git
cd openinsider_trading_bot
```

### **Step 2: Create Virtual Environment**
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

### **Step 3: Install Dependencies**
```bash
pip install -r requirements.txt
```

### **Step 4: Configure API Keys**

Create a `.env` file in the project root:
```env
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here

# Optional: Financial Modeling Prep API
#FMP_API_KEY=your_fmp_api_key_here
```

**Where to Get API Keys:**
- **Alpaca Paper Trading (Free)**: https://alpaca.markets/docs/trading/paper-trading/
- **Alpaca Live Trading**: https://alpaca.markets/docs/trading/
- **FMP API (Optional)**: https://financialmodelingprep.com/developer/docs/

## 🚀 Usage

### **Run the Trading Bot**
```bash
python -m src.main
```

### **Run the Dashboard (Optional)**
```bash
streamlit run dashboard.py
```

## ⚙️ Configuration

Edit `src/config.py` to customize bot behavior:

### **Position Sizing**
```python
MAX_PORTFOLIO_RISK_PCT = 0.02    # 2% of portfolio per trade
MAX_POSITION_SIZE = 0.02         # Max 2% in single position
MAX_CONCURRENT_POSITIONS = 5     # Maximum 5 open positions
```

### **Circuit Breaker Limits**
```python
USE_PERCENTAGE_MODE = False
MAX_DAILY_LOSS_USD = 500         # Halt at $500 loss
MAX_DAILY_PROFIT_USD = 250       # Halt at $250 profit
```

### **Stop Loss / Take Profit**
```python
USE_PERCENTAGE_MODE_TRADES = False
STOP_LOSS_USD = 100              # $100 max loss per trade
TAKE_PROFIT_USD = 250            # $250 profit target
```

### **Insider Signal Filters**
```python
MIN_TRADE_VALUE = 20000          # Minimum $20k insider purchase
REQUIRED_TITLES = ['CEO', 'CFO', 'Director', 'President']
```

### **Fundamental Analysis Thresholds**
```python
MIN_CURRENT_RATIO = 1.5          # Liquidity
MAX_DEBT_TO_EQUITY = 2.0         # Leverage
MIN_PROFIT_MARGIN = 0.45         # Profitability (45%)
MAX_PE_RATIO = 50                # Valuation
```

### **Technical Analysis Filters**
```python
REQUIRE_PRICE_ABOVE_50MA = True
REQUIRE_PRICE_ABOVE_200MA = True
MIN_VOLUME_20D_AVG = 100000
MAX_RSI = 70
MIN_RSI = 30
```

### **Macro Market Filters**
```python
MAX_VIX_THRESHOLD = 30           # No trades if VIX > 30
CHECK_MARKET_TREND = True        # Require SPY > 50-day MA
```

### **Trading Schedule**
```python
MARKET_OPEN_EAT = "16:30"        # 9:30 AM EST
MARKET_CLOSE_EAT = "23:00"       # 4:00 PM EST
RUN_INTERVAL_MINUTES = 5         # Scan every 5 minutes
```

## 🧪 Testing Strategy

### **Phase 1: Paper Trading (Mandatory)**

1. **Initial Setup (Week 1-2)**
   - Create Alpaca paper account
   - Configure bot with conservative settings
   - Monitor all signals and executions

2. **Optimization (Week 3-4)**
   - Adjust filter thresholds
   - Test different position sizes
   - Review performance

3. **Stress Testing (Week 5-6)**
   - Test during volatile conditions
   - Verify circuit breaker works
   - Check all safety limits

### **Phase 2: Live Trading (After Success)**

⚠️ **Only after 6+ weeks successful paper trading**

- Start with minimum position sizes
- Monitor daily for first month
- Never risk more than you can afford to lose

## 📈 Performance Monitoring

### **Log Files**
- `logs/trading_bot.log` - Main execution log
- Includes: signals, filters, trades, errors

### **State Files**
- `circuit_breaker_state.json` - Current P&L, limits
- `trade_history.json` - Complete trade record
- `positions.json` - Current open positions

## 🐛 Troubleshooting

### **Connection Errors**
- Check internet connection
- Verify API keys in `.env`
- Ensure Alpaca account is active

### **No Signals Detected**
- Check OpenInsider.com for data
- Adjust filter thresholds in config
- Verify market hours

### **Circuit Breaker Triggered**
- Review `circuit_breaker_state.json`
- Wait for next trading day
- Adjust limits if too restrictive

### **API Key Issues**
- Verify keys in `.env` are correct
- Check for paper vs live keys
- Regenerate if compromised

## 🔒 Security Best Practices

### **API Key Protection**
- ✅ Never commit `.env` to Git
- ✅ Use separate keys for paper/live
- ✅ Enable IP whitelisting
- ✅ Rotate keys regularly

### **Account Security**
- ✅ Enable 2FA on Alpaca
- ✅ Monitor account activity
- ✅ Review trades daily
- ✅ Set up alerts

## ⚠️ Risk Disclaimer

**TRADING INVOLVES SUBSTANTIAL RISK OF LOSS**

- This software is for **educational purposes only**
- Past performance does **NOT** guarantee future results
- You can lose some or all of your capital
- Only trade with money you can afford to lose
- The author(s) are **NOT** responsible for losses

### **Not Financial Advice**
- This is a tool, not investment advice
- Always do your own research
- Consult a licensed financial advisor
- Start with paper trading only

### **Insider Trading Legality**
- Uses **PUBLIC** insider data from SEC filings
- Following published trades is **100% legal**
- No illegal inside information used
- Data from official Form 4 filings

## 📝 License

MIT License - See LICENSE file for details

## 🤝 Contributing

Pull requests welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests if applicable
4. Submit PR with description

## 📚 Resources

- **Alpaca API**: https://alpaca.markets/docs/
- **OpenInsider**: http://openinsider.com/
- **SEC Filings**: https://www.sec.gov/edgar/

## 🙏 Acknowledgments

- Alpaca Markets for trading API
- OpenInsider for insider data
- Python trading community

---

**⭐ Star this repo if you find it useful!**

**💡 Remember: Start with paper trading and never risk more than you can afford to lose!**