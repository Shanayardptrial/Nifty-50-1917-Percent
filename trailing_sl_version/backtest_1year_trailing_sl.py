import urllib.request, json, math, os, datetime
import pandas as pd, numpy as np

LOT_SIZE, INITIAL_CAPITAL, SL_SPOT_PTS = 65, 15000.0, 35.0

def std_norm_cdf(x):
    return 0.5 * (1.0 + np.vectorize(math.erf)(x / np.sqrt(2.0)))

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

def run_trailing_sl_backtest():
    url = 'https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?range=1y&interval=1h'
    headers = {'User-Agent': 'Mozilla/5.0'}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    result = data['chart']['result'][0]
    df = pd.DataFrame({'open': result['indicators']['quote'][0]['open'], 'high': result['indicators']['quote'][0]['high'], 'low': result['indicators']['quote'][0]['low'], 'close': result['indicators']['quote'][0]['close']}, index=pd.to_datetime(result['timestamp'], unit='s', utc=True).tz_convert('Asia/Kolkata'))
    df.dropna(inplace=True)

    gk_var = 0.5 * (np.log(df['high'] / df['low']))**2 - (2 * np.log(2) - 1) * (np.log(df['close'] / df['open']))**2
    df['gk_vol'] = np.sqrt(np.maximum(0.0, gk_var))
    df['ma_vol'] = df['gk_vol'].rolling(20).mean()

    capital, active_trade, trades = INITIAL_CAPITAL, None, []
    for i in range(20, len(df)):
        curr_dt, last_bar, prev_bar = df.index[i], df.iloc[i], df.iloc[i-1]
        spot, high, low = last_bar['close'], last_bar['high'], last_bar['low']

        if active_trade:
            opt_type, spot_entry, entry_price, strike, curr_sl_spot, peak_spot = active_trade['type'], active_trade['spot_entry'], active_trade['entry_price'], active_trade['strike'], active_trade['sl_spot'], active_trade['peak_spot']
            if opt_type == 'CE':
                peak_spot = max(peak_spot, high)
                curr_sl_spot = max(curr_sl_spot, peak_spot - SL_SPOT_PTS)
                hit_sl = low <= curr_sl_spot
            else:
                peak_spot = min(peak_spot, low)
                curr_sl_spot = min(curr_sl_spot, peak_spot + SL_SPOT_PTS)
                hit_sl = high >= curr_sl_spot

            active_trade['peak_spot'], active_trade['sl_spot'] = peak_spot, curr_sl_spot

            if hit_sl:
                exit_spot = curr_sl_spot
                pts = (exit_spot - spot_entry) if opt_type == 'CE' else (spot_entry - exit_spot)
                exit_opt_price, _ = calculate_option_price(exit_spot, strike, opt_type)
                pnl = (exit_opt_price - entry_price) * LOT_SIZE
                capital += pnl
                trades.append({'Trade #': len(trades)+1, 'Entry Time': active_trade['entry_time'], 'Exit Time': curr_dt.strftime('%Y-%m-%d %H:%M'), 'Type': opt_type, 'Strike': strike, 'Entry Spot': round(spot_entry, 2), 'Exit Spot': round(exit_spot, 2), 'Option Buy Price (RS)': entry_price, 'Option Sell Price (RS)': exit_opt_price, 'Qty': LOT_SIZE, 'Trade PnL (RS)': round(pnl, 2), 'Capital (RS)': round(capital, 2)})
                active_trade = None

        if active_trade is None and curr_dt.time() <= datetime.time(14, 45):
            vol_accel = last_bar['gk_vol'] > last_bar['ma_vol']
            if (spot > prev_bar['high'] and vol_accel) or (spot < prev_bar['low'] and vol_accel):
                opt_type = 'CE' if spot > prev_bar['high'] else 'PE'
                strike = (round(spot / 100) * 100 - 100) if opt_type == 'CE' else (round(spot / 100) * 100 + 100)
                opt_price, delta = calculate_option_price(spot, strike, opt_type)
                active_trade = {'entry_time': curr_dt.strftime('%Y-%m-%d %H:%M'), 'type': opt_type, 'strike': strike, 'spot_entry': spot, 'entry_price': opt_price, 'sl_spot': spot - SL_SPOT_PTS if opt_type=='CE' else spot + SL_SPOT_PTS, 'peak_spot': spot, 'delta': delta}

    out_csv = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backtest_trades_1year_trailing_sl.csv')
    pd.DataFrame(trades).to_csv(out_csv, index=False)
    print(f"[SUCCESS] Trailing SL 1-Year Backtest Finished. Final Capital: RS {capital:,.2f}")

if __name__ == '__main__':
    run_trailing_sl_backtest()
