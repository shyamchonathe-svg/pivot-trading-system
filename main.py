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
from datetime import datetime, timedelta
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
        
        logger.info("System components initialized")
    
        
        # Load trading control state
        self.control_file = 'data/trading_control.json'
        self.load_control_state()
    def load_config(self, config_path):
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except Exception as e:
    
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
            import os
            os.makedirs('data', exist_ok=True)
            with open(self.control_file, 'w') as f:
                json.dump(self.control, f, indent=2)
        
        logger.info(f"Control state: trading_enabled={self.control['trading_enabled']}, panic_mode={self.control['panic_mode']}")
    
            logger.error(f"Failed to load config: {e}")
            sys.exit(1)
    
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
        """
        Pre-market setup (8:45 - 9:15 AM)
        - Fetch spot price
        - Calculate ATM strike
        - Fetch previous day OHLC for all strikes
        - Calculate pivots
        - Determine market structure
        """
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
    
    def analyze_candle(self, strike, option_type):
        """
        Analyze current candle for entry/exit signals
        
        Args:
            strike: Strike price
            option_type: 'CE' or 'PE'
        
        Returns:
            Signal object or None
        """
        try:
            # Get symbol
            symbol = self.data_manager.get_option_symbol(strike, option_type)
            
            # Fetch current candle
            current_candle = self.data_manager.fetch_current_candle(symbol)
            if not current_candle:
                return None
            
            # Get recent candles for percentile calculation
            recent_candles = self.data_manager.get_recent_candles(symbol, 20)
            if len(recent_candles) < 10:
                logger.warning(f"Not enough historical candles for {symbol}")
                return None
            
            # Get pivots and structure
            pivots = self.pivot_data.get(strike, {}).get(option_type)
            structure = self.market_structure.get(strike, {}).get(option_type)
            
            if not pivots or not structure:
                return None
            
            # Check for entry signal (if no position)
            if not self.position_mgr.has_position():
                signal = self.signal_gen.generate_entry_signal(
                    current_candle,
                    recent_candles,
                    pivots,
                    structure,
                    symbol,
                    strike,
                    option_type
                )
                
                if signal:
                    logger.info(f"✅ ENTRY SIGNAL: {symbol} Scenario {signal.scenario}")
                    
                    # Log signal to database
                    signal_data = {
                        'symbol': symbol,
                        'strike': strike,
                        'option_type': option_type,
                        'signal_type': 'ENTRY',
                        'scenario': signal.scenario,
                        'structure': structure,
                        'candle_open': current_candle['open'],
                        'candle_high': current_candle['high'],
                        'candle_low': current_candle['low'],
                        'candle_close': current_candle['close'],
                        'candle_size_pct': signal.candle_data['size_percent'],
                        'is_significant': True,
                        'pivot_pp': pivots['PP'],
                        'pivot_r1': pivots['R1'],
                        'pivot_r2': pivots['R2'],
                        'pivot_r3': pivots['R3'],
                        'action_taken': True,
                        'reason': signal.reason
                    }
                    self.database.log_signal(signal_data)
                
                return signal
            
            else:
                # Check for exit signal (if position exists)
                should_exit, exit_reason, exit_price = self.signal_gen.check_exit_conditions(
                    self.position_mgr.position,
                    current_candle,
                    self.candle_count
                )
                
                if should_exit:
                    logger.info(f"🚪 EXIT SIGNAL: {exit_reason} @ {exit_price:.2f}")
                    return (True, exit_reason, exit_price)
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing candle for {strike} {option_type}: {e}")
            return None
    
    def trading_loop(self):
        """
        Main trading loop (9:15 AM - 3:15 PM)
        Runs every 3 minutes
        """
        logger.info("=" * 80)
        logger.info("STARTING TRADING LOOP")
        logger.info("=" * 80)
        
        while self.running:
            try:
                # Check if still trading hours
                if not self.trading_hours.is_market_open():
                    logger.info("Market closed. Exiting trading loop.")
                    break
                
                current_time = datetime.now()
                logger.info(f"\n--- Cycle {self.candle_count + 1} @ {current_time.strftime('%H:%M:%S')} ---")
                
                # Increment candle count if position exists
                if self.position_mgr.has_position():
                    self.candle_count += 1
                    self.position_mgr.update_position(self.candle_count)
                    logger.info(f"Position open: {self.candle_count} candles held")
                
                # Analyze ATM strike (focus on current ATM)
                for option_type in ['CE', 'PE']:
                    result = self.analyze_candle(self.atm_strike, option_type)
                    
                    if result:
                        # Entry signal
                        if isinstance(result, object) and hasattr(result, 'signal_type'):
                            if result.signal_type == 'ENTRY':
                                # Check if can enter
                                if self.position_mgr.can_re_enter():
                                    # Open position
                                    is_re_entry = self.position_mgr.stop_loss_count > 0
                                    position = self.position_mgr.open_position(result, is_re_entry)
                                    
                                    # Send entry alert
                                    self.notifier.send_entry_signal(result, position)
                                    
                                    # Reset candle count
                                    self.candle_count = 0
                                    
                                    logger.info(f"Position opened: {position.trade_id}")
                                else:
                                    logger.warning("Re-entry limit reached")
                        
                        # Exit signal
                        elif isinstance(result, tuple) and result[0] == True:
                            should_exit, exit_reason, exit_price = result
                            
                            # Close position
                            is_re_entry = self.position_mgr.position.re_entry if hasattr(self.position_mgr.position, 're_entry') else False
                            trade_result = self.position_mgr.close_position(
                                exit_price,
                                exit_reason,
                                is_re_entry
                            )
                            
                            # Log trade to database
                            self.database.log_trade(trade_result.to_dict())
                            
                            # Send exit alert
                            self.notifier.send_exit_signal(trade_result)
                            
                            # Reset candle count
                            self.candle_count = 0
                            
                            logger.info(f"Position closed: P&L = ₹{trade_result.pnl_rupees:+.2f}")
                
                # Sleep for 3 minutes
                logger.info("Sleeping for 3 minutes...")
                time.sleep(180)
                
            except KeyboardInterrupt:
                logger.info("Trading loop interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                self.notifier.send_error_alert("Trading Loop Error", str(e))
                time.sleep(60)  # Wait 1 minute before retry
        
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
            if self.position_mgr.has_position():
                logger.warning("Force closing open position at EOD")
                
                # Get current price
                symbol = self.position_mgr.position.symbol
                exit_price = self.data_manager.get_ltp(symbol)
                
                if not exit_price:
                    exit_price = self.position_mgr.position.entry_price
                    logger.warning("Could not fetch LTP, using entry price")
                
                # Close position
                trade_result = self.position_mgr.close_position(exit_price, 'EOD', False)
                
                # Log trade
                self.database.log_trade(trade_result.to_dict())
                
                # Send alert
                self.notifier.send_exit_signal(trade_result)
                
                logger.info(f"EOD position closed: P&L = ₹{trade_result.pnl_rupees:+.2f}")
            
            # Generate daily summary
            summary = self.database.generate_daily_summary()
            
            if summary.get('total_trades', 0) > 0:
                self.notifier.send_daily_summary(summary)
                logger.info(f"Daily Summary: {summary['total_trades']} trades, P&L: ₹{summary['gross_pnl']:+.2f}")
            else:
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
            # Reload control state each cycle
            self.load_control_state()
            
            # Check panic mode
            if self.control["panic_mode"]:
                logger.warning("🚨 PANIC MODE - Force closing all positions")
                for strike in self.pivot_data.keys():
                    for option_type in ["CE", "PE"]:
                        position = self.position_manager.get_position(strike, option_type)
                        if position and position["status"] == "OPEN":
                            symbol = self.data_manager.get_option_symbol(strike, option_type, self.expiry_date)
                            ltp = self.data_manager.get_ltp(symbol)
                            if ltp:
                                self.position_manager.close_position(strike, option_type, ltp, "PANIC")
                                self.notifier.send_exit_signal(symbol, position["entry_price"], ltp, ltp - position["entry_price"], "PANIC")
                logger.info("All positions closed. Exiting trading loop.")
                break
            
                now = datetime.now()
                current_time = now.time()
                
                # Check if trading day
                if not self.trading_hours.is_trading_day():
                    if now.hour == 8 and now.minute == 0:  # Log once at 8 AM
                        logger.info("Not a trading day (weekend/holiday)")
                    # Sleep for 1 hour
                    time.sleep(3600)
                    continue
                
                # Reset flags for new day
                if now.hour == 0 and now.minute < 5:
                    pre_market_done = False
                    trading_done = False
                    logger.info("New day - resetting flags")
                    time.sleep(300)  # Sleep 5 min to avoid multiple resets
                    continue
                
                # Pre-market setup (8:45 AM - 9:00 AM)
                if not pre_market_done and 8 <= now.hour < 9:
                    if now.hour == 8 and now.minute >= 45:
                        logger.info("Starting pre-market setup...")
                        
                        # Authenticate
                        if not self.authenticate():
                            logger.error("Authentication failed. Retrying in 5 minutes...")
                            time.sleep(300)
                            continue
                        
                        # Pre-market setup
                        if self.pre_market_setup():
                            pre_market_done = True
                            logger.info("Pre-market setup completed")
                        else:
                            logger.error("Pre-market setup failed. Retrying in 5 minutes...")
                            time.sleep(300)
                            continue
                    else:
                        # Before 8:45 AM
                        logger.info(f"Waiting for pre-market time (8:45 AM). Current: {now.strftime('%H:%M')}")
                        time.sleep(600)  # Sleep 10 minutes
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
                        
                        # After trading loop ends, run EOD cleanup
                        logger.info("Trading hours ended. Running EOD cleanup...")
                        self.end_of_day_cleanup()
                
                # After market close (after 3:15 PM)
                elif now.hour >= 15 and now.minute >= 15:
                    if not trading_done and pre_market_done:
                        # Market closed early or we missed it
                        logger.info("Market closed. Running EOD cleanup...")
                        self.end_of_day_cleanup()
                        trading_done = True
                    
                    # Calculate sleep time until next day 8:00 AM
                    tomorrow_8am = datetime.combine(
                        now.date() + timedelta(days=1),
                        datetime.strptime("08:00", "%H:%M").time()
                    )
                    sleep_seconds = (tomorrow_8am - now).total_seconds()
                    
                    logger.info(f"📅 Market closed. Sleeping until {tomorrow_8am.strftime('%Y-%m-%d %H:%M')} ({sleep_seconds/3600:.1f} hours)")
                    logger.info("🌙 System in idle mode. No messages until tomorrow.")
                    
                    # Sleep until tomorrow
                    time.sleep(sleep_seconds)
                
                else:
                    # Before market hours (before 9:15 AM, after 8:45 AM)
                    logger.info(f"Before market hours. Current: {now.strftime('%H:%M')}. Waiting...")
                    time.sleep(300)  # Check every 5 minutes
                
        except KeyboardInterrupt:
            logger.info("System stopped by user")
            self.shutdown()
        except Exception as e:
            logger.error(f"Fatal error in run loop: {e}", exc_info=True)
            self.notifier.send_message(f"❌ Fatal Error: {str(e)}")
            raise
                logger.error("Pre-market setup failed. Exiting.")
                return
            
            # Wait for market open (9:15 AM)
            market_open_time = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
            now = datetime.now()
            
            if now < market_open_time:
                wait_seconds = (market_open_time - now).total_seconds()
                logger.info(f"Waiting {wait_seconds/60:.1f} minutes until market open (9:15 AM)...")
                time.sleep(wait_seconds)
            
            # Trading loop
            self.trading_loop()
            
            # End-of-day cleanup
            self.end_of_day_cleanup()
            
            logger.info("System shutdown complete")
            
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            self.notifier.send_error_alert("System Fatal Error", str(e))
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
