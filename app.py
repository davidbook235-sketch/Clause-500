import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scanner.backtest import run_backtest, summarize
from scanner.data import download_prices, load_universe
from scanner.indicators import Params, add_indicators, scan_all

st.set_page_config(page_title="Nifty 500 Scanner", page_icon="📈", layout="wide")
CHUNK = 50


@st.cache_data(ttl=86400, show_spinner=False)
def get_universe():
    return load_universe()


@st.cache_data(ttl=600, show_spinner=False)
def fetch_chunk(symbols: tuple, period: str):
    return download_prices(list(symbols), period=period)


def fetch_all(symbols, period, label):
    bar, prices = st.progress(0.0, text=label), {}
    for i in range(0, len(symbols), CHUNK):
        prices.update(fetch_chunk(tuple(symbols[i:i + CHUNK]), period))
        bar.progress(min(1.0, (i + CHUNK) / len(symbols)), text=f"{label} {min(i + CHUNK, len(symbols))}/{len(symbols)}")
    bar.empty()
    return prices


# ---------------- Sidebar ----------------
symbols, src = get_universe()
st.sidebar.title("⚙️ Settings")
st.sidebar.caption(f"Universe: {len(symbols)} stocks · {src}")
with st.sidebar.expander("Indicators", expanded=False):
    p = Params(
        ema_fast=st.number_input("EMA fast", 5, 100, 20),
        ema_slow=st.number_input("EMA slow", 10, 300, 50),
        rsi_min=st.number_input("RSI >", 40.0, 80.0, 55.0),
        breakout_days=st.number_input("Breakout days", 5, 100, 20),
        vol_mult=st.number_input("Volume spike (x avg)", 1.0, 5.0, 1.5, 0.1),
        atr_mult=st.number_input("StopLoss = ATR x", 0.5, 5.0, 1.5, 0.1),
        rr=st.number_input("Target Risk:Reward", 1.0, 5.0, 2.0, 0.5),
        buy_score=st.slider("BUY min score", 1, 5, 4),
        watch_score=st.slider("WATCH min score", 1, 5, 3),
    )

st.title("📈 Nifty 500 Scanner")
tab_scan, tab_bt, tab_about = st.tabs(["🔍 Live Scanner", "🧪 Backtest", "ℹ️ Rules"])

# ---------------- Live scanner ----------------
with tab_scan:
    c1, c2, c3 = st.columns([2, 1, 1])
    n = c1.slider("Kitne stocks scan karne hain", 20, len(symbols), len(symbols), 10)
    sig_f = c2.multiselect("Signal", ["BUY", "WATCH"], ["BUY", "WATCH"])
    go_scan = c3.button("🔍 Scan now", type="primary", use_container_width=True)
    if c3.button("♻️ Fresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if go_scan:
        prices = fetch_all(symbols[:n], "1y", "Data download")
        st.session_state["prices"] = prices
        st.session_state["scan"] = scan_all(prices, p)
        st.session_state["scan_time"] = dt.datetime.now().strftime("%d %b %Y %H:%M:%S")
        st.session_state["scan_n"] = len(prices)

    res = st.session_state.get("scan")
    if res is None:
        st.info("'Scan now' dabao. Market hours me last candle live hoti hai (Yahoo data ~ thoda delayed).")
    elif res.empty:
        st.warning("Koi stock in conditions par nahi mila.")
    else:
        st.caption(f"Last scan: {st.session_state['scan_time']} · {st.session_state['scan_n']} stocks ka data mila")
        view = res[res["Signal"].isin(sig_f)]
        m1, m2, m3 = st.columns(3)
        m1.metric("BUY", int((res.Signal == "BUY").sum()))
        m2.metric("WATCH", int((res.Signal == "WATCH").sum()))
        m3.metric("Scanned", st.session_state["scan_n"])
        st.dataframe(view, use_container_width=True, hide_index=True)
        st.download_button("⬇️ CSV download", view.to_csv(index=False), "scan_results.csv", "text/csv")

        pick = st.selectbox("Chart dekho", view["Symbol"].tolist()) if not view.empty else None
        if pick:
            d = add_indicators(st.session_state["prices"][pick], p).tail(120)
            row = view[view.Symbol == pick].iloc[0]
            fig = go.Figure(go.Candlestick(x=d.index, open=d.Open, high=d.High, low=d.Low, close=d.Close, name=pick))
            fig.add_scatter(x=d.index, y=d.ema_f, name=f"EMA{p.ema_fast}", line=dict(width=1))
            fig.add_scatter(x=d.index, y=d.ema_s, name=f"EMA{p.ema_slow}", line=dict(width=1))
            for lvl, col in ((row.StopLoss, "red"), (row.Target, "green")):
                fig.add_hline(y=lvl, line_dash="dash", line_color=col)
            fig.update_layout(height=450, xaxis_rangeslider_visible=False, margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig, use_container_width=True)

# ---------------- Backtest ----------------
with tab_bt:
    st.caption("Same rules historical data par: signal candle ke baad agle din open par entry.")
    a, b, c, d_ = st.columns(4)
    period = a.selectbox("History", ["2y", "3y", "5y"], index=1)
    min_score = b.slider("Entry min score", 1, 5, p.buy_score)
    max_hold = c.number_input("Max hold (days)", 1, 120, 20)
    cost = d_.number_input("Cost per side %", 0.0, 1.0, 0.1, 0.05)
    e, f = st.columns(2)
    bt_n = e.slider("Kitne stocks (list ke top N)", 10, len(symbols), min(50, len(symbols)), 10)
    alloc = f.slider("Capital per trade %", 1, 50, 10) / 100
    custom = st.multiselect("Ya khud ke stocks chuno (N ignore hoga)", symbols)

    if st.button("▶️ Run backtest", type="primary"):
        pool = custom or symbols[:bt_n]
        prices = fetch_all(pool, period, "History download")
        with st.spinner("Backtest chal raha hai..."):
            trades = run_backtest(prices, p, min_score=min_score, max_hold=int(max_hold), cost_pct=cost)
        st.session_state["bt"] = (trades, alloc)

    if "bt" in st.session_state:
        trades, alloc_used = st.session_state["bt"]
        if trades.empty:
            st.warning("Is setting par koi trade nahi bana.")
        else:
            met, eq = summarize(trades, alloc=alloc_used)
            cols = st.columns(5)
            for i, (k, v) in enumerate(met.items()):
                cols[i % 5].metric(k, v)
            st.subheader("Equity curve (₹1,00,000 start)")
            st.line_chart(eq)
            g1, g2 = st.columns(2)
            g1.write("**Score ke hisaab se**")
            g1.dataframe(trades.groupby("Score")["ret"].agg(Trades="count", WinRate=lambda s: round((s > 0).mean() * 100, 1),
                                                           AvgRet=lambda s: round(s.mean() * 100, 2)))
            g2.write("**Exit reason**")
            g2.dataframe(trades["Exit reason"].value_counts())
            show = trades.drop(columns="ret")
            st.dataframe(show, use_container_width=True, hide_index=True)
            st.download_button("⬇️ Trades CSV", show.to_csv(index=False), "backtest_trades.csv", "text/csv")
            st.caption("Equity approximate hai: concurrent trades ka capital overlap model nahi kiya. Survivorship bias bhi hai (aaj ki Nifty 500 list).")

# ---------------- About ----------------
with tab_about:
    st.markdown(f"""
**Score = in 5 conditions me se kitni True hain**
1. EMA{p.ema_fast} > EMA{p.ema_slow}
2. RSI > {p.rsi_min:g}
3. MACD > Signal line
4. Close > pichhle {p.breakout_days} din ka high (breakout)
5. Volume > {p.vol_mult}× pichhle 20 din ka average

**BUY** = score ≥ {p.buy_score}, **WATCH** = score ≥ {p.watch_score}.
**StopLoss** = Entry − {p.atr_mult}×ATR(14), **Target** = Entry + {p.rr}×risk.

⚠️ Sirf educational tool hai, investment advice nahi. Real paisa lagane se pehle apni research karo.
""")
