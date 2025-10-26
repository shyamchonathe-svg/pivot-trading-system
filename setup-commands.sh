#!/bin/bash
# Complete setup script for pivot-trading-system repository
# Run this on your EC2 instance after creating the GitHub repo

set -e  # Exit on error

echo "=========================================="
echo "Setting up Pivot Trading System Repository"
echo "=========================================="

# Ensure we're in the right directory
cd ~/pivot-trading-system

# Create directory structure
echo "Creating directory structure..."
mkdir -p modules utils tests scripts data data/cache logs docs systemd

# Create __init__.py files
touch modules/__init__.py
touch utils/__init__.py
touch tests/__init__.py

# Create .gitkeep for empty directories
touch data/.gitkeep
touch logs/.gitkeep

echo "✓ Directory structure created"

# Create .gitignore
echo "Creating .gitignore..."
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
ENV/
env/

# Data & Secrets
data/access_token.txt
data/*.db
data/cache/
config.json

# Logs
logs/*.log
logs/*.txt

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Backup files
*.bak
backup_*.db

# Testing
.pytest_cache/
.coverage
htmlcov/

# Temporary files
*.tmp
*.temp
EOF
echo "✓ .gitignore created"

# Create requirements.txt
echo "Creating requirements.txt..."
cat > requirements.txt << 'EOF'
# Kite Connect API
kiteconnect==4.2.0

# Data processing
pandas==2.0.3
numpy==1.24.3
pytz==2023.3

# Web server for OAuth
flask==3.0.0
requests==2.31.0

# Telegram bot
python-telegram-bot==20.5

# Testing (optional)
pytest==7.4.0
pytest-cov==4.1.0
EOF
echo "✓ requirements.txt created"

# Create README.md
echo "Creating README.md..."
cat > README.md << 'EOF'
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
EOF
echo "✓ README.md created"

# Create CHANGELOG.md
echo "Creating CHANGELOG.md..."
cat > CHANGELOG.md << 'EOF'
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
EOF
echo "✓ CHANGELOG.md created"

# Create config.example.json
echo "Creating config.example.json..."
cat > config.example.json << 'EOF'
{
  "api_key": "your_kite_api_key_here",
  "api_secret": "your_kite_api_secret_here",
  "telegram_token": "your_telegram_bot_token_here",
  "telegram_chat_id": "your_telegram_chat_id_here",
  
  "auth": {
    "callback_host": "0.0.0.0",
    "callback_port": 5000,
    "redirect_url": "http://your-ddns-domain.ddns.net:5000/callback",
    "auth_timeout_seconds": 300
  },
  
  "trading": {
    "instrument": "SENSEX",
    "strike_interval": 100,
    "strike_range": 500,
    "candle_size_percentile": 75,
    "max_candles_timeout": 10,
    "max_re_entries": 1,
    "lot_size": 10,
    "paper_trading": true
  },
  
  "market": {
    "start_time": "09:15",
    "end_time": "15:30",
    "eod_exit_time": "15:15",
    "holidays": [
      "2025-01-26",
      "2025-02-12",
      "2025-03-14",
      "2025-04-10",
      "2025-04-14",
      "2025-05-01",
      "2025-08-15",
      "2025-10-02",
      "2025-10-29",
      "2025-11-14"
    ]
  },
  
  "data": {
    "database_path": "data/trading.db",
    "cache_dir": "data/cache",
    "access_token_file": "data/access_token.txt",
    "log_retention_days": 7
  },
  
  "notifications": {
    "send_entry_signals": true,
    "send_exit_signals": true,
    "send_daily_summary": true,
    "send_errors": true,
    "send_auth_requests": true
  }
}
EOF
echo "✓ config.example.json created"

# Create setup.sh
echo "Creating setup.sh..."
cat > setup.sh << 'SETUPEOF'
#!/bin/bash
# EC2 Setup Script for Pivot Trading System

set -e  # Exit on error

echo "=================================="
echo "Pivot Trading System - EC2 Setup"
echo "=================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running on Ubuntu
if [ ! -f /etc/lsb-release ]; then
    echo -e "${RED}Error: This script is designed for Ubuntu${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Ubuntu detected"

# Update system
echo ""
echo "Updating system packages..."
sudo apt-get update -qq

# Install Python 3 and pip
echo ""
echo "Installing Python 3 and pip..."
sudo apt-get install -y python3 python3-pip python3-venv

# Verify Python version
PYTHON_VERSION=$(python3 --version | cut -d ' ' -f 2)
echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION installed"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate
echo -e "${GREEN}✓${NC} Virtual environment created"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip -q
echo -e "${GREEN}✓${NC} Pip upgraded"

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt -q
echo -e "${GREEN}✓${NC} Dependencies installed"

# Set permissions
echo ""
echo "Setting permissions..."
chmod 700 data
chmod 755 scripts
echo -e "${GREEN}✓${NC} Permissions set"

# Create config from example
if [ ! -f config.json ]; then
    if [ -f config.example.json ]; then
        cp config.example.json config.json
        chmod 600 config.json
        echo -e "${YELLOW}⚠${NC}  Created config.json from example"
        echo -e "${YELLOW}⚠${NC}  Please edit config.json with your credentials"
    fi
else
    echo -e "${GREEN}✓${NC} config.json already exists"
fi

# Summary
echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Edit config.json with your credentials:"
echo "   nano config.json"
echo ""
echo "2. Activate virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "3. Run the system:"
echo "   python main.py"
echo ""
SETUPEOF

chmod +x setup.sh
echo "✓ setup.sh created and made executable"

echo ""
echo "=========================================="
echo "Initial file structure created successfully!"
echo "=========================================="
echo ""
echo "Files created:"
echo "  ✓ .gitignore"
echo "  ✓ requirements.txt"
echo "  ✓ README.md"
echo "  ✓ CHANGELOG.md"
echo "  ✓ config.example.json"
echo "  ✓ setup.sh"
echo ""
echo "Directories created:"
echo "  ✓ modules/"
echo "  ✓ utils/"
echo "  ✓ tests/"
echo "  ✓ scripts/"
echo "  ✓ data/"
echo "  ✓ logs/"
echo "  ✓ docs/"
echo "  ✓ systemd/"
echo ""
echo "Next: Add core module files to modules/ and utils/"
