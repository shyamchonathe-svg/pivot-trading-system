"""
Trading Hours Utility
Validates market hours, holidays, and trading windows
"""

from datetime import datetime, time


class TradingHours:
    def __init__(self, config):
        self.config = config
        self.market_start = datetime.strptime(
            config['market']['start_time'], '%H:%M'
        ).time()
        self.market_end = datetime.strptime(
            config['market']['end_time'], '%H:%M'
        ).time()
        self.eod_exit = datetime.strptime(
            config['market']['eod_exit_time'], '%H:%M'
        ).time()
        
        self.holidays = [
            datetime.strptime(h, '%Y-%m-%d').date()
            for h in config['market']['holidays']
        ]
    
    def is_holiday(self, date=None):
        """Check if given date is a holiday"""
        if date is None:
            date = datetime.now().date()
        
        # Weekend
        if date.weekday() >= 5:  # Saturday=5, Sunday=6
            return True
        
        # Holiday list
        return date in self.holidays
    
    def is_trading_day(self, date=None):
        """Check if given date is a trading day"""
        return not self.is_holiday(date)
    
    def is_market_open(self, current_time=None):
        """
        Check if market is currently open
        
        Args:
            current_time: datetime or time object (default: now)
        
        Returns: bool
        """
        if current_time is None:
            current_time = datetime.now()
        
        # Check if today is trading day
        if not self.is_trading_day(current_time.date()):
            return False
        
        # Extract time
        if isinstance(current_time, datetime):
            current_time = current_time.time()
        
        # Check time window
        return self.market_start <= current_time <= self.market_end
    
    def is_pre_market(self, current_time=None):
        """Check if we're in pre-market hours (before 9:15 AM)"""
        if current_time is None:
            current_time = datetime.now().time()
        
        if isinstance(current_time, datetime):
            current_time = current_time.time()
        
        return current_time < self.market_start
    
    def is_eod_exit_time(self, current_time=None):
        """Check if it's time for EOD exit (3:15 PM)"""
        if current_time is None:
            current_time = datetime.now().time()
        
        if isinstance(current_time, datetime):
            current_time = current_time.time()
        
        return current_time >= self.eod_exit
    
    def time_to_market_open(self, current_time=None):
        """
        Calculate minutes until market opens
        
        Returns: int (minutes) or None if already open
        """
        if current_time is None:
            current_time = datetime.now()
        
        if isinstance(current_time, time):
            today = datetime.now().date()
            current_time = datetime.combine(today, current_time)
        
        if self.is_market_open(current_time):
            return 0
        
        # Find next market open
        next_open = datetime.combine(current_time.date(), self.market_start)
        
        # If past today's open, check next trading day
        if current_time.time() > self.market_start:
            next_day = current_time.date()
            while True:
                next_day = next_day.replace(day=next_day.day + 1)
                if self.is_trading_day(next_day):
                    next_open = datetime.combine(next_day, self.market_start)
                    break
        
        delta = next_open - current_time
        return int(delta.total_seconds() / 60)
    
    def time_to_eod_exit(self, current_time=None):
        """
        Calculate minutes until EOD exit time
        
        Returns: int (minutes) or 0 if past exit time
        """
        if current_time is None:
            current_time = datetime.now()
        
        if isinstance(current_time, time):
            today = datetime.now().date()
            current_time = datetime.combine(today, current_time)
        
        exit_time = datetime.combine(current_time.date(), self.eod_exit)
        
        if current_time >= exit_time:
            return 0
        
        delta = exit_time - current_time
        return int(delta.total_seconds() / 60)
    
    def get_market_status(self):
        """
        Get comprehensive market status
        
        Returns: dict with status information
        """
        now = datetime.now()
        
        status = {
            'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
            'is_trading_day': self.is_trading_day(),
            'is_market_open': self.is_market_open(),
            'is_pre_market': self.is_pre_market(),
            'is_eod_exit_time': self.is_eod_exit_time(),
            'market_start': self.market_start.strftime('%H:%M'),
            'market_end': self.market_end.strftime('%H:%M'),
            'eod_exit': self.eod_exit.strftime('%H:%M')
        }
        
        if status['is_market_open']:
            status['phase'] = 'TRADING'
            status['minutes_to_eod'] = self.time_to_eod_exit()
        elif status['is_pre_market']:
            status['phase'] = 'PRE_MARKET'
            status['minutes_to_open'] = self.time_to_market_open()
        elif not status['is_trading_day']:
            status['phase'] = 'HOLIDAY'
            status['minutes_to_open'] = self.time_to_market_open()
        else:
            status['phase'] = 'POST_MARKET'
            status['minutes_to_open'] = self.time_to_market_open()
        
        return status


if __name__ == "__main__":
    # Test trading hours
    config = {
        'market': {
            'start_time': '09:15',
            'end_time': '15:30',
            'eod_exit_time': '15:15',
            'holidays': [
                '2025-01-26', '2025-02-12', '2025-03-14',
                '2025-04-10', '2025-04-14', '2025-05-01',
                '2025-08-15', '2025-10-02', '2025-10-29',
                '2025-11-14'
            ]
        }
    }
    
    th = TradingHours(config)
    
    # Test current status
    print("Current Market Status:")
    status = th.get_market_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    # Test specific dates
    print("\n\nTesting specific dates:")
    
    # Weekend
    weekend = datetime(2025, 10, 26).date()  # Sunday
    print(f"\n{weekend} (Sunday):")
    print(f"  Is holiday: {th.is_holiday(weekend)}")
    print(f"  Is trading day: {th.is_trading_day(weekend)}")
    
    # Holiday
    holiday = datetime(2025, 10, 2).date()  # Gandhi Jayanti
    print(f"\n{holiday} (Gandhi Jayanti):")
    print(f"  Is holiday: {th.is_holiday(holiday)}")
    print(f"  Is trading day: {th.is_trading_day(holiday)}")
    
    # Normal trading day
    trading_day = datetime(2025, 10, 27).date()  # Monday
    print(f"\n{trading_day} (Monday):")
    print(f"  Is holiday: {th.is_holiday(trading_day)}")
    print(f"  Is trading day: {th.is_trading_day(trading_day)}")
    
    # Test different times
    print("\n\nTesting different times:")
    
    test_times = [
        time(8, 30),   # Pre-market
        time(9, 15),   # Market open
        time(12, 0),   # Mid-day
        time(15, 15),  # EOD exit
        time(15, 30),  # Market close
        time(18, 0)    # After market
    ]
    
    for t in test_times:
        test_dt = datetime.combine(datetime.now().date(), t)
        print(f"\n{t.strftime('%H:%M')}:")
        print(f"  Market open: {th.is_market_open(test_dt)}")
        print(f"  Pre-market: {th.is_pre_market(t)}")
        print(f"  EOD exit time: {th.is_eod_exit_time(t)}")
