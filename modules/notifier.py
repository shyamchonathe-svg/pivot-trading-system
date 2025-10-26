"""
Telegram Notifier Module
Sends trading alerts and system notifications via Telegram
"""

import requests
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, config):
        """
        Initialize Telegram notifier
        
        Args:
            config: Configuration dictionary with telegram_token and telegram_chat_id
        """
        self.token = config.get('telegram_token')
        self.chat_id = config.get('telegram_chat_id')
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.enabled = config.get('notifications', {})
        
        if not self.token or not self.chat_id:
            logger.warning("Telegram credentials not configured")
    
    def send_message(self, message, parse_mode='HTML'):
        """
        Send message via Telegram
        
        Args:
            message: Message text
            parse_mode: 'HTML' or 'Markdown'
        
        Returns:
            True if successful
        """
        try:
            if not self.token or not self.chat_id:
                logger.warning("Cannot send Telegram message: credentials not configured")
                return False
            
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                logger.info("Telegram message sent successfully")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def send_authentication_request(self, login_url):
        """Send authentication request with login link"""
        if not self.enabled.get('send_auth_requests', True):
            return False
        
        ist_time = datetime.now(self.ist_tz).strftime("%Y-%m-%d %H:%M:%S IST")
        
        message = f"""
🔐 <b>DAILY AUTHENTICATION REQUIRED</b>

📅 Time: {ist_time}
⚠️ Trading system needs authentication to start

<b>👉 Click link to authenticate:</b>
<a href="{login_url}">🔗 Login to Zerodha</a>

<b>⏰ Important:</b>
• Authentication link valid for 5 minutes
• System will NOT trade without authentication
• Complete login and 2FA within timeout

<b>🚨 What happens next:</b>
1. Click link above
2. Login to Zerodha
3. Complete 2FA verification
4. System will auto-start trading

⏳ Waiting for authentication...
        """
        
        return self.send_message(message)
    
    def send_authentication_success(self, user_name, token_preview):
        """Send authentication success notification"""
        if not self.enabled.get('send_auth_requests', True):
            return False
        
        ist_time = datetime.now(self.ist_tz).strftime("%Y-%m-%d %H:%M:%S IST")
        
        message = f"""
✅ <b>AUTHENTICATION SUCCESSFUL!</b>

📅 Time: {ist_time}
👤 User: {user_name}
🔑 Token: <code>{token_preview}</code>

<b>🚀 System Status:</b>
• Authentication: ✅ Complete
• Token: ✅ Saved
• Trading System: 🟢 Starting...

<b>📊 Next Steps:</b>
Pre-market setup starting at 8:45 AM
Trading will begin at 9:15 AM

<b>💡 System Ready!</b>
You will receive alerts for:
• Entry signals
• Exit signals  
• Daily P&L summary
• Any errors or issues
        """
        
        return self.send_message(message)
    
    def send_authentication_failure(self, error_reason):
        """Send authentication failure notification"""
        if not self.enabled.get('send_auth_requests', True):
            return False
        
        ist_time = datetime.now(self.ist_tz).strftime("%Y-%m-%d %H:%M:%S IST")
        
        message = f"""
❌ <b>AUTHENTICATION FAILED</b>

📅 Time: {ist_time}
⚠️ Reason: {error_reason}

<b>🔧 Possible Issues:</b>
• Authentication timeout (5 minutes)
• Invalid Zerodha credentials
• Network connectivity problem
• 2FA not completed

<b>🔄 What to do:</b>
1. Check your Zerodha credentials
2. Ensure stable internet connection
3. Restart system to try again
4. Check logs for detailed error

<b>📞 Need Help?</b>
Check system logs: <code>tail -f logs/system.log</code>

🚨 <b>System cannot trade without authentication!</b>
        """
        
        return self.send_message(message)
    
    def send_entry_signal(self, signal, position):
        """Send entry signal notification"""
        if not self.enabled.get('send_entry_signals', True):
            return False
        
        ist_time = datetime.now(self.ist_tz).strftime("%Y-%m-%d %H:%M:%S IST")
        
        entry_type = "First Candle (9:15-9:18 AM)" if signal.is_first_candle else "Intraday"
        
        message = f"""
🚀 <b>ENTRY SIGNAL</b>

📅 Time: {ist_time}

<b>📊 Instrument Details:</b>
Symbol: <code>{signal.symbol}</code>
Strike: {signal.strike} {signal.option_type}
Entry Price: ₹{signal.entry_price:.2f}

<b>🎯 Trade Setup:</b>
Scenario: {signal.scenario}
Entry Type: {entry_type}
Structure: {signal.structure}

<b>💰 Risk Management:</b>
Stop Loss: ₹{signal.stop_loss:.2f}
Target: ₹{signal.target:.2f}
Lot Size: {position.lot_size}

<b>📈 Pivot Levels:</b>
PP: {signal.pivots['PP']:.2f}
R1: {signal.pivots['R1']:.2f} | R2: {signal.pivots['R2']:.2f} | R3: {signal.pivots['R3']:.2f}
S1: {signal.pivots['S1']:.2f}

<b>📋 Signal Details:</b>
Candle: O:{signal.candle_data['open']:.2f} H:{signal.candle_data['high']:.2f} L:{signal.candle_data['low']:.2f} C:{signal.candle_data['close']:.2f}
Size: {signal.candle_data['size_percent']:.2f}% (Significant ✅)

<b>🎯 Trade Objective:</b>
Expected Risk: ₹{abs(signal.entry_price - signal.stop_loss) * position.lot_size:.2f}
Expected Reward: ₹{abs(signal.target - signal.entry_price) * position.lot_size:.2f}

📍 Trade ID: <code>{position.trade_id}</code>

🔔 Monitoring position for exit conditions...
        """
        
        return self.send_message(message)
    
    def send_exit_signal(self, trade_result):
        """Send exit signal notification"""
        if not self.enabled.get('send_exit_signals', True):
            return False
        
        ist_time = datetime.now(self.ist_tz).strftime("%Y-%m-%d %H:%M:%S IST")
        
        # Duration calculation
        duration_mins = (trade_result.exit_time - trade_result.entry_time).total_seconds() / 60
        
        # Emoji based on P&L
        pnl_emoji = "✅" if trade_result.pnl_points > 0 else "❌"
        outcome = "PROFIT" if trade_result.pnl_points > 0 else "LOSS"
        
        # Exit reason emoji
        reason_emoji = {
            'TARGET': '🎯',
            'STOP_LOSS': '🛑',
            '10_CANDLE_TIMEOUT': '⏰',
            'EOD': '🌅'
        }.get(trade_result.exit_reason, '🚪')
        
        message = f"""
🚪 <b>EXIT SIGNAL - {outcome}</b> {pnl_emoji}

📅 Time: {ist_time}

<b>📊 Trade Summary:</b>
Symbol: <code>{trade_result.symbol}</code>
Strike: {trade_result.strike} {trade_result.option_type}
Scenario: {trade_result.scenario}

<b>💰 Entry & Exit:</b>
Entry: ₹{trade_result.entry_price:.2f} @ {trade_result.entry_time.strftime('%H:%M:%S')}
Exit: ₹{trade_result.exit_price:.2f} @ {trade_result.exit_time.strftime('%H:%M:%S')}
Duration: {int(duration_mins)} minutes ({trade_result.candles_held} candles)

<b>📈 P&L:</b>
Points: {trade_result.pnl_points:+.2f}
Rupees: ₹{trade_result.pnl_rupees:+.2f}
Lot Size: {trade_result.lot_size}

<b>{reason_emoji} Exit Reason:</b>
{trade_result.exit_reason.replace('_', ' ').title()}

<b>🎯 Trade Setup Recap:</b>
Target: ₹{trade_result.target:.2f}
Stop Loss: ₹{trade_result.stop_loss:.2f}
First Candle: {'Yes' if trade_result.is_first_candle else 'No'}
Re-entry: {'Yes' if trade_result.re_entry else 'No'}

📍 Trade ID: <code>{trade_result.trade_id}</code>

{'🎉 Congratulations on profitable trade!' if trade_result.pnl_points > 0 else '📊 Trade completed. Analyzing next opportunity...'}
        """
        
        return self.send_message(message)
    
    def send_daily_summary(self, summary):
        """Send end-of-day summary"""
        if not self.enabled.get('send_daily_summary', True):
            return False
        
        ist_time = datetime.now(self.ist_tz).strftime("%Y-%m-%d %H:%M:%S IST")
        
        # Overall emoji
        overall_emoji = "✅" if summary['gross_pnl'] > 0 else "❌" if summary['gross_pnl'] < 0 else "➖"
        
        message = f"""
📊 <b>DAILY TRADING SUMMARY</b> {overall_emoji}

📅 Date: {summary['date']}
🕐 Generated: {ist_time}

<b>📈 Performance:</b>
Total Trades: {summary['total_trades']}
Wins: {summary['wins']} ✅ | Losses: {summary['losses']} ❌
Win Rate: {summary['win_rate']:.2f}%

<b>💰 P&L:</b>
Gross P&L: ₹{summary['gross_pnl']:+.2f}
Max Drawdown: ₹{summary['max_drawdown']:.2f}

<b>📋 Breakdown by Scenario:</b>
Scenario 1 (PP-S1 → R1): {summary['scenario_1_trades']} trades
Scenario 2 (PP-R1 → R2): {summary['scenario_2_trades']} trades
Scenario 3 (R2-R3 → R3): {summary['scenario_3_trades']} trades

<b>⏰ Entry Types:</b>
First Candle: {summary['first_candle_entries']}
Intraday: {summary['intraday_entries']}

<b>🚪 Exit Breakdown:</b>
🎯 Targets Hit: {summary['targets_hit']}
🛑 Stop Losses: {summary['stop_losses']}
⏰ Timeouts: {summary['timeouts']}
🌅 EOD Exits: {summary['eod_exits']}

<b>📊 Trade Quality:</b>
{'🎉 Excellent day! Keep the momentum!' if summary['win_rate'] >= 70 else '👍 Good performance!' if summary['win_rate'] >= 50 else '📈 Room for improvement. Analyze and adapt.'}

<b>💡 Notes:</b>
• Review logs for detailed trade analysis
• Database updated with all trade details
• System will start fresh tomorrow

🌙 <b>End of Trading Day</b>
System shutting down. See you tomorrow! 🚀
        """
        
        return self.send_message(message)
    
    def send_error_alert(self, error_type, error_message, context=None):
        """Send error alert notification"""
        if not self.enabled.get('send_errors', True):
            return False
        
        ist_time = datetime.now(self.ist_tz).strftime("%Y-%m-%d %H:%M:%S IST")
        
        message = f"""
🚨 <b>SYSTEM ERROR ALERT</b>

📅 Time: {ist_time}
❌ Error Type: {error_type}

<b>📝 Error Details:</b>
<code>{error_message[:500]}</code>

{f'<b>📍 Context:</b>\n{context}' if context else ''}

<b>🔧 Action Required:</b>
• Check system logs for details
• Verify system is still running
• Manual intervention may be needed

<b>📋 Debug Commands:</b>
<code>tail -f logs/system.log</code>
<code>systemctl status pivot-trading</code>

⚠️ <b>System may have stopped trading!</b>
Please investigate immediately.
        """
        
        return self.send_message(message)
    
    def send_system_startup(self):
        """Send system startup notification"""
        ist_time = datetime.now(self.ist_tz).strftime("%Y-%m-%d %H:%M:%S IST")
        
        message = f"""
🚀 <b>TRADING SYSTEM STARTED</b>

📅 Time: {ist_time}

<b>✅ System Initialized:</b>
• Core modules loaded
• Database connected
• Configuration validated
• Telegram notifications active

<b>📋 Next Steps:</b>
1. Waiting for authentication (if needed)
2. Pre-market setup at 8:45 AM
3. Trading starts at 9:15 AM

<b>🔔 You will be notified of:</b>
• Authentication requests
• Entry/exit signals
• Daily P&L summary
• Any system errors

🟢 <b>System Ready and Monitoring...</b>
        """
        
        return self.send_message(message)
    
    def send_system_shutdown(self, reason="Normal EOD shutdown"):
        """Send system shutdown notification"""
        ist_time = datetime.now(self.ist_tz).strftime("%Y-%m-%d %H:%M:%S IST")
        
        message = f"""
🌙 <b>TRADING SYSTEM SHUTDOWN</b>

📅 Time: {ist_time}
📝 Reason: {reason}

<b>✅ Cleanup Complete:</b>
• All positions closed
• Data cached cleared
• Logs rotated
• Database updated

<b>📊 Summary:</b>
Daily summary has been generated and saved
Check database for complete trade history

<b>🔄 System Status:</b>
System has stopped gracefully
Will auto-start tomorrow at configured time

😴 <b>Good night! See you tomorrow!</b>
        """
        
        return self.send_message(message)


if __name__ == "__main__":
    # Test notifier
    logging.basicConfig(level=logging.INFO)
    
    test_config = {
        'telegram_token': '8427480734:AAFjkFwNbM9iUo0wa1Biwg8UHmJCvLs5vho',
        'telegram_chat_id': '1639045622',
        'notifications': {
            'send_entry_signals': True,
            'send_exit_signals': True,
            'send_daily_summary': True,
            'send_errors': True,
            'send_auth_requests': True
        }
    }
    
    notifier = TelegramNotifier(test_config)
    
    # Test basic message
    print("Testing basic message...")
    notifier.send_message("🧪 <b>Test Message</b>\n\nTelegram notifier is working!")
    
    print("\n✅ Notifier test complete")
    print("Check your Telegram for the test message!")
