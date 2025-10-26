"""
Data Manager Module
Handles data fetching, caching, and processing
"""

import pandas as pd
from datetime import datetime, timedelta
from collections import deque


class DataManager:
    def __init__(self, kite_client, config):
        self.kite = kite_client
        self.config = config
        
        # In-memory cache for candles
        self.candle_cache = {}  # {symbol: deque of candles}
        self.max_cache_size = 50  # Keep last 50 candles
        
        # Cache for option symbols
        self.symbol_cache = {}  # {strike: {CE: symbol, PE: symbol}}
    
    def get_previous_trading_day(self, date=None):
        """
        Get previous trading day (skip weekends and holidays)
        
        Args:
            date: datetime.date object (default: today)
        
        Returns: datetime.date of previous trading day
        """
        if date is None:
            date = datetime.now().date()
        
        holidays = [
            datetime.strptime(h, '%Y-%m-%d').date() 
            for h in self.config['market']['holidays']
        ]
        
        prev = date - timedelta(days=1)
        
        # Skip weekends and holidays
        while prev.weekday() >= 5 or prev in holidays:
            prev -= timedelta(days=1)
        
        return prev
    
    def get_option_symbol(self, strike, option_type, expiry_date=None):
        """
        Generate option symbol
        Format: SENSEX<YYMMDD><STRIKE><CE/PE>
        Example: SENSEX2510280100CE
        
        Args:
            strike: Strike price (e.g., 80100)
            option_type: 'CE' or 'PE'
            expiry_date: datetime.date (default: next weekly expiry)
        
        Returns: Option symbol string
        """
        instrument = self.config['trading']['instrument']
        
        if expiry_date is None:
            expiry_date = self.get_next_expiry()
        
        # Format: YYMMDD
        date_str = expiry_date.strftime('%y%m%d')
        
        # Format strike (remove decimals, pad if needed)
        strike_str = f"{int(strike)}"
        
        symbol = f"{instrument}{date_str}{strike_str}{option_type}"
        
        return symbol
    
    def get_next_expiry(self, from_date=None):
        """
        Get next weekly expiry date
        Sensex: Thursday
        Nifty: Tuesday
        
        Returns: datetime.date
        """
        if from_date is None:
            from_date = datetime.now().date()
        
        instrument = self.config['trading']['instrument']
        
        # Determine expiry day of week
        if instrument == 'SENSEX':
            expiry_weekday = 3  # Thursday (0=Mon, 6=Sun)
        elif instrument == 'NIFTY':
            expiry_weekday = 1  # Tuesday
        else:
            raise ValueError(f"Unknown instrument: {instrument}")
        
        # Find next expiry
        days_ahead = expiry_weekday - from_date.weekday()
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        expiry = from_date + timedelta(days=days_ahead)
        
        # Check if it's a holiday, if yes move to previous day
        holidays = [
            datetime.strptime(h, '%Y-%m-%d').date() 
            for h in self.config['market']['holidays']
        ]
        
        while expiry in holidays:
            expiry -= timedelta(days=1)
        
        return expiry
    
    def days_to_expiry(self, from_date=None):
        """Calculate days remaining to expiry"""
        if from_date is None:
            from_date = datetime.now().date()
        
        expiry = self.get_next_expiry(from_date)
        return (expiry - from_date).days
    
    def fetch_previous_day_ohlc(self, symbol, date=None):
        """
        Fetch previous trading day's OHLC for option
        
        Args:
            symbol: Option symbol
            date: Date for which to fetch (default: today)
        
        Returns: dict with {high, low, close} or None if error
        """
        if date is None:
            date = datetime.now().date()
        
        prev_day = self.get_previous_trading_day(date)
        
        try:
            # Fetch day candle
            from_date = datetime.combine(prev_day, datetime.min.time())
            to_date = datetime.combine(prev_day, datetime.max.time())
            
            data = self.kite.get_historical_data(
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
                interval='day'
            )
            
            if not data or len(data) == 0:
                print(f"No data for {symbol} on {prev_day}")
                return None
            
            # Get last row (should be only row for daily)
            last_row = data[-1]
            
            return {
                'high': last_row['high'],
                'low': last_row['low'],
                'close': last_row['close'],
                'open': last_row['open'],
                'date': prev_day
            }
            
        except Exception as e:
            print(f"Error fetching OHLC for {symbol}: {e}")
            return None
    
    def fetch_current_candle(self, symbol):
        """
        Fetch latest 3-minute candle
        
        Returns: dict with {open, high, low, close, timestamp}
        """
        try:
            # Fetch last 2 candles to get the latest closed one
            to_date = datetime.now()
            from_date = to_date - timedelta(minutes=10)
            
            data = self.kite.get_historical_data(
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
                interval='3minute'
            )
            
            if not data or len(data) == 0:
                return None
            
            # Get last candle
            last_candle = data[-1]
            
            candle = {
                'open': last_candle['open'],
                'high': last_candle['high'],
                'low': last_candle['low'],
                'close': last_candle['close'],
                'timestamp': last_candle['date'],
                'volume': last_candle.get('volume', 0)
            }
            
            # Add to cache
            self._add_to_cache(symbol, candle)
            
            return candle
            
        except Exception as e:
            print(f"Error fetching current candle for {symbol}: {e}")
            return None
    
    def get_recent_candles(self, symbol, count=20):
        """
        Get recent candles for percentile calculation
        
        Strategy:
        - If < 20 candles today: Use (previous day's last candles + today's)
        - Always maintain rolling window of 20 candles
        
        Args:
            symbol: Option symbol
            count: Number of candles to return (default: 20)
        
        Returns: List of candle dicts, oldest first
        """
        # Check cache first
        if symbol in self.candle_cache:
            cached = list(self.candle_cache[symbol])
            if len(cached) >= count:
                return cached[-count:]
        
        # Fetch from API
        try:
            today = datetime.now().date()
            from_date = datetime.combine(today, datetime.min.time())
            to_date = datetime.now()
            
            data = self.kite.get_historical_data(
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
                interval='3minute'
            )
            
            candles = [
                {
                    'open': c['open'],
                    'high': c['high'],
                    'low': c['low'],
                    'close': c['close'],
                    'timestamp': c['date']
                }
                for c in data
            ]
            
            # If not enough candles today, fetch from previous day
            if len(candles) < count:
                prev_day = self.get_previous_trading_day(today)
                prev_from = datetime.combine(prev_day, datetime.min.time())
                prev_to = datetime.combine(prev_day, datetime.max.time())
                
                prev_data = self.kite.get_historical_data(
                    symbol=symbol,
                    from_date=prev_from,
                    to_date=prev_to,
                    interval='3minute'
                )
                
                prev_candles = [
                    {
                        'open': c['open'],
                        'high': c['high'],
                        'low': c['low'],
                        'close': c['close'],
                        'timestamp': c['date']
                    }
                    for c in prev_data
                ]
                
                # Combine: last N from prev day + today's candles
                needed_from_prev = count - len(candles)
                combined = prev_candles[-needed_from_prev:] + candles
                candles = combined
            
            # Update cache
            self.candle_cache[symbol] = deque(candles, maxlen=self.max_cache_size)
            
            return candles[-count:] if len(candles) >= count else candles
            
        except Exception as e:
            print(f"Error fetching recent candles for {symbol}: {e}")
            return []
    
    def _add_to_cache(self, symbol, candle):
        """Add candle to in-memory cache"""
        if symbol not in self.candle_cache:
            self.candle_cache[symbol] = deque(maxlen=self.max_cache_size)
        
        # Avoid duplicates (check timestamp)
        if self.candle_cache[symbol]:
            last_candle = self.candle_cache[symbol][-1]
            if last_candle['timestamp'] == candle['timestamp']:
                return  # Already have this candle
        
        self.candle_cache[symbol].append(candle)
    
    def get_ltp(self, symbol):
        """
        Get Last Traded Price (real-time)
        
        Returns: float or None
        """
        try:
            ltp = self.kite.get_ltp(symbol)
            return ltp
        except Exception as e:
            print(f"Error fetching LTP for {symbol}: {e}")
            return None
    
    def cleanup_cache(self):
        """Clear all cached data (call at EOD)"""
        self.candle_cache.clear()
        self.symbol_cache.clear()
        print("Data cache cleared")
    
    def get_cache_stats(self):
        """Get cache statistics for monitoring"""
        return {
            'cached_symbols': len(self.candle_cache),
            'total_candles': sum(len(v) for v in self.candle_cache.values()),
            'symbols': list(self.candle_cache.keys())
        }


if __name__ == "__main__":
    # Test data manager (requires mock kite client)
    class MockKiteClient:
        def get_historical_data(self, symbol, from_date, to_date, interval):
            # Mock data
            import random
            base_price = 145.0
            data = []
            
            if interval == 'day':
                return [{
                    'date': from_date,
                    'open': base_price,
                    'high': base_price + 5,
                    'low': base_price - 3,
                    'close': base_price + 2
                }]
            else:  # 3minute
                for i in range(20):
                    data.append({
                        'date': from_date + timedelta(minutes=3*i),
                        'open': base_price + random.uniform(-2, 2),
                        'high': base_price + random.uniform(0, 3),
                        'low': base_price + random.uniform(-3, 0),
                        'close': base_price + random.uniform(-2, 2)
                    })
                return data
        
        def get_ltp(self, symbol):
            return 147.50
    
    config = {
        'trading': {
            'instrument': 'SENSEX',
            'strike_interval': 100
        },
        'market': {
            'holidays': ['2025-01-26', '2025-10-02']
        }
    }
    
    mock_kite = MockKiteClient()
    dm = DataManager(mock_kite, config)
    
    # Test previous trading day
    print("Testing previous trading day...")
    prev_day = dm.get_previous_trading_day()
    print(f"Previous trading day: {prev_day}")
    
    # Test next expiry
    print("\nTesting next expiry...")
    expiry = dm.get_next_expiry()
    print(f"Next expiry: {expiry} (Days to expiry: {dm.days_to_expiry()})")
    
    # Test option symbol generation
    print("\nTesting option symbol...")
    symbol = dm.get_option_symbol(80100, 'CE')
    print(f"Option symbol: {symbol}")
    
    # Test OHLC fetch
    print("\nTesting previous day OHLC...")
    ohlc = dm.fetch_previous_day_ohlc(symbol)
    if ohlc:
        print(f"OHLC: H={ohlc['high']}, L={ohlc['low']}, C={ohlc['close']}")
    
    # Test recent candles
    print("\nTesting recent candles...")
    candles = dm.get_recent_candles(symbol, 20)
    print(f"Fetched {len(candles)} candles")
    
    # Test cache stats
    print("\nCache stats:")
    stats = dm.get_cache_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
