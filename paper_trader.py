import time
import datetime
import pandas as pd
import numpy as np

# Paper Trading Engine for Nifty Option Buying (1 Lot = 25 Qty)
LOT_SIZE = 65
INITIAL_CAPITAL = 15000.0

class PaperTrader:
    def __init__(self, log_file="paper_trading_log.csv"):
        self.capital = INITIAL_CAPITAL
        self.log_file = log_file
        self.active_position = None
        
    def log_trade(self, trade_data):
        df = pd.DataFrame([trade_data])
        df.to_csv(self.log_file, mode='a', header=not pd.io.common.file_exists(self.log_file), index=False)

    def enter_trade(self, symbol, option_type, strike, entry_price, sl_price, target_price):
        if self.active_position is not None:
            print("[WARN] Position already active!")
            return
        
        cost = entry_price * LOT_SIZE
        if cost > self.capital:
            print(f"[REJECTED] Capital insufficient (Req: ₹{cost:.2f}, Avail: ₹{self.capital:.2f})")
            return
            
        self.active_position = {
            'timestamp_entry': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'symbol': symbol,
            'type': option_type,
            'strike': strike,
            'entry_price': entry_price,
            'sl_price': sl_price,
            'target_price': target_price,
            'qty': LOT_SIZE,
            'investment': cost
        }
        print(f"[BUY ENTRY] {option_type} {strike} @ ₹{entry_price:.2f} | Lot: 1 (25 Qty) | Cost: ₹{cost:.2f}")

    def update_price(self, current_price):
        if self.active_position is None:
            return

        pos = self.active_position
        # Target hit
        if current_price >= pos['target_price']:
            self.exit_trade(current_price, "TARGET_HIT (+1:4.3 RR)")
        # SL hit
        elif current_price <= pos['sl_price']:
            self.exit_trade(current_price, "SL_HIT (-35 Spot Pts)")

    def exit_trade(self, exit_price, reason):
        pos = self.active_position
        pnl = (exit_price - pos['entry_price']) * pos['qty']
        self.capital += pnl
        
        trade_log = {
            **pos,
            'timestamp_exit': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'exit_price': exit_price,
            'pnl': round(pnl, 2),
            'return_pct': round((pnl / pos['investment']) * 100, 2),
            'reason': reason,
            'balance': round(self.capital, 2)
        }
        self.log_trade(trade_log)
        print(f"[EXIT {reason}] Price: ₹{exit_price:.2f} | PnL: ₹{pnl:.2f} ({trade_log['return_pct']}%) | New Balance: ₹{self.capital:.2f}")
        self.active_position = None

if __name__ == "__main__":
    trader = PaperTrader()
    print(f"Paper Trader initialized with ₹{INITIAL_CAPITAL} balance.")
    # Example simulated trade:
    # trader.enter_trade("NIFTY", "CE", 23200, 130.0, 112.5, 205.0)
    # trader.update_price(205.0)
