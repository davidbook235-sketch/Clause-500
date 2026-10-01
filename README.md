# 📈 Nifty 500 Scanner (Streamlit)

Indicators: EMA20>EMA50, RSI>55, MACD bullish, 20-day breakout, Volume spike.
Score = kitni conditions True. BUY ≥ 4, WATCH = 3. SL = ATR based, Target = 1:2 RR.

## Local chalane ke liye
```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub + Streamlit Cloud
1. Is folder ko GitHub repo me push karo.
2. https://share.streamlit.io par login → **New app** → repo chuno → Main file: `app.py` → Deploy.
3. (Optional) `.github/workflows/daily_scan.yml` roz market close ke baad scan chala ke `results/latest_scan.csv` commit karta hai.
   Repo → Settings → Actions → General → Workflow permissions: **Read and write**.

## Nifty 500 list
App pehle NSE se live list laata hai. Agar NSE block kare to `data/nifty500.csv` (column `Symbol`) daal do —
file NSE se download: niftyindices.com → Nifty 500 constituents.

## Notes
- Data yfinance (Yahoo) se aata hai: free, thoda delayed, kabhi kabhi symbols miss.
- Volume spike (1.5x) aur ATR multiplier (1.5x) tumhari CSV se infer kiye gaye hain — sidebar se badal sakte ho.
- Backtest: next-day open entry, SL pehle check hota hai, cost per side configurable.
