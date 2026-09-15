import urllib.request
import json
import math
import pandas as pd
import numpy as np
import datetime
import os

# ==========================================
# VERSION 1: BASELINE BLACK-SCHOLES QUANT MODEL
# Lot Size: 65 Qty (Nifty)
# ==========================================
LOT_SIZE = 65
INITIAL_CAPITAL = 15000.0
SL_SPOT_PTS = 35.0
TP_SPOT_PTS = 150.0

def std_norm_cdf(x):
    erf_vec = np.vectorize(math.erf)
    return 0.5 * (1.0 + erf_vec(x / np.sqrt(2.0)))

def calculate_option_price(spot, strike, option_type, days_to_expiry=4, iv=0.14, r=0.07):
    T = max(days_to_expiry / 365.0, 0.001)
    d1 = (np.log(spot / strike) + (r + 0.5 * iv**2) * T) / (iv * np.sqrt(T))
    d2 = d1 - iv * np.sqrt(T)
    if option_type == 'CE':
        price = spot * std_norm_cdf(d1) - strike * np.exp(-r * T) * std_norm_cdf(d2)
        delta = std_norm_cdf(d1)
    else:
        price = strike * np.exp(-r * T) * std_norm_cdf(-d2) - spot * np.exp(-r * T) * std_norm_cdf(-d1)
        delta = std_norm_cdf(d1) - 1.0
    return max(round(price, 2), 2.0), round(abs(delta), 3)

def fetch_2026_data():
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?period1=1767225600&period2=1789430400&interval=1h"
    headers = {'User-Agent': 'Mozilla/5.0'}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    result = data['chart']['result'][0]
    timestamps = result['timestamp']
    quote = result['indicators']['quote'][0]
    
    df = pd.DataFrame({
        'open': quote['open'],
        'high': quote['high'],
        'low': quote['low'],
        'close': quote['close']
    }, index=pd.to_datetime(timestamps, unit='s', utc=True).tz_convert('Asia/Kolkata'))
    df.dropna(inplace=True)
    return df

def run_v1_backtest():
    df = fetch_2026_data()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_out = os.path.join(base_dir, "backtest_version_1_2026.csv")
    
    capital = INITIAL_CAPITAL
    active_trade = None
    trades = []

    for i in range(1, len(df)):
        curr_dt = df.index[i]
        last_bar = df.iloc[i]
        prev_bar = df.iloc[i-1]
        spot = last_bar['close']
        high = last_bar['high']
        low = last_bar['low']

        # Version 1 Exit Check (Trailing SL)
        if active_trade is not None:
            opt_type = active_trade['type']
            spot_entry = active_trade['spot_entry']
            entry_price = active_trade['entry_price']
            strike = active_trade['strike']
            curr_sl_spot = active_trade['sl_spot']
            peak_spot = active_trade['peak_spot']

            if opt_type == 'CE':
                peak_spot = max(peak_spot, high)
                curr_sl_spot = max(curr_sl_spot, peak_spot - SL_SPOT_PTS)
                hit_sl = low <= curr_sl_spot
            else:
                peak_spot = min(peak_spot, low)
                curr_sl_spot = min(curr_sl_spot, peak_spot + SL_SPOT_PTS)
                hit_sl = high >= curr_sl_spot

            active_trade['peak_spot'] = peak_spot
            active_trade['sl_spot'] = curr_sl_spot

            if hit_sl:
                exit_spot = curr_sl_spot
                pts = (exit_spot - spot_entry) if opt_type == 'CE' else (spot_entry - exit_spot)
                reason = f"TRAILING SL HIT ({pts:+.1f} Spot Pts)" if pts > 0 else f"STOP LOSS HIT ({pts:+.1f} Spot Pts)"

                exit_opt_price, _ = calculate_option_price(exit_spot, strike, opt_type)
                pnl = (exit_opt_price - entry_price) * LOT_SIZE
                capital += pnl

                trades.append({
                    'Trade #': len(trades) + 1,
                    'Entry Time': active_trade['entry_time'],
                    'Exit Time': curr_dt.strftime('%Y-%m-%d %H:%M'),
                    'Type': opt_type,
                    'Strike': strike,
                    'Entry Spot': round(spot_entry, 2),
                    'Exit Spot': round(exit_spot, 2),
                    'Option Buy Price (RS)': entry_price,
                    'Option Sell Price (RS)': exit_opt_price,
                    'Qty': LOT_SIZE,
                    'Trade PnL (RS)': round(pnl, 2),
                    'Return (%)': round((pnl / (entry_price * LOT_SIZE)) * 100, 2),
                    'Reason': reason,
                    'Capital (RS)': round(capital, 2)
                })
                active_trade = None

        # Version 1 Entry Check (Simple 15m Breakout)
        if active_trade is None and curr_dt.time() <= datetime.time(14, 45):
            buy_ce_cond = spot > prev_bar['high']
            buy_pe_cond = spot < prev_bar['low']

            if buy_ce_cond or buy_pe_cond:
                opt_type = 'CE' if buy_ce_cond else 'PE'
                atm = round(spot / 100) * 100
                strike = atm - 100 if opt_type == 'CE' else atm + 100
                opt_price, delta = calculate_option_price(spot, strike, opt_type)

                initial_sl = (spot - SL_SPOT_PTS) if opt_type == 'CE' else (spot + SL_SPOT_PTS)
                active_trade = {
                    'entry_time': curr_dt.strftime('%Y-%m-%d %H:%M'),
                    'type': opt_type,
                    'strike': strike,
                    'spot_entry': spot,
                    'entry_price': opt_price,
                    'sl_spot': initial_sl,
                    'peak_spot': spot,
                    'delta': delta,
                    'qty': LOT_SIZE
                }

    trades_df = pd.DataFrame(trades)
    print("==================================================")
    print("  VERSION 1 BASELINE BS MODEL: 2026 BACKTEST (LOT SIZE = 65)")
    print("==================================================")
    print(f"Initial Capital: RS {INITIAL_CAPITAL:,.2f}")
    print(f"Final Capital:   RS {capital:,.2f}")
    net_pnl = capital - INITIAL_CAPITAL
    pct_return = (net_pnl / INITIAL_CAPITAL) * 100
    print(f"Net Profit/Loss: RS {net_pnl:,.2f} ({pct_return:+.2f}%)")
    print(f"Total Trades:    {len(trades)}")

    if len(trades) > 0:
        wins = [t for t in trades if t['Trade PnL (RS)'] > 0]
        losses = [t for t in trades if t['Trade PnL (RS)'] < 0]
        win_rate = (len(wins) / len(trades)) * 100
        print(f"Wins: {len(wins)} | Losses: {len(losses)}")
        print(f"Win Rate: {win_rate:.2f}%")
        
        cap_series = trades_df['Capital (RS)']
        peak = cap_series.cummax()
        drawdown = (cap_series - peak) / peak
        max_dd = drawdown.min() * 100
        print(f"Max Drawdown:    {max_dd:.2f}%")
        
        try:
            trades_df.to_csv(csv_out, index=False)
            print(f"\n[EXPORTED] Saved Version 1 trade log to {csv_out}")
        except PermissionError:
            alt_out = csv_out.replace(".csv", "_updated.csv")
            trades_df.to_csv(alt_out, index=False)
            print(f"\n[EXPORTED] Primary CSV locked. Saved trade log to {alt_out}")
        print("\n--- Last 5 Trades ---")
        print(trades_df.tail(5).to_string(index=False))

if __name__ == '__main__':
    run_v1_backtest()
