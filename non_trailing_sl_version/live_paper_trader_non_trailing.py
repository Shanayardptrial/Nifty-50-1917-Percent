import time
import datetime
import os
import json
import math
import urllib.request
import numpy as np
import pandas as pd

# ==========================================
# CONFIGURATION - NON-TRAILING SL (FIXED SL & TARGET)
# ==========================================
SYMBOL = "%5ENSEI"  # Nifty 50 Index (^NSEI)
LOT_SIZE = 65       # 1 Lot Nifty (65 Qty)
INITIAL_CAPITAL = 15000.0
SL_SPOT_POINTS = 35.0
TARGET_SPOT_POINTS = 150.0
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "live_paper_trades_non_trailing.csv")
STATE_FILE = os.path.join(BASE_DIR, "bot_state_non_trailing.json")

TELEGRAM_BOT_TOKEN = "8859909604:AAH7TtJlGQetefXLXrJ6W3jOIvF9pVdXH3Q" 
TELEGRAM_CHAT_ID = "6680606934"

def std_norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def send_telegram(message):
    try:
        print(f"\n[ALERT] {message.encode('ascii', 'ignore').decode('ascii')}")
    except Exception:
        pass
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            req = urllib.request.Request(url, data=json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}).encode('utf-8'), headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"Telegram error: {e}")

def calculate_option_price(spot, strike, option_type, days_to_expiry=4, iv=0.14, r=0.07):
    T = max(days_to_expiry / 365.0, 0.001)
    d1 = (math.log(spot / strike) + (r + 0.5 * iv**2) * T) / (iv * math.sqrt(T))
    d2 = d1 - iv * math.sqrt(T)
    if option_type == 'CE':
        price = spot * std_norm_cdf(d1) - strike * math.exp(-r * T) * std_norm_cdf(d2)
        delta = std_norm_cdf(d1)
    else:
        price = strike * math.exp(-r * T) * std_norm_cdf(-d2) - spot * math.exp(-r * T) * std_norm_cdf(-d1)
        delta = std_norm_cdf(d1) - 1.0
    return max(round(price, 2), 2.0), round(abs(delta), 3)

class LivePaperTraderNonTrailingBot:
    def __init__(self):
        self.capital = INITIAL_CAPITAL
        self.active_trade = None
        self.load_trades()

    def load_trades(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
                    self.capital = state.get("capital", INITIAL_CAPITAL)
                    self.active_trade = state.get("active_trade", None)
            except Exception:
                pass

    def save_state(self):
        with open(STATE_FILE, "w") as f:
            json.dump({"capital": self.capital, "active_trade": self.active_trade}, f, indent=4)

    def fetch_live_data(self):
        urls = [
            f"https://query2.finance.yahoo.com/v8/finance/chart/{SYMBOL}?range=5d&interval=15m",
            f"https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}?range=5d&interval=15m"
        ]
        headers = {'User-Agent': 'Mozilla/5.0'}

        for url in urls:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    result = data['chart']['result'][0]
                    timestamps = result['timestamp']
                    quote = result['indicators']['quote'][0]
                    
                    df = pd.DataFrame({
                        'Open': quote['open'],
                        'High': quote['high'],
                        'Low': quote['low'],
                        'Close': quote['close']
                    }, index=pd.to_datetime(timestamps, unit='s'))
                    df.dropna(inplace=True)
                    if len(df) >= 10:
                        return df
            except Exception:
                continue
        return None

    def evaluate_signals(self, df):
        if len(df) < 30:
            return None, df['Close'].iloc[-1] if not df.empty else 0
        
        df = df.copy()
        gk_var = 0.5 * (np.log(df['High'] / df['Low']))**2 - (2 * np.log(2) - 1) * (np.log(df['Close'] / df['Open']))**2
        df['gk_vol'] = np.sqrt(np.maximum(0.0, gk_var))
        df['ma_vol'] = df['gk_vol'].rolling(20).mean()

        last_bar = df.iloc[-1]
        prev_bar = df.iloc[-2]
        close = last_bar['Close']
        
        is_bullish = (close > prev_bar['High']) and (last_bar['gk_vol'] > last_bar['ma_vol'])
        is_bearish = (close < prev_bar['Low']) and (last_bar['gk_vol'] > last_bar['ma_vol'])

        if is_bullish:
            return 'CE', close
        elif is_bearish:
            return 'PE', close
        return None, close

    def run_cycle(self):
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df = self.fetch_live_data()
        if df is None or df.empty:
            print(f"[{now_str}] Waiting for live market data...")
            return

        signal, spot = self.evaluate_signals(df)
        print(f"[{now_str}] [NON-TRAILING SL BOT] Spot: {spot:.2f} | Signal: {signal if signal else 'NONE'} | Capital: RS {self.capital:.2f}")

        # Update Active Trade (FIXED SL & TP)
        if self.active_trade:
            opt_type = self.active_trade['type']
            strike = self.active_trade['strike']
            opt_price, _ = calculate_option_price(spot, strike, opt_type)

            if opt_type == 'CE':
                sl_spot = self.active_trade['spot_entry'] - SL_SPOT_POINTS
                target_spot = self.active_trade['spot_entry'] + TARGET_SPOT_POINTS
                hit_sl = spot <= sl_spot
                hit_tp = spot >= target_spot
            else:
                sl_spot = self.active_trade['spot_entry'] + SL_SPOT_POINTS
                target_spot = self.active_trade['spot_entry'] - TARGET_SPOT_POINTS
                hit_sl = spot >= sl_spot
                hit_tp = spot <= target_spot

            if hit_tp or hit_sl:
                reason = "TARGET HIT (+150 Pts)" if hit_tp else "FIXED SL HIT (-35 Pts)"
                pnl = (opt_price - self.active_trade['entry_price']) * LOT_SIZE
                self.capital += pnl
                
                msg = (f"🚨 *EXIT TRADE FIXED SL/TP ({reason})*\n"
                       f"Type: {opt_type} {strike}\n"
                       f"Exit Option Price: ₹{opt_price}\n"
                       f"Spot: {spot:.2f}\n"
                       f"PnL: ₹{pnl:.2f}\n"
                       f"New Capital: ₹{self.capital:.2f}")
                send_telegram(msg)
                
                log_df = pd.DataFrame([{
                    **self.active_trade,
                    'exit_time': now_str,
                    'exit_spot': spot,
                    'exit_opt_price': opt_price,
                    'pnl': round(pnl, 2),
                    'reason': reason,
                    'capital': round(self.capital, 2)
                }])
                log_df.to_csv(LOG_FILE, mode='a', header=not os.path.exists(LOG_FILE), index=False)
                self.active_trade = None
                self.save_state()

        # Enter New Trade
        if self.active_trade is None and signal is not None:
            opt_type = signal
            strike = round(spot / 100) * 100
            strike = strike - 100 if opt_type == 'CE' else strike + 100
            opt_price, delta = calculate_option_price(spot, strike, opt_type)

            cost = opt_price * LOT_SIZE
            if cost <= self.capital:
                self.active_trade = {
                    'entry_time': now_str,
                    'type': opt_type,
                    'strike': strike,
                    'spot_entry': spot,
                    'entry_price': opt_price,
                    'delta': delta,
                    'qty': LOT_SIZE,
                    'investment': cost
                }
                self.save_state()
                msg = (f"🚀 *NEW LIVE PAPER TRADE (NON-TRAILING)*\n"
                       f"Type: {opt_type} {strike}\n"
                       f"Spot: {spot:.2f}\n"
                       f"Option Premium: ₹{opt_price} (Delta: {delta})\n"
                       f"1 Lot (65 Qty) Cost: ₹{cost:.2f}\n"
                       f"Target Spot: {spot + TARGET_SPOT_POINTS if opt_type=='CE' else spot - TARGET_SPOT_POINTS:.2f}\n"
                       f"SL Spot: {spot - SL_SPOT_POINTS if opt_type=='CE' else spot + SL_SPOT_POINTS:.2f}")
                send_telegram(msg)

if __name__ == "__main__":
    bot = LivePaperTraderNonTrailingBot()
    print("[BOT] Autonomous Live Paper Trader Started (Fixed SL/TP Model)")
    send_telegram("🤖 *Nifty Autonomous Live Trader Online*\nStrategy: Fixed SL (-35 Pts) & Target (+150 Pts)\nMonitoring 15m Market Candles...")
    
    # Continuous 60s live cycle loop
    while True:
        try:
            bot.run_cycle()
        except Exception as e:
            print(f"Cycle error: {e}")
        time.sleep(60)
