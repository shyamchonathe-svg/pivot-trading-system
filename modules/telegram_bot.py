"""
Telegram Bot Command Handler
Provides interactive control via Telegram commands
"""

import json
import sqlite3
import subprocess
import psutil
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import logging

logger = logging.getLogger(__name__)


class TradingBotCommands:
    def __init__(self, config_path='config.json'):
        self.config = self.load_config(config_path)
        self.config_path = config_path
        self.db_path = self.config['data']['database_path']
        self.control_file = 'data/trading_control.json'
        self.load_control_state()
    
    def load_config(self, path):
        with open(path, 'r') as f:
            return json.load(f)
    
    def save_config(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def load_control_state(self):
        """Load trading control state"""
        try:
            with open(self.control_file, 'r') as f:
                self.control = json.load(f)
        except:
            self.control = {
                'trading_enabled': True,
                'panic_mode': False,
                'last_updated': None
            }
            self.save_control_state()
    
    def save_control_state(self):
        """Save trading control state"""
        self.control['last_updated'] = datetime.now().isoformat()
        with open(self.control_file, 'w') as f:
            json.dump(self.control, f, indent=2)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - show help"""
        help_text = """
🤖 *Pivot Trading Bot Commands*

*Trading Control:*
/status - System status & current positions
/enable - Enable trading
/disable - Disable trading
/panic - Emergency: Close all positions

*Monitoring:*
/health - Server health (CPU, Memory, Disk)
/trades - Today's trades
/summary - Daily/Monthly summary
/logs - Recent system logs

*Configuration:*
/config - View current settings
/setlots <number> - Change lot size
/setmaxre <number> - Max re-entries per day

*Reports:*
/day - Today's detailed report
/week - This week's performance
/month - This month's statistics

*Reminders:*
/reminders - View upcoming renewals
/setreminder - Setup reminder

Type /help anytime to see this message.
"""
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get current system status"""
        try:
            # Trading status
            trading_status = "✅ ENABLED" if self.control['trading_enabled'] else "⛔ DISABLED"
            panic_status = "🚨 PANIC MODE" if self.control['panic_mode'] else "✅ Normal"
            
            # Check if services are running
            auth_running = self.is_service_running('pivot-auth.service')
            trading_running = self.is_service_running('pivot-trading.service')
            
            # Get open positions
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM trades 
                WHERE date = ? AND exit_time IS NULL
            """, (date.today(),))
            open_positions = cursor.fetchone()[0]
            
            # Today's stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as trades,
                    SUM(CASE WHEN pnl_rupees > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(pnl_rupees) as pnl
                FROM trades
                WHERE date = ?
            """, (date.today(),))
            stats = cursor.fetchone()
            conn.close()
            
            # Handle None values safely
            total_trades = stats[0] or 0
            total_wins = stats[1] or 0
            total_pnl = stats[2] if stats[2] is not None else 0.0
            
            message = f"""
📊 *System Status*

*Trading:* {trading_status}
*Mode:* {panic_status}

*Services:*
Auth Server: {'✅ Running' if auth_running else '❌ Stopped'}
Trading System: {'✅ Running' if trading_running else '❌ Stopped'}

*Today ({date.today()}):*
Open Positions: {open_positions}
Total Trades: {total_trades}
Wins: {total_wins}
P&L: ₹{total_pnl:.2f}

*Last Updated:* {self.control['last_updated'] or 'Never'}
"""
            
            # Add control buttons
            keyboard = [
                [
                    InlineKeyboardButton("🟢 Enable" if not self.control['trading_enabled'] else "🔴 Disable", 
                                       callback_data='toggle_trading'),
                    InlineKeyboardButton("🚨 Panic", callback_data='panic')
                ],
                [
                    InlineKeyboardButton("📊 Health", callback_data='health'),
                    InlineKeyboardButton("📈 Trades", callback_data='trades')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def health(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Server health check"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_gb = memory.used / (1024**3)
            memory_total_gb = memory.total / (1024**3)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_used_gb = disk.used / (1024**3)
            disk_total_gb = disk.total / (1024**3)
            
            # Uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            
            status = "✅ Healthy"
            if cpu_percent > 80 or memory_percent > 90 or disk_percent > 90:
                status = "⚠️ Warning"
            
            message = f"""
🏥 *Server Health Check*

*Status:* {status}

*CPU:* {cpu_percent}%
{'⚠️ High CPU usage!' if cpu_percent > 80 else ''}

*Memory:* {memory_percent}%
{memory_used_gb:.2f} GB / {memory_total_gb:.2f} GB
{'⚠️ High memory usage!' if memory_percent > 90 else ''}

*Disk:* {disk_percent}%
{disk_used_gb:.2f} GB / {disk_total_gb:.2f} GB
{'⚠️ Low disk space!' if disk_percent > 90 else ''}

*Uptime:* {uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m

*Timestamp:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}
"""
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def enable_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enable trading"""
        self.control['trading_enabled'] = True
        self.control['panic_mode'] = False
        self.save_control_state()
        
        await update.message.reply_text(
            "✅ *Trading Enabled*\n\nSystem will now process entry signals.",
            parse_mode='Markdown'
        )
    
    async def disable_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Disable trading"""
        self.control['trading_enabled'] = False
        self.save_control_state()
        
        await update.message.reply_text(
            "⛔ *Trading Disabled*\n\nNo new positions will be opened.\nExisting positions will continue to be monitored.",
            parse_mode='Markdown'
        )
    
    async def panic(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Emergency: Close all positions"""
        try:
            # Set panic mode
            self.control['panic_mode'] = True
            self.control['trading_enabled'] = False
            self.save_control_state()
            
            # Get open positions
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM trades 
                WHERE date = ? AND exit_time IS NULL
            """, (date.today(),))
            open_positions = cursor.fetchone()[0]
            conn.close()
            
            message = f"""
🚨 *PANIC MODE ACTIVATED*

Trading disabled immediately.
Closing {open_positions} open position(s).

The system will exit all positions at market price on the next cycle.

To resume normal operation:
/enable - Re-enable trading
"""
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def trades_today(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show today's trades"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    trade_id, symbol, entry_time, exit_time,
                    entry_price, exit_price, pnl_rupees, exit_reason
                FROM trades
                WHERE date = ?
                ORDER BY entry_time DESC
            """, (date.today(),))
            
            trades = cursor.fetchall()
            conn.close()
            
            if not trades:
                await update.message.reply_text("No trades today.")
                return
            
            message = f"📈 *Today's Trades* ({len(trades)})\n\n"
            
            for trade in trades:
                trade_id, symbol, entry_time, exit_time, entry_price, exit_price, pnl, reason = trade
                status = "🟢 OPEN" if exit_time is None else ("✅ WIN" if pnl > 0 else "❌ LOSS")
                
                message += f"*{trade_id}*\n"
                message += f"{symbol}\n"
                message += f"Entry: ₹{entry_price:.2f} @ {entry_time}\n"
                if exit_time:
                    message += f"Exit: ₹{exit_price:.2f} @ {exit_time}\n"
                    message += f"P&L: ₹{pnl:.2f} ({reason})\n"
                else:
                    message += f"Status: {status}\n"
                message += "\n"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Daily and monthly summary"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Today's summary
            cursor.execute("""
                SELECT 
                    COUNT(*) as trades,
                    SUM(CASE WHEN pnl_rupees > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pnl_rupees < 0 THEN 1 ELSE 0 END) as losses,
                    SUM(pnl_rupees) as total_pnl,
                    AVG(pnl_rupees) as avg_pnl,
                    MAX(pnl_rupees) as best_trade,
                    MIN(pnl_rupees) as worst_trade
                FROM trades
                WHERE date = ?
            """, (date.today(),))
            today = cursor.fetchone()
            
            # This month
            cursor.execute("""
                SELECT 
                    COUNT(*) as trades,
                    SUM(CASE WHEN pnl_rupees > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(pnl_rupees) as total_pnl
                FROM trades
                WHERE strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
            """, ())
            month = cursor.fetchone()
            
            conn.close()
            
            win_rate_today = (today[1] / today[0] * 100) if today[0] and today[0] > 0 else 0
            win_rate_month = (month[1] / month[0] * 100) if month[0] and month[0] > 0 else 0
            
            # Handle None values safely
            today_trades = today[0] or 0
            today_wins = today[1] or 0
            today_losses = today[2] or 0
            today_pnl = today[3] if today[3] is not None else 0.0
            today_avg = today[4] if today[4] is not None else 0.0
            today_best = today[5] if today[5] is not None else 0.0
            today_worst = today[6] if today[6] is not None else 0.0
            
            month_trades = month[0] or 0
            month_wins = month[1] or 0
            month_pnl = month[2] if month[2] is not None else 0.0
            
            message = f"""
📊 *Trading Summary*

*Today ({date.today()}):*
Trades: {today_trades}
Wins: {today_wins} | Losses: {today_losses}
Win Rate: {win_rate_today:.1f}%
Total P&L: ₹{today_pnl:.2f}
Avg P&L: ₹{today_avg:.2f}
Best: ₹{today_best:.2f}
Worst: ₹{today_worst:.2f}

*This Month:*
Total Trades: {month_trades}
Wins: {month_wins}
Win Rate: {win_rate_month:.1f}%
Total P&L: ₹{month_pnl:.2f}
"""
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def set_lot_size(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Change lot size"""
        try:
            if not context.args or len(context.args) != 1:
                await update.message.reply_text("Usage: /setlots <number>\nExample: /setlots 15")
                return
            
            new_lot_size = int(context.args[0])
            
            if new_lot_size < 1 or new_lot_size > 50:
                await update.message.reply_text("❌ Lot size must be between 1 and 50")
                return
            
            old_lot_size = self.config['trading']['lot_size']
            self.config['trading']['lot_size'] = new_lot_size
            self.save_config()
            
            await update.message.reply_text(
                f"✅ *Lot Size Updated*\n\nOld: {old_lot_size}\nNew: {new_lot_size}\n\n⚠️ Restart required: /restart",
                parse_mode='Markdown'
            )
            
        except ValueError:
            await update.message.reply_text("❌ Invalid number. Usage: /setlots <number>")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def config_view(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View current configuration"""
        trading = self.config['trading']
        
        message = f"""
⚙️ *Current Configuration*

*Trading Settings:*
Instrument: {trading['instrument']}
Lot Size: {trading['lot_size']}
Strike Range: ±{trading['strike_range']}
Max Re-entries: {trading['max_re_entries']}
Paper Trading: {'Yes' if trading['paper_trading'] else 'No'}

*Percentile:* {trading['candle_size_percentile']}th
*Timeout:* {trading['max_candles_timeout']} candles

*Market Hours:*
Start: {self.config['market']['start_time']}
End: {self.config['market']['end_time']}
EOD Exit: {self.config['market']['eod_exit_time']}

To modify settings, use:
/setlots <number>
/setmaxre <number>
"""
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def reminders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show upcoming renewals"""
        message = """
📅 *Upcoming Renewals & Reminders*

*SSL Certificate:*
Expires: Nov 8, 2025
Auto-renews: ✅ Yes (Let's Encrypt)
Action: None required

*No-IP DDNS:*
Renewal: Monthly (manual confirmation)
Next: Check email
Action: ⚠️ Must confirm monthly

*Kite API:*
Access Token: Daily (auto-handled)
API Key: Never expires
Action: None required

*AWS EC2:*
Instance: On-demand billing
Action: Monitor costs

*Domain Renewal:*
sensexbot.ddns.net: Free (No-IP)
Action: Confirm monthly email

To setup custom reminders:
/setreminder <days> <message>
"""
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'toggle_trading':
            if self.control['trading_enabled']:
                await self.disable_trading(update, context)
            else:
                await self.enable_trading(update, context)
        
        elif query.data == 'panic':
            await self.panic(update, context)
        
        elif query.data == 'health':
            await self.health(update, context)
        
        elif query.data == 'trades':
            await self.trades_today(update, context)
    
    def is_service_running(self, service_name):
        """Check if systemd service is running"""
        try:
            # Method 1: Try systemctl
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True,
                text=True
            )
            if result.stdout.strip() == 'active':
                return True
            
            # Method 2: Fallback - check process
            if 'auth' in service_name:
                result = subprocess.run(['pgrep', '-f', 'auth_server.py'], capture_output=True)
            elif 'trading' in service_name:
                result = subprocess.run(['pgrep', '-f', 'main.py'], capture_output=True)
            else:
                return False
            
            return result.returncode == 0
        except:
            return False
    
    def setup_bot(self):
        """Setup Telegram bot with all handlers"""
        app = Application.builder().token(self.config['telegram_token']).build()
        
        # Command handlers
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.start))
        app.add_handler(CommandHandler("status", self.status))
        app.add_handler(CommandHandler("health", self.health))
        app.add_handler(CommandHandler("enable", self.enable_trading))
        app.add_handler(CommandHandler("disable", self.disable_trading))
        app.add_handler(CommandHandler("panic", self.panic))
        app.add_handler(CommandHandler("trades", self.trades_today))
        app.add_handler(CommandHandler("summary", self.summary))
        app.add_handler(CommandHandler("config", self.config_view))
        app.add_handler(CommandHandler("setlots", self.set_lot_size))
        app.add_handler(CommandHandler("reminders", self.reminders))
        
        # Button handler
        app.add_handler(CallbackQueryHandler(self.button_handler))
        
        return app


def main():
    """Run bot in polling mode"""
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    bot = TradingBotCommands()
    app = bot.setup_bot()
    
    print("🤖 Telegram Bot Started!")
    print("Send /start to your bot to see available commands")
    
    app.run_polling()


if __name__ == '__main__':
    main()
