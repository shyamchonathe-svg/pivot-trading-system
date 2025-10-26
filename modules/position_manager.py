"""
Position Manager Module
Tracks open positions and manages exits
"""

from datetime import datetime
from dataclasses import dataclass


@dataclass
class Position:
    """Represents an open trading position"""
    trade_id: str
    symbol: str
    strike: int
    option_type: str
    
    entry_time: datetime
    entry_price: float
    entry_candle_low: float
    
    scenario: int
    structure: str
    is_first_candle: bool
    
    target: float
    stop_loss: float
    lot_size: int
    
    pivots: dict
    candles_held: int = 0
    
    def to_dict(self):
        """Convert position to dictionary"""
        return {
            'trade_id': self.trade_id,
            'symbol': self.symbol,
            'strike': self.strike,
            'option_type': self.option_type,
            'entry_time': self.entry_time.strftime('%H:%M:%S'),
            'entry_price': self.entry_price,
            'entry_candle_low': self.entry_candle_low,
            'scenario': self.scenario,
            'structure': self.structure,
            'is_first_candle': self.is_first_candle,
            'target': self.target,
            'stop_loss': self.stop_loss,
            'lot_size': self.lot_size,
            'candles_held': self.candles_held,
            'pivots': self.pivots
        }


@dataclass
class TradeResult:
    """Result of a closed trade"""
    trade_id: str
    symbol: str
    strike: int
    option_type: str
    
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    exit_reason: str
    
    scenario: int
    structure: str
    is_first_candle: bool
    re_entry: bool
    
    target: float
    stop_loss: float
    candles_held: int
    lot_size: int
    
    pnl_points: float
    pnl_rupees: float
    
    pivots: dict
    
    def to_dict(self):
        """Convert trade result to dictionary for database"""
        return {
            'trade_id': self.trade_id,
            'symbol': self.symbol,
            'strike': self.strike,
            'option_type': self.option_type,
            'entry_time': self.entry_time.strftime('%H:%M:%S'),
            'entry_price': self.entry_price,
            'entry_candle_low': self.stop_loss,
            'exit_time': self.exit_time.strftime('%H:%M:%S'),
            'exit_price': self.exit_price,
            'exit_reason': self.exit_reason,
            'scenario': self.scenario,
            'structure': self.structure,
            'first_candle_entry': self.is_first_candle,
            're_entry': self.re_entry,
            'target_price': self.target,
            'sl_price': self.stop_loss,
            'candles_held': self.candles_held,
            'lot_size': self.lot_size,
            'pnl_points': self.pnl_points,
            'pnl_rupees': self.pnl_rupees,
            'pivot_pp': self.pivots['PP'],
            'pivot_r1': self.pivots['R1'],
            'pivot_r2': self.pivots['R2'],
            'pivot_r3': self.pivots['R3'],
            'pivot_r4': self.pivots['R4'],
            'pivot_r5': self.pivots['R5'],
            'pivot_s1': self.pivots['S1']
        }


class PositionManager:
    def __init__(self, config):
        self.config = config
        self.position = None
        self.stop_loss_count = 0
        self.max_re_entries = config['trading']['max_re_entries']
        self.lot_size = config['trading']['lot_size']
        self.trade_counter = 0
        self.today_date = datetime.now().strftime('%Y%m%d')
    
    def has_position(self):
        """Check if position is currently open"""
        return self.position is not None
    
    def can_re_enter(self):
        """Check if re-entry is allowed after stop loss"""
        return self.stop_loss_count <= self.max_re_entries
    
    def generate_trade_id(self):
        """Generate unique trade ID: YYYYMMDD_NNN"""
        self.trade_counter += 1
        return f"{self.today_date}_{self.trade_counter:03d}"
    
    def open_position(self, signal, is_re_entry=False):
        """
        Open a new position from entry signal
        
        Args:
            signal: Signal object with entry details
            is_re_entry: Boolean indicating if this is a re-entry after SL
        
        Returns: Position object
        """
        if self.has_position():
            raise Exception("Cannot open position: Position already exists")
        
        trade_id = self.generate_trade_id()
        
        self.position = Position(
            trade_id=trade_id,
            symbol=signal.symbol,
            strike=signal.strike,
            option_type=signal.option_type,
            entry_time=signal.timestamp,
            entry_price=signal.entry_price,
            entry_candle_low=signal.stop_loss,
            scenario=signal.scenario,
            structure=signal.structure,
            is_first_candle=signal.is_first_candle,
            target=signal.target,
            stop_loss=signal.stop_loss,
            lot_size=self.lot_size,
            pivots=signal.pivots,
            candles_held=0
        )
        
        return self.position
    
    def update_position(self, candle_count):
        """Update candles held count"""
        if self.has_position():
            self.position.candles_held = candle_count
    
    def close_position(self, exit_price, exit_reason, is_re_entry=False):
        """
        Close current position and calculate P&L
        
        Args:
            exit_price: Exit price
            exit_reason: 'TARGET', 'STOP_LOSS', '10_CANDLE_TIMEOUT', 'EOD'
            is_re_entry: If this position was a re-entry
        
        Returns: TradeResult object
        """
        if not self.has_position():
            raise Exception("Cannot close position: No position exists")
        
        pos = self.position
        exit_time = datetime.now()
        
        # Calculate P&L
        pnl_points = exit_price - pos.entry_price
        pnl_rupees = pnl_points * pos.lot_size
        
        # Update stop loss count if SL hit
        if exit_reason == 'STOP_LOSS':
            self.stop_loss_count += 1
        
        # Create trade result
        result = TradeResult(
            trade_id=pos.trade_id,
            symbol=pos.symbol,
            strike=pos.strike,
            option_type=pos.option_type,
            entry_time=pos.entry_time,
            entry_price=pos.entry_price,
            exit_time=exit_time,
            exit_price=exit_price,
            exit_reason=exit_reason,
            scenario=pos.scenario,
            structure=pos.structure,
            is_first_candle=pos.is_first_candle,
            re_entry=is_re_entry,
            target=pos.target,
            stop_loss=pos.stop_loss,
            candles_held=pos.candles_held,
            lot_size=pos.lot_size,
            pnl_points=round(pnl_points, 2),
            pnl_rupees=round(pnl_rupees, 2),
            pivots=pos.pivots
        )
        
        # Clear position
        self.position = None
        
        return result
    
    def get_position_status(self):
        """Get current position status for monitoring"""
        if not self.has_position():
            return None
        
        pos = self.position
        current_time = datetime.now()
        duration_mins = (current_time - pos.entry_time).total_seconds() / 60
        
        return {
            'trade_id': pos.trade_id,
            'symbol': pos.symbol,
            'strike': pos.strike,
            'option_type': pos.option_type,
            'entry_price': pos.entry_price,
            'entry_time': pos.entry_time.strftime('%H:%M:%S'),
            'duration_mins': round(duration_mins, 1),
            'candles_held': pos.candles_held,
            'target': pos.target,
            'stop_loss': pos.stop_loss,
            'scenario': pos.scenario,
            'is_first_candle': pos.is_first_candle
        }
    
    def reset_daily_state(self):
        """Reset state for new trading day"""
        self.position = None
        self.stop_loss_count = 0
        self.trade_counter = 0
        self.today_date = datetime.now().strftime('%Y%m%d')
    
    def get_stats(self):
        """Get daily trading stats"""
        return {
            'has_position': self.has_position(),
            'stop_loss_count': self.stop_loss_count,
            'can_re_enter': self.can_re_enter(),
            'trades_today': self.trade_counter,
            'position': self.get_position_status() if self.has_position() else None
        }


if __name__ == "__main__":
    # Test position manager
    from signal_generator import Signal
    from datetime import datetime
    
    config = {
        'trading': {
            'max_re_entries': 1,
            'lot_size': 10
        }
    }
    
    manager = PositionManager(config)
    
    # Create test signal
    signal = Signal(
        signal_type='ENTRY',
        scenario=1,
        symbol='SENSEX2510280100CE',
        strike=80100,
        option_type='CE',
        entry_price=145.50,
        stop_loss=138.20,
        target=175.00,
        pivots={'PP': 143.5, 'R1': 146.0, 'R2': 150.0, 'R3': 175.0,
                'R4': 180.0, 'R5': 185.0, 'S1': 139.0},
        structure='BULLISH',
        is_first_candle=True,
        candle_data={},
        reason='Test signal'
    )
    
    # Open position
    print("Opening position...")
    pos = manager.open_position(signal)
    print(f"Position opened: {pos.trade_id}")
    print(f"Has position: {manager.has_position()}")
    
    # Update candles
    manager.update_position(5)
    print(f"Candles held: {manager.position.candles_held}")
    
    # Get status
    status = manager.get_position_status()
    print(f"\nPosition Status:")
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    # Close position (TARGET hit)
    print("\nClosing position at target...")
    result = manager.close_position(175.00, 'TARGET')
    print(f"Trade closed: {result.exit_reason}")
    print(f"P&L Points: {result.pnl_points}")
    print(f"P&L Rupees: ₹{result.pnl_rupees}")
    print(f"Has position: {manager.has_position()}")
    
    # Test re-entry
    print(f"\nCan re-enter: {manager.can_re_enter()}")
    print(f"Stop loss count: {manager.stop_loss_count}")
    
    # Open another position
    signal.entry_price = 148.00
    pos2 = manager.open_position(signal)
    print(f"\nRe-entry position: {pos2.trade_id}")
    
    # Close with stop loss
    result2 = manager.close_position(135.00, 'STOP_LOSS')
    print(f"Trade closed: {result2.exit_reason}")
    print(f"P&L: ₹{result2.pnl_rupees}")
    print(f"Stop loss count: {manager.stop_loss_count}")
    print(f"Can re-enter: {manager.can_re_enter()}")
