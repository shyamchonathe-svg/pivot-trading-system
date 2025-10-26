"""
Database Module
SQLite operations for trade logging and analytics
"""

import sqlite3
import logging
from datetime import datetime, date
from typing import Dict, List, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path='data/trading.db'):
        """
        Initialize database connection
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def init_database(self):
        """Create database tables if they don't exist"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Trades table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    date DATE NOT NULL,
                    instrument TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    strike INTEGER NOT NULL,
                    option_type TEXT NOT NULL,
                    
                    entry_time TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    entry_candle_low REAL NOT NULL,
                    
                    exit_time TEXT,
                    exit_price REAL,
                    exit_reason TEXT,
                    
                    scenario INTEGER NOT NULL,
                    structure TEXT NOT NULL,
                    first_candle_entry BOOLEAN NOT NULL,
                    
                    target_price REAL NOT NULL,
                    sl_price REAL NOT NULL,
                    candles_held INTEGER,
                    
                    pnl_points REAL,
                    pnl_rupees REAL,
                    lot_size INTEGER NOT NULL,
                    
                    re_entry BOOLEAN DEFAULT 0,
                    
                    pivot_pp REAL,
                    pivot_r1 REAL,
                    pivot_r2 REAL,
                    pivot_r3 REAL,
                    pivot_r4 REAL,
                    pivot_r5 REAL,
                    pivot_s1 REAL,
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Daily summary table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_summary (
                    date DATE PRIMARY KEY,
                    instrument TEXT NOT NULL,
                    
                    total_trades INTEGER NOT NULL,
                    wins INTEGER NOT NULL,
                    losses INTEGER NOT NULL,
                    win_rate REAL,
                    
                    gross_pnl REAL NOT NULL,
                    max_drawdown REAL,
                    
                    scenario_1_trades INTEGER DEFAULT 0,
                    scenario_2_trades INTEGER DEFAULT 0,
                    scenario_3_trades INTEGER DEFAULT 0,
                    
                    first_candle_entries INTEGER DEFAULT 0,
                    intraday_entries INTEGER DEFAULT 0,
                    
                    stop_losses INTEGER DEFAULT 0,
                    targets_hit INTEGER DEFAULT 0,
                    timeouts INTEGER DEFAULT 0,
                    eod_exits INTEGER DEFAULT 0,
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Signals log table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    time TEXT NOT NULL,
                    instrument TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    strike INTEGER NOT NULL,
                    option_type TEXT NOT NULL,
                    
                    signal_type TEXT NOT NULL,
                    scenario INTEGER,
                    structure TEXT,
                    
                    candle_open REAL,
                    candle_high REAL,
                    candle_low REAL,
                    candle_close REAL,
                    candle_size_pct REAL,
                    is_significant BOOLEAN,
                    
                    pivot_pp REAL,
                    pivot_r1 REAL,
                    pivot_r2 REAL,
                    pivot_r3 REAL,
                    
                    action_taken BOOLEAN DEFAULT 0,
                    reason TEXT,
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_scenario ON trades(scenario)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_date ON signals(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol)')
            
            logger.info("Database initialized successfully")
    
    def log_trade(self, trade_result: Dict) -> bool:
        """
        Log completed trade to database
        
        Args:
            trade_result: Dictionary from TradeResult.to_dict()
        
        Returns:
            True if successful
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO trades (
                        trade_id, date, instrument, symbol, strike, option_type,
                        entry_time, entry_price, entry_candle_low,
                        exit_time, exit_price, exit_reason,
                        scenario, structure, first_candle_entry,
                        target_price, sl_price, candles_held,
                        pnl_points, pnl_rupees, lot_size, re_entry,
                        pivot_pp, pivot_r1, pivot_r2, pivot_r3, pivot_r4, pivot_r5, pivot_s1
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trade_result['trade_id'],
                    datetime.now().date(),
                    trade_result.get('instrument', 'SENSEX'),
                    trade_result['symbol'],
                    trade_result['strike'],
                    trade_result['option_type'],
                    trade_result['entry_time'],
                    trade_result['entry_price'],
                    trade_result['entry_candle_low'],
                    trade_result['exit_time'],
                    trade_result['exit_price'],
                    trade_result['exit_reason'],
                    trade_result['scenario'],
                    trade_result['structure'],
                    trade_result['first_candle_entry'],
                    trade_result['target_price'],
                    trade_result['sl_price'],
                    trade_result['candles_held'],
                    trade_result['pnl_points'],
                    trade_result['pnl_rupees'],
                    trade_result['lot_size'],
                    trade_result['re_entry'],
                    trade_result['pivot_pp'],
                    trade_result['pivot_r1'],
                    trade_result['pivot_r2'],
                    trade_result['pivot_r3'],
                    trade_result['pivot_r4'],
                    trade_result['pivot_r5'],
                    trade_result['pivot_s1']
                ))
                
                logger.info(f"Trade logged: {trade_result['trade_id']}")
                return True
                
        except Exception as e:
            logger.error(f"Error logging trade: {e}")
            return False
    
    def log_signal(self, signal_data: Dict) -> bool:
        """
        Log entry/exit signal to database
        
        Args:
            signal_data: Dictionary with signal details
        
        Returns:
            True if successful
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO signals (
                        date, time, instrument, symbol, strike, option_type,
                        signal_type, scenario, structure,
                        candle_open, candle_high, candle_low, candle_close,
                        candle_size_pct, is_significant,
                        pivot_pp, pivot_r1, pivot_r2, pivot_r3,
                        action_taken, reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    signal_data.get('date', datetime.now().date()),
                    signal_data.get('time', datetime.now().strftime('%H:%M:%S')),
                    signal_data.get('instrument', 'SENSEX'),
                    signal_data['symbol'],
                    signal_data['strike'],
                    signal_data['option_type'],
                    signal_data['signal_type'],
                    signal_data.get('scenario'),
                    signal_data.get('structure'),
                    signal_data.get('candle_open'),
                    signal_data.get('candle_high'),
                    signal_data.get('candle_low'),
                    signal_data.get('candle_close'),
                    signal_data.get('candle_size_pct'),
                    signal_data.get('is_significant'),
                    signal_data.get('pivot_pp'),
                    signal_data.get('pivot_r1'),
                    signal_data.get('pivot_r2'),
                    signal_data.get('pivot_r3'),
                    signal_data.get('action_taken', False),
                    signal_data.get('reason', '')
                ))
                
                return True
                
        except Exception as e:
            logger.error(f"Error logging signal: {e}")
            return False
    
    def get_daily_trades(self, trade_date: Optional[date] = None) -> List[Dict]:
        """
        Get all trades for a specific date
        
        Args:
            trade_date: Date to query (default: today)
        
        Returns:
            List of trade dictionaries
        """
        if trade_date is None:
            trade_date = datetime.now().date()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT * FROM trades WHERE date = ? ORDER BY entry_time',
                    (trade_date,)
                )
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error fetching daily trades: {e}")
            return []
    
    def generate_daily_summary(self, trade_date: Optional[date] = None) -> Dict:
        """
        Generate and save daily summary
        
        Args:
            trade_date: Date to summarize (default: today)
        
        Returns:
            Summary dictionary
        """
        if trade_date is None:
            trade_date = datetime.now().date()
        
        try:
            trades = self.get_daily_trades(trade_date)
            
            if not trades:
                return {
                    'date': trade_date,
                    'total_trades': 0,
                    'message': 'No trades today'
                }
            
            # Calculate metrics
            total_trades = len(trades)
            wins = sum(1 for t in trades if t['pnl_points'] and t['pnl_points'] > 0)
            losses = total_trades - wins
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            
            gross_pnl = sum(t['pnl_rupees'] or 0 for t in trades)
            
            # Count by scenario
            scenario_1 = sum(1 for t in trades if t['scenario'] == 1)
            scenario_2 = sum(1 for t in trades if t['scenario'] == 2)
            scenario_3 = sum(1 for t in trades if t['scenario'] == 3)
            
            # Count entry types
            first_candle = sum(1 for t in trades if t['first_candle_entry'])
            intraday = total_trades - first_candle
            
            # Count exit reasons
            stop_losses = sum(1 for t in trades if t['exit_reason'] == 'STOP_LOSS')
            targets = sum(1 for t in trades if t['exit_reason'] == 'TARGET')
            timeouts = sum(1 for t in trades if t['exit_reason'] == '10_CANDLE_TIMEOUT')
            eod_exits = sum(1 for t in trades if t['exit_reason'] == 'EOD')
            
            # Max drawdown (simple calculation)
            cumulative_pnl = []
            running_pnl = 0
            for trade in trades:
                running_pnl += trade['pnl_rupees'] or 0
                cumulative_pnl.append(running_pnl)
            
            max_dd = 0
            if cumulative_pnl:
                peak = cumulative_pnl[0]
                for pnl in cumulative_pnl:
                    if pnl > peak:
                        peak = pnl
                    dd = peak - pnl
                    if dd > max_dd:
                        max_dd = dd
            
            summary = {
                'date': trade_date,
                'instrument': trades[0]['instrument'] if trades else 'SENSEX',
                'total_trades': total_trades,
                'wins': wins,
                'losses': losses,
                'win_rate': round(win_rate, 2),
                'gross_pnl': round(gross_pnl, 2),
                'max_drawdown': round(max_dd, 2),
                'scenario_1_trades': scenario_1,
                'scenario_2_trades': scenario_2,
                'scenario_3_trades': scenario_3,
                'first_candle_entries': first_candle,
                'intraday_entries': intraday,
                'stop_losses': stop_losses,
                'targets_hit': targets,
                'timeouts': timeouts,
                'eod_exits': eod_exits
            }
            
            # Save to database
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO daily_summary (
                        date, instrument, total_trades, wins, losses, win_rate,
                        gross_pnl, max_drawdown,
                        scenario_1_trades, scenario_2_trades, scenario_3_trades,
                        first_candle_entries, intraday_entries,
                        stop_losses, targets_hit, timeouts, eod_exits
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    summary['date'], summary['instrument'],
                    summary['total_trades'], summary['wins'], summary['losses'],
                    summary['win_rate'], summary['gross_pnl'], summary['max_drawdown'],
                    summary['scenario_1_trades'], summary['scenario_2_trades'],
                    summary['scenario_3_trades'], summary['first_candle_entries'],
                    summary['intraday_entries'], summary['stop_losses'],
                    summary['targets_hit'], summary['timeouts'], summary['eod_exits']
                ))
            
            logger.info(f"Daily summary generated for {trade_date}")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating daily summary: {e}")
            return {'error': str(e)}
    
    def get_monthly_stats(self, year: int, month: int) -> Dict:
        """Get monthly trading statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN pnl_points > 0 THEN 1 ELSE 0 END) as wins,
                        SUM(pnl_rupees) as total_pnl,
                        AVG(pnl_rupees) as avg_pnl,
                        MAX(pnl_rupees) as best_trade,
                        MIN(pnl_rupees) as worst_trade
                    FROM trades
                    WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
                ''', (str(year), f'{month:02d}'))
                
                row = cursor.fetchone()
                return dict(row) if row else {}
                
        except Exception as e:
            logger.error(f"Error fetching monthly stats: {e}")
            return {}


if __name__ == "__main__":
    # Test database operations
    logging.basicConfig(level=logging.INFO)
    
    db = Database('data/test_trading.db')
    
    # Test trade logging
    test_trade = {
        'trade_id': '20251025_001',
        'symbol': 'SENSEX2510280100CE',
        'strike': 80100,
        'option_type': 'CE',
        'entry_time': '09:18:00',
        'entry_price': 145.50,
        'entry_candle_low': 138.20,
        'exit_time': '09:45:00',
        'exit_price': 165.20,
        'exit_reason': 'TARGET',
        'scenario': 1,
        'structure': 'BULLISH',
        'first_candle_entry': True,
        'target_price': 175.00,
        'sl_price': 138.20,
        'candles_held': 9,
        'pnl_points': 19.70,
        'pnl_rupees': 197.00,
        'lot_size': 10,
        're_entry': False,
        'pivot_pp': 143.50,
        'pivot_r1': 146.00,
        'pivot_r2': 150.00,
        'pivot_r3': 175.00,
        'pivot_r4': 180.00,
        'pivot_r5': 185.00,
        'pivot_s1': 139.00
    }
    
    print("Testing trade logging...")
    db.log_trade(test_trade)
    
    print("\nFetching today's trades...")
    trades = db.get_daily_trades()
    print(f"Found {len(trades)} trades")
    
    print("\nGenerating daily summary...")
    summary = db.generate_daily_summary()
    print(f"Summary: {summary}")
    
    print("\n✅ Database tests complete")
