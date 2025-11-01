"""
Authentication Manager Module - FIXED VERSION
CRITICAL: Never trust tokens older than 2 hours
"""

import os
import time
import logging
import requests
from datetime import datetime, date
from kiteconnect import KiteConnect

logger = logging.getLogger(__name__)


class AuthManager:
    def __init__(self, config, notifier):
        """Initialize authentication manager"""
        self.config = config
        self.notifier = notifier
        self.api_key = config['api_key']
        self.api_secret = config['api_secret']
        self.token_file = config['data']['access_token_file']
        self.auth_timeout = config['auth'].get('auth_timeout_seconds', 300)
        self.postback_url = config['auth'].get('postback_url')
        
        # Extract server URL
        if self.postback_url:
            parts = self.postback_url.rsplit('/', 1)
            self.server_url = parts[0] if len(parts) > 1 else self.postback_url
        else:
            self.server_url = None
    
    def is_token_acceptable(self):
        """
        Check if existing token is acceptable for use
        
        Token must be:
        1. From today
        2. Generated after 6:00 AM (not overnight token)
        3. Less than 2 hours old (Kite tokens can expire)
        
        Returns: (is_acceptable, reason)
        """
        try:
            if not os.path.exists(self.token_file):
                return False, "Token file does not exist"
            
            # Check file modification time
            file_mtime = os.path.getmtime(self.token_file)
            file_time = datetime.fromtimestamp(file_mtime)
            now = datetime.now()
            
            # Must be from today
            if file_time.date() != now.date():
                return False, f"Token from {file_time.date()}, today is {now.date()}"
            
            # Must be after 6 AM (reject overnight tokens)
            if file_time.hour < 6:
                return False, f"Token too early: {file_time.strftime('%H:%M')} (before 6 AM)"
            
            # Must be less than 2 hours old
            age_hours = (now - file_time).total_seconds() / 3600
            if age_hours > 2:
                return False, f"Token too old: {age_hours:.1f} hours"
            
            # Check date stamp in file
            with open(self.token_file, 'r') as f:
                content = f.read().strip()
            
            if '|' in content:
                token, date_str = content.split('|', 1)
                token_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                if token_date != now.date():
                    return False, f"Token date {token_date} != today {now.date()}"
            
            return True, f"Token OK (age: {age_hours:.1f}h, time: {file_time.strftime('%H:%M')})"
            
        except Exception as e:
            logger.error(f"Error checking token: {e}")
            return False, str(e)
    
    def load_access_token(self):
        """
        Load access token ONLY if acceptable
        
        Returns: Access token string or None
        """
        try:
            is_acceptable, reason = self.is_token_acceptable()
            
            if not is_acceptable:
                logger.warning(f"Token not acceptable: {reason}")
                return None
            
            with open(self.token_file, 'r') as f:
                token_data = f.read().strip()
            
            if '|' in token_data:
                token, date_str = token_data.split('|', 1)
                logger.info(f"✅ Loaded acceptable token: {reason}")
                return token
            else:
                logger.warning("Token in old format")
                return token_data
                
        except Exception as e:
            logger.error(f"Error loading token: {e}")
            return None
    
    def save_access_token(self, token):
        """Save access token with current date and timestamp"""
        try:
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
            
            today = datetime.now().strftime('%Y-%m-%d')
            token_data = f"{token}|{today}"
            
            with open(self.token_file, 'w') as f:
                f.write(token_data)
            
            os.chmod(self.token_file, 0o600)
            
            logger.info(f"✅ Token saved: {self.token_file}")
            logger.info(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            logger.error(f"Error saving token: {e}")
            raise
    
    def validate_token(self, token):
        """Validate token with actual API call"""
        try:
            kite = KiteConnect(api_key=self.api_key)
            kite.set_access_token(token)
            
            profile = kite.profile()
            
            logger.info(f"✅ Token valid for: {profile['user_name']}")
            return True, profile
            
        except Exception as e:
            logger.error(f"❌ Token validation failed: {e}")
            return False, str(e)
    
    def generate_login_url(self):
        """Generate Kite OAuth login URL"""
        login_url = f"https://kite.zerodha.com/connect/login?api_key={self.api_key}&v=3"
        logger.info("Generated OAuth URL")
        return login_url
    
    def check_postback_server(self):
        """Check if auth server is running"""
        if not self.server_url:
            logger.warning("No postback server URL configured")
            return False
        
        try:
            health_url = "http://localhost:8001/health"
            response = requests.get(health_url, timeout=5)
            
            if response.status_code == 200:
                logger.info("✅ Auth server reachable")
                return True
            else:
                logger.warning(f"Auth server status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Cannot reach auth server: {e}")
            return False
    
    def wait_for_request_token(self, timeout=None):
        """Wait for request token from auth server"""
        if timeout is None:
            timeout = self.auth_timeout
        
        if not self.server_url:
            logger.error("No server URL configured")
            return None
        
        token_url = "http://localhost:8001/get_token"
        start_time = time.time()
        
        logger.info(f"⏳ Waiting for request token (timeout: {timeout}s)...")
        
        check_count = 0
        while time.time() - start_time < timeout:
            check_count += 1
            
            try:
                response = requests.get(token_url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        request_token = data.get('request_token')
                        logger.info(f"✅ Request token received (after {check_count} checks)")
                        return request_token
                    
                elif response.status_code == 410:
                    logger.error("Request token expired")
                    return None
                    
            except requests.exceptions.RequestException:
                pass  # Keep waiting silently
            
            # Log progress every 30 seconds
            elapsed = time.time() - start_time
            if check_count % 15 == 0:  # Every 30 seconds (15 * 2s)
                logger.info(f"⏳ Still waiting... ({int(elapsed)}s elapsed, {int(timeout - elapsed)}s remaining)")
            
            time.sleep(2)
        
        logger.error(f"⏰ Timeout after {timeout}s")
        return None
    
    def exchange_token(self, request_token):
        """Exchange request token for access token"""
        try:
            kite = KiteConnect(api_key=self.api_key)
            
            data = kite.generate_session(request_token, api_secret=self.api_secret)
            
            access_token = data['access_token']
            user_info = data.get('user_name', 'Unknown')
            
            logger.info(f"✅ Access token generated for: {user_info}")
            
            return access_token, user_info
            
        except Exception as e:
            logger.error(f"❌ Token exchange failed: {e}")
            return None, str(e)
    
    def authenticate(self):
        """
        Main authentication method - FIXED VERSION
        
        CRITICAL CHANGES:
        1. Check token freshness (age + time of day)
        2. Send auth request immediately if no valid token
        3. Don't send "Using existing token" messages (causes confusion)
        
        Returns: Access token or None
        """
        # Step 1: Check for acceptable token
        token = self.load_access_token()
        
        if token:
            # Validate with API
            is_valid, result = self.validate_token(token)
            
            if is_valid:
                user_name = result['user_name']
                logger.info(f"✅ Using existing valid token for: {user_name}")
                # DON'T send Telegram message here - main.py will handle it
                return token
            else:
                logger.warning(f"Existing token failed validation: {result}")
                # Delete bad token
                if os.path.exists(self.token_file):
                    os.remove(self.token_file)
        
        # Step 2: Need new authentication
        logger.info("🔐 Starting new authentication flow...")
        
        # Check auth server
        if not self.check_postback_server():
            error_msg = "Auth server not reachable at http://localhost:8001"
            logger.error(error_msg)
            self.notifier.send_error_alert("Auth Server Down", error_msg)
            return None
        
        # Generate login URL
        login_url = self.generate_login_url()
        
        # Send auth request
        logger.info("📱 Sending authentication request via Telegram...")
        self.notifier.send_authentication_request(login_url)
        
        # Wait for request token
        logger.info("⏳ Waiting for user to complete OAuth flow...")
        request_token = self.wait_for_request_token()
        
        if not request_token:
            error_msg = "Timeout waiting for authentication"
            logger.error(error_msg)
            self.notifier.send_authentication_failure(error_msg)
            return None
        
        # Exchange for access token
        logger.info("🔄 Exchanging request token for access token...")
        access_token, user_info = self.exchange_token(request_token)
        
        if not access_token:
            error_msg = f"Token exchange failed: {user_info}"
            logger.error(error_msg)
            self.notifier.send_authentication_failure(error_msg)
            return None
        
        # Save token
        logger.info("💾 Saving access token...")
        self.save_access_token(access_token)
        
        # Validate saved token
        is_valid, profile = self.validate_token(access_token)
        
        if not is_valid:
            error_msg = f"Saved token validation failed: {profile}"
            logger.error(error_msg)
            self.notifier.send_authentication_failure(error_msg)
            return None
        
        # Success!
        user_name = profile['user_name']
        token_preview = f"{access_token[:20]}..."
        
        logger.info(f"🎉 Authentication successful for: {user_name}")
        self.notifier.send_authentication_success(user_name, token_preview)
        
        return access_token
    
    def clear_token(self):
        """Clear saved token file"""
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                logger.info("Token file deleted")
        except Exception as e:
            logger.error(f"Error deleting token: {e}")


if __name__ == "__main__":
    # Test
    import json
    logging.basicConfig(level=logging.INFO)
    
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    class DummyNotifier:
        def send_message(self, msg):
            print(f"\n[MSG]\n{msg}\n")
        def send_authentication_request(self, url):
            print(f"\n[AUTH REQ]\n{url}\n")
        def send_authentication_success(self, user, token):
            print(f"\n[SUCCESS] {user}: {token}\n")
        def send_authentication_failure(self, reason):
            print(f"\n[FAILED] {reason}\n")
        def send_error_alert(self, type, msg):
            print(f"\n[ERROR] {type}: {msg}\n")
    
    notifier = DummyNotifier()
    auth = AuthManager(config, notifier)
    
    print("Testing token freshness...")
    acceptable, reason = auth.is_token_acceptable()
    print(f"Acceptable: {acceptable}")
    print(f"Reason: {reason}")
