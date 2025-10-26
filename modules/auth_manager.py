"""
Authentication Manager Module
Handles daily Kite Connect OAuth authentication
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
        """
        Initialize authentication manager
        
        Args:
            config: Configuration dictionary
            notifier: TelegramNotifier instance
        """
        self.config = config
        self.notifier = notifier
        self.api_key = config['api_key']
        self.api_secret = config['api_secret']
        self.token_file = config['data']['access_token_file']
        self.auth_timeout = config['auth'].get('auth_timeout_seconds', 300)
        self.postback_url = config['auth'].get('postback_url')
        
        # Extract server URL from postback URL
        # Example: https://sensexbot.ddns.net:8001/postback -> https://sensexbot.ddns.net:8001
        if self.postback_url:
            parts = self.postback_url.rsplit('/', 1)
            self.server_url = parts[0] if len(parts) > 1 else self.postback_url
        else:
            self.server_url = None
    
    def load_access_token(self):
        """
        Load access token from file
        
        Returns:
            Access token string or None
        """
        try:
            if not os.path.exists(self.token_file):
                logger.info("No token file found")
                return None
            
            with open(self.token_file, 'r') as f:
                token_data = f.read().strip()
            
            if not token_data:
                logger.warning("Token file is empty")
                return None
            
            # Token format: "token|YYYY-MM-DD"
            if '|' in token_data:
                token, date_str = token_data.split('|', 1)
                token_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                today = datetime.now().date()
                
                if token_date == today:
                    logger.info(f"Loaded valid token from {self.token_file}")
                    return token
                else:
                    logger.info(f"Token expired (date: {token_date}, today: {today})")
                    return None
            else:
                # Old format without date - assume valid for today only
                logger.info("Token in old format, assuming valid for today")
                return token_data
                
        except Exception as e:
            logger.error(f"Error loading access token: {e}")
            return None
    
    def save_access_token(self, token):
        """
        Save access token to file with current date
        
        Args:
            token: Access token string
        """
        try:
            # Create data directory if it doesn't exist
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
            
            today = datetime.now().strftime('%Y-%m-%d')
            token_data = f"{token}|{today}"
            
            with open(self.token_file, 'w') as f:
                f.write(token_data)
            
            # Set restrictive permissions
            os.chmod(self.token_file, 0o600)
            
            logger.info(f"Access token saved to {self.token_file}")
            
        except Exception as e:
            logger.error(f"Error saving access token: {e}")
            raise
    
    def validate_token(self, token):
        """
        Validate access token by making a test API call
        
        Args:
            token: Access token to validate
        
        Returns:
            tuple (is_valid, user_info or error_message)
        """
        try:
            kite = KiteConnect(api_key=self.api_key)
            kite.set_access_token(token)
            
            # Test API call
            profile = kite.profile()
            
            logger.info(f"Token validated successfully for user: {profile['user_name']}")
            return True, profile
            
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return False, str(e)
    
    def generate_login_url(self):
        """
        Generate Kite OAuth login URL
        
        Returns:
            OAuth login URL
        """
        login_url = f"https://kite.zerodha.com/connect/login?api_key={self.api_key}&v=3"
        logger.info("Generated OAuth login URL")
        return login_url
    
    def check_postback_server(self):
        """
        Check if postback server is running and accessible
        
        Returns:
            True if server is reachable
        """
        if not self.server_url:
            logger.warning("No postback server URL configured")
            return False
        
        try:
            # Try to reach health endpoint
            health_url = f"{self.server_url}/health"
            response = requests.get(health_url, timeout=5, verify=False)
            
            if response.status_code == 200:
                logger.info("Postback server is reachable")
                return True
            else:
                logger.warning(f"Postback server returned status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Cannot reach postback server: {e}")
            return False
    
    def wait_for_request_token(self, timeout=None):
        """
        Wait for request token from postback server
        
        Args:
            timeout: Timeout in seconds (default: from config)
        
        Returns:
            Request token or None
        """
        if timeout is None:
            timeout = self.auth_timeout
        
        if not self.server_url:
            logger.error("No postback server URL configured")
            return None
        
        token_url = f"{self.server_url}/get_token"
        start_time = time.time()
        
        logger.info(f"Waiting for request token (timeout: {timeout}s)...")
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(token_url, timeout=5, verify=False)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        request_token = data.get('request_token')
                        logger.info("Request token received from postback server")
                        return request_token
                    
                elif response.status_code == 404:
                    # No token yet, continue waiting
                    pass
                    
                elif response.status_code == 410:
                    # Token expired
                    logger.error("Request token expired")
                    return None
                    
            except requests.exceptions.RequestException as e:
                logger.debug(f"Waiting for token... ({e})")
            
            time.sleep(2)  # Check every 2 seconds
        
        logger.error("Timeout waiting for request token")
        return None
    
    def exchange_token(self, request_token):
        """
        Exchange request token for access token
        
        Args:
            request_token: Request token from OAuth callback
        
        Returns:
            tuple (access_token, user_info) or (None, error_message)
        """
        try:
            kite = KiteConnect(api_key=self.api_key)
            
            # Generate session (exchange request token)
            data = kite.generate_session(request_token, api_secret=self.api_secret)
            
            access_token = data['access_token']
            user_info = data.get('user_name', 'Unknown')
            
            logger.info(f"Access token generated for user: {user_info}")
            
            return access_token, user_info
            
        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            return None, str(e)
    
    def authenticate(self):
        """
        Main authentication method
        
        Flow:
        1. Check for existing valid token
        2. If no token, request new authentication:
           - Check postback server is running
           - Generate and send login URL via Telegram
           - Wait for user to complete OAuth
           - Exchange request token for access token
           - Save and validate token
        
        Returns:
            Access token or None
        """
        # Step 1: Try to load existing token
        token = self.load_access_token()
        
        if token:
            # Validate existing token
            is_valid, result = self.validate_token(token)
            
            if is_valid:
                user_name = result['user_name']
                logger.info(f"Using existing valid token for user: {user_name}")
                
                # Send notification
                self.notifier.send_message(f"""
✅ <b>Using Existing Token</b>

👤 User: {user_name}
🔑 Token: Valid
📅 Date: {datetime.now().strftime('%Y-%m-%d')}

🟢 System starting with existing authentication...
                """)
                
                return token
            else:
                logger.warning(f"Existing token invalid: {result}")
        
        # Step 2: Need new authentication
        logger.info("Starting new authentication flow...")
        
        # Check postback server
        if not self.check_postback_server():
            error_msg = "Postback server not reachable. Please start auth_server.py first!"
            logger.error(error_msg)
            self.notifier.send_error_alert("Authentication Error", error_msg)
            return None
        
        # Generate login URL
        login_url = self.generate_login_url()
        
        # Send authentication request via Telegram
        self.notifier.send_authentication_request(login_url)
        
        # Wait for request token
        request_token = self.wait_for_request_token()
        
        if not request_token:
            error_msg = "Authentication timeout - no request token received"
            logger.error(error_msg)
            self.notifier.send_authentication_failure(error_msg)
            return None
        
        # Exchange for access token
        access_token, user_info = self.exchange_token(request_token)
        
        if not access_token:
            error_msg = f"Token exchange failed: {user_info}"
            logger.error(error_msg)
            self.notifier.send_authentication_failure(error_msg)
            return None
        
        # Save token
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
        
        logger.info(f"Authentication successful for user: {user_name}")
        self.notifier.send_authentication_success(user_name, token_preview)
        
        return access_token
    
    def clear_token(self):
        """Clear saved token file"""
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                logger.info("Token file cleared")
        except Exception as e:
            logger.error(f"Error clearing token: {e}")


if __name__ == "__main__":
    # Test authentication manager
    import json
    logging.basicConfig(level=logging.INFO)
    
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Create dummy notifier for testing
    class DummyNotifier:
        def send_message(self, msg):
            print(f"\n[TELEGRAM]\n{msg}\n")
        
        def send_authentication_request(self, url):
            print(f"\n[AUTH REQUEST]\nLogin URL: {url}\n")
        
        def send_authentication_success(self, user, token):
            print(f"\n[AUTH SUCCESS]\nUser: {user}, Token: {token}\n")
        
        def send_authentication_failure(self, reason):
            print(f"\n[AUTH FAILED]\nReason: {reason}\n")
        
        def send_error_alert(self, type, msg):
            print(f"\n[ERROR]\n{type}: {msg}\n")
    
    notifier = DummyNotifier()
    auth_manager = AuthManager(config, notifier)
    
    print("Testing authentication manager...")
    print("\n1. Checking for existing token...")
    token = auth_manager.load_access_token()
    
    if token:
        print(f"Found token: {token[:20]}...")
        print("\n2. Validating token...")
        is_valid, result = auth_manager.validate_token(token)
        print(f"Valid: {is_valid}")
        if is_valid:
            print(f"User: {result['user_name']}")
    else:
        print("No existing token found")
        print("\n2. To authenticate, run:")
        print("   python auth_server.py")
        print("   Then run this test again")
    
    print("\n✅ Auth manager test complete")
