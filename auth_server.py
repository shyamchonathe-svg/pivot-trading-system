#!/usr/bin/env python3
"""
Authentication Server for Kite Connect
Handles OAuth callback and postback endpoints
Runs on port 8001 (proxied by nginx with SSL)
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from flask import Flask, request, jsonify
import pytz

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/auth_server.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class AuthenticationServer:
    def __init__(self):
        self.app = Flask(__name__)
        self.request_token = None
        self.token_timestamp = None
        self.config = self.load_config()
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.auth_timeout = self.config['auth'].get('auth_timeout_seconds', 300)
        self.setup_routes()
    
    def load_config(self):
        """Load configuration from config.json"""
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
            logger.info("Configuration loaded successfully")
            return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            sys.exit(1)
    
    def get_token_age(self):
        """Get age of current token in seconds"""
        if not self.token_timestamp:
            return 0
        return int((datetime.now(self.ist_tz) - self.token_timestamp).total_seconds())
    
    def setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            """Main status page"""
            ist_time = datetime.now(self.ist_tz).strftime("%Y-%m-%d %H:%M:%S IST")
            
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Pivot Trading Authentication Server</title>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        margin: 0; padding: 0;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }}
                    .container {{
                        background: rgba(255,255,255,0.95);
                        padding: 40px;
                        border-radius: 20px;
                        max-width: 600px;
                        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
                    }}
                    h1 {{ color: #667eea; margin-top: 0; }}
                    .status {{ 
                        padding: 15px;
                        margin: 15px 0;
                        border-radius: 10px;
                        border-left: 4px solid;
                    }}
                    .success {{ background: #d4edda; border-color: #28a745; color: #155724; }}
                    .info {{ background: #d1ecf1; border-color: #17a2b8; color: #0c5460; }}
                    .warning {{ background: #fff3cd; border-color: #ffc107; color: #856404; }}
                    .endpoint {{ 
                        font-family: 'Courier New', monospace;
                        background: #f8f9fa;
                        padding: 5px 10px;
                        border-radius: 5px;
                        display: inline-block;
                        margin: 5px 0;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🔐 Pivot Trading Authentication Server</h1>
                    
                    <div class="status success">
                        <h3>✅ Server Status: RUNNING</h3>
                        <p><strong>Time:</strong> {ist_time}</p>
                        <p><strong>Port:</strong> 8001 (proxied via nginx)</p>
                        <p><strong>SSL:</strong> Handled by nginx</p>
                    </div>
                    
                    <div class="status {'success' if self.request_token else 'warning'}">
                        <h3>🔑 Token Status</h3>
                        <p><strong>Available:</strong> {'✅ Yes' if self.request_token else '❌ No'}</p>
                        <p><strong>Age:</strong> {self.get_token_age()}s</p>
                        <p><strong>Timeout:</strong> {self.auth_timeout}s</p>
                        {'<p><strong>Token:</strong> ' + self.request_token[:20] + '...</p>' if self.request_token else ''}
                    </div>
                    
                    <div class="status info">
                        <h3>📡 Endpoints</h3>
                        <p><span class="endpoint">/callback</span> - OAuth callback</p>
                        <p><span class="endpoint">/postback</span> - Postback webhook</p>
                        <p><span class="endpoint">/health</span> - Health check</p>
                        <p><span class="endpoint">/status</span> - JSON status</p>
                        <p><span class="endpoint">/get_token</span> - Retrieve token</p>
                        <p><span class="endpoint">/clear_token</span> - Clear token</p>
                    </div>
                    
                    <div class="status info">
                        <h3>🔧 Quick Actions</h3>
                        <p><a href="/status">View JSON Status</a></p>
                        <p><a href="/get_token">Get Current Token</a></p>
                        <p><a href="/clear_token">Clear Token</a></p>
                    </div>
                </div>
            </body>
            </html>
            """
        
        @self.app.route('/health')
        def health():
            """Health check endpoint"""
            return jsonify({"status": "ok", "server": "running"})
        
        @self.app.route('/status')
        def status():
            """JSON status endpoint"""
            ist_time = datetime.now(self.ist_tz).strftime("%Y-%m-%d %H:%M:%S IST")
            
            return jsonify({
                "status": "running",
                "server": "Pivot Trading Authentication Server",
                "time": ist_time,
                "port": 8001,
                "ssl": "nginx",
                "token": {
                    "available": bool(self.request_token),
                    "age_seconds": self.get_token_age(),
                    "timeout_seconds": self.auth_timeout,
                    "preview": self.request_token[:20] + "..." if self.request_token else None
                }
            })
        
        @self.app.route('/callback')
        @self.app.route('/postback')
        def handle_callback():
            """Handle OAuth callback from Kite Connect"""
            try:
                ist_time = datetime.now(self.ist_tz).strftime("%Y-%m-%d %H:%M:%S IST")
                
                request_token = request.args.get('request_token')
                action = request.args.get('action', 'login')
                status = request.args.get('status', 'success')
                
                logger.info(f"Callback received at {ist_time}")
                logger.info(f"  Action: {action}, Status: {status}")
                logger.info(f"  Token: {request_token[:20] if request_token else 'None'}...")
                
                if request_token and status == 'success':
                    # Store token
                    self.request_token = request_token
                    self.token_timestamp = datetime.now(self.ist_tz)
                    
                    logger.info("✅ Request token stored successfully")
                    
                    # Beautiful success page
                    return f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Authentication Successful</title>
                        <meta charset="utf-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1">
                        <style>
                            body {{
                                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                                margin: 0; padding: 0;
                                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                min-height: 100vh;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                color: white;
                            }}
                            .container {{
                                background: rgba(255,255,255,0.1);
                                padding: 50px;
                                border-radius: 20px;
                                backdrop-filter: blur(10px);
                                border: 1px solid rgba(255,255,255,0.2);
                                text-align: center;
                                max-width: 500px;
                                box-shadow: 0 8px 32px rgba(0,0,0,0.3);
                            }}
                            .success-icon {{
                                font-size: 80px;
                                margin-bottom: 20px;
                                animation: bounce 1s ease-in-out;
                            }}
                            @keyframes bounce {{
                                0%, 100% {{ transform: translateY(0); }}
                                50% {{ transform: translateY(-20px); }}
                            }}
                            h1 {{ margin: 20px 0; font-size: 32px; }}
                            .info {{
                                font-size: 18px;
                                line-height: 1.8;
                                opacity: 0.95;
                                margin: 30px 0;
                            }}
                            .token-box {{
                                background: rgba(0,0,0,0.3);
                                padding: 15px;
                                border-radius: 10px;
                                font-family: 'Courier New', monospace;
                                margin: 20px 0;
                                word-break: break-all;
                                font-size: 14px;
                            }}
                            .countdown {{
                                font-size: 14px;
                                opacity: 0.8;
                                margin-top: 30px;
                            }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <div class="success-icon">🎉</div>
                            <h1>Authentication Successful!</h1>
                            
                            <div class="info">
                                <p><strong>Time:</strong> {ist_time}</p>
                                <div class="token-box">
                                    <strong>Token:</strong><br>
                                    {request_token[:30]}...
                                </div>
                                <p>Your Zerodha account has been successfully authenticated!</p>
                                <p><strong>✅ You can now close this window.</strong></p>
                                <p>Your trading system will start automatically.</p>
                            </div>
                            
                            <div class="countdown">
                                <p>Auto-closing in <span id="countdown">10</span> seconds...</p>
                            </div>
                        </div>
                        
                        <script>
                            let seconds = 10;
                            const countdownEl = document.getElementById('countdown');
                            
                            const timer = setInterval(() => {{
                                seconds--;
                                countdownEl.textContent = seconds;
                                
                                if (seconds <= 0) {{
                                    clearInterval(timer);
                                    window.close();
                                }}
                            }}, 1000);
                        </script>
                    </body>
                    </html>
                    """
                
                else:
                    # Authentication failed
                    error_reason = request.args.get('error_type', 'Authentication failed')
                    logger.error(f"❌ Authentication failed: {error_reason}")
                    
                    return f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Authentication Failed</title>
                        <meta charset="utf-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1">
                        <style>
                            body {{
                                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                                background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
                                color: white;
                                text-align: center;
                                padding: 50px;
                                margin: 0;
                            }}
                            .container {{
                                background: rgba(255,255,255,0.1);
                                padding: 40px;
                                border-radius: 20px;
                                backdrop-filter: blur(10px);
                                max-width: 500px;
                                margin: 0 auto;
                            }}
                            h1 {{ font-size: 48px; margin: 0; }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h1>❌</h1>
                            <h2>Authentication Failed</h2>
                            <p><strong>Time:</strong> {ist_time}</p>
                            <p><strong>Reason:</strong> {error_reason}</p>
                            <p>Please try authenticating again or check your Zerodha credentials.</p>
                        </div>
                    </body>
                    </html>
                    """, 400
                    
            except Exception as e:
                logger.error(f"Callback handling error: {e}")
                return jsonify({"error": "Internal server error"}), 500
        
        @self.app.route('/get_token')
        def get_token():
            """Retrieve current request token"""
            if not self.request_token:
                return jsonify({
                    "status": "error",
                    "message": "No token available"
                }), 404
            
            age = self.get_token_age()
            
            # Check if token expired
            if age > self.auth_timeout:
                self.request_token = None
                self.token_timestamp = None
                return jsonify({
                    "status": "error",
                    "message": "Token expired"
                }), 410
            
            return jsonify({
                "status": "success",
                "request_token": self.request_token,
                "timestamp": self.token_timestamp.strftime("%Y-%m-%d %H:%M:%S IST"),
                "age_seconds": age,
                "timeout_seconds": self.auth_timeout
            })
        
        @self.app.route('/clear_token')
        def clear_token():
            """Clear stored token"""
            self.request_token = None
            self.token_timestamp = None
            logger.info("Token cleared")
            
            return jsonify({
                "status": "success",
                "message": "Token cleared"
            })
    
    def run(self):
        """Run the Flask server"""
        ist_time = datetime.now(self.ist_tz).strftime("%Y-%m-%d %H:%M:%S IST")
        
        logger.info("=" * 60)
        logger.info("STARTING PIVOT TRADING AUTHENTICATION SERVER")
        logger.info(f"  Time: {ist_time}")
        logger.info("=" * 60)
        logger.info("  Port: 8001 (localhost)")
        logger.info("  SSL: Handled by nginx")
        logger.info("  Public URL: https://sensexbot.ddns.net")
        logger.info("=" * 60)
        logger.info("")
        logger.info("ENDPOINTS:")
        logger.info("  Callback: https://sensexbot.ddns.net/callback")
        logger.info("  Postback: https://sensexbot.ddns.net/postback")
        logger.info("  Health: https://sensexbot.ddns.net/health")
        logger.info("  Status: https://sensexbot.ddns.net/status")
        logger.info("")
        logger.info("TEST LOCALLY:")
        logger.info("  curl http://localhost:8001/health")
        logger.info("  curl http://localhost:8001/status")
        logger.info("=" * 60)
        
        try:
            # Run on localhost only (nginx will proxy)
            self.app.run(
                host='0.0.0.0',
                port=8001,
                debug=False,
                threaded=True
            )
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise


def main():
    """Main function"""
    try:
        server = AuthenticationServer()
        server.run()
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
