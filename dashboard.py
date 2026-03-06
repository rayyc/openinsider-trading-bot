"""
Streamlit Dashboard for OpenInsider Trading Bot
Real-time monitoring of insider signals, portfolio, and bot performance
ENHANCED VERSION - Now includes FMP, Technical Analysis, and Macro Filters
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
import os
import sys
import traceback
from pathlib import Path
import pytz

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Try to import all components
try:
    from src.config import config
    from src.data_collection import OpenInsiderScraper
    from src.signal_filtering import SignalFilter
    from src.fundamental_analysis import FundamentalAnalyzer
    from src.technical_analysis import TechnicalAnalyzer  # NEW
    from src.macro_filter import MacroFilter  # NEW
    from src.trade_execution import TradeExecutor
    from src.risk_manager import RiskManager
    from src.circuit_breaker import CircuitBreaker
except ImportError as e:
    st.error(f"Import error: {e}. Please make sure all modules are in the correct location.")
    st.stop()

# Page config
st.set_page_config(
    page_title="Ray Charles Trading Bot - Enhanced",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stMetric {
        background-color: #1e2130;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #2e3241;
    }
    .signal-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        margin: 10px 0;
        color: white;
    }
    .buy-signal {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
    }
    .risk-high {
        background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
    }
    h1 {
        color: #667eea;
        font-weight: 700;
    }
    h2, h3 {
        color: #38ef7d;
    }
    .trade-win {
        background: #1e4620;
        border-left: 4px solid #38ef7d;
    }
    .trade-loss {
        background: #4a1e1e;
        border-left: 4px solid #f45c43;
    }
    .circuit-open {
        border-left: 6px solid #38ef7d;
        background: rgba(56, 239, 125, 0.1);
    }
    .circuit-closed {
        border-left: 6px solid #f45c43;
        background: rgba(244, 92, 67, 0.1);
    }
    .metric-card {
        background: #1e2130;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
        border: 1px solid #2e3241;
    }
    .new-feature {
        background: linear-gradient(135deg, #2c3e50 100%, #3498db 0%);
        padding: 10px;
        border-radius: 8px;
        margin: 5px 0;
        color: white;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=30)
def get_cached_signals(_scraper, _signal_filter):
    """Cache signal fetching to reduce API calls"""
    try:
        raw_data = _scraper.scrape_prebuilt_screen("cluster")
        if not raw_data.empty:
            filtered_signals = _signal_filter.filter_high_conviction(raw_data)
            return filtered_signals
    except Exception as e:
        st.error(f"Error fetching signals: {e}")
    return pd.DataFrame()

@st.cache_data(ttl=10)
def get_cached_fundamentals(_analyzer, tickers, min_score=60):
    """Cache fundamental analysis with FMP fallback"""
    try:
        results = _analyzer.batch_analyze(tickers, min_score=min_score)
        return results
    except Exception as e:
        st.error(f"Error in fundamental analysis: {e}")
    return []

@st.cache_data(ttl=10)
def get_cached_technicals(_technical_analyzer, tickers):
    """Cache technical analysis"""
    try:
        results = _technical_analyzer.batch_analyze(tickers)
        return results
    except Exception as e:
        st.error(f"Error in technical analysis: {e}")
    return []

@st.cache_resource
def init_components():
    """Initialize bot components with error handling"""
    try:
        scraper = OpenInsiderScraper()
        signal_filter = SignalFilter()
        analyzer = FundamentalAnalyzer()
        technical_analyzer = TechnicalAnalyzer()  # NEW
        macro_filter = MacroFilter()  # NEW
        executor = TradeExecutor()
        risk_manager = RiskManager(executor)
        circuit_breaker = CircuitBreaker(executor)
        
        return {
            'scraper': scraper,
            'filter': signal_filter,
            'analyzer': analyzer,
            'technical': technical_analyzer,  # NEW
            'macro': macro_filter,  # NEW
            'executor': executor,
            'risk_manager': risk_manager,
            'circuit_breaker': circuit_breaker,
            'config': config
        }
    except Exception as e:
        st.error(f"Failed to initialize components: {e}")
        st.error(traceback.format_exc())
        return None

def get_market_status():
    """Check if market is open based on EAT timezone"""
    eat_tz = pytz.timezone('Africa/Nairobi')
    now_eat = datetime.now(eat_tz)
    
    # Check day of week
    if now_eat.weekday() not in config.TRADING_DAYS:
        return False, "Market closed (weekend)"
    
    # Check time
    from datetime import time as dt_time
    market_open = dt_time(16, 30)
    market_close = dt_time(23, 0)
    current_time = now_eat.time()
    
    if market_open <= current_time <= market_close:
        return True, "Market open"
    elif current_time < market_open:
        return False, f"Market opens at {market_open.strftime('%H:%M')} EAT"
    else:
        return False, "Market closed for the day"

def get_account_summary(executor):
    """Get Alpaca account summary"""
    try:
        account = executor.api.get_account()
        positions = executor.get_positions()
        
        portfolio_value = float(account.portfolio_value)
        cash = float(account.cash)
        buying_power = float(account.buying_power)
        equity = float(account.equity)
        
        day_pl = float(account.equity) - float(account.last_equity)
        day_pl_pct = (day_pl / float(account.last_equity)) * 100 if float(account.last_equity) > 0 else 0
        
        position_values = [p['current_value'] for p in positions]
        total_position_value = sum(position_values)
        unrealized_pl = portfolio_value - (total_position_value + cash)
        
        return {
            'portfolio_value': portfolio_value,
            'cash': cash,
            'buying_power': buying_power,
            'equity': equity,
            'day_pl': day_pl,
            'day_pl_pct': day_pl_pct,
            'num_positions': len(positions),
            'total_position_value': total_position_value,
            'unrealized_pl': unrealized_pl,
            'positions': positions
        }
    except Exception as e:
        st.error(f"Error getting account summary: {e}")
        return None

def get_orders_history(executor, days=7):
    """Get recent orders history"""
    try:
        utc_tz = pytz.UTC
        since_date = datetime.now(utc_tz) - timedelta(days=days)
        
        orders = executor.api.list_orders(
            status='all',
            after=since_date.isoformat(),
            limit=100
        )
        
        orders_data = []
        for order in orders:
            orders_data.append({
                'id': order.id,
                'symbol': order.symbol,
                'qty': float(order.qty) if order.qty else 0,
                'filled_qty': float(order.filled_qty) if order.filled_qty else 0,
                'side': order.side,
                'type': order.type,
                'status': order.status,
                'filled_avg_price': float(order.filled_avg_price) if order.filled_avg_price else 0,
                'submitted_at': order.submitted_at,
                'filled_at': order.filled_at if order.filled_at else None
            })
        
        return pd.DataFrame(orders_data)
    except Exception as e:
        st.error(f"Error getting orders: {e}")
        return pd.DataFrame()

def check_if_bot_process_running():
    """Check if the main trading bot process is running"""
    try:
        import psutil
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    cmdline = proc.info['cmdline']
                    if cmdline and any('main.py' in str(arg) for arg in cmdline):
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        log_file = Path(__file__).parent / 'logs' / 'trading_bot.log'
        if log_file.exists():
            import time
            if time.time() - log_file.stat().st_mtime < 300:
                return True
        
        return False
    except:
        log_file = Path(__file__).parent / 'logs' / 'trading_bot.log'
        if log_file.exists():
            import time
            if time.time() - log_file.stat().st_mtime < 300:
                return True
        return None

def calculate_position_metrics(positions):
    if not positions:
        return {
            'total_positions': 0,
            'total_value': 0,
            'avg_position_size': 0,
            'largest_position': 0,
            'sector_exposure': {},
            'position_types': {'long': 0, 'short': 0}
        }
    
    df = pd.DataFrame(positions)
    
    total_value = df['current_value'].sum()
    avg_position_size = df['current_value'].mean() if len(df) > 0 else 0
    largest_position = df['current_value'].max() if len(df) > 0 else 0
    
    sector_exposure = {'Unknown': len(df)}
    
    return {
        'total_positions': len(df),
        'total_value': total_value,
        'avg_position_size': avg_position_size,
        'largest_position': largest_position,
        'sector_exposure': sector_exposure,
        'position_types': {'long': len(df), 'short': 0}
    }

def main():
    st.markdown("<h1>📈 Ray Charles Enhanced Trading Dashboard</h1>", unsafe_allow_html=True)
    
    # NEW FEATURES BANNER
    st.markdown("""
        <div class="new-feature">
            🆕 NEW: FMP Integration | Technical Analysis | Macro Filter | Multi-Layer Filtering
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Auto-refresh
    st.markdown('<meta http-equiv="refresh" content="180">', unsafe_allow_html=True)
    
    # Initialize components
    components = init_components()
    if not components:
        st.error("Failed to initialize bot components. Check the logs for details.")
        return
    
    # Unpack components
    scraper = components['scraper']
    signal_filter = components['filter']
    analyzer = components['analyzer']
    technical_analyzer = components['technical']  # NEW
    macro_filter = components['macro']  # NEW
    executor = components['executor']
    risk_manager = components['risk_manager']
    circuit_breaker = components['circuit_breaker']
    config_obj = components['config']
    
    # Refresh circuit breaker state
    try:
        state_file = "circuit_breaker_state.json"
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state = json.load(f)
                saved_date = datetime.fromisoformat(state.get('date', '2000-01-01')).date()
                if saved_date == datetime.now().date():
                    circuit_breaker.trading_halted = state.get('trading_halted', False)
                    circuit_breaker.daily_start_equity = state.get('daily_start_equity', 0)
                    circuit_breaker.daily_pnl = state.get('daily_pnl', 0)
    except Exception as e:
        st.warning(f"Could not refresh circuit breaker state: {e}")
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 🤖 Bot Controls")
        
        # NEW: Show macro filter status
        is_safe, macro_reason = macro_filter.is_safe_to_trade()
        if is_safe:
            st.success(f"🟢 Macro: {macro_reason}")
        else:
            st.error(f"🔴 Macro: {macro_reason}")
        
        st.markdown("---")
        
        # Auto-refresh
        auto_refresh = st.checkbox("Auto Refresh (180s)", value=True)
        if auto_refresh:
            st.info("✅ Auto-refresh enabled")
        else:
            st.info("❌ Auto-refresh disabled")
        
        if st.button("🔄 Refresh All Data", type="primary", width='stretch'):
            st.cache_resource.clear()
            st.rerun()
        
        if st.button("🧹 Clear Cache", help="Clear cached data"):
            st.cache_resource.clear()
            st.success("Cache cleared!")
            st.rerun()
        
        st.markdown("---")
        
        # Signal Filters
        st.markdown("### 🎯 Signal Filters")
        
        min_value_filter = st.slider(
            "Minimum Trade Value ($)",
            min_value=0,
            max_value=1000000,
            value=config_obj.MIN_TRADE_VALUE,
            step=10000
        )
        
        title_filter = st.multiselect(
            "Insider Titles",
            options=config_obj.REQUIRED_TITLES,
            default=config_obj.REQUIRED_TITLES
        )
        
        days_filter = st.slider(
            "Max Days Old",
            min_value=1,
            max_value=30,
            value=5,
            step=1
        )
        
        # UPDATED: Lowered from 85 to 70
        min_score_filter = st.slider(
            "Min Fundamental Score",
            min_value=0,
            max_value=100,
            value=70,
            step=5,
            help="Lowered from 85 due to additional technical filters"
        )
        
        st.markdown("---")
        
        # NEW: Technical Filter Settings
        st.markdown("### 📊 Technical Filters")
        
        tech_settings = {
            "Price > 50MA": "✅" if config_obj.REQUIRE_PRICE_ABOVE_50MA else "❌",
            "Price > 200MA": "✅" if config_obj.REQUIRE_PRICE_ABOVE_200MA else "❌",
            "Min Volume": f"{config_obj.MIN_VOLUME_20D_AVG:,}",
            "RSI Range": f"{config_obj.MIN_RSI}-{config_obj.MAX_RSI}"
        }
        
        for key, value in tech_settings.items():
            st.text(f"{key}: {value}")
        
        st.markdown("---")
        
        # NEW: Macro Filter Settings
        st.markdown("### 🌍 Macro Filters")
        
        macro_settings = {
            "Max VIX": str(config_obj.MAX_VIX_THRESHOLD),
            "Check SPY Trend": "✅" if config_obj.CHECK_MARKET_TREND else "❌"
        }
        
        for key, value in macro_settings.items():
            st.text(f"{key}: {value}")
        
        st.markdown("---")
        
        # Risk Controls
        st.markdown("### ⚠️ Risk Controls")
        
        if config_obj.USE_PERCENTAGE_MODE:
            daily_loss_display = f"{config_obj.MAX_DAILY_LOSS_PCT*100:.1f}%"
            daily_profit_display = f"{config_obj.MAX_DAILY_PROFIT_PCT*100:.1f}%"
        else:
            daily_loss_display = f"${config_obj.MAX_DAILY_LOSS_USD:,.0f}"
            daily_profit_display = f"${config_obj.MAX_DAILY_PROFIT_USD:,.0f}"
        
        if config_obj.USE_PERCENTAGE_MODE_TRADES:
            stop_loss_display = f"{config_obj.STOP_LOSS_PCT*100:.1f}%"
            take_profit_display = f"{config_obj.TAKE_PROFIT_PCT*100:.1f}%"
        else:
            stop_loss_display = f"${config_obj.STOP_LOSS_USD:,.0f}"
            take_profit_display = f"${config_obj.TAKE_PROFIT_USD:,.0f}"
        
        risk_display = {
            "Max Portfolio Risk": f"{config_obj.MAX_PORTFOLIO_RISK_PCT*100:.1f}%",
            "Max Daily Loss": daily_loss_display,
            "Max Daily Profit": daily_profit_display,
            "Stop Loss": stop_loss_display,
            "Take Profit": take_profit_display,
            "Max Positions": str(config_obj.MAX_CONCURRENT_POSITIONS)
        }
        
        for key, value in risk_display.items():
            st.text(f"{key}: {value}")
        
        st.markdown("---")
        
        # Market Status
        market_open, market_status = get_market_status()
        if market_open:
            st.success(f"🟢 {market_status}")
        else:
            st.error(f"🔴 {market_status}")
        
        # Circuit Breaker Status
        cb_status = "🔴 HALTED" if circuit_breaker.trading_halted else "🟢 ACTIVE"
        st.text(f"Circuit Breaker: {cb_status}")
        
        if circuit_breaker.trading_halted:
            if st.button("🟢 Reset Circuit Breaker", type="secondary"):
                circuit_breaker.reset_daily()
                st.success("Circuit breaker reset!")
                st.rerun()
    
    # Bot Status
    bot_running = check_if_bot_process_running()
    if bot_running is True:
        st.success("🤖 Bot Status: RUNNING")
    elif bot_running is False:
        st.warning("🤖 Bot Status: STOPPED")
    else:
        st.info("🤖 Bot Status: UNKNOWN")
    
    # Main tabs - UPDATED with new tab
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Overview", 
        "🎯 Signals", 
        "💰 Portfolio", 
        "📈 Analytics",
        "🔬 Multi-Layer Filter",  # NEW TAB
        "⚙️ Configuration",
        "📋 Logs"
    ])
    
    with tab1:
        # Account Overview (same as before)
        st.markdown("## 💼 Account Overview")
        
        account_summary = get_account_summary(executor)
        if account_summary:
            current_daily_pnl = account_summary['equity'] - circuit_breaker.daily_start_equity
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric(
                    "Portfolio Value",
                    f"${account_summary['portfolio_value']:,.2f}",
                    delta=f"{account_summary['day_pl_pct']:+.2f}%"
                )
            
            with col2:
                st.metric("Equity", f"${account_summary['equity']:,.2f}")
            
            with col3:
                st.metric("Cash", f"${account_summary['cash']:,.2f}")
            
            with col4:
                st.metric("Buying Power", f"${account_summary['buying_power']:,.2f}")
            
            with col5:
                pl_color = "normal" if account_summary['day_pl'] >= 0 else "inverse"
                st.metric(
                    "Today's P&L",
                    f"${account_summary['day_pl']:+,.2f}",
                    delta=f"{account_summary['day_pl_pct']:+.2f}%",
                    delta_color=pl_color
                )
            
            st.markdown("---")
            
            # Risk Metrics
            st.markdown("## ⚠️ Risk Metrics")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("Open Positions", account_summary['num_positions'])
            
            with col2:
                max_positions = config_obj.MAX_CONCURRENT_POSITIONS
                position_pct = (account_summary['num_positions'] / max_positions) * 100
                st.metric(
                    "Position Limit",
                    f"{account_summary['num_positions']}/{max_positions}",
                    delta=f"{position_pct:.1f}%"
                )
            
            with col3:
                if config_obj.USE_PERCENTAGE_MODE:
                    daily_loss_pct = (-current_daily_pnl / circuit_breaker.daily_start_equity) * 100 if current_daily_pnl < 0 else 0
                    loss_limit = config_obj.MAX_DAILY_LOSS_PCT * 100
                    remaining_loss = max(0, loss_limit - daily_loss_pct)
                    st.metric("Daily Loss Limit", f"{daily_loss_pct:.2f}% / {loss_limit:.1f}%", delta=f"{remaining_loss:.1f}% remaining")
                else:
                    daily_loss_usd = -current_daily_pnl if current_daily_pnl < 0 else 0
                    loss_limit_usd = config_obj.MAX_DAILY_LOSS_USD
                    remaining_loss = max(0, loss_limit_usd - daily_loss_usd)
                    st.metric("Daily Loss Limit", f"${daily_loss_usd:,.2f} / ${loss_limit_usd:,.0f}", delta=f"${remaining_loss:,.2f} remaining")
            
            with col4:
                if config_obj.USE_PERCENTAGE_MODE:
                    daily_profit_pct = (current_daily_pnl / circuit_breaker.daily_start_equity) * 100 if current_daily_pnl > 0 else 0
                    profit_target = config_obj.MAX_DAILY_PROFIT_PCT * 100
                    remaining_profit = max(0, profit_target - daily_profit_pct)
                    st.metric("Daily Profit Target", f"{daily_profit_pct:.2f}% / {profit_target:.1f}%", delta=f"{remaining_profit:.1f}% to target")
                else:
                    daily_profit_usd = current_daily_pnl if current_daily_pnl > 0 else 0
                    profit_target_usd = config_obj.MAX_DAILY_PROFIT_USD
                    remaining_profit = max(0, profit_target_usd - daily_profit_usd)
                    st.metric("Daily Profit Target", f"${daily_profit_usd:,.2f} / ${profit_target_usd:,.0f}", delta=f"${remaining_profit:,.2f} to target")
            
            with col5:
                circuit_status = "ACTIVE" if not circuit_breaker.trading_halted else "HALTED"
                st.metric("Circuit Breaker", circuit_status)
            
            st.markdown("---")
            
            # Recent Activity
            st.markdown("## 📊 Recent Activity")
            
            orders_df = get_orders_history(executor, days=3)
            
            if not orders_df.empty:
                filled_orders = orders_df[orders_df['status'] == 'filled']
                
                if not filled_orders.empty:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### Recent Trades")
                        recent_trades = filled_orders.sort_values('submitted_at', ascending=False).head(10)
                        display_df = recent_trades[['symbol', 'side', 'qty', 'filled_avg_price', 'submitted_at']].copy()
                        display_df['filled_avg_price'] = display_df['filled_avg_price'].apply(lambda x: f"${x:.2f}")
                        display_df['submitted_at'] = pd.to_datetime(display_df['submitted_at']).dt.strftime('%Y-%m-%d %H:%M')
                        st.dataframe(display_df, width='stretch')
                    
                    with col2:
                        st.markdown("#### Trade Summary")
                        total_trades = len(filled_orders)
                        buy_trades = len(filled_orders[filled_orders['side'] == 'buy'])
                        avg_trade_size = filled_orders['qty'].mean()
                        
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.metric("Total Trades", total_trades)
                        with col_b:
                            st.metric("Buy Orders", buy_trades)
                        with col_c:
                            st.metric("Avg Shares", f"{avg_trade_size:.0f}")
                else:
                    st.info("No filled orders in the last 3 days")
            else:
                st.info("No order history available")
        else:
            st.error("Could not load account data")
    
    with tab2:
        # Signal Discovery - ENHANCED
        st.markdown("## 🎯 Enhanced Insider Signal Discovery")
        st.info("🆕 Now with multi-layer filtering: Fundamentals + Technical + Macro")
        
        with st.spinner("Scanning with enhanced filters..."):
            try:
                raw_data = get_cached_signals(scraper, signal_filter)
                
                if not raw_data.empty:
                    filtered_signals = signal_filter.filter_high_conviction(raw_data)
                    
                    if not filtered_signals.empty:
                        # Apply user filters
                        filtered_signals = filtered_signals[
                            (filtered_signals['value'] >= min_value_filter) &
                            (filtered_signals['title'].apply(
                                lambda x: any(title in str(x) for title in title_filter)
                            )) &
                            ((datetime.now() - pd.to_datetime(filtered_signals['trade_date'])).dt.days <= days_filter)
                        ]
                        
                        if not filtered_signals.empty:
                            st.success(f"Found {len(filtered_signals)} high-conviction signals")
                            
                            # Get top tickers
                            top_tickers = filtered_signals['ticker'].unique()[:10]
                            
                            # LAYER 1: Fundamental Analysis
                            fundamental_results = get_cached_fundamentals(analyzer, top_tickers, min_score=min_score_filter)
                            
                            if fundamental_results:
                                st.info(f"✅ {len(fundamental_results)} passed fundamental analysis")
                                
                                # LAYER 2: Technical Analysis
                                fundamental_tickers = [r['ticker'] for r in fundamental_results]
                                technical_results = get_cached_technicals(technical_analyzer, fundamental_tickers)
                                
                                if technical_results:
                                    st.info(f"✅ {len(technical_results)} passed technical analysis")
                                    
                                    # Merge results
                                    technical_tickers = {r['ticker'] for r in technical_results}
                                    final_results = [r for r in fundamental_results if r['ticker'] in technical_tickers]
                                    
                                    # Display signals
                                    for result in final_results:
                                        ticker = result['ticker']
                                        ticker_signals = filtered_signals[filtered_signals['ticker'] == ticker]
                                        
                                        if not ticker_signals.empty:
                                            best_signal = ticker_signals.iloc[0]
                                            
                                            # Get technical data
                                            tech_data = next((t for t in technical_results if t['ticker'] == ticker), None)
                                            
                                            # Calculate overall score
                                            overall_score = (result['score'] + best_signal['conviction_score']) / 2
                                            
                                            # Determine signal strength
                                            if overall_score >= 75:
                                                card_class = "signal-card buy-signal"
                                                emoji = "🚀"
                                                strength = "STRONG BUY"
                                            elif overall_score >= 60:
                                                card_class = "signal-card"
                                                emoji = "🟢"
                                                strength = "BUY"
                                            else:
                                                card_class = "signal-card"
                                                emoji = "⚪"
                                                strength = "HOLD"
                                            
                                            price = tech_data.get('current_price') if tech_data else None
                                            sma_50 = tech_data.get('sma_50') if tech_data else None
                                            rsi = tech_data.get('rsi') if tech_data else None

                                            # Format with None handling
                                            price_str = f"${price:.2f}" if price is not None else "N/A"
                                            sma_50_str = f"${sma_50:.2f}" if sma_50 is not None else "N/A"
                                            rsi_str = f"{rsi:.1f}" if rsi is not None else "N/A"
                                            
                                            with st.container():
                                                st.markdown(f"""
                                                    <div class="{card_class}">
                                                        <h3>{emoji} {ticker} - {strength}</h3>
                                                        <p><strong>Overall Score:</strong> {overall_score:.1f}/100 
                                                        | <strong>Fundamental:</strong> {result['score']}
                                                        | <strong>Conviction:</strong> {best_signal['conviction_score']}</p>
                                                        <p><strong>Insider:</strong> {best_signal['insider']} ({best_signal['title']})</p>
                                                        <p><strong>Trade:</strong> {best_signal['qty']:,} shares @ ${best_signal['price']:.2f} 
                                                        (Value: ${best_signal['value']:,.0f})</p>
                                                        <p><strong>Trade Date:</strong> {best_signal['trade_date'].strftime('%Y-%m-%d')}</p>
                                                        <p><strong>🆕 Technical:</strong> Price={price_str}, 
                                                        50MA={sma_50_str}, 
                                                        RSI={rsi_str}</p>
                                                        <p><strong>🆕 Data Source:</strong> {result.get('data_source', 'yfinance')}</p>
                                                        <p style="font-size: 0.9em; opacity: 0.8;">
                                                            Warnings: {len(result['warnings'])} | 
                                                            Market Cap: ${result['metrics'].get('market_cap', 0)/1_000_000:.1f}M
                                                        </p>
                                                    </div>
                                                """, unsafe_allow_html=True)
                                                
                                                col_a, col_b, col_c = st.columns([1, 1, 4])
                                                with col_a:
                                                    if st.button(f"📊 Details", key=f"analyze_{ticker}"):
                                                        with st.expander("Full Analysis"):
                                                            st.json(result)
                                                            if tech_data:
                                                                st.json(tech_data)
                                                
                                                st.markdown("---")
                                else:
                                    st.warning("No signals passed technical analysis")
                            else:
                                st.warning("No signals passed fundamental analysis")
                        else:
                            st.info("No signals match your filters")
                    else:
                        st.warning("No high-conviction signals found")
                else:
                    st.warning("No data from OpenInsider")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.error(traceback.format_exc())
    
    # Continue with tab3 (Portfolio) - same as before...
    with tab3:
        st.markdown("## 💰 Portfolio Management")
        
        account_summary = get_account_summary(executor)
        if account_summary and account_summary['positions']:
            positions = account_summary['positions']
            pos_metrics = calculate_position_metrics(positions)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Positions", pos_metrics['total_positions'])
            with col2:
                st.metric("Total Value", f"${pos_metrics['total_value']:,.2f}")
            with col3:
                st.metric("Avg Position", f"${pos_metrics['avg_position_size']:,.2f}")
            with col4:
                st.metric("Largest Position", f"${pos_metrics['largest_position']:,.2f}")
            
            st.markdown("---")
            st.markdown("#### 📊 Current Positions")
            
            pos_df = pd.DataFrame(positions)
            if not pos_df.empty:
                pos_df['position_pct'] = (pos_df['current_value'] / account_summary['portfolio_value'] * 100).round(2)
                st.dataframe(pos_df, width='stretch')
                
                fig = px.pie(
                    pos_df,
                    values='current_value',
                    names='ticker',
                    title='Portfolio Allocation',
                    color_discrete_sequence=px.colors.sequential.Viridis
                )
                fig.update_layout(template='plotly_dark', height=400)
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No positions")
        else:
            st.info("No positions")
    
    with tab4:
    # Analytics - Complete Position P&L Analysis
     st.markdown("## 📈 Current Position Analytics")
    
    account_summary = get_account_summary(executor)
    if account_summary and account_summary['positions']:
        positions = account_summary['positions']
        
        # Current Position P&L Analysis
        st.markdown("### 💰 Current Position Performance")
        
        pos_df = pd.DataFrame(positions)
        
        if not pos_df.empty:
            # Get current prices and calculate P&L
            pos_analysis = []
            
            for idx, row in pos_df.iterrows():
                ticker = row['ticker']
                avg_price = row['avg_price']
                qty = row['qty']
                current_value = row['current_value']
                
                # Calculate P&L
                try:
                    # Use yfinance to get current price
                    import yfinance as yf
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="1d")
                    
                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                        position_value = qty * current_price
                        unrealized_pnl = position_value - (qty * avg_price)
                        unrealized_pct = (unrealized_pnl / (qty * avg_price)) * 100
                        
                        pos_analysis.append({
                            'ticker': ticker,
                            'qty': qty,
                            'avg_price': avg_price,
                            'current_price': current_price,
                            'current_value': position_value,
                            'unrealized_pnl': unrealized_pnl,
                            'unrealized_pct': unrealized_pct,
                            'position_pct_portfolio': (position_value / account_summary['portfolio_value']) * 100
                        })
                except Exception as e:
                    st.warning(f"Could not get current price for {ticker}: {e}")
            
            if pos_analysis:
                analysis_df = pd.DataFrame(pos_analysis)
                
                # Summary metrics
                total_unrealized_pnl = analysis_df['unrealized_pnl'].sum()
                avg_unrealized_pct = analysis_df['unrealized_pct'].mean()
                best_performer = analysis_df.loc[analysis_df['unrealized_pct'].idxmax()]
                worst_performer = analysis_df.loc[analysis_df['unrealized_pct'].idxmin()]
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    pnl_color = "normal" if total_unrealized_pnl >= 0 else "inverse"
                    st.metric(
                        "Total Unrealized P&L",
                        f"${total_unrealized_pnl:+,.2f}",
                        delta=f"{avg_unrealized_pct:+.2f}% avg",
                        delta_color=pnl_color
                    )
                
                with col2:
                    st.metric("Best Performer", f"{best_performer['ticker']}", 
                            delta=f"{best_performer['unrealized_pct']:+.2f}%")
                
                with col3:
                    st.metric("Worst Performer", f"{worst_performer['ticker']}", 
                            delta=f"{worst_performer['unrealized_pct']:+.2f}%")
                
                with col4:
                    profitable_positions = len(analysis_df[analysis_df['unrealized_pnl'] > 0])
                    st.metric("Profitable Positions", f"{profitable_positions}/{len(analysis_df)}")
                
                st.markdown("---")
                
                # Position P&L Table
                st.markdown("#### 📊 Position P&L Details")
                
                display_df = analysis_df.copy()
                display_df['avg_price'] = display_df['avg_price'].apply(lambda x: f"${x:.2f}")
                display_df['current_price'] = display_df['current_price'].apply(lambda x: f"${x:.2f}")
                display_df['current_value'] = display_df['current_value'].apply(lambda x: f"${x:,.2f}")
                display_df['unrealized_pnl'] = display_df['unrealized_pnl'].apply(lambda x: f"${x:+,.2f}")
                display_df['unrealized_pct'] = display_df['unrealized_pct'].apply(lambda x: f"{x:+.2f}%")
                display_df['position_pct_portfolio'] = display_df['position_pct_portfolio'].apply(lambda x: f"{x:.2f}%")
                
                st.dataframe(display_df[['ticker', 'qty', 'avg_price', 'current_price', 'current_value', 
                                       'unrealized_pnl', 'unrealized_pct', 'position_pct_portfolio']], 
                           width='stretch')
                
                st.markdown("---")
                
                # P&L Distribution Chart
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 📈 P&L Distribution")
                    fig = px.bar(
                        analysis_df,
                        x='ticker',
                        y='unrealized_pct',
                        title='Unrealized P&L by Position (%)',
                        color='unrealized_pct',
                        color_continuous_scale='RdYlGn'
                    )
                    fig.update_layout(
                        template='plotly_dark',
                        xaxis_title='Ticker',
                        yaxis_title='Unrealized P&L (%)',
                        height=300
                    )
                    st.plotly_chart(fig, width='stretch')
                
                with col2:
                    st.markdown("#### 🥧 Portfolio Allocation")
                    fig = px.pie(
                        analysis_df,
                        values='current_value',
                        names='ticker',
                        title='Current Portfolio Allocation',
                        color_discrete_sequence=px.colors.sequential.Viridis
                    )
                    fig.update_layout(template='plotly_dark', height=300)
                    st.plotly_chart(fig, width='stretch')
                
                st.markdown("---")
                
                # Historical P&L Chart
                st.markdown("#### 📊 Historical Daily P&L")
                
                # Load historical P&L data
                try:
                    
                    from pathlib import Path
                    
                    history_file = Path("pnl_history.json")
                    if history_file.exists():
                        with open(history_file, 'r') as f:
                            pnl_history = json.load(f)
                        
                        if pnl_history:
                            # Convert to DataFrame
                            history_df = pd.DataFrame(pnl_history)
                            history_df['date'] = pd.to_datetime(history_df['date'])
                            history_df = history_df.sort_values('date')
                            
                            # Create line chart
                            fig = px.line(
                                history_df,
                                x='date',
                                y='daily_pnl',
                                title='Daily P&L Over Time',
                                markers=True
                            )
                            fig.update_layout(
                                template='plotly_dark',
                                xaxis_title='Date',
                                yaxis_title='Daily P&L ($)',
                                height=300
                            )
                            fig.update_traces(line_color='#38ef7d', marker_color='#38ef7d')
                            st.plotly_chart(fig, width='stretch')
                        else:
                            st.info("No historical P&L data available yet. Data will appear after a few trading days.")
                    else:
                        st.info("Historical P&L tracking will begin after the next trading day.")
                
                except Exception as e:
                    st.warning(f"Could not load historical P&L data: {e}")
                
                st.markdown("---")
                st.markdown("#### ⚠️ Position Risk Analysis")
                
                risk_analysis = []
                for idx, row in analysis_df.iterrows():
                    unrealized_pct = row['unrealized_pct']
                    
                    # Calculate distance to stop loss and take profit
                    if config.USE_PERCENTAGE_MODE_TRADES:
                        stop_loss_distance = unrealized_pct - (-config.STOP_LOSS_PCT * 100)
                        take_profit_distance = (config.TAKE_PROFIT_PCT * 100) - unrealized_pct
                    else:
                        # For fixed dollar mode, calculate based on position value
                        position_value = row['qty'] * row['avg_price']
                        stop_loss_pct = (config.STOP_LOSS_USD / position_value) * 100
                        take_profit_pct = (config.TAKE_PROFIT_USD / position_value) * 100
                        stop_loss_distance = unrealized_pct - (-stop_loss_pct)
                        take_profit_distance = take_profit_pct - unrealized_pct
                    
                    risk_level = "LOW"
                    if stop_loss_distance < 2:
                        risk_level = "HIGH"
                    elif stop_loss_distance < 5:
                        risk_level = "MEDIUM"
                    
                    risk_analysis.append({
                        'ticker': row['ticker'],
                        'unrealized_pct': unrealized_pct,
                        'distance_to_stop_pct': stop_loss_distance,
                        'distance_to_profit_pct': take_profit_distance,
                        'risk_level': risk_level
                    })
                
                risk_df = pd.DataFrame(risk_analysis)
                
                # Color coding for risk levels
                def color_risk(val):
                    if val == "HIGH":
                        return 'color: #ff4444'
                    elif val == "MEDIUM":
                        return 'color: #ffaa44'
                    else:
                        return 'color: #44aa44'
                
                display_risk_df = risk_df.copy()
                display_risk_df['unrealized_pct'] = display_risk_df['unrealized_pct'].apply(lambda x: f"{x:+.2f}%")
                display_risk_df['distance_to_stop_pct'] = display_risk_df['distance_to_stop_pct'].apply(lambda x: f"{x:+.2f}%")
                display_risk_df['distance_to_profit_pct'] = display_risk_df['distance_to_profit_pct'].apply(lambda x: f"{x:+.2f}%")
                
                st.dataframe(
                    display_risk_df.style.map(color_risk, subset=['risk_level']),
                    width='stretch'
                )
                
                # Risk summary
                high_risk_count = len(risk_df[risk_df['risk_level'] == 'HIGH'])
                if high_risk_count > 0:
                    st.warning(f"⚠️ {high_risk_count} position(s) are at HIGH risk (close to stop loss)")
            
            else:
                st.info("Unable to calculate position P&L - check API connection")
        else:
            st.info("No positions to analyze")
    else:
        st.info("No account data available for position analysis")
    
    # Circuit Breaker Analytics
    st.markdown("---")
    st.markdown("#### 🔌 Circuit Breaker Analytics")
    
    # Circuit breaker status visualization
    cb_data = {
        'Metric': ['Daily Loss Limit', 'Daily Profit Target', 'Position Limit', 'Circuit Breaker Status'],
        'Current': [
            f"{-circuit_breaker.daily_pnl/circuit_breaker.daily_start_equity*100:.2f}%" if circuit_breaker.daily_pnl < 0 else "0%",
            f"{circuit_breaker.daily_pnl/circuit_breaker.daily_start_equity*100:.2f}%" if circuit_breaker.daily_pnl > 0 else "0%",
            f"{account_summary['num_positions'] if account_summary else 0}/{config.MAX_CONCURRENT_POSITIONS}",
            "ACTIVE" if not circuit_breaker.trading_halted else "HALTED"
        ],
        'Limit/Target': [
            f"${config.MAX_DAILY_LOSS_USD}",
            f"${config.MAX_DAILY_PROFIT_USD}",
            f"{config.MAX_CONCURRENT_POSITIONS}",
            "N/A"
        ]
    }
    
    cb_df = pd.DataFrame(cb_data)
    st.dataframe(cb_df, width='stretch')
    
    # NEW TAB: Multi-Layer Filter Visualization
    with tab5:
        st.markdown("## 🔬 Multi-Layer Filter Pipeline")
        st.markdown("### See how signals pass through each filter stage")
        
        with st.spinner("Running complete filter pipeline..."):
            try:
                # Stage 1: Raw Data
                raw_data = get_cached_signals(scraper, signal_filter)
                stage1_count = len(raw_data) if not raw_data.empty else 0
                
                # Stage 2: Signal Filtering
                filtered_signals = signal_filter.filter_high_conviction(raw_data) if not raw_data.empty else pd.DataFrame()
                stage2_count = len(filtered_signals) if not filtered_signals.empty else 0
                
                # Stage 3: Fundamental Analysis
                tickers = filtered_signals['ticker'].unique()[:10] if not filtered_signals.empty else []
                fundamental_results = get_cached_fundamentals(analyzer, tickers, min_score=min_score_filter) if len(tickers) > 0 else []
                stage3_count = len(fundamental_results)
                
                # Stage 4: Technical Analysis
                fundamental_tickers = [r['ticker'] for r in fundamental_results]
                technical_results = get_cached_technicals(technical_analyzer, fundamental_tickers) if fundamental_tickers else []
                stage4_count = len(technical_results)
                
                # Stage 5: Macro Filter
                is_safe, macro_reason = macro_filter.is_safe_to_trade()
                stage5_count = stage4_count if is_safe else 0
                
                # Visualize funnel
                st.markdown("### 📊 Signal Funnel")
                
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    st.metric("1️⃣ Raw Signals", stage1_count)
                    st.caption("OpenInsider scrape")
                
                with col2:
                    retention = (stage2_count / stage1_count * 100) if stage1_count > 0 else 0
                    st.metric("2️⃣ Conviction Filter", stage2_count, delta=f"{retention:.1f}%")
                    st.caption("Title, value, cluster")
                
                with col3:
                    retention = (stage3_count / stage2_count * 100) if stage2_count > 0 else 0
                    st.metric("3️⃣ Fundamental", stage3_count, delta=f"{retention:.1f}%")
                    st.caption("FMP + yfinance")
                
                with col4:
                    retention = (stage4_count / stage3_count * 100) if stage3_count > 0 else 0
                    st.metric("4️⃣ Technical", stage4_count, delta=f"{retention:.1f}%")
                    st.caption("MA, RSI, Volume")
                
                with col5:
                    retention = (stage5_count / stage4_count * 100) if stage4_count > 0 else 0
                    st.metric("5️⃣ Macro", stage5_count, delta=f"{retention:.1f}%")
                    st.caption(f"VIX, SPY trend")
                
                # Funnel chart
                funnel_data = pd.DataFrame({
                    'Stage': ['Raw Signals', 'Conviction', 'Fundamental', 'Technical', 'Macro'],
                    'Count': [stage1_count, stage2_count, stage3_count, stage4_count, stage5_count]
                })
                
                fig = go.Figure(go.Funnel(
                    y=funnel_data['Stage'],
                    x=funnel_data['Count'],
                    textinfo="value+percent initial",
                    marker=dict(color=["#667eea", "#764ba2", "#11998e", "#38ef7d", "#f093fb"])
                ))
                fig.update_layout(
                    title="Signal Filtering Funnel",
                    template='plotly_dark',
                    height=400
                )
                st.plotly_chart(fig, width='stretch')
                
                # Show filter effectiveness
                st.markdown("### 📈 Filter Effectiveness")
                
                if stage1_count > 0:
                    overall_pass_rate = (stage5_count / stage1_count) * 100
                    st.metric("Overall Pass Rate", f"{overall_pass_rate:.1f}%", 
                             help="Percentage of raw signals that pass all filters")
                    
                    if overall_pass_rate < 5:
                        st.success("✅ Excellent filtering - very selective system")
                    elif overall_pass_rate < 15:
                        st.info("✅ Good filtering - balanced selectivity")
                    else:
                        st.warning("⚠️ High pass rate - consider stricter filters")
                
            except Exception as e:
                st.error(f"Error in filter pipeline: {e}")
    
    with tab6:
        # Configuration tab - UPDATED
        st.markdown("## ⚙️ Enhanced Bot Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Trading Parameters")
            config_display = {
                "Min Trade Value": f"${config_obj.MIN_TRADE_VALUE:,.0f}",
                "Required Titles": ", ".join(config_obj.REQUIRED_TITLES),
                "Max Position Size": f"{config_obj.MAX_POSITION_SIZE*100:.1f}%",
                "Max Concurrent Positions": str(config_obj.MAX_CONCURRENT_POSITIONS),
                "Run Interval": f"{config_obj.RUN_INTERVAL_MINUTES} minutes"
            }
            
            for key, value in config_display.items():
                st.text(f"• {key}: {value}")
            
            st.markdown("### 🆕 Technical Filters")
            tech_config = {
                "Price > 50MA": "✅" if config_obj.REQUIRE_PRICE_ABOVE_50MA else "❌",
                "Price > 200MA": "✅" if config_obj.REQUIRE_PRICE_ABOVE_200MA else "❌",
                "Min Volume (20D)": f"{config_obj.MIN_VOLUME_20D_AVG:,}",
                "RSI Min": str(config_obj.MIN_RSI),
                "RSI Max": str(config_obj.MAX_RSI)
            }
            
            for key, value in tech_config.items():
                st.text(f"• {key}: {value}")
        
        with col2:
            st.markdown("### Risk Parameters")
            risk_display = {
                "Max Portfolio Risk": f"{config_obj.MAX_PORTFOLIO_RISK_PCT*100:.1f}%",
                "Max Daily Loss": f"{config_obj.MAX_DAILY_LOSS_PCT*100:.1f}%",
                "Max Daily Profit": f"{config_obj.MAX_DAILY_PROFIT_PCT*100:.1f}%",
                "Stop Loss": f"{config_obj.STOP_LOSS_PCT*100:.1f}%",
                "Take Profit": f"{config_obj.TAKE_PROFIT_PCT*100:.1f}%"
            }
            
            for key, value in risk_display.items():
                st.text(f"• {key}: {value}")
            
            st.markdown("### 🆕 Macro Filters")
            macro_config = {
                "Max VIX Threshold": str(config_obj.MAX_VIX_THRESHOLD),
                "Check Market Trend": "✅" if config_obj.CHECK_MARKET_TREND else "❌"
            }
            
            for key, value in macro_config.items():
                st.text(f"• {key}: {value}")
        
        st.markdown("---")
        
        # API Status - UPDATED
        st.markdown("### 🔌 API Status")
        
        try:
            account = executor.api.get_account()
            st.success(f"✅ Alpaca API Connected")
            st.text(f"Account Status: {account.status}")
        except Exception as e:
            st.error(f"❌ Alpaca API Error: {e}")
        
        # Test OpenInsider
        with st.spinner("Testing OpenInsider..."):
            try:
                test_data = scraper.scrape_prebuilt_screen("cluster")
                if not test_data.empty:
                    st.success(f"✅ OpenInsider Connected - {len(test_data)} trades")
                else:
                    st.warning("⚠️ OpenInsider connected but no data")
            except Exception as e:
                st.error(f"❌ OpenInsider Error: {e}")
        
        # NEW: Test FMP API (only if enabled)
        if hasattr(config_obj, 'USE_FMP_FALLBACK') and config_obj.USE_FMP_FALLBACK:
            # FMP is enabled - test it
            if hasattr(config_obj, 'FMP_API_KEY') and config_obj.FMP_API_KEY:
                with st.spinner("Testing FMP API..."):
                    try:
                        from src.fmp_analyzer import FMPAnalyzer
                        fmp = FMPAnalyzer()
                        test_result = fmp.get_key_metrics("AAPL")
                        if test_result:
                            st.success(f"✅ FMP API Connected - Test: AAPL P/E={test_result.get('pe_ratio', 'N/A')}")
                        else:
                            st.warning("⚠️ FMP API connected but returned no data - check API key or rate limits")
                    except Exception as e:
                        st.error(f"❌ FMP API Error: {e}")
            else:
                st.info("ℹ️ FMP API key not configured - add to .env file for enhanced fundamental data")
        else:
            # FMP is disabled - show friendly message
            st.info("ℹ️ FMP API disabled (USE_FMP_FALLBACK = False) - using yfinance only ✅")
    
    with tab7:
     # Logs tab
     st.markdown("## 📋 System Logs")
    
    # Import Path locally to avoid scoping issues
    from pathlib import Path as PathType
    logs_path = PathType("logs/trading_bot.log")
    
    if logs_path.is_file():
        with open(logs_path, "r", encoding='utf-8', errors='ignore') as log_file:
            lines = log_file.readlines()[-100:]
            lines = lines[::-1]
            
            for line in lines:
                st.text(line.strip())
    else:
        st.info("No logs found")
    
    # Footer
    st.markdown("---")
    st.markdown("""
        <div style="text-align: center; color: #666; padding: 20px;">
            <p>🆕 Enhanced OpenInsider Trading Bot v2.0 | Multi-Layer Filtering | 
            <a href="https://alpaca.markets" target="_blank" style="color: #667eea;">Alpaca</a> | 
            <a href="http://openinsider.com" target="_blank" style="color: #667eea;">OpenInsider</a> |
            <a href="https://financialmodelingprep.com" target="_blank" style="color: #667eea;">FMP</a></p>
            <p style="font-size: 0.8em;">New Features: FMP Integration • Technical Analysis • Macro Filters</p>
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()