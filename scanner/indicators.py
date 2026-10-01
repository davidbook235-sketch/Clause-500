"""Indicators + scoring rules.

Rules tumhari export file (EMA20>EMA50, RSI>55, MACD bullish, 20-day breakout,
Volume spike) se liye gaye hain. Score = kitni conditions True hain (max 5).
BUY: score >= 4, WATCH: score == 3. SL = Entry - ATR_mult*ATR, Target = Entry + RR*risk.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Params:
    ema_fast: int = 20
    ema_slow: int = 50
    rsi_period: int = 14
    rsi_min: float = 55.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    breakout_days: int = 20
    vol_days: int = 20
    vol_mult: float = 1.5
    atr_period: int = 14
    atr_mult: float = 1.5
    rr: float = 2.0
    buy_score: int = 4
    watch_score: int = 3


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up, dn = d.clip(lower=0), -d.clip(upper=0)
    ru = up.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rd = dn.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    out = 100 - 100 / (1 + ru / rd.replace(0, np.nan))
    out[(rd == 0) & ru.notna()] = 100.0
    return out


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["Close"].shift(1)
    tr = pd.concat(
        [df["High"] - df["Low"], (df["High"] - pc).abs(), (df["Low"] - pc).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def add_indicators(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    d = df.copy()
    c = d["Close"]
    d["ema_f"], d["ema_s"] = ema(c, p.ema_fast), ema(c, p.ema_slow)
    d["rsi"] = rsi(c, p.rsi_period)
    d["macd"] = ema(c, p.macd_fast) - ema(c, p.macd_slow)
    d["macd_sig"] = ema(d["macd"], p.macd_signal)
    d["atr"] = atr(d, p.atr_period)
    d["hh"] = d["High"].shift(1).rolling(p.breakout_days).max()
    d["vol_avg"] = d["Volume"].shift(1).rolling(p.vol_days).mean()
    d["vol_ratio"] = d["Volume"] / d["vol_avg"]

    d["c_ema"] = d["ema_f"] > d["ema_s"]
    d["c_rsi"] = d["rsi"] > p.rsi_min
    d["c_macd"] = d["macd"] > d["macd_sig"]
    d["c_brk"] = c > d["hh"]
    d["c_vol"] = d["vol_ratio"] > p.vol_mult
    conds = ["c_ema", "c_rsi", "c_macd", "c_brk", "c_vol"]
    d[conds] = d[conds].fillna(False).astype(bool)
    d["score"] = d[conds].sum(axis=1).astype(int)
    return d


def reason_labels(p: Params) -> dict:
    return {
        "c_ema": f"EMA{p.ema_fast} > EMA{p.ema_slow}",
        "c_rsi": f"RSI > {p.rsi_min:g}",
        "c_macd": "MACD bullish",
        "c_brk": f"{p.breakout_days}-day breakout",
        "c_vol": "Volume spike",
    }


MIN_BARS = 80


def scan_symbol(sym: str, df: pd.DataFrame, p: Params):
    """Latest candle par signal. None agar score watch_score se kam ho."""
    if df is None or len(df) < MIN_BARS:
        return None
    d = add_indicators(df, p)
    r = d.iloc[-1]
    if pd.isna(r["atr"]) or r["score"] < p.watch_score:
        return None
    entry = float(r["Close"])
    risk = p.atr_mult * float(r["atr"])
    labels = reason_labels(p)
    return {
        "Symbol": sym,
        "Signal": "BUY" if r["score"] >= p.buy_score else "WATCH",
        "Score": int(r["score"]),
        "Entry": round(entry, 2),
        "StopLoss": round(entry - risk, 2),
        "Target": round(entry + p.rr * risk, 2),
        "Reasons": ", ".join(v for k, v in labels.items() if r[k]),
        "RSI": round(float(r["rsi"]), 1),
        "VolX": round(float(r["vol_ratio"]), 2) if pd.notna(r["vol_ratio"]) else None,
        "Risk%": round(risk / entry * 100, 2),
    }


def scan_all(prices: dict, p: Params) -> pd.DataFrame:
    rows = [x for s, df in prices.items() if (x := scan_symbol(s, df, p))]
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    return out.sort_values(["Score", "VolX"], ascending=False, na_position="last").reset_index(drop=True)
