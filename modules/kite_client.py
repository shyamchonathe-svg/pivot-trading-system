"""
Kite Client Module
Wrapper for Kite Connect API with error handling and retry logic
"""

from kiteconnect import KiteConnect
import time
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class KiteClient:
    def __init__(self, api_key, api_secret, access_token=None):
        """
        Initialize Kite Connect client
        
        Args:
            api_key: Your API key
            api_secret: Your API secret
            access_token: Access token (if already authenticated)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.kite = KiteConnect(api_key=api_key)
        
        if access_token:
            self.kite.set_access_token(access_token)
            self.access_token = access_token
        else:
            self.access_token = None
        
        # Cache for instrument tokens
        self.instrument_cache = {}
        self.instruments_loaded = False
    
    def set_access_token(self, access_token):
        """Set access token after authentication"""
        self.access_token = access_token
        self.kite.set_access_token(access_token)
    
    def get_profile(self):
        """Get user profile (useful for validation)"""
        try:
            return self.kite.profile()
        except Exception as e:
            logger.error(f"Error fetching profile: {e}")
            raise
    
    def get_spot_price(self, symbol):
        """
        Get spot price for index
        
        Args:
            symbol: 'BSE:SENSEX' or 'NSE:NIFTY 50'
        
        Returns: float spot price
        """
        try:
            ltp_data = self.kite.ltp(symbol)
            return ltp_data[symbol]['last_price']
        except Exception as e:
            logger.error(f"Error fetching spot price for {symbol}: {e}")
            raise
    
    def load_instruments(self, exchange='BFO'):
        """
        Load and cache instrument list
        Call this once during initialization
        
        Args:
            exchange: 'BFO' for BSE Futures & Options, 'NFO' for NSE
        """
        try:
            logger.info(f"Loading instruments for {exchange}...")
            instruments = self.kite.instruments(exchange)
            
            # Cache instruments by trading symbol
            for inst in instruments:
                symbol = inst['tradingsymbol']
                self.instrument_cache[symbol] = {
                    'instrument_token': inst['instrument_token'],
                    'exchange_token': inst['exchange_token'],
                    'name': inst['name'],
                    'expiry': inst['expiry'],
                    'strike': inst['strike'],
                    'lot_size': inst['lot_size'],
                    'instrument_type': inst['instrument_type'],
                    'exchange': inst['exchange']
                }
            
            self.instruments_loaded = True
            logger.info(f"Loaded {len(self.instrument_cache)} instruments")
            
        except Exception as e:
            logger.error(f"Error loading instruments: {e}")
            raise
    
    def get_instrument_token(self, symbol):
        """
        Get instrument token for a symbol
        
        Args:
            symbol: Trading symbol (e.g., 'SENSEX2510280100CE')
        
        Returns: instrument_token (int) or None
        """
        if not self.instruments_loaded:
            # Auto-load if not loaded
            exchange = 'BFO' if 'SENSEX' in symbol else 'NFO'
            self.load_instruments(exchange)
        
        if symbol in self.instrument_cache:
            return self.instrument_cache[symbol]['instrument_token']
        else:
            logger.warning(f"Instrument token not found for {symbol}")
            return None
    
    def get_instrument_details(self, symbol):
        """Get full instrument details"""
        if not self.instruments_loaded:
            exchange = 'BFO' if 'SENSEX' in symbol else 'NFO'
            self.load_instruments(exchange)
        
        return self.instrument_cache.get(symbol, None)
    
    def get_historical_data(self, symbol, from_date, to_date, interval='3minute'):
        """
        Fetch historical OHLC data
        
        Args:
            symbol: Trading symbol or instrument_token
            from_date: datetime object
            to_date: datetime object
            interval: 'minute', '3minute', '5minute', 'day', etc.
        
        Returns: List of candle dicts
        """
        try:
            # Get instrument token if symbol provided
            if isinstance(symbol, str):
                instrument_token = self.get_instrument_token(symbol)
                if not instrument_token:
                    raise ValueError(f"Instrument token not found for {symbol}")
            else:
                instrument_token = symbol
            
            # Fetch data
            data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            raise
    
    def get_ltp(self, symbol):
        """
        Get Last Traded Price
        
        Args:
            symbol: Trading symbol (e.g., 'SENSEX2510280100CE')
        
        Returns: float LTP
        """
        try:
            # Get full symbol with exchange
            inst_details = self.get_instrument_details(symbol)
            if not inst_details:
                raise ValueError(f"Instrument not found: {symbol}")
            
            exchange = inst_details['exchange']
            full_symbol = f"{exchange}:{symbol}"
            
            ltp_data = self.kite.ltp(full_symbol)
            return ltp_data[full_symbol]['last_price']
            
        except Exception as e:
            logger.error(f"Error fetching LTP for {symbol}: {e}")
            raise
    
    def get_quote(self, symbol):
        """
        Get full quote (OHLC + LTP + volume)
        
        Returns: dict with detailed quote
        """
        try:
            inst_details = self.get_instrument_details(symbol)
            if not inst_details:
                raise ValueError(f"Instrument not found: {symbol}")
            
            exchange = inst_details['exchange']
            full_symbol = f"{exchange}:{symbol}"
            
            quote_data = self.kite.quote(full_symbol)
            return quote_data[full_symbol]
            
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            raise
    
    def place_order(self, symbol, transaction_type, quantity, 
                    order_type='MARKET', product='MIS', variety='regular',
                    price=None, trigger_price=None):
        """
        Place order (for live trading)
        
        Args:
            symbol: Trading symbol
            transaction_type: 'BUY' or 'SELL'
            quantity: Number of lots * lot_size
            order_type: 'MARKET', 'LIMIT', 'SL', 'SL-M'
            product: 'MIS' (intraday), 'CNC' (delivery), 'NRML' (normal)
            variety: 'regular', 'amo', 'iceberg'
            price: Limit price (required for LIMIT orders)
            trigger_price: Trigger price (required for SL orders)
        
        Returns: order_id
        """
        try:
            # Get exchange
            inst_details = self.get_instrument_details(symbol)
            if not inst_details:
                raise ValueError(f"Instrument not found: {symbol}")
            
            exchange = inst_details['exchange']
            
            order_params = {
                'exchange': exchange,
                'tradingsymbol': symbol,
                'transaction_type': transaction_type,
                'quantity': quantity,
                'order_type': order_type,
                'product': product,
                'variety': variety
            }
            
            if price:
                order_params['price'] = price
            if trigger_price:
                order_params['trigger_price'] = trigger_price
            
            order_id = self.kite.place_order(**order_params)
            logger.info(f"Order placed: {order_id} - {transaction_type} {quantity} {symbol}")
            
            return order_id
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise
    
    def get_positions(self):
        """Get current positions"""
        try:
            return self.kite.positions()
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            raise
    
    def get_orders(self):
        """Get order history for the day"""
        try:
            return self.kite.orders()
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            raise
    
    def cancel_order(self, order_id, variety='regular'):
        """Cancel pending order"""
        try:
            self.kite.cancel_order(variety=variety, order_id=order_id)
            logger.info(f"Order cancelled: {order_id}")
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            raise
    
    def exit_position(self, symbol, quantity, product='MIS'):
        """
        Exit existing position (sell if long, buy if short)
        
        Args:
            symbol: Trading symbol
            quantity: Quantity to exit (positive number)
            product: Product type (MIS/NRML)
        
        Returns: order_id
        """
        try:
            # Determine transaction type based on existing position
            positions = self.get_positions()['net']
            
            position = None
            for pos in positions:
                if pos['tradingsymbol'] == symbol and pos['product'] == product:
                    position = pos
                    break
            
            if not position:
                raise ValueError(f"No position found for {symbol}")
            
            # If net quantity is positive, we're long → SELL to exit
            # If net quantity is negative, we're short → BUY to exit
            if position['quantity'] > 0:
                transaction_type = 'SELL'
            else:
                transaction_type = 'BUY'
                quantity = abs(quantity)
            
            return self.place_order(
                symbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                order_type='MARKET',
                product=product
            )
            
        except Exception as e:
            logger.error(f"Error exiting position: {e}")
            raise
    
    def validate_token(self):
        """
        Validate if access token is working
        
        Returns: tuple (is_valid, user_info or error_message)
        """
        try:
            profile = self.get_profile()
            return True, profile
        except Exception as e:
            return False, str(e)


if __name__ == "__main__":
    # Test Kite client (requires valid credentials)
    import os
    
    # Mock credentials for testing structure
    API_KEY = "your_api_key"
    API_SECRET = "your_api_secret"
    ACCESS_TOKEN = "your_access_token"
    
    # Initialize client
    print("Initializing Kite client...")
    kite = KiteClient(API_KEY, API_SECRET, ACCESS_TOKEN)
    
    # Test token validation
    print("\nValidating access token...")
    is_valid, result = kite.validate_token()
    if is_valid:
        print(f"✅ Token valid. User: {result['user_name']}")
    else:
        print(f"❌ Token invalid: {result}")
    
    # Test spot price fetch
    print("\nFetching Sensex spot price...")
    try:
        spot = kite.get_spot_price('BSE:SENSEX')
        print(f"Sensex: {spot}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test instrument loading
    print("\nLoading BFO instruments...")
    try:
        kite.load_instruments('BFO')
        print(f"✅ Instruments loaded")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test instrument token lookup
    print("\nLooking up instrument token...")
    symbol = "SENSEX2510280100CE"
    token = kite.get_instrument_token(symbol)
    if token:
        print(f"Token for {symbol}: {token}")
    else:
        print(f"❌ Token not found")
    
    # Test historical data (commented out - requires valid token)
    """
    print("\nFetching historical data...")
    from datetime import datetime, timedelta
    
    to_date = datetime.now()
    from_date = to_date - timedelta(days=1)
    
    try:
        data = kite.get_historical_data(
            symbol=symbol,
            from_date=from_date,
            to_date=to_date,
            interval='3minute'
        )
        print(f"Fetched {len(data)} candles")
        if data:
            print(f"Latest candle: {data[-1]}")
    except Exception as e:
        print(f"Error: {e}")
    """
    
    print("\n✅ Kite client tests complete")
