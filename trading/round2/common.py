"""Shared pieces for the round-2 strategies: data loading, statistics and the
walk-forward protocol that every strategy goes through.

Walk-forward protocol (fixed before any second-half result was looked at):
  1. Each strategy declares a small parameter grid up front.
  2. Every variant is run over the whole window; trades belong to the half in
     which they were entered.
  3. The variant with the highest first-half profit factor (with at least
     MIN_TRADES first-half trades) is selected.
  4. Only that variant's second-half result counts. Promotion to paper trading
     needs second-half profit factor >= 1.2 and max drawdown < $150.
"""
import glob
import json
import zipfile

import numpy as np
import pandas as pd

ACCOUNT = 2500.0
RISK = 25.0
MIN_PF, MAX_DD = 1.2, 150.0
COST = {"SPY": 0.0001, "QQQ": 0.0001, "BTC": 0.001, "ETH": 0.001}  # per side


def load_daily_etf(data_dir, sym):
    r = json.load(open(f"{data_dir}/{sym}-1d.json"))["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({k: q[k] for k in ["open", "high", "low", "close"]})
    df.index = pd.to_datetime(r["timestamp"], unit="s", utc=True).tz_convert("America/New_York").normalize().tz_localize(None)
    return df.dropna()


def load_daily_crypto(data_dir, sym):
    frames = []
    for path in sorted(glob.glob(f"{data_dir}/{sym}USDT-1d-*.zip")):
        with zipfile.ZipFile(path) as z:
            f = pd.read_csv(z.open(z.namelist()[0]), header=None, usecols=range(5))
        f.columns = ["t", "open", "high", "low", "close"]
        f["t"] = pd.to_datetime(f["t"], unit="us" if f["t"].iloc[0] > 1e14 else "ms")
        frames.append(f)
    return pd.concat(frames).set_index("t").sort_index()


def load_all(data_dir):
    return {"SPY": load_daily_etf(data_dir, "SPY"), "QQQ": load_daily_etf(data_dir, "QQQ"),
            "BTC": load_daily_crypto(data_dir, "BTC"), "ETH": load_daily_crypto(data_dir, "ETH")}


def rma(x, n):
    return x.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def atr(df, n=14):
    pc = df.close.shift()
    tr = pd.concat([df.high - df.low, (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    return rma(tr, n)


def rsi(x, n):
    d = x.diff()
    return 100 - 100 / (1 + rma(d.clip(lower=0), n) / rma(-d.clip(upper=0), n))


def stats(tr, months):
    """tr: DataFrame with columns entry, exit, pnl."""
    if len(tr) == 0:
        return dict(trades=0, win_rate=float("nan"), pf=float("nan"), net=0, max_dd=0, monthly=0.0)
    tr = tr.sort_values("exit")
    eq = tr.pnl.cumsum()
    dd = float((eq.cummax().clip(lower=0) - eq).max())
    wins, losses = tr.pnl[tr.pnl > 0].sum(), -tr.pnl[tr.pnl <= 0].sum()
    return dict(trades=len(tr), win_rate=100 * (tr.pnl > 0).mean(),
                pf=wins / losses if losses else float("inf"), net=tr.pnl.sum(),
                max_dd=dd, monthly=tr.pnl.sum() / months)


def months_between(a, b):
    return (pd.Timestamp(b) - pd.Timestamp(a)).days / 30.44


def walk_forward(name, grid, run, start, split, end, min_trades=20):
    """run(params) -> trades DataFrame over [start, end]. Returns a result dict."""
    start, split, end = map(pd.Timestamp, (start, split, end))
    m1, m2 = months_between(start, split), months_between(split, end)
    scored = []
    for p in grid:
        tr = run(p)
        tr = tr[(tr.entry >= start) & (tr.entry <= end)]
        s1 = stats(tr[tr.entry < split], m1)
        scored.append((s1["pf"] if s1["trades"] >= min_trades else -1.0, p, tr, s1))
    best = max(scored, key=lambda x: x[0])
    _, p, tr, s1 = best
    s2 = stats(tr[tr.entry >= split], m2)
    ok = s2["trades"] > 0 and s2["pf"] >= MIN_PF and s2["max_dd"] < MAX_DD
    return dict(name=name, params=p, window=(start.date(), split.date(), end.date()),
                is_=s1, oos=s2, passed=bool(ok), variants=len(grid),
                qualified=sum(1 for x in scored if x[0] >= 0), trades=tr,
                all_is=[(x[1], x[3]) for x in scored])


def fmt(s):
    return (f"trades={s['trades']:>3}  win={s['win_rate']:5.1f}%  PF={s['pf']:5.2f}  "
            f"net=${s['net']:8.0f}  maxDD=${s['max_dd']:6.0f}  avg/month=${s['monthly']:7.1f} "
            f"({100 * s['monthly'] / ACCOUNT:+.1f}% of $2,500)")


def report(r):
    a, b, c = r["window"]
    print(f"\n=== {r['name']} ===")
    print(f"window {a} -> {c}, split {b}; {r['variants']} variants, {r['qualified']} with enough first-half trades")
    print(f"selected on first half: {r['params']}")
    print(f"  in-sample     : {fmt(r['is_'])}")
    print(f"  out-of-sample : {fmt(r['oos'])}")
    print(f"  VERDICT: {'PASS' if r['passed'] else 'FAIL'} (rule: out-of-sample PF >= {MIN_PF} and max DD < ${MAX_DD:.0f})")
