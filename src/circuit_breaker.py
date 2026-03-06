# src/circuit_breaker.py - UPDATED WITH DUAL-MODE LOGIC
from datetime import datetime, date
import structlog
import json
import os
import logging
from src.config import config

logger = structlog.get_logger()
logger = logging.getLogger(__name__)

class CircuitBreaker:
    def __init__(self, trade_executor):
        self.executor = trade_executor
        self.api = trade_executor.api
        self.state_file = "circuit_breaker_state.json"
        self.trading_halted = False
        self.daily_pnl = 0
        self.daily_start_equity = 0
        
        self._load_state()
    
    def _load_state(self):
        """Load or initialize circuit breaker state."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    
                    # Check if it's the same trading day
                    saved_date = datetime.fromisoformat(state.get('date', '2000-01-01')).date()
                    if saved_date == date.today():
                        self.trading_halted = state.get('trading_halted', False)
                        self.daily_start_equity = state.get('daily_start_equity', 0)
                        self.daily_pnl = state.get('daily_pnl', 0)
                        logger.info(f"Loaded circuit breaker state: halted={self.trading_halted}")
                        return
            
            # New trading day or no state file
            account = self.api.get_account()
            self.daily_start_equity = float(account.equity)
            self.daily_pnl = 0
            self.trading_halted = False
            self._save_state()
            logger.info(f"New trading day. Start equity: ${self.daily_start_equity:.2f}")
            
        except Exception as e:
            logger.error(f"Failed to load circuit breaker state: {e}")
            # Default safe values
            self.trading_halted = True
            self.daily_start_equity = 0
    
    def _save_state(self):
        """Save current state to file."""
        try:
            state = {
                'date': date.today().isoformat(),
                'trading_halted': self.trading_halted,
                'daily_start_equity': self.daily_start_equity,
                'daily_pnl': self.daily_pnl,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save circuit breaker state: {e}")
    
    def _save_historical_pnl(self):
        """Save daily P&L to historical data file."""
        try:
            history_file = "pnl_history.json"
            today = date.today().isoformat()
            
            # Load existing history
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    history = json.load(f)
            else:
                history = []
            
            # Check if we already have an entry for today
            today_entry = None
            for entry in history:
                if entry.get('date') == today:
                    today_entry = entry
                    break
            
            if today_entry:
                # Update existing entry
                today_entry['daily_pnl'] = self.daily_pnl
                today_entry['last_updated'] = datetime.now().isoformat()
            else:
                # Add new entry
                history.append({
                    'date': today,
                    'daily_pnl': self.daily_pnl,
                    'start_equity': self.daily_start_equity,
                    'last_updated': datetime.now().isoformat()
                })
            
            # Keep only last 30 days
            history = sorted(history, key=lambda x: x['date'], reverse=True)[:30]
            
            # Save
            with open(history_file, 'w') as f:
                json.dump(history, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save historical P&L: {e}")
    
    def check_daily_limits(self):
        """Check if daily loss OR profit exceeds thresholds."""
        if self.trading_halted:
            return False
        
        try:
            account = self.api.get_account()
            current_equity = float(account.equity)
            self.daily_pnl = current_equity - self.daily_start_equity
            
            # --- Dual Mode Logic ---
            if config.USE_PERCENTAGE_MODE:
                loss_limit = self.daily_start_equity * config.MAX_DAILY_LOSS_PCT
                profit_limit = self.daily_start_equity * config.MAX_DAILY_PROFIT_PCT
            else:
                loss_limit = config.MAX_DAILY_LOSS_USD
                profit_limit = config.MAX_DAILY_PROFIT_USD
            
            # Save to historical P&L
            self._save_historical_pnl()
            
            logger.info(
                f"Daily P&L: ${self.daily_pnl:+.2f}, "
                f"Equity: ${current_equity:.2f}, "
                f"Loss limit: ${loss_limit:.2f}, Profit limit: ${profit_limit:.2f}"
            )
            
            # Check if profit target reached
            if self.daily_pnl >= profit_limit:
                self.trading_halted = True
                self._save_state()
                logger.critical(
                    f"DAILY PROFIT TARGET REACHED! "
                    f"Daily P&L: ${self.daily_pnl:.2f} (Limit: ${profit_limit:.2f}). Trading HALTED."
                )
                return False
            
            # Check if loss exceeds threshold
            if -self.daily_pnl >= loss_limit:
                self.trading_halted = True
                self._save_state()
                
                try:
                    self.api.cancel_all_orders()
                    logger.critical("Cancelled all orders due to daily loss breach")
                except:
                    pass
                
                logger.critical(
                    f"DAILY LOSS CIRCUIT BREAKER TRIGGERED! "
                    f"Daily P&L: ${self.daily_pnl:.2f} (Limit: ${loss_limit:.2f}). Trading HALTED."
                )
                return False
            
            self._save_state()
            return True
            
        except Exception as e:
            logger.error(f"Error checking daily limits: {e}")
            # Fail safe - halt trading on error
            self.trading_halted = True
            return False
    
    def halt_trading(self, reason="Manual halt"):
        """Manually halt trading."""
        self.trading_halted = True
        self._save_state()
        logger.critical(f"Trading manually halted: {reason}")
    
    def reset_daily(self):
        """Reset for new trading day (call this after market close)."""
        account = self.api.get_account()
        self.daily_start_equity = float(account.equity)
        self.daily_pnl = 0
        self.trading_halted = False
        self._save_state()
        logger.info(f"Circuit breaker reset. New start equity: ${self.daily_start_equity:.2f}")
