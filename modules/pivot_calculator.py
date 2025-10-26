"""
Pivot Point Calculator Module
Calculates standard pivot points and determines market structure
"""

class PivotCalculator:
    def __init__(self, config):
        self.config = config
        self.instrument = config['trading']['instrument']
        self.strike_interval = config['trading']['strike_interval']
        self.strike_range = config['trading']['strike_range']
    
    def calculate_pivots(self, high, low, close):
        """
        Calculate standard pivot points
        Returns: dict with PP, R1-R5, S1-S3
        """
        pp = (high + low + close) / 3
        
        # Resistance levels
        r1 = 2 * pp - low
        r2 = pp + (high - low)
        r3 = high + 2 * (pp - low)
        r4 = r3 + (r2 - r1)
        r5 = r4 + (r3 - r2)
        
        # Support levels
        s1 = 2 * pp - high
        s2 = pp - (high - low)
        s3 = low - 2 * (high - pp)
        
        return {
            'PP': round(pp, 2),
            'R1': round(r1, 2),
            'R2': round(r2, 2),
            'R3': round(r3, 2),
            'R4': round(r4, 2),
            'R5': round(r5, 2),
            'S1': round(s1, 2),
            'S2': round(s2, 2),
            'S3': round(s3, 2)
        }
    
    def determine_structure(self, pivots):
        """
        Determine market structure: BULLISH, BEARISH, or NEUTRAL
        Based on: (R1 - PP) vs (PP - S1)
        
        Bullish:  (R1 - PP) > (PP - S1)
        Bearish:  (PP - S1) > (R1 - PP)
        Neutral:  |(R1 - PP) - (PP - S1)| < 5
        """
        r1_pp_diff = pivots['R1'] - pivots['PP']
        pp_s1_diff = pivots['PP'] - pivots['S1']
        
        difference = abs(r1_pp_diff - pp_s1_diff)
        
        if difference < 5:
            return 'NEUTRAL'
        elif r1_pp_diff > pp_s1_diff:
            return 'BULLISH'
        else:
            return 'BEARISH'
    
    def get_atm_strike(self, spot_price):
        """
        Calculate ATM strike based on spot price
        Example: Sensex 80,150 → 80,100 (interval = 100)
        """
        return round(spot_price / self.strike_interval) * self.strike_interval
    
    def get_strikes_to_analyze(self, spot_price):
        """
        Generate list of strikes to analyze
        Sensex: ATM ± 500 (11 strikes with 100 interval)
        Nifty: ATM ± 500 (21 strikes with 50 interval)
        
        Returns: List of strike prices
        """
        atm = self.get_atm_strike(spot_price)
        strikes = []
        
        # Generate strikes from (ATM - range) to (ATM + range)
        current = atm - self.strike_range
        while current <= atm + self.strike_range:
            strikes.append(current)
            current += self.strike_interval
        
        return strikes
    
    def get_itm_strike(self, atm_strike, option_type, day_to_expiry):
        """
        Get ITM strike based on expiry day
        
        Sensex (Thursday expiry):
        - Mon, Tue, Wed: ATM or ATM-1 (100 points ITM)
        - Thursday: ATM-2 (200 points ITM)
        
        Nifty (Tuesday expiry):
        - Fri, Mon: ATM or ATM-1 (50 points ITM)
        - Tuesday: ATM-2 (100 points ITM)
        
        Args:
            atm_strike: ATM strike price
            option_type: 'CE' or 'PE'
            day_to_expiry: Days remaining to expiry (0 = expiry day)
        """
        if day_to_expiry == 0:
            # Expiry day: ATM-2
            itm_distance = 2 * self.strike_interval
        else:
            # Non-expiry days: ATM-1
            itm_distance = self.strike_interval
        
        if option_type == 'CE':
            # For CE, ITM means lower strike
            return atm_strike - itm_distance
        else:
            # For PE, ITM means higher strike
            return atm_strike + itm_distance
    
    def is_price_in_range(self, price, lower, upper):
        """Helper to check if price is between two levels"""
        return lower <= price <= upper
    
    def get_price_zone(self, price, pivots):
        """
        Determine which zone the price is in
        Returns: tuple (zone_name, target_level)
        
        Zones:
        - Below S3: No trade
        - S3 to S1: Support zone
        - S1 to PP: Below pivot
        - PP to R1: Between PP-R1 (Scenario 2 zone)
        - PP to S1: Between PP-S1 (Scenario 1 zone)
        - R1 to R2: Above R1
        - R2 to R3: Between R2-R3 (Scenario 3 zone)
        - R3 to R4: Above R3
        - R4 to R5: Above R4
        - Above R5: No trade
        """
        if price < pivots['S3']:
            return ('BELOW_S3', None)
        elif self.is_price_in_range(price, pivots['S3'], pivots['S1']):
            return ('S3_S1', 'S1')
        elif self.is_price_in_range(price, pivots['S1'], pivots['PP']):
            return ('S1_PP', 'PP')
        elif self.is_price_in_range(price, pivots['PP'], pivots['S1']):
            return ('PP_S1', 'R1')  # Scenario 1 zone
        elif self.is_price_in_range(price, pivots['PP'], pivots['R1']):
            return ('PP_R1', 'R2')  # Scenario 2 zone
        elif self.is_price_in_range(price, pivots['R1'], pivots['R2']):
            return ('R1_R2', 'R2')
        elif self.is_price_in_range(price, pivots['R2'], pivots['R3']):
            return ('R2_R3', 'R3')  # Scenario 3 zone
        elif self.is_price_in_range(price, pivots['R3'], pivots['R4']):
            return ('R3_R4', 'R4')
        elif self.is_price_in_range(price, pivots['R4'], pivots['R5']):
            return ('R4_R5', 'R5')
        else:
            return ('ABOVE_R5', None)


if __name__ == "__main__":
    # Test the calculator
    config = {
        'trading': {
            'instrument': 'SENSEX',
            'strike_interval': 100,
            'strike_range': 500
        }
    }
    
    calc = PivotCalculator(config)
    
    # Test with sample OHLC data
    high = 150.50
    low = 138.20
    close = 145.75
    
    pivots = calc.calculate_pivots(high, low, close)
    structure = calc.determine_structure(pivots)
    
    print("Pivot Points:")
    for key, value in pivots.items():
        print(f"  {key}: {value}")
    
    print(f"\nMarket Structure: {structure}")
    
    # Test ATM calculation
    spot = 80150
    atm = calc.get_atm_strike(spot)
    print(f"\nSpot: {spot}, ATM: {atm}")
    
    # Test strikes to analyze
    strikes = calc.get_strikes_to_analyze(spot)
    print(f"\nStrikes to analyze: {strikes}")
    
    # Test ITM strikes
    itm_ce_expiry = calc.get_itm_strike(atm, 'CE', 0)
    itm_ce_normal = calc.get_itm_strike(atm, 'CE', 3)
    print(f"\nITM CE (Expiry day): {itm_ce_expiry}")
    print(f"ITM CE (Normal day): {itm_ce_normal}")
