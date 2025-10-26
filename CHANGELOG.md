# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [0.1.0] - 2025-10-25

### Added - Core Trading Logic Modules

#### pivot_calculator.py
- Standard pivot calculation (PP, R1-R5, S1-S3)
- Market structure determination (BULLISH/BEARISH/NEUTRAL)
- ATM strike calculation based on spot price
- ITM strike selection based on expiry day
- Strike range generation for analysis
- Price zone identification

#### signal_generator.py
- 75th percentile significant candle detection
- Scenario 1: PP-S1 → R1 breakout detection
- Scenario 2: PP-R1 → R2 breakout detection
- Scenario 3: R2-R3 → R3 breakout detection
- Exit condition checking (Stop Loss, Target, Timeout, EOD)
- First candle vs intraday logic separation
- Pre-condition validation (BULLISH + GREEN + SIGNIFICANT)

#### position_manager.py
- Open/close position tracking
- P&L calculation (points and rupees)
- Re-entry limit enforcement (max 1 after stop loss)
- Trade ID generation (YYYYMMDD_NNN format)
- Position status monitoring
- Candle count tracking

#### data_manager.py
- Previous trading day calculation (skip weekends/holidays)
- Next expiry date calculation (weekly Thu for Sensex, Tue for Nifty)
- Option symbol generation (format: SENSEX2510280100CE)
- Previous day OHLC fetching for pivot calculation
- Current 3-minute candle fetching
- Rolling 20-candle window management for percentile
- In-memory caching for performance
- LTP (Last Traded Price) fetching

#### kite_client.py
- Kite Connect API wrapper with error handling
- Access token management
- Instrument loading and caching (BFO/NFO)
- Spot price fetching for indices
- Historical data fetching (3-minute candles)
- LTP and quote fetching
- Order placement interface (for live trading)
- Position management
- Token validation

#### utils/trading_hours.py
- Holiday checking (weekends + NSE holidays list)
- Trading day validation
- Market open/close status checking
- Pre-market detection
- EOD exit time checking
- Time calculations (minutes to open/close)
- Comprehensive market status reporting

### Documentation
- Initial README.md with project overview
- CHANGELOG.md for tracking changes
- Inline code documentation and docstrings
- Test code in each module's `__main__` block

### Configuration
- requirements.txt with all dependencies
- config.example.json template
- .gitignore for security

### Notes
- All modules follow exact specifications from handover document
- Virtual environment setup for dependency isolation
- Proper error handling and logging support
- Ready for integration testing

---

## Commit Message Format

```
[TYPE] Brief description (max 50 chars)

Detailed description if needed.

Changes:
- Change 1
- Change 2

Testing:
- Test performed

Related: #issue_number
```

**Types**: `init`, `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
