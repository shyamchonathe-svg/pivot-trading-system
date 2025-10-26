"""
Signal Generator Module
Detects entry and exit signals based on pivot strategy
"""

import numpy as np
from datetime import datetime, time


class Signal:
    """Represents a trading signal"""
    def __init__(self, signal_type, scenario, symbol, strike, option_type,
                 entry_price, stop_loss, target, pivots, structure,
                 is_first_candle, candle_data, reason=""):
        self.signal_type = signal_type  # 'ENTRY' or 'EXIT'
        self.scenario = scenario  # 1, 2, 3, or None for exit
        self.symbol = symbol
        self.strike = strike
        self.option_type = option_type
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.target = target
        self.pivots = pivots
        self.structure = structure
        self.is_first_candle = is_first_candle
        self.candle_data = candle_data
        self.reason = reason
        self.timestamp = datetime.now()


class SignalGenerator:
    def __init__(self, config, pivot_calculator):
        self.config = config
        self.pivot_calc = pivot_calculator
        self.percentile = config['trading']['candle_size_percentile']
        self.max_candles_timeout = config['trading']['max_candles_timeout']
    
    def is_market_hours(self, current_time=None):
        """Check if current time is within trading hours"""
        if current_time is None:
            current_time = datetime.now().time()
        
        if isinstance(current_time, str):
            current_time = datetime.strptime(current_time, '%H:%M:%S').time()
        
        start_time = datetime.strptime(
            self.config['market']['start_time'], '%H:%M'
        ).time()
        end_time = datetime.strptime(
            self.config['market']['end_time'], '%H:%M'
        ).time()
        
        return start_time <= current_time <= end_time
    
    def is_first_candle_time(self, current_time=None):
        """Check if current time is first candle (9:15-9:21 buffer)"""
        if current_time is None:
            current_time = datetime.now().time()
        
        if isinstance(current_time, str):
            current_time = datetime.strptime(current_time, '%H:%M:%S').time()
        
        first_candle_start = time(9, 15)
        first_candle_end = time(9, 21)
        
        return first_candle_start <= current_time <= first_candle_end
    
    def calculate_candle_size_percent(self, candle):
        """Calculate candle size as percentage"""
        if candle['open'] == 0:
            return 0
        return abs((candle['close'] - candle['open']) / candle['open']) * 100
    
    def is_significant_candle(self, current_candle, recent_candles):
        """
        Check if candle is significant (>= 75th percentile)
        
        Args:
            current_candle: Current candle dict
            recent_candles: List of recent candles (up to 20)
        
        Returns: tuple (is_significant, threshold, current_size)
        """
        if not recent_candles:
            return False, 0, 0
        
        # Calculate sizes for all candles
        sizes = [self.calculate_candle_size_percent(c) for c in recent_candles]
        
        # Calculate threshold
        threshold = np.percentile(sizes, self.percentile)
        
        # Current candle size
        current_size = self.calculate_candle_size_percent(current_candle)
        
        return current_size >= threshold, threshold, current_size
    
    def is_green_candle(self, candle):
        """Check if candle is green (close > open)"""
        return candle['close'] > candle['open']
    
    def check_scenario_1(self, candle, pivots, is_first_candle, structure):
        """
        Scenario 1: Opens between PP and S1
        
        First Candle:
        - Open: Between PP and S1
        - Close: Above R1
        - Target: R3
        - 10-candle timeout applies
        
        Intraday:
        - Opened between PP-S1 in first candle but didn't break R1
        - ANY candle closes above R1
        - Target: R3
        """
        if structure != 'BULLISH':
            return None
        
        pp = pivots['PP']
        s1 = pivots['S1']
        r1 = pivots['R1']
        r3 = pivots['R3']
        
        candle_open = candle['open']
        candle_close = candle['close']
        
        if is_first_candle:
            # First candle logic
            if pp >= candle_open >= s1 and candle_close > r1:
                return {
                    'scenario': 1,
                    'target': r3,
                    'reason': 'First candle: Opened PP-S1, closed above R1',
                    'has_timeout': True
                }
        else:
            # Intraday logic: Just need to close above R1
            if candle_close > r1:
                return {
                    'scenario': 1,
                    'target': r3,
                    'reason': 'Intraday: Closed above R1',
                    'has_timeout': False
                }
        
        return None
    
    def check_scenario_2(self, candle, pivots, is_first_candle, structure):
        """
        Scenario 2: Opens between PP and R1
        
        First Candle:
        - Open: Between PP and R1
        - Close: Above R2 (but below R3)
        - Target: R4
        - 10-candle timeout applies
        
        Intraday:
        - Opened between PP-R1 in first candle but didn't break R2
        - ANY candle closes above R2 (but below R3)
        - Target: R4
        """
        if structure != 'BULLISH':
            return None
        
        pp = pivots['PP']
        r1 = pivots['R1']
        r2 = pivots['R2']
        r3 = pivots['R3']
        r4 = pivots['R4']
        
        candle_open = candle['open']
        candle_close = candle['close']
        
        if is_first_candle:
            # First candle logic
            if pp <= candle_open <= r1 and r2 < candle_close < r3:
                return {
                    'scenario': 2,
                    'target': r4,
                    'reason': 'First candle: Opened PP-R1, closed above R2 below R3',
                    'has_timeout': True
                }
        else:
            # Intraday logic: Close above R2 but below R3
            if r2 < candle_close < r3:
                return {
                    'scenario': 2,
                    'target': r4,
                    'reason': 'Intraday: Closed above R2 below R3',
                    'has_timeout': False
                }
        
        return None
    
    def check_scenario_3(self, candle, pivots, is_first_candle, structure):
        """
        Scenario 3: Opens between R2 and R3
        
        First Candle: NO TRADE (too extended)
        
        Intraday ONLY:
        - Open: Between R2 and R3
        - Close: Above R3
        - Target: R5
        """
        if structure != 'BULLISH':
            return None
        
        if is_first_candle:
            # No trade on first candle for scenario 3
            return None
        
        r2 = pivots['R2']
        r3 = pivots['R3']
        r5 = pivots['R5']
        
        candle_open = candle['open']
        candle_close = candle['close']
        
        # Intraday logic only
        if r2 <= candle_open <= r3 and candle_close > r3:
            return {
                'scenario': 3,
                'target': r5,
                'reason': 'Intraday: Opened R2-R3, closed above R3',
                'has_timeout': False
            }
        
        return None
    
    def generate_entry_signal(self, candle, recent_candles, pivots, structure,
                              symbol, strike, option_type):
        """
        Main method to generate entry signals
        
        Pre-conditions (ALL must be true):
        1. Market structure = BULLISH
        2. Candle is GREEN
        3. Candle is SIGNIFICANT
        4. No existing position (checked by caller)
        
        Returns: Signal object or None
        """
        # Check if in trading hours
        if not self.is_market_hours():
            return None
        
        # Pre-condition 1: Structure must be BULLISH
        if structure != 'BULLISH':
            return None
        
        # Pre-condition 2: Candle must be GREEN
        if not self.is_green_candle(candle):
            return None
        
        # Pre-condition 3: Candle must be SIGNIFICANT
        is_sig, threshold, current_size = self.is_significant_candle(
            candle, recent_candles
        )
        if not is_sig:
            return None
        
        # Check if first candle
        is_first = self.is_first_candle_time()
        
        # Check scenarios in order
        result = None
        
        # Scenario 1
        result = self.check_scenario_1(candle, pivots, is_first, structure)
        if result:
            return self._create_entry_signal(
                result, candle, pivots, structure, symbol, strike,
                option_type, is_first, current_size
            )
        
        # Scenario 2
        result = self.check_scenario_2(candle, pivots, is_first, structure)
        if result:
            return self._create_entry_signal(
                result, candle, pivots, structure, symbol, strike,
                option_type, is_first, current_size
            )
        
        # Scenario 3
        result = self.check_scenario_3(candle, pivots, is_first, structure)
        if result:
            return self._create_entry_signal(
                result, candle, pivots, structure, symbol, strike,
                option_type, is_first, current_size
            )
        
        return None
    
    def _create_entry_signal(self, scenario_result, candle, pivots, structure,
                            symbol, strike, option_type, is_first_candle,
                            candle_size):
        """Helper to create Signal object"""
        entry_price = candle['close']
        stop_loss = candle['low']
        target = scenario_result['target']
        
        return Signal(
            signal_type='ENTRY',
            scenario=scenario_result['scenario'],
            symbol=symbol,
            strike=strike,
            option_type=option_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target,
            pivots=pivots.copy(),
            structure=structure,
            is_first_candle=is_first_candle,
            candle_data={
                'open': candle['open'],
                'high': candle['high'],
                'low': candle['low'],
                'close': candle['close'],
                'size_percent': candle_size,
                'timestamp': candle.get('timestamp', datetime.now())
            },
            reason=scenario_result['reason']
        )
    
    def check_exit_conditions(self, position, current_candle, candle_count):
        """
        Check if any exit condition is met
        
        Exit Conditions:
        1. Stop Loss Hit: current_price <= entry_candle_low
        2. Target Hit: current_price >= target
        3. 10-Candle Timeout: candle_count >= 10 (first candle only)
        4. EOD Exit: time >= 15:15
        
        Returns: tuple (should_exit, reason, exit_price)
        """
        current_price = current_candle['close']
        current_time = datetime.now().time()
        
        # 1. Check Stop Loss
        if current_price <= position.stop_loss:
            return True, 'STOP_LOSS', current_price
        
        # 2. Check Target
        if current_price >= position.target:
            return True, 'TARGET', current_price
        
        # 3. Check 10-Candle Timeout (first candle entries only)
        if position.is_first_candle and candle_count >= self.max_candles_timeout:
            return True, '10_CANDLE_TIMEOUT', current_price
        
        # 4. Check EOD Exit
        eod_time = datetime.strptime(
            self.config['market']['eod_exit_time'], '%H:%M'
        ).time()
        if current_time >= eod_time:
            return True, 'EOD', current_price
        
        return False, None, None


if __name__ == "__main__":
    # Test signal generator
    from pivot_calculator import PivotCalculator
    
    config = {
        'trading': {
            'instrument': 'SENSEX',
            'strike_interval': 100,
            'strike_range': 500,
            'candle_size_percentile': 75,
            'max_candles_timeout': 10
        },
        'market': {
            'start_time': '09:15',
            'end_time': '15:30',
            'eod_exit_time': '15:15'
        }
    }
    
    pivot_calc = PivotCalculator(config)
    signal_gen = SignalGenerator(config, pivot_calc)
    
    # Test candle
    current_candle = {
        'open': 142.5,
        'high': 148.2,
        'low': 141.8,
        'close': 147.5,
        'timestamp': datetime.now()
    }
    
    # Recent candles (smaller ones)
    recent_candles = [
        {'open': 140, 'high': 141, 'low': 139.5, 'close': 140.5},
        {'open': 140.5, 'high': 141.5, 'low': 140, 'close': 141},
        {'open': 141, 'high': 142, 'low': 140.8, 'close': 141.5},
    ] * 7  # Repeat to get 21 candles
    
    # Test pivots
    pivots = {
        'PP': 143.5, 'R1': 146.0, 'R2': 150.0, 'R3': 155.0,
        'R4': 160.0, 'R5': 165.0, 'S1': 139.0, 'S2': 135.0, 'S3': 130.0
    }
    
    # Test significance
    is_sig, threshold, size = signal_gen.is_significant_candle(
        current_candle, recent_candles
    )
    print(f"Significant: {is_sig}, Threshold: {threshold:.2f}%, Current: {size:.2f}%")
    
    # Test entry signal
    signal = signal_gen.generate_entry_signal(
        current_candle, recent_candles, pivots, 'BULLISH',
        'SENSEX2510280100CE', 80100, 'CE'
    )
    
    if signal:
        print(f"\n✅ Entry Signal Generated!")
        print(f"Scenario: {signal.scenario}")
        print(f"Entry: {signal.entry_price}, SL: {signal.stop_loss}, Target: {signal.target}")
        print(f"Reason: {signal.reason}")
    else:
        print("\n❌ No entry signal")
