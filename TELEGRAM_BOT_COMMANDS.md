# Telegram Bot Commands Reference

## Quick Command List

### Trading Control
- `/enable` - Enable trading (allows new positions)
- `/disable` - Disable trading (monitor only, no new entries)
- `/panic` - 🚨 EMERGENCY: Close all positions immediately

### System Status
- `/status` - Overall system status, open positions, today's P&L
- `/health` - Server health (CPU, RAM, Disk, Uptime)
- `/config` - View current configuration

### Trading Reports
- `/trades` - Today's trades list
- `/summary` - Daily and monthly summary with statistics

### Configuration
- `/setlots <number>` - Change lot size (e.g., `/setlots 15`)
- `/setmaxre <number>` - Change max re-entries (pending implementation)

### Information
- `/reminders` - View upcoming renewals (SSL, No-IP, etc.)
- `/start` or `/help` - Show all available commands

## When to Use Each Command

### Daily Monitoring
**Morning (8:00-9:00 AM)**:
- Check Telegram for auth request (if token expired)
- Optional: `/status` to verify system started

**During Trading (9:15 AM - 3:15 PM)**:
- System sends automatic entry/exit alerts
- Use `/trades` to see current trades
- Use `/disable` if you want to stop trading (high VIX, busy day)

**End of Day (3:15 PM)**:
- Automatic daily summary sent
- Optional: `/summary` for detailed breakdown

### Emergency Situations
**High VIX / Market Crash**:
```
/disable  → Stop new entries
/panic    → Close all positions + disable trading
```

**System Issues**:
```
/health   → Check if server is overloaded
/status   → Check if services are running
```

### Configuration Changes
**Change Position Size**:
```
/setlots 15  → Changes from 10 to 15 lots
              ⚠️ Requires service restart
              sudo systemctl restart pivot-trading.service
```

### Weekly/Monthly Reviews
```
/summary  → View month-to-date performance
            - Total trades
            - Win rate
            - Total P&L
```

## Response Examples

### /status Output
```
📊 System Status

Trading: ✅ ENABLED
Mode: ✅ Normal

Services:
Auth Server: ✅ Running
Trading System: ✅ Running

Today (2025-10-28):
Open Positions: 1
Total Trades: 3
Wins: 2
P&L: ₹377.00

Last Updated: 2025-10-28T14:30:00
```

### /health Output
```
🏥 Server Health Check

Status: ✅ Healthy

CPU: 12.5%
Memory: 46.1%
0.41 GB / 0.89 GB

Disk: 64.4%
4.87 GB / 7.57 GB

Uptime: 99d 2h 48m

Timestamp: 2025-10-28 14:30:00 IST
```

### /summary Output
```
📊 Trading Summary

Today (2025-10-28):
Trades: 3
Wins: 2 | Losses: 1
Win Rate: 66.7%
Total P&L: ₹377.00
Avg P&L: ₹125.67
Best: ₹200.00
Worst: -₹50.00

This Month:
Total Trades: 15
Wins: 10
Win Rate: 66.7%
Total P&L: ₹1,234.50
```

### /trades Output
```
📈 Today's Trades (3)

20251028_001
SENSEX25OCT84300CE
Entry: ₹145.00 @ 09:18:00
Exit: ₹165.00 @ 09:30:00
P&L: ₹200.00 (TARGET)

20251028_002
SENSEX25OCT84500CE
Entry: ₹123.00 @ 10:21:00
Exit: ₹143.00 @ 10:45:00
P&L: ₹200.00 (TARGET)

20251028_003
SENSEX25OCT84700CE
Entry: ₹98.00 @ 11:15:00
Exit: ₹93.00 @ 11:27:00
P&L: -₹50.00 (STOP_LOSS)
```

## Interactive Buttons

Some commands show interactive buttons:

### /status Buttons
```
[🟢 Enable / 🔴 Disable]  [🚨 Panic]
[📊 Health]               [📈 Trades]
```

Click buttons for quick actions without typing commands.

## Tips

1. **Save this bot in Telegram favorites** for quick access
2. **Enable notifications** to get real-time trade alerts
3. **Check /status once daily** to ensure system is running
4. **Use /panic sparingly** - it closes ALL positions at market price
5. **After /setlots**, restart service for changes to take effect

## Troubleshooting

**Bot not responding?**
```bash
# SSH to server
sudo systemctl status pivot-bot.service
sudo systemctl restart pivot-bot.service
```

**Commands returning errors?**
```bash
# Check bot logs
tail -50 logs/bot.log
```

**Want to add new commands?**
- Edit: `modules/telegram_bot.py`
- Restart: `sudo systemctl restart pivot-bot.service`

---

**Bot Token**: Stored in config.json (never share!)  
**Chat ID**: Your Telegram user ID  
**Bot Username**: @YourBotName (check with BotFather)
