"""Strategy 2: daily swing - buy a short-term pullback inside an uptrend.

Markets: SPY, QQQ, BTC, ETH (daily bars, long only, one position per market).

Rules (signals on the daily close, orders at the next daily open):
  entry : close > SMA(trend_n)  and  RSI(2) < rsi_thr           -> buy next open
  stop  : entry - stop_atr * ATR(14) of the signal day (resting stop order;
          a gap below it fills at the open)
  exit  : close > SMA(5) -> sell next open; or after 10 bars -> sell next open
  size  : $25 / (stop_atr * ATR), capped so notional <= $2,500 (no leverage)
  costs : 0.01% per side ETFs, 0.10% per side crypto

Grid (8 variants): rsi_thr {10, 25} x trend_n {100, 200} x stop_atr {2, 3}
"""
import itertools

import numpy as np
import pandas as pd

from common import ACCOUNT, COST, RISK, atr, rsi

GRID = [dict(rsi_thr=r, trend_n=t, stop_atr=k) for r, t, k in itertools.product((10, 25), (100, 200), (2, 3))]
MAX_HOLD = 10


def run_symbol(df, sym, p):
    o, h, l, c = (df[k].values for k in ["open", "high", "low", "close"])
    a = atr(df).values
    r2 = rsi(df.close, 2).values
    trend = df.close.rolling(p["trend_n"]).mean().values
    fast = df.close.rolling(5).mean().values
    cost, out, pos = COST[sym], [], None
    for i in range(1, len(df)):
        if pos is None:
            j = i - 1
            if np.isfinite(trend[j]) and np.isfinite(a[j]) and c[j] > trend[j] and r2[j] < p["rsi_thr"]:
                dist = p["stop_atr"] * a[j]
                qty = min(RISK / dist, ACCOUNT / o[i])
                pos = dict(entry=o[i], stop=o[i] - dist, qty=qty, i=i, t=df.index[i])
        if pos is not None:
            px = None
            if i > pos["i"] and (c[i - 1] > fast[i - 1] or i - pos["i"] >= MAX_HOLD):
                px = o[i]                                   # exit signalled on yesterday's close
            elif l[i] <= pos["stop"]:
                px = min(pos["stop"], o[i])
            if px is not None:
                pnl = (px - pos["entry"]) * pos["qty"] - cost * pos["qty"] * (px + pos["entry"])
                out.append((pos["t"], df.index[i], sym, pnl))
                pos = None
    return pd.DataFrame(out, columns=["entry", "exit", "sym", "pnl"])


def run(data, p):
    return pd.concat([run_symbol(df, s, p) for s, df in data.items()], ignore_index=True)
