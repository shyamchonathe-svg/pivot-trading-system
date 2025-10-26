# System Architecture
## Pivot Trading System - Technical Design

**Version**: 1.0.0  
**Last Updated**: October 25, 2025  
**Status**: Core modules complete

---

## 📐 System Overview
```
┌─────────────────────────────────────────────────────────────┐
│                    PIVOT TRADING SYSTEM                      │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   ┌────▼────┐         ┌────▼────┐        ┌────▼────┐
   │  Auth   │         │  Data   │        │ Trading │
   │ Manager │         │ Manager │        │  Logic  │
   └────┬────┘         └────┬────┘        └────┬────┘
        │                   │                   │
        │         ┌─────────┴─────────┐         │
        │         │                   │         │
   ┌────▼────┐   │              ┌────▼────┐   ┌▼─────────┐
   │  Kite   │   │              │  Pivot  │   │ Signal   │
   │ Connect │◄──┤              │  Calc   │   │Generator │
   └─────────┘   │              └─────────┘   └──────────┘
                 │                                   │
            ┌────▼────┐                        ┌────▼────┐
            │Database │                        │Position │
            │ SQLite  │                        │ Manager │
            └─────────┘                        └─────────┘
                 │                                   │
            ┌────▼────────────────────────────────────▼──┐
            │          Telegram Notifier                 │
            └────────────────────────────────────────────┘
```

---

## 🔐 Authentication Architecture

Uses existing SSL setup from previous system:
- **Port 8000**: HTTPS OAuth callback (with SSL cert)
- **Port 8001**: HTTPS postback webhook (with SSL cert)
- **Domain**: sensexbot.ddns.net
- Daily authentication via Telegram link

---

## 🏗️ Module Status

### ✅ Completed
- [x] `modules/pivot_calculator.py` - Pivot calculation
- [x] `modules/signal_generator.py` - Signal detection
- [x] `modules/position_manager.py` - Position management
- [x] `modules/data_manager.py` - Data fetching
- [x] `modules/kite_client.py` - Kite API wrapper
- [x] `utils/trading_hours.py` - Time validation

### 🚧 In Progress
- [ ] `modules/database.py` - SQLite operations
- [ ] `modules/notifier.py` - Telegram integration
- [ ] `modules/auth_manager.py` - Authentication
- [ ] `auth_server.py` - Flask server
- [ ] `main.py` - Main loop

---

## 📊 Trading Strategy

### Entry Scenarios
1. **Scenario 1**: PP-S1 → R1 breakout (Target: R3)
2. **Scenario 2**: PP-R1 → R2 breakout (Target: R4)
3. **Scenario 3**: R2-R3 → R3 breakout (Target: R5)

### Entry Conditions (ALL must be true)
- Market structure = BULLISH
- Candle is GREEN
- Candle is SIGNIFICANT (≥75th percentile)
- No existing position OR re-entry allowed

### Exit Rules
- Stop Loss: Entry candle low
- Target: R3/R4/R5
- Timeout: 10 candles (first candle only)
- EOD: 3:15 PM

---

## 🔒 Security

- Config file permissions: 600
- Data directory permissions: 700
- SSL certificates for HTTPS
- Secrets never committed to git
- Access token regenerated daily

