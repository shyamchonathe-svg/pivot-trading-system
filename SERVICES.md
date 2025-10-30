# System Services Guide
## Pivot Trading System - Service Management

**Date**: October 28, 2025  
**Services**: 3 systemd services for hands-free operation

---

## 📋 All Services Overview

| Service Name | Purpose | Port | Auto-Start | Status Check |
|-------------|---------|------|------------|--------------|
| `pivot-auth.service` | OAuth callback server | 8001 | ✅ Yes | `/health` |
| `pivot-trading.service` | Main trading system | - | ✅ Yes | Logs |
| `pivot-bot.service` | Telegram bot | - | ✅ Yes | `/status` |

---

## 🔧 Service 1: pivot-auth.service

### Purpose
Handles OAuth callbacks from Zerodha for daily authentication.

### What It Does
- Runs Flask server on `localhost:8001`
- Receives OAuth redirect from Zerodha
- Stores request_token temporarily
- Provides `/get_token` endpoint for auth_manager
- Shows beautiful success/failure pages

### File Location
```
/etc/systemd/system/pivot-auth.service
```

### Service Configuration
```ini
[Unit]
Description=Pivot Trading Authentication Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/pivot-trading-system
Environment="PATH=/home/ubuntu/pivot-trading-system/venv/bin"
ExecStart=/home/ubuntu/pivot-trading-system/venv/bin/python auth_server.py
Restart=always
RestartSec=10
StandardOutput=append:/home/ubuntu/pivot-trading-system/logs/auth_server.log
StandardError=append:/home/ubuntu/pivot-trading-system/logs/auth_server_error.log

[Install]
WantedBy=multi-user.target
```

### Commands
```bash
# Check status
sudo systemctl status pivot-auth.service

# Start
sudo systemctl start pivot-auth.service

# Stop
sudo systemctl stop pivot-auth.service

# Restart
sudo systemctl restart pivot-auth.service

# Enable (auto-start on boot)
sudo systemctl enable pivot-auth.service

# Disable (don't auto-start)
sudo systemctl disable pivot-auth.service

# View live logs
sudo journalctl -u pivot-auth.service -f

# View last 100 lines
sudo journalctl -u pivot-auth.service -n 100
```

### Health Check
```bash
# From server
curl http://localhost:8001/health
# Should return: {"status": "ok", "server": "running"}

# From outside
curl https://sensexbot.ddns.net/health
# Should also work (via nginx)
```

### Log Files
```
logs/auth_server.log       - Main logs
logs/auth_server_error.log - Error logs
```

### Troubleshooting
```bash
# Port 8001 already in use?
sudo lsof -i :8001
sudo netstat -tlnp | grep 8001

# Service won't start?
# Check logs
sudo journalctl -u pivot-auth.service -n 50

# Common issues:
# 1. Port already used → Kill other process or change port
# 2. Permission denied → Check file permissions
# 3. Module not found → Check venv path
```

---

## 🔧 Service 2: pivot-trading.service

### Purpose
Main trading system - runs the trading loop, manages positions, sends signals.

### What It Does
- Authenticates with Zerodha (8:00-8:15 AM)
- Calculates pivots (8:45 AM)
- Runs trading loop (9:15 AM - 3:15 PM)
- Monitors positions every 3 minutes
- Generates entry/exit signals
- Sends Telegram notifications
- EOD cleanup (3:15 PM)
- Sleeps until next day

### Dependencies
- Requires: `pivot-auth.service` (must be running first)
- Network access
- Valid config.json

### File Location
```
/etc/systemd/system/pivot-trading.service
```

### Service Configuration
```ini
[Unit]
Description=Pivot Trading System
After=network.target pivot-auth.service
Requires=pivot-auth.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/pivot-trading-system
Environment="PATH=/home/ubuntu/pivot-trading-system/venv/bin"
ExecStart=/home/ubuntu/pivot-trading-system/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=append:/home/ubuntu/pivot-trading-system/logs/trading.log
StandardError=append:/home/ubuntu/pivot-trading-system/logs/trading_error.log

[Install]
WantedBy=multi-user.target
```

### Commands
```bash
# Check status
sudo systemctl status pivot-trading.service

# Start
sudo systemctl start pivot-trading.service

# Stop
sudo systemctl stop pivot-trading.service

# Restart (if config changes)
sudo systemctl restart pivot-trading.service

# Enable (auto-start on boot)
sudo systemctl enable pivot-trading.service

# View live logs
sudo journalctl -u pivot-trading.service -f

# View last 100 lines
sudo journalctl -u pivot-trading.service -n 100 --no-pager
```

### Log Files
```
logs/system_YYYYMMDD.log  - Daily main logs (detailed)
logs/trading.log          - Systemd stdout
logs/trading_error.log    - Systemd stderr
```

### Monitoring
```bash
# Watch real-time activity
tail -f logs/system_$(date +%Y%m%d).log

# Check today's log
cat logs/system_$(date +%Y%m%d).log

# Search for errors
grep -i error logs/system_$(date +%Y%m%d).log

# Search for entry signals
grep "ENTRY SIGNAL" logs/system_$(date +%Y%m%d).log

# Search for exits
grep "EXIT" logs/system_$(date +%Y%m%d).log
```

### Troubleshooting
```bash
# Service failed to start?
sudo journalctl -u pivot-trading.service -n 50

# Check Python errors
tail -50 logs/trading_error.log

# Common issues:
# 1. Auth service not running → Start pivot-auth first
# 2. Config.json not found → Check file exists
# 3. Database locked → Check no other process using it
# 4. Import error → Check venv has all dependencies

# Force restart if stuck
sudo systemctl stop pivot-trading.service
sleep 2
sudo systemctl start pivot-trading.service
```

### Expected Behavior
```
08:00 - Service starts (via cron restart)
08:15 - Authentication check/complete
08:45 - Pre-market setup (ONE Telegram message)
09:15 - Trading loop starts
09:15-15:15 - Entry/exit signals as they occur
15:15 - EOD cleanup (ONE summary message)
15:16 - System sleeps (no more logs until next day)
```

---

## 🔧 Service 3: pivot-bot.service

### Purpose
Telegram bot for system control and monitoring.

### What It Does
- Listens for Telegram commands 24/7
- Provides system status (/status)
- Controls trading (/enable, /disable, /panic)
- Shows reports (/trades, /summary)
- Monitors server health (/health)
- Updates control state file

### File Location
```
/etc/systemd/system/pivot-bot.service
```

### Service Configuration
```ini
[Unit]
Description=Pivot Trading Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/pivot-trading-system
Environment="PATH=/home/ubuntu/pivot-trading-system/venv/bin"
ExecStart=/home/ubuntu/pivot-trading-system/venv/bin/python modules/telegram_bot.py
Restart=always
RestartSec=10
StandardOutput=append:/home/ubuntu/pivot-trading-system/logs/bot.log
StandardError=append:/home/ubuntu/pivot-trading-system/logs/bot_error.log

[Install]
WantedBy=multi-user.target
```

### Commands
```bash
# Check status
sudo systemctl status pivot-bot.service

# Start
sudo systemctl start pivot-bot.service

# Stop
sudo systemctl stop pivot-bot.service

# Restart (after bot code changes)
sudo systemctl restart pivot-bot.service

# Enable
sudo systemctl enable pivot-bot.service

# View logs
sudo journalctl -u pivot-bot.service -f
```

### Log Files
```
logs/bot.log        - Main bot logs
logs/bot_error.log  - Error logs
```

### Testing
```
# Send these in Telegram:
/start   - Should show command list
/status  - Should show system status
/health  - Should show server metrics
```

### Troubleshooting
```bash
# Bot not responding?
sudo systemctl status pivot-bot.service

# Check logs
tail -50 logs/bot.log
tail -50 logs/bot_error.log

# Common issues:
# 1. Invalid token → Check config.json telegram_token
# 2. Network error → Check internet connection
# 3. Module error → Check dependencies installed

# Restart bot
sudo systemctl restart pivot-bot.service
```

---

## 🔄 Daily Restart (Cron Jobs)

### Why Daily Restart?
- Fresh authentication daily
- Clear memory leaks (if any)
- Reload configuration changes
- Ensure clean state

### Cron Configuration
```bash
# View current cron
crontab -l

# Should see:
0 8 * * 1-5 /usr/bin/systemctl restart pivot-auth.service
1 8 * * 1-5 /usr/bin/systemctl restart pivot-trading.service
```

### Edit Cron
```bash
# Edit crontab
crontab -e

# Add these lines:
0 8 * * 1-5 /usr/bin/systemctl restart pivot-auth.service
1 8 * * 1-5 /usr/bin/systemctl restart pivot-trading.service

# Save and exit (Ctrl+X, Y, Enter in nano)
```

### Cron Explanation
```
0 8 * * 1-5  - Run at 08:00 on Mon-Fri
│ │ │ │ │
│ │ │ │ └─── Day of week (1-5 = Mon-Fri)
│ │ │ └───── Month (1-12)
│ │ └─────── Day of month (1-31)
│ └───────── Hour (0-23)
└─────────── Minute (0-59)
```

### Test Cron
```bash
# Run manually
sudo systemctl restart pivot-auth.service
sudo systemctl restart pivot-trading.service

# Check if services restarted
sudo systemctl status pivot-auth.service | grep "Active:"
sudo systemctl status pivot-trading.service | grep "Active:"
```

---

## 📊 All Services Quick Check

### One Command Status
```bash
# Check all services at once
for service in pivot-auth pivot-trading pivot-bot; do
    echo "=== $service.service ==="
    sudo systemctl is-active $service.service
done
```

### Quick Health Check Script
```bash
# Create health check script
cat > check_services.sh << 'EOF'
#!/bin/bash
echo "=== Pivot Trading System Health Check ==="
echo ""
echo "Auth Server:"
sudo systemctl is-active pivot-auth.service
curl -s http://localhost:8001/health | jq .

echo ""
echo "Trading System:"
sudo systemctl is-active pivot-trading.service

echo ""
echo "Telegram Bot:"
sudo systemctl is-active pivot-bot.service

echo ""
echo "Recent Activity:"
tail -5 logs/system_$(date +%Y%m%d).log 2>/dev/null || echo "No logs today yet"
EOF

chmod +x check_services.sh

# Run it
./check_services.sh
```

---

## 🚀 Common Operations

### Daily Startup (Automated at 8 AM)
```bash
# Cron runs these automatically:
sudo systemctl restart pivot-auth.service
sleep 1
sudo systemctl restart pivot-trading.service

# You should receive Telegram notification within 2-3 minutes
```

### Manual Startup (If needed)
```bash
# Start all services
sudo systemctl start pivot-auth.service
sudo systemctl start pivot-trading.service
sudo systemctl start pivot-bot.service

# Verify all started
sudo systemctl status pivot-auth.service --no-pager | grep "Active:"
sudo systemctl status pivot-trading.service --no-pager | grep "Active:"
sudo systemctl status pivot-bot.service --no-pager | grep "Active:"
```

### Graceful Shutdown
```bash
# Stop trading (keeps services running)
# Send in Telegram: /disable

# Stop all services
sudo systemctl stop pivot-trading.service
sudo systemctl stop pivot-bot.service
sudo systemctl stop pivot-auth.service
```

### Configuration Changes
```bash
# 1. Edit config.json
nano config.json

# 2. Restart trading service
sudo systemctl restart pivot-trading.service

# 3. Restart bot (if bot-related changes)
sudo systemctl restart pivot-bot.service

# 4. Verify via Telegram
# Send: /config
```

### Update Code (from GitHub)
```bash
# 1. Stop services
sudo systemctl stop pivot-trading.service

# 2. Pull changes
git pull origin main

# 3. Install new dependencies (if any)
source venv/bin/activate
pip install -r requirements.txt

# 4. Start services
sudo systemctl start pivot-trading.service

# 5. Check logs
tail -f logs/system_$(date +%Y%m%d).log
```

---

## 🐛 Troubleshooting Guide

### Service Won't Start
```bash
# Check logs
sudo journalctl -u pivot-trading.service -n 50

# Common fixes:
# 1. Check permissions
ls -la /home/ubuntu/pivot-trading-system/main.py

# 2. Check Python path
which python
# Should be: /home/ubuntu/pivot-trading-system/venv/bin/python

# 3. Test manually
cd /home/ubuntu/pivot-trading-system
source venv/bin/activate
python main.py
# Press Ctrl+C after seeing startup message
```

### Service Keeps Restarting
```bash
# View restart attempts
sudo systemctl status pivot-trading.service

# Check error logs
tail -100 logs/trading_error.log

# Disable auto-restart temporarily
sudo systemctl stop pivot-trading.service
sudo systemctl disable pivot-trading.service

# Run manually to see errors
cd /home/ubuntu/pivot-trading-system
source venv/bin/activate
python main.py
```

### No Telegram Messages
```bash
# Check bot service
sudo systemctl status pivot-bot.service

# Test notifications manually
cd /home/ubuntu/pivot-trading-system
source venv/bin/activate
python -c "
from modules.notifier import TelegramNotifier
import json
config = json.load(open('config.json'))
notifier = TelegramNotifier(config)
notifier.send_message('Test message from server')
"

# If fails, check config
grep telegram_token config.json
grep telegram_chat_id config.json
```

### Database Locked
```bash
# Check if database is in use
sudo lsof | grep trading.db

# If multiple processes, kill extras
sudo systemctl stop pivot-trading.service
# Wait 5 seconds
sudo systemctl start pivot-trading.service
```

---

## 📅 Maintenance Schedule

### Daily (Automated)
- ✅ Services restart at 8:00 AM (cron)
- ✅ New authentication (if token expired)
- ✅ Log rotation (new daily log file)

### Weekly (Manual)
- Check disk space: `df -h`
- Review error logs: `grep -i error logs/*.log`
- Check service status: `./check_services.sh`

### Monthly (Manual)
- Confirm No-IP renewal email
- Review monthly performance: `/summary` in Telegram
- Update holidays in config.json (if needed)
- Check SSL certificate: `sudo certbot certificates`

### Quarterly (Manual)
- Update Python packages: `pip install -U -r requirements.txt`
- Pull latest code: `git pull origin main`
- Backup database: `cp data/trading.db backups/trading_$(date +%Y%m%d).db`

---

## 🔒 Security Checklist

### File Permissions
```bash
# Config file (contains secrets)
chmod 600 config.json

# Data directory
chmod 700 data/

# Service files
sudo chmod 644 /etc/systemd/system/pivot-*.service
```

### Service User
```bash
# All services run as 'ubuntu' user (not root)
ps aux | grep python | grep pivot
```

### Network Access
```bash
# Check open ports
sudo netstat -tlnp | grep LISTEN

# Should see:
# Port 8001: Only listening on 127.0.0.1 (localhost)
# Port 80, 443: nginx (public)
```

---

## 📚 Quick Reference

### Start All
```bash
sudo systemctl start pivot-auth.service
sudo systemctl start pivot-trading.service  
sudo systemctl start pivot-bot.service
```

### Stop All
```bash
sudo systemctl stop pivot-trading.service
sudo systemctl stop pivot-bot.service
sudo systemctl stop pivot-auth.service
```

### Restart All
```bash
sudo systemctl restart pivot-auth.service
sudo systemctl restart pivot-trading.service
sudo systemctl restart pivot-bot.service
```

### View All Logs
```bash
tail -f logs/system_$(date +%Y%m%d).log \
        logs/auth_server.log \
        logs/bot.log
```

### Emergency Stop
```bash
# Stop trading immediately
# Send in Telegram: /panic

# Or stop services
sudo systemctl stop pivot-trading.service
```

---

## ✅ Service Health Indicators

### Healthy System
```
✅ All 3 services show "active (running)"
✅ Telegram bot responds to /status
✅ Daily logs being created
✅ Startup message received at 8 AM
✅ Pre-market message received at 8:45 AM
```

### Unhealthy System
```
❌ Service status shows "failed" or "inactive"
❌ No Telegram messages received
❌ Logs show repeated errors
❌ No new log entries for hours
❌ /status command returns error
```

### Recovery Steps
```bash
# 1. Check services
sudo systemctl status pivot-*.service

# 2. Restart failed services
sudo systemctl restart <service-name>

# 3. Check logs
tail -100 logs/*_error.log

# 4. Test manually if needed
cd /home/ubuntu/pivot-trading-system
source venv/bin/activate
python main.py
```

---

**Created**: October 28, 2025  
**Services**: 3 systemd services  
**Status**: ✅ Production Ready
