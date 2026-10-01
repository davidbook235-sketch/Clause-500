"""CLI scan (GitHub Actions ya local): python run_scan.py"""
import datetime as dt

from scanner.data import download_prices, load_universe
from scanner.indicators import Params, scan_all

if __name__ == "__main__":
    syms, src = load_universe()
    print(f"{len(syms)} symbols ({src})")
    prices = {}
    for i in range(0, len(syms), 50):
        prices.update(download_prices(syms[i:i + 50], period="1y"))
    res = scan_all(prices, Params())
    res.insert(0, "ScanTime", dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))
    res.to_csv("results/latest_scan.csv", index=False)
    print(res.head(20).to_string() if not res.empty else "No signals")
