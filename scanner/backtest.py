"""Simple rule-based backtest.

Signal candle ke close par score >= min_score  ->  next day ke OPEN par entry.
SL = entry - atr_mult*ATR(signal day), Target = entry + rr*risk.
Same candle me SL aur Target dono touch ho to SL pehle maana jata hai (conservative).
Max holding days ke baad close par exit. Ek symbol me ek time par ek hi trade.
"""
import numpy as np
import pandas as pd

from .indicators import Params, add_indicators


def backtest_symbol(sym, df, p: Params, min_score=4, max_hold=20, cost_pct=0.1) -> list:
    d = add_indicators(df, p)
    o, h, l, c = (d[k].values for k in ("Open", "High", "Low", "Close"))
    atr_v, score, idx = d["atr"].values, d["score"].values, d.index
    n, trades, i = len(d), [], 0
    while i < n - 1:
        if score[i] < min_score or np.isnan(atr_v[i]):
            i += 1
            continue
        e = o[i + 1]
        risk = p.atr_mult * atr_v[i]
        sl, tgt = e - risk, e + p.rr * risk
        if not (e > 0 and sl > 0):
            i += 1
            continue
        last = min(i + max_hold, n - 1)
        px, why, j = c[last], "TIME", last
        for j in range(i + 1, last + 1):
            if l[j] <= sl:
                px, why = min(sl, o[j]), "STOP"
                break
            if h[j] >= tgt:
                px, why = max(tgt, o[j]), "TARGET"
                break
        ret = px / e - 1 - 2 * cost_pct / 100
        trades.append({
            "Symbol": sym, "Score": int(score[i]), "EntryDate": idx[i + 1], "ExitDate": idx[j],
            "Entry": round(e, 2), "Exit": round(px, 2), "Exit reason": why,
            "Days": j - i, "ret": ret,
        })
        i = j
    return trades


def run_backtest(prices: dict, p: Params, **kw) -> pd.DataFrame:
    rows = []
    for s, df in prices.items():
        if len(df) > 100:
            rows += backtest_symbol(s, df, p, **kw)
    t = pd.DataFrame(rows)
    if not t.empty:
        t = t.sort_values("ExitDate").reset_index(drop=True)
        t["Return%"] = (t["ret"] * 100).round(2)
    return t


def summarize(t: pd.DataFrame, alloc=0.1, capital=100000.0):
    """(metrics dict, equity DataFrame). Equity approximate hai: har trade me capital ka `alloc` fraction."""
    if t.empty:
        return {}, pd.DataFrame()
    r = t["ret"].values
    wins, losses = r[r > 0], r[r <= 0]
    eq = capital * np.cumprod(1 + r * alloc)
    peak = np.maximum.accumulate(np.r_[capital, eq])[1:]
    m = {
        "Trades": len(r),
        "Win rate %": round(len(wins) / len(r) * 100, 1),
        "Avg return/trade %": round(r.mean() * 100, 2),
        "Avg win %": round(wins.mean() * 100, 2) if len(wins) else 0.0,
        "Avg loss %": round(losses.mean() * 100, 2) if len(losses) else 0.0,
        "Profit factor": round(wins.sum() / abs(losses.sum()), 2) if losses.sum() != 0 else float("inf"),
        "Total return %": round((eq[-1] / capital - 1) * 100, 1),
        "Max drawdown %": round(((eq / peak) - 1).min() * 100, 1),
        "Avg hold days": round(t["Days"].mean(), 1),
    }
    return m, pd.DataFrame({"Equity": eq}, index=pd.to_datetime(t["ExitDate"].values))
