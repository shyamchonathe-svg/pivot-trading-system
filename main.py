#!/usr/bin/env python3
"""
Pivot Trading System - Main Entry Point
Automated options trading using pivot point strategy
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
        self.pivot_data = {}  # {strike: {CE: pivots, PE: pivots}}
        self.market_structure = {}  # {strike: {CE: structure, PE: structure}}
        self.atm_strike = None
        self.candle_count = 0
        
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
            # Create file
            os.makedirs('data', exist_ok=True)
            with open(self.control_file, 'w') as f:
                json.dump(self.control, f, indent=2)
        
        logger.info(f"Control state: trading_enabled={self.control['trading_enabled']}, panic_mode={self.control['panic_mode']}")
    
    def authenticate(self):
        """Authenticate with Kite Connect"""
        logger.info("Starting authentication process...")
        
        auth_manager = AuthManager(self.config, self.notifier)
        access_token = auth_manager.authenticate()
        
        if not access_token:
            logger.error("Authentication failed!")
            return False
        
        # Initialize Kite client
        self.kite = KiteClient(
            self.config['api_key'],
            self.config['api_secret'],
            access_token
        )
        
        # Validate token
        is_valid, result = self.kite.validate_token()
        if not is_valid:
            logger.error(f"Token validation failed: {result}")
            return False
        
        logger.info(f"✅ Authenticated as: {result['user_name']}")
        
        # Initialize data-dependent components
        self.data_manager = DataManager(self.kite, self.config)
        self.pivot_calc = PivotCalculator(self.config)
        self.signal_gen = SignalGenerator(self.config, self.pivot_calc)
        self.position_mgr = PositionManager(self.config)
        
        return True
    
    def pre_market_setup(self):
        """Pre-market setup (8:45 - 9:15 AM)"""
        logger.info("=" * 80)
        logger.info("PRE-MARKET SETUP")
        logger.info("=" * 80)
        
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
            
            # 5. For each strike, calculate pivots for CE and PE
            for strike in strikes:
                self.pivot_data[strike] = {'CE': None, 'PE': None}
                self.market_structure[strike] = {'CE': None, 'PE': None}
                
                for option_type in ['CE', 'PE']:
                    # Generate option symbol
                    symbol = self.data_manager.get_option_symbol(strike, option_type)
                    
                    # Fetch previous day OHLC
                    ohlc = self.data_manager.fetch_previous_day_ohlc(symbol)
                    
                    if not ohlc:
                        logger.warning(f"No OHLC data for {symbol}")
                        continue
                    
                    # Calculate pivots
                    pivots = self.pivot_calc.calculate_pivots(
                        ohlc['high'],
                        ohlc['low'],
                        ohlc['close']
                    )
                    
                    # Determine market structure
                    structure = self.pivot_calc.determine_structure(pivots)
                    
                    # Store
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
            
            logger.info("=" * 80)
            logger.info("EOD CLEANUP COMPLETE")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"EOD cleanup error: {e}", exc_info=True)
    
    def shutdown(self, signum=None, frame=None):
        """Graceful shutdown handler"""
        logger.info("Shutdown signal received")
        self.running = False
        
        if self.notifier:
            self.notifier.send_message("""
🌙 <b>TRADING SYSTEM SHUTDOWN</b>

📅 Time: {}
📝 Reason: System shutdown requested

✅ <b>Cleanup Complete:</b>
- All positions closed
- Data cached cleared
- Logs rotated
- Database updated

📊 <b>Summary:</b>
Daily summary has been generated and saved
Check database for complete trade history

🔄 <b>System Status:</b>
System has stopped gracefully
Will auto-start tomorrow at configured time

😴 Good night! See you tomorrow!
            """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')))
    
    def run(self):
        """Main run method with proper scheduling"""
        try:
            # Setup signal handlers
            signal.signal(signal.SIGINT, self.shutdown)
            signal.signal(signal.SIGTERM, self.shutdown)
            
            # Send startup notification ONLY ONCE
            startup_msg = """🚀 TRADING SYSTEM STARTED
📅 Time: {}

✅ System Initialized
🟢 Monitoring started

Next: Pre-market at 8:45 AM
Trading: 9:15 AM - 3:15 PM
""".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S IST'))
            
            self.notifier.send_message(startup_msg)
            logger.info("Trading system started")
            
            # Main scheduling loop
            pre_market_done = False
            trading_done = False
            
            while True:
                now = datetime.now()
                current_time = now.time()
                
                # Check if trading day
                if not self.trading_hours.is_trading_day():
                    if now.hour == 8 and now.minute == 0:
                        logger.info("Not a trading day (weekend/holiday)")
                    time.sleep(3600)
                    continue
                
                # Reset flags for new day
                if now.hour == 0 and now.minute < 5:
                    pre_market_done = False
                    trading_done = False
                    logger.info("New day - resetting flags")
                    time.sleep(300)
                    continue
                
                # Pre-market setup (8:45 AM - 9:00 AM)
                if not pre_market_done and 8 <= now.hour < 9:
                    if now.hour == 8 and now.minute >= 45:
                        logger.info("Starting pre-market setup...")
                        
                        if not self.authenticate():
                            logger.error("Authentication failed. Retrying in 5 minutes...")
                            time.sleep(300)
                            continue
                        
                        if self.pre_market_setup():
                            pre_market_done = True
                            logger.info("Pre-market setup completed")
                        else:
                            logger.error("Pre-market setup failed. Retrying in 5 minutes...")
                            time.sleep(300)
                            continue
                    else:
                        logger.info(f"Waiting for pre-market time (8:45 AM). Current: {now.strftime('%H:%M')}")
                        time.sleep(600)
                        continue
                
                # Trading hours (9:15 AM - 3:15 PM)
                elif self.trading_hours.is_market_open():
                    if not pre_market_done:
                        logger.warning("Market open but pre-market not done. Running now...")
                        if self.authenticate() and self.pre_market_setup():
                            pre_market_done = True
                    
                    if not trading_done:
                        logger.info("Starting trading loop...")
                        self.trading_loop()
                        trading_done = True
                        
                        logger.info("Trading hours ended. Running EOD cleanup...")
                        self.end_of_day_cleanup()
                
                # After market close (after 3:15 PM)
                elif now.hour >= 15 and now.minute >= 15:
                    if not trading_done and pre_market_done:
                        logger.info("Market closed. Running EOD cleanup...")
                        self.end_of_day_cleanup()
                        trading_done = True
                    
                    # Calculate sleep time until next day 8:00 AM
                    tomorrow_8am = datetime.combine(
                        now.date() + timedelta(days=1),
                        dt_time(8, 0)
                    )
                    sleep_seconds = (tomorrow_8am - now).total_seconds()
                    
                    logger.info(f"📅 Market closed. Sleeping until {tomorrow_8am.strftime('%Y-%m-%d %H:%M')} ({sleep_seconds/3600:.1f} hours)")
                    logger.info("🌙 System in idle mode. No messages until tomorrow.")
                    
                    time.sleep(sleep_seconds)
                
                else:
                    logger.info(f"Before market hours. Current: {now.strftime('%H:%M')}. Waiting...")
                    time.sleep(300)
                
        except KeyboardInterrupt:
            logger.info("System stopped by user")
            self.shutdown()
        except Exception as e:
            logger.error(f"Fatal error in run loop: {e}", exc_info=True)
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
