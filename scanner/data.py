"""Nifty 500 universe + yfinance price download."""
import io
import os

import pandas as pd
import requests
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_CSV = os.path.join(HERE, "..", "data", "nifty500.csv")
NSE_URLS = [
    "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
    "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
]
# Last-resort fallback (agar NSE site block kare aur data/nifty500.csv na ho)
FALLBACK = (
    "RELIANCE TCS HDFCBANK ICICIBANK INFY SBIN BHARTIARTL ITC LT HINDUNILVR AXISBANK KOTAKBANK "
    "BAJFINANCE MARUTI SUNPHARMA TITAN ASIANPAINT ULTRACEMCO NTPC POWERGRID ONGC TATASTEEL "
    "M&M TATAMOTORS ADANIENT ADANIPORTS COALINDIA JSWSTEEL HCLTECH WIPRO TECHM NESTLEIND "
    "BAJAJ-AUTO EICHERMOT HEROMOTOCO DRREDDY CIPLA DIVISLAB APOLLOHOSP HAL BEL SIEMENS "
    "ABB HAVELLS POLYCAB DIXON TRENT ZOMATO INDIGO IRCTC PFC RECLTD BHEL SAIL NMDC "
    "ABDL CARBORUNIV CASTROLIND LALPATHLAB ENGINERSIN GESHIP HBLENGINE HFCL KIRLOSENG "
    "LEMONTREE SYRMA TEGA WHIRLPOOL WELSPUNLIV SCHNEIDER SUNTV"
).split()


def load_universe():
    """(symbols, source) return karta hai."""
    for url in NSE_URLS:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            syms = df["Symbol"].astype(str).str.strip().tolist()
            if len(syms) > 400:
                os.makedirs(os.path.dirname(LOCAL_CSV), exist_ok=True)
                df.to_csv(LOCAL_CSV, index=False)
                return syms, "NSE (live list)"
        except Exception:
            continue
    if os.path.exists(LOCAL_CSV):
        try:
            return pd.read_csv(LOCAL_CSV)["Symbol"].astype(str).str.strip().tolist(), "local data/nifty500.csv"
        except Exception:
            pass
    return FALLBACK, "built-in fallback (chhoti list) - data/nifty500.csv add karo"


def download_prices(symbols, period="1y", interval="1d") -> dict:
    """{symbol: OHLCV DataFrame}. Jo symbol Yahoo par na mile woh skip."""
    tick = [s + ".NS" for s in symbols]
    raw = yf.download(
        tick, period=period, interval=interval, group_by="ticker",
        auto_adjust=True, progress=False, threads=True,
    )
    out = {}
    if raw is None or raw.empty:
        return out
    for s, t in zip(symbols, tick):
        try:
            d = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
            d = d[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
            if getattr(d.index, "tz", None) is not None:
                d.index = d.index.tz_localize(None)
            if len(d) >= 60:
                out[s] = d
        except KeyError:
            continue
    return out
