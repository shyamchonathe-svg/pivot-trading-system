# Pivot-Based Options Trading System

Automated options trading system for Sensex/Nifty using pivot point strategy.

## 🎯 Features

- **Automated Trading**: Hands-free option buying based on pivot points
- **3 Entry Scenarios**: PP-S1, PP-R1, R2-R3 breakouts
- **Smart Exit**: Stop loss, target, timeout, EOD management
- **Telegram Integration**: Real-time alerts and daily summaries
- **Daily Authentication**: Automated Kite Connect OAuth flow
- **Paper Trading**: Test strategy without real money

## 🏗️ Architecture

```
Pre-Market (8:45 AM) → Calculate Pivots → Trading Loop (9:15-3:15 PM)
                                              ↓
                        Entry Signal → Open Position → Monitor Exit
                                              ↓
                                         Close Position → Log Trade
```

## 🚀 Quick Start

### Prerequisites
- EC2 Instance (Ubuntu 20.04+)
- Zerodha Kite Connect API credentials
- Telegram Bot Token
- DDNS setup (e.g., sensexbot.ddns.net)

### Installation

```bash
# Clone repository
git clone https://github.com/shyamchonathe-svg/pivot-trading-system.git
cd pivot-trading-system

# Run setup script
chmod +x setup.sh
./setup.sh

# Configure credentials
cp config.example.json config.json
nano config.json  # Add your API keys

# Test authentication
source venv/bin/activate
python scripts/test_auth.py
```

### Running the System

```bash
# Manual run
source venv/bin/activate
python main.py

# Or use systemd service
sudo systemctl start pivot-trading
sudo systemctl status pivot-trading
```

## 📊 Trading Strategy

### Entry Conditions (ALL must be true)
1. Market structure = **BULLISH**
2. Candle is **GREEN** (Close > Open)
3. Candle is **SIGNIFICANT** (≥ 75th percentile size)
4. No existing position open

### Scenarios
- **Scenario 1**: Open PP-S1, Close > R1 → Target R3
- **Scenario 2**: Open PP-R1, Close > R2 → Target R4
- **Scenario 3**: Open R2-R3, Close > R3 → Target R5

### Exit Rules
- Stop Loss: Entry candle low
- Target: R3/R4/R5 based on scenario
- Timeout: 10 candles (first candle entries only)
- EOD: 3:15 PM force exit

## 📁 Project Structure

```
modules/          # Core trading logic
utils/            # Helper utilities
tests/            # Unit tests
scripts/          # Setup & utility scripts
data/             # Database & cache (gitignored)
logs/             # System logs (gitignored)
```

## 🔧 Configuration

Edit `config.json`:
```json
{
  "api_key": "your_kite_api_key",
  "api_secret": "your_kite_api_secret",
  "telegram_token": "your_telegram_bot_token",
  "telegram_chat_id": "your_chat_id",
  "trading": {
    "instrument": "SENSEX",
    "paper_trading": true
  }
}
```

## 📝 Development

### Branching Strategy
- `main`: Production-ready code
- `develop`: Development branch
- `feature/*`: New features
- `hotfix/*`: Urgent fixes

### Testing
```bash
source venv/bin/activate
pytest tests/ -v --cov=modules
```

## 📊 Monitoring

- **Logs**: `tail -f logs/system.log`
- **Database**: `sqlite3 data/trading.db`
- **Telegram**: Real-time alerts
- **System Status**: `sudo systemctl status pivot-trading`

## 🔐 Security

- Never commit `config.json` or `data/access_token.txt`
- Use environment variables for production
- Restrict EC2 security group (port 5000 only for OAuth)
- Regular database backups

## ⚠️ Disclaimer

This is for educational purposes. Trading involves risk. Test thoroughly with paper trading before live trading.

---

**Version**: 1.0.0  
**Last Updated**: October 25, 2025  
**Status**: Core modules complete, ready for integration testing
