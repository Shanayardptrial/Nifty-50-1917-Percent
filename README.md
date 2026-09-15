# Nifty 50 Options Buyer Strategy (+1,917% Return)

An advanced Quantitative Black-Scholes Delta Expansion & Garman-Klass Volatility model for Nifty 50 Options Buying (15m Timeframe).

## 📊 Backtest Performance (Year 2026)
* **Initial Capital**: ₹15,000.00
* **Final Capital**: **₹3,02,580.15**
* **Net Return**: **+1,917.20%**
* **Win Rate**: **46.63%** (256 Wins / 293 Losses)
* **Risk-Reward Ratio**: 1 : 4.3 (Asymmetric High Payoff Strategy)
* **Max Drawdown**: -24.03%

## 📂 Repository Contents
* `bs_nifty_option_buyer_15m.pine`: TradingView Pine Script (v5) implementation.
* `backtest_version_1_2026.py`: Full Python backtest engine using Black-Scholes Delta & Garman-Klass Volatility math.
* `live_paper_trader_bot.py`: Live paper trading bot engine.
* `backtest_version_1_2026.csv`: Detailed trade log export.
* `summary_v1.md`: Model architecture and performance breakdown summary.

## 🚀 How to Run Backtest
```bash
pip install -r requirements.txt
python backtest_version_1_2026.py
```
