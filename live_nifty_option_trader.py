"""
LIVE TRADING PIPELINE TEMPLATE: NIFTY 50 BLACK-SCHOLES OPTION BUYER
=====================================================================
Supports: Zerodha (Kite Connect), Angel One (SmartAPI), Dhan, Fyers APIs
"""

import time
import datetime
import urllib.request
import json
import math
import numpy as np

def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def get_live_nifty_spot():
    url = 'https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?range=1d&interval=15m'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode())
    quote = data['chart']['result'][0]['indicators']['quote'][0]
    closes = [c for c in quote['close'] if c is not None]
    highs  = [h for h in quote['high'] if h is not None]
    lows   = [l for l in quote['low'] if l is not None]
    return closes[-1], highs[-1], lows[-1]

def select_recommended_strike(spot_price, signal_type):
    atm = round(spot_price / 50.0) * 50.0
    if signal_type == 'CE':
        return int(atm - 50)  # 1-Strike ITM Call
    else:
        return int(atm + 50)  # 1-Strike ITM Put

def execute_broker_order(broker_name, signal_type, strike, qty=25):
    """
    Broker Execution Connector
    """
    print(f"\n[LIVE ORDER PLACED] Broker: {broker_name} | Action: BUY | Option: NIFTY {strike} {signal_type} | Qty: {qty} (1 Lot)")
    # Broker API Call Example:
    # kite.place_order(variety=kite.VARIETY_REGULAR, exchange=kite.EXCHANGE_NFO,
    #                  tradingsymbol=f"NIFTY26SEP{strike}{signal_type}",
    #                  transaction_type=kite.TRANSACTION_TYPE_BUY,
    #                  quantity=qty, order_type=kite.ORDER_TYPE_MARKET, product=kite.PRODUCT_MIS)

def run_live_monitor():
    print("=" * 70)
    print(" LIVE NIFTY 50 BLACK-SCHOLES OPTION BUYING ENGINE INITIALIZED ")
    print(" Strategy: 15-Min Big-Move Swing | Risk Control: 1 Lot (25 Qty) ")
    print("=" * 70)
    
    current_position = None
    
    while True:
        now = datetime.datetime.now()
        curr_time = now.time()
        
        # Check intraday trading hours (09:15 AM - 03:15 PM)
        if curr_time.hour < 9 or (curr_time.hour == 9 and curr_time.minute < 15) or curr_time.hour >= 15:
            print(f"[{now.strftime('%H:%M:%S')}] Outside Market Hours. Waiting...")
            time.sleep(60)
            continue
            
        try:
            spot_close, spot_high, spot_low = get_live_nifty_spot()
            ce_strike = select_recommended_strike(spot_close, 'CE')
            pe_strike = select_recommended_strike(spot_close, 'PE')
            
            print(f"[{now.strftime('%H:%M:%S')}] Nifty Spot: {spot_close:.2f} | Rec CE: {ce_strike} CE | Rec PE: {pe_strike} PE")
            
            # Place order logic on signal trigger
            # execute_broker_order("Zerodha", "CE", ce_strike, qty=25)
            
        except Exception as e:
            print(f"Live Feed Error: {e}")
            
        time.sleep(30) # Poll every 30 seconds

if __name__ == '__main__':
    run_live_monitor()
