#!/usr/bin/env python3
"""
Pivot Trading System - Main Entry Point (FIXED V2)
CRITICAL FIX: Always authenticate fresh at 8 AM, never trust old tokens
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta, time as dt_time
import signal

# Add modules to path
sys.path.insert(0, os.path.dirname(__file__))

# Import custom modules
from modules.kite_client import KiteClient
from modules.data_manager import DataManager
from modules.pivot_calculator import PivotCalculator
from modules.signal_generator import SignalGenerator
from modules.position_manager import PositionManager
from modules.database import Database
from modules.notifier import TelegramNotifier
from modules.auth_manager import AuthManager
from utils.trading_hours import TradingHours

# Setup logging
os.makedirs('logs', exist_ok=True)
log_file = f"logs/system_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class PivotTradingSystem:
    def __init__(self, config_path='config.json'):
        """Initialize the trading system"""
        logger.info("=" * 80)
        logger.info("PIVOT TRADING SYSTEM INITIALIZING")
        logger.info("=" * 80)
        
        # Load configuration
        self.config = self.load_config(config_path)
        self.running = True
        
        # Initialize components
        self.notifier = TelegramNotifier(self.config)
        self.trading_hours = TradingHours(self.config)
        self.database = Database(self.config['data']['database_path'])
        
        # Components to be initialized after authentication
        self.kite = None
        self.data_manager = None
        self.pivot_calc = None
        self.signal_gen = None
        self.position_mgr = None
        
        # Trading state
        self.pivot_data = {}
        self.market_structure = {}
        self.atm_strike = None
        self.candle_count = 0
        self.authenticated = False
        self.auth_attempts = 0
        self.max_auth_attempts = 20  # Try for ~1 hour (3 min intervals)
        
        # Load trading control state
        self.control_file = 'data/trading_control.json'
        self.load_control_state()
        
        logger.info("System components initialized")
    
    def load_config(self, config_path):
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            sys.exit(1)
    
    def load_control_state(self):
        """Load trading control state from file"""
        try:
            with open(self.control_file, 'r') as f:
                self.control = json.load(f)
        except:
            self.control = {
                'trading_enabled': True,
                'panic_mode': False,
                'last_updated': None
            }
            os.makedirs('data', exist_ok=True)
            with open(self.control_file, 'w') as f:
                json.dump(self.control, f, indent=2)
        
        logger.info(f"Control state: trading_enabled={self.control['trading_enabled']}, panic_mode={self.control['panic_mode']}")
    
    def is_token_fresh(self, token_file_path):
        """
        Check if token was generated today AND recently (within 2 hours)
        
        Kite tokens expire, so only trust tokens from:
        - Today's date
        - Generated after 6:00 AM (to avoid overnight tokens)
        - Less than 2 hours old
        """
        try:
            if not os.path.exists(token_file_path):
                logger.info("No token file exists")
                return False
            
            # Check file modification time
            file_mtime = os.path.getmtime(token_file_path)
            file_time = datetime.fromtimestamp(file_mtime)
            now = datetime.now()
            
            # Check if token from today
            if file_time.date() != now.date():
                logger.warning(f"Token file is from {file_time.date()}, today is {now.date()}")
                return False
            
            # Check if token generated after 6 AM
            if file_time.hour < 6:
                logger.warning(f"Token generated too early: {file_time.strftime('%H:%M:%S')}")
                return False
            
            # Check if token less than 2 hours old
            age_hours = (now - file_time).total_seconds() / 3600
            if age_hours > 2:
                logger.warning(f"Token is {age_hours:.1f} hours old (too old)")
                return False
            
            # Read and check date stamp inside file
            with open(token_file_path, 'r') as f:
                content = f.read().strip()
            
            if '|' in content:
                token, date_str = content.split('|', 1)
                token_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                if token_date != now.date():
                    logger.warning(f"Token date stamp is {token_date}, today is {now.date()}")
                    return False
            
            logger.info(f"Token is FRESH (age: {age_hours:.1f} hours, time: {file_time.strftime('%H:%M:%S')})")
            return True
            
        except Exception as e:
            logger.error(f"Error checking token freshness: {e}")
            return False
    
    def wait_for_authentication(self):
        """
        Wait for user to complete authentication
        Retries every 3 minutes until pre-market time (8:45 AM)
        """
        auth_manager = AuthManager(self.config, self.notifier)
        
        # CRITICAL: Delete any old token first
        token_file = self.config['data']['access_token_file']
        if os.path.exists(token_file):
            if not self.is_token_fresh(token_file):
                logger.warning("Deleting old/stale token file")
                os.remove(token_file)
                
        start_time = datetime.now()
        
        while self.auth_attempts < self.max_auth_attempts:
            self.auth_attempts += 1
            now = datetime.now()
            
            logger.info("=" * 80)
            logger.info(f"AUTHENTICATION ATTEMPT {self.auth_attempts}/{self.max_auth_attempts}")
            logger.info(f"Time: {now.strftime('%H:%M:%S')}")
            logger.info("=" * 80)
            
            # Try to authenticate
            access_token = auth_manager.authenticate()
            
            if access_token:
                # Validate token immediately
                kite_test = KiteClient(
                    self.config['api_key'],
                    self.config['api_secret'],
                    access_token
                )
                
                is_valid, result = kite_test.validate_token()
                
                if is_valid:
                    logger.info(f"✅ AUTHENTICATION SUCCESS!")
                    logger.info(f"✅ User: {result['user_name']}")
                    logger.info(f"✅ Token: {access_token[:20]}...")
                    logger.info(f"✅ Attempts: {self.auth_attempts}")
                    logger.info(f"✅ Duration: {(datetime.now() - start_time).total_seconds() / 60:.1f} minutes")
                    
                    # Initialize Kite components
                    self.kite = kite_test
                    self.data_manager = DataManager(self.kite, self.config)
                    self.pivot_calc = PivotCalculator(self.config)
                    self.signal_gen = SignalGenerator(self.config, self.pivot_calc)
                    self.position_mgr = PositionManager(self.config)
                    
                    self.authenticated = True
                    return True
                else:
                    logger.error(f"Token validation failed: {result}")
            
            # Check if we should stop trying
            now = datetime.now()
            
            # If past 8:45 AM, we need to hurry (only 30 min until trading)
            if now.hour >= 8 and now.minute >= 45:
                logger.warning("⚠️  URGENT: Past 8:45 AM, need authentication NOW!")
                retry_interval = 60  # Try every minute
            else:
                retry_interval = 180  # Try every 3 minutes
            
            # If past 9:00 AM, give up (not enough time for pre-market)
            if now.hour >= 9:
                logger.error("❌ Past 9:00 AM - Too late for today's trading")
                self.notifier.send_error_alert(
                    "Authentication Timeout",
                    "Failed to authenticate by 9:00 AM. System will not trade today."
                )
                return False
            
            logger.warning(f"Authentication attempt {self.auth_attempts} failed")
            logger.info(f"⏳ Waiting {retry_interval} seconds before retry...")
            logger.info(f"📱 Please check Telegram for authentication link")
            
            time.sleep(retry_interval)
        
        # Max attempts reached
        logger.error(f"❌ Authentication failed after {self.max_auth_attempts} attempts")
        self.notifier.send_error_alert(
            "Authentication Failed",
            f"Could not authenticate after {self.max_auth_attempts} attempts over {(datetime.now() - start_time).total_seconds() / 60:.1f} minutes"
        )
        return False
    
    def pre_market_setup(self):
        """Pre-market setup (8:45 - 9:15 AM)"""
        logger.info("=" * 80)
        logger.info("PRE-MARKET SETUP")
        logger.info("=" * 80)
        
        # Double-check authentication
        if not self.authenticated or not self.kite:
            logger.error("❌ Cannot run pre-market: Not authenticated!")
            return False
        
        # Validate token one more time before pre-market
        is_valid, result = self.kite.validate_token()
        if not is_valid:
            logger.error(f"❌ Token invalid at pre-market: {result}")
            self.notifier.send_error_alert(
                "Token Validation Failed",
                f"Token became invalid before pre-market: {result}"
            )
            return False
        
        logger.info(f"✅ Token validated successfully (User: {result['user_name']})")
        
        try:
            instrument = self.config['trading']['instrument']
            
            # 1. Get spot price
            spot_symbol = 'BSE:SENSEX' if instrument == 'SENSEX' else 'NSE:NIFTY 50'
            spot_price = self.kite.get_spot_price(spot_symbol)
            
            if not spot_price:
                logger.error("Failed to fetch spot price")
                return False
            
            logger.info(f"Spot Price: {spot_price}")
            
            # 2. Calculate ATM strike
            self.atm_strike = self.pivot_calc.get_atm_strike(spot_price)
            logger.info(f"ATM Strike: {self.atm_strike}")
            
            # 3. Get strikes to analyze
            strikes = self.pivot_calc.get_strikes_to_analyze(spot_price)
            logger.info(f"Analyzing {len(strikes)} strikes: {strikes[0]} to {strikes[-1]}")
            
            # 4. Calculate days to expiry
            days_to_expiry = self.data_manager.days_to_expiry()
            logger.info(f"Days to expiry: {days_to_expiry}")
            
            # 5. For each strike, calculate pivots
            for strike in strikes:
                self.pivot_data[strike] = {'CE': None, 'PE': None}
                self.market_structure[strike] = {'CE': None, 'PE': None}
                
                for option_type in ['CE', 'PE']:
                    symbol = self.data_manager.get_option_symbol(strike, option_type)
                    ohlc = self.data_manager.fetch_previous_day_ohlc(symbol)
                    
                    if not ohlc:
                        logger.warning(f"No OHLC data for {symbol}")
                        continue
                    
                    pivots = self.pivot_calc.calculate_pivots(
                        ohlc['high'],
                        ohlc['low'],
                        ohlc['close']
                    )
                    
                    structure = self.pivot_calc.determine_structure(pivots)
                    
                    self.pivot_data[strike][option_type] = pivots
                    self.market_structure[strike][option_type] = structure
                    
                    logger.info(
                        f"  {strike} {option_type}: "
                        f"Structure={structure}, "
                        f"PP={pivots['PP']:.2f}, "
                        f"R1={pivots['R1']:.2f}, "
                        f"R3={pivots['R3']:.2f}"
                    )
            
            logger.info("=" * 80)
            logger.info("PRE-MARKET SETUP COMPLETE")
            logger.info("=" * 80)
            
            # Send SINGLE pre-market message
            self.notifier.send_message(f"""
📊 <b>Pre-Market Setup Complete</b>

📅 Date: {datetime.now().strftime('%Y-%m-%d')}
🎯 Instrument: {instrument}
💹 Spot Price: {spot_price:.2f}
🎲 ATM Strike: {self.atm_strike}
📏 Strike Range: {strikes[0]} to {strikes[-1]}
📆 Days to Expiry: {days_to_expiry}

<b>✅ System Ready for Trading</b>
Trading starts at 9:15 AM

Monitoring for entry signals...
            """)
            
            return True
            
        except Exception as e:
            logger.error(f"Pre-market setup failed: {e}", exc_info=True)
            self.notifier.send_error_alert("Pre-Market Setup Error", str(e))
            return False
    
    def trading_loop(self):
        """Main trading loop (9:15 AM - 3:15 PM)"""
        logger.info("=" * 80)
        logger.info("STARTING TRADING LOOP")
        logger.info("=" * 80)
        
        cycle_count = 0
        
        while self.running:
            try:
                # Check if still trading hours
                if not self.trading_hours.is_market_open():
                    logger.info("Market closed. Exiting trading loop.")
                    break
                
                cycle_count += 1
                current_time = datetime.now()
                logger.info(f"\n--- Cycle {cycle_count} @ {current_time.strftime('%H:%M:%S')} ---")
                
                # Reload control state
                self.load_control_state()
                
                # Check panic mode
                if self.control['panic_mode']:
                    logger.warning("🚨 PANIC MODE - Force closing all positions")
                    if self.position_mgr.has_position():
                        symbol = self.position_mgr.position.symbol
                        ltp = self.data_manager.get_ltp(symbol)
                        if ltp:
                            trade_result = self.position_mgr.close_position(ltp, 'PANIC', False)
                            self.database.log_trade(trade_result.to_dict())
                            self.notifier.send_exit_signal(trade_result)
                    logger.info("All positions closed. Exiting trading loop.")
                    break
                
                # Trading logic here (simplified for now)
                logger.info("Monitoring... (trading logic placeholder)")
                
                # Sleep for 3 minutes
                logger.info("Sleeping for 3 minutes...")
                time.sleep(180)
                
            except KeyboardInterrupt:
                logger.info("Trading loop interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                self.notifier.send_error_alert("Trading Loop Error", str(e))
                time.sleep(60)
        
        logger.info("=" * 80)
        logger.info("TRADING LOOP ENDED")
        logger.info("=" * 80)
    
    def end_of_day_cleanup(self):
        """End-of-day cleanup"""
        logger.info("=" * 80)
        logger.info("END-OF-DAY CLEANUP")
        logger.info("=" * 80)
        
        try:
            # Force exit any open position
            if self.position_mgr and self.position_mgr.has_position():
                logger.warning("Force closing open position at EOD")
                symbol = self.position_mgr.position.symbol
                exit_price = self.data_manager.get_ltp(symbol)
                
                if not exit_price:
                    exit_price = self.position_mgr.position.entry_price
                    logger.warning("Could not fetch LTP, using entry price")
                
                trade_result = self.position_mgr.close_position(exit_price, 'EOD', False)
                self.database.log_trade(trade_result.to_dict())
                self.notifier.send_exit_signal(trade_result)
                logger.info(f"EOD position closed: P&L = ₹{trade_result.pnl_rupees:+.2f}")
            
            # Generate daily summary
            summary = self.database.generate_daily_summary()
            
            if summary.get('total_trades', 0) > 0:
                self.notifier.send_daily_summary(summary)
                logger.info(f"Daily Summary: {summary['total_trades']} trades, P&L: ₹{summary.get('gross_pnl', 0):+.2f}")
            else:
                logger.info("📊 No trades executed today.")
            
            # Data cleanup
            if self.data_manager:
                self.data_manager.cleanup_cache()
            
            # IMPORTANT: Delete token file at EOD
            token_file = self.config['data']['access_token_file']
            if os.path.exists(token_file):
                logger.info("Deleting token file (will re-authenticate tomorrow)")
                os.remove(token_file)
            
            logger.info("=" * 80)
            logger.info("EOD CLEANUP COMPLETE")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"EOD cleanup error: {e}", exc_info=True)
    
    def shutdown(self, signum=None, frame=None):
        """Graceful shutdown handler"""
        logger.info("Shutdown signal received")
        self.running = False
    
    def run(self):
        """
        Main run method - FIXED V2
        
        CRITICAL CHANGES:
        1. Always delete old tokens at startup
        2. Wait for authentication with retries
        3. Validate token before pre-market
        4. Delete token at EOD (force fresh auth tomorrow)
        """
        try:
            # Setup signal handlers
            signal.signal(signal.SIGINT, self.shutdown)
            signal.signal(signal.SIGTERM, self.shutdown)
            
            logger.info("=" * 80)
            logger.info("TRADING SYSTEM STARTED")
            logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
            logger.info("=" * 80)
            
            # STEP 1: AUTHENTICATE (with retries until 9:00 AM)
            logger.info("\n🔐 STEP 1: AUTHENTICATION")
            logger.info("Waiting for authentication...")
            
            if not self.wait_for_authentication():
                logger.error("❌ Authentication failed. Cannot proceed.")
                return
            
            # Send startup notification ONCE after successful auth
            startup_msg = f"""🚀 <b>TRADING SYSTEM AUTHENTICATED</b>

📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}

✅ <b>Status:</b>
- Authentication: ✅ Complete
- Attempts: {self.auth_attempts}
- System: 🟢 Running
- Database: ✅ Connected

⏰ <b>Schedule:</b>
- Pre-market: 8:45 AM
- Trading: 9:15 AM - 3:15 PM
- EOD Summary: 3:15 PM

🔔 <b>Next Steps:</b>
{"- Waiting for 8:45 AM for pre-market setup" if datetime.now().hour < 8 or (datetime.now().hour == 8 and datetime.now().minute < 45) else "- Running pre-market setup NOW"}

📊 System ready for trading!
"""
            self.notifier.send_message(startup_msg)
            
            # Main scheduling loop
            pre_market_done = False
            trading_done = False
            
            while self.running:
                now = datetime.now()
                
                # Check if trading day
                if not self.trading_hours.is_trading_day():
                    logger.info(f"Not a trading day. Sleeping until next trading day...")
                    tomorrow_8am = datetime.combine(
                        now.date() + timedelta(days=1),
                        dt_time(8, 0)
                    )
                    sleep_seconds = (tomorrow_8am - now).total_seconds()
                    logger.info(f"Sleeping {sleep_seconds/3600:.1f} hours")
                    time.sleep(min(sleep_seconds, 3600))
                    continue
                
                # STEP 2: PRE-MARKET SETUP (8:45 AM - 9:15 AM)
                if not pre_market_done and now.hour >= 8 and now.minute >= 45 and now.hour < 10:
                    logger.info("\n📊 STEP 2: PRE-MARKET SETUP")
                    if self.pre_market_setup():
                        pre_market_done = True
                        logger.info("✅ Pre-market setup completed")
                    else:
                        logger.error("❌ Pre-market setup failed, retrying in 2 minutes...")
                        time.sleep(120)
                    continue
                
                # STEP 3: TRADING LOOP (9:15 AM - 3:15 PM)
                if self.trading_hours.is_market_open() and not trading_done:
                    if not pre_market_done:
                        logger.warning("Market open but pre-market not done! Running now...")
                        if self.pre_market_setup():
                            pre_market_done = True
                    
                    logger.info("\n📈 STEP 3: TRADING LOOP")
                    self.trading_loop()
                    trading_done = True
                    
                    # STEP 4: EOD CLEANUP
                    logger.info("\n🌅 STEP 4: EOD CLEANUP")
                    self.end_of_day_cleanup()
                    
                    # Calculate sleep until tomorrow 8 AM
                    tomorrow_8am = datetime.combine(
                        now.date() + timedelta(days=1),
                        dt_time(8, 0)
                    )
                    sleep_seconds = (tomorrow_8am - now).total_seconds()
                    
                    logger.info("=" * 80)
                    logger.info(f"📅 Trading day complete!")
                    logger.info(f"🌙 Sleeping until {tomorrow_8am.strftime('%Y-%m-%d %H:%M')}")
                    logger.info("=" * 80)
                    
                    # Sleep until tomorrow
                    while sleep_seconds > 0 and self.running:
                        chunk = min(3600, sleep_seconds)
                        time.sleep(chunk)
                        sleep_seconds -= chunk
                    
                    # Reset for next day
                    pre_market_done = False
                    trading_done = False
                    self.authenticated = False
                    self.auth_attempts = 0
                    
                # Before pre-market
                elif now.hour < 8 or (now.hour == 8 and now.minute < 45):
                    mins_to_premarket = ((8 * 60 + 45) - (now.hour * 60 + now.minute))
                    logger.info(f"Before pre-market ({mins_to_premarket} mins). Waiting...")
                    time.sleep(min(300, mins_to_premarket * 60))
                
                # After market
                else:
                    logger.info(f"After market hours. Waiting...")
                    time.sleep(600)
                
        except KeyboardInterrupt:
            logger.info("System stopped by user")
            self.shutdown()
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            self.notifier.send_message(f"❌ Fatal Error: {str(e)}")
            raise


def main():
    """Main entry point"""
    logger.info("Starting Pivot Trading System...")
    
    try:
        system = PivotTradingSystem()
        system.run()
    except Exception as e:
        logger.error(f"System startup failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
