"""Strategy 3: weekly relative-momentum rotation across SPY, QQQ, BTC, ETH.

Rules:
  decision : after the close of the last US trading day of each week
  rank     : return over the last `lookback` calendar days, per market
  target   : the single top-ranked market, only if its return is > 0; else cash
  entry    : next daily open of that market (Monday for ETFs, Saturday 00:00 UTC
             for crypto)
  stop     : entry - stop_atr * ATR(14); with trail=True the stop is raised at
             each weekly decision to close - stop_atr * ATR(14), never lowered
  exit     : stop hit, or at a weekly decision where the market is no longer
             the target -> sell at its next open
  re-entry : a stopped-out market can be re-entered at the next weekly decision
  size     : $25 / (stop_atr * ATR), capped so notional <= $2,500
  costs    : 0.01% per side ETFs, 0.10% per side crypto

Grid (8 variants): lookback {28, 84} x stop_atr {2, 3} x trail {False, True}
"""
import itertools

import numpy as np
import pandas as pd

from common import ACCOUNT, COST, RISK, atr

GRID = [dict(lookback=lb, stop_atr=k, trail=t) for lb, k, t in itertools.product((28, 84), (2, 3), (False, True))]


def run(data, p):
    spy_days = data["SPY"].index
    week = spy_days.to_series().dt.to_period("W-SUN")
    decisions = spy_days[(week != week.shift(-1)).values][:-1]
    atrs = {s: atr(df) for s, df in data.items()}
    closes = {s: df.close for s, df in data.items()}
    events = sorted(set().union(*[set(df.index) for df in data.values()]))
    decision_set = set(decisions)
    out, pos, pending_exit, pending_entry = [], None, False, None

    def close_pos(px, t):
        nonlocal pos
        pnl = (px - pos["entry"]) * pos["qty"] - COST[pos["sym"]] * pos["qty"] * (px + pos["entry"])
        out.append((pos["t"], t, pos["sym"], pnl))
        pos = None

    for t in events:
        # 1. orders from the last decision fill at this market's open; stops rest intraday
        if pos is not None and t in data[pos["sym"]].index and t > pos["t"]:
            bar = data[pos["sym"]].loc[t]
            if pending_exit:
                close_pos(bar.open, t)
                pending_exit = False
            elif bar.low <= pos["stop"]:
                close_pos(min(pos["stop"], bar.open), t)
        if pending_entry and pos is None and t in data[pending_entry["sym"]].index and t > pending_entry["t"]:
            s, dist = pending_entry["sym"], pending_entry["dist"]
            bar = data[s].loc[t]
            pos = dict(sym=s, entry=bar.open, stop=bar.open - dist, qty=min(RISK / dist, ACCOUNT / bar.open), t=t)
            pending_entry = None
            if bar.low <= pos["stop"]:
                close_pos(pos["stop"], t)
        # 2. weekly decision after the close of day t
        if t in decision_set:
            mom = {}
            for s in data:
                c = closes[s][:t]
                past = c[:t - pd.Timedelta(days=p["lookback"])]
                if len(past) and len(c):
                    mom[s] = c.iloc[-1] / past.iloc[-1] - 1
            target = max(mom, key=mom.get) if mom and max(mom.values()) > 0 else None
            pending_entry = None
            if pos is not None and pos["sym"] != target:
                pending_exit = True
            if pos is not None and pos["sym"] == target and p["trail"]:
                a = atrs[target][:t].iloc[-1]
                pos["stop"] = max(pos["stop"], closes[target][:t].iloc[-1] - p["stop_atr"] * a)
            if target is not None and (pos is None or pos["sym"] != target):
                a = atrs[target][:t].iloc[-1]
                if np.isfinite(a):
                    pending_entry = dict(sym=target, dist=p["stop_atr"] * a, t=t)
    return pd.DataFrame(out, columns=["entry", "exit", "sym", "pnl"])
