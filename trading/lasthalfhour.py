"""Walk-forward test of last-half-hour momentum on SPY and QQQ 5-minute bars.

Usage: python3 trading/lasthalfhour.py <data_dir>

<data_dir> holds SPY.json and QQQ.json from `fetch_alpaca.py <data_dir> 24`
(24 months, Alpaca SIP feed). Bars are labelled by their start time, New York.

Rules (approved 2026-11-13, fixed before any bar was loaded, nothing tuned):
  * Signal, once per day: close of the 09:55 bar (the 10:00 price) versus the
    previous session's close (close of its 15:55 bar; of its 12:55 bar if that
    session was an early close). Up = long, down = short, unchanged = no trade.
  * Entry at the open of the 15:30 bar.
  * Exit at the close of the 15:55 bar, unless stopped first.
  * Stop distance: the average high-to-low range of the 15:30-15:55 window
    (six bars) over the prior 20 full sessions. Today is never in the average.
    If any bar from the entry bar on trades through the stop, the fill is at
    the stop price.
  * Early-close days are not traded and are left out of the 20-session average.
  * Sizing: shares = $25 / stop distance, fractional allowed.
  * Costs: 1 cent per share slippage on each side, no commission.
  * One trade per asset per day at most.

Protocol:
  1. Each asset's 24 months are cut in half by time. Nothing is tuned, so the
     first half is reported for reference only.
  2. Long and short are reported separately; the verdict is on the two combined.
  3. Per asset: PASS only if second-half profit factor >= 1.2 AND max drawdown
     < $300 AND at least 100 second-half trades.
  4. Run once. No changes after seeing the output.

Pinned gaps:
  * Bar-based fills: the 15:30 open and 15:55 close are bar prices, with no
    real bid/ask behind them.
  * The 15:55 bar's close is the last trade before 16:00, which can differ
    slightly from the official closing-auction price.
  * Early closes are detected from the data, not from a calendar: a session is
    an early close when its 15:30-15:55 volume is under 5% of its 09:30-09:55
    volume. Every skipped day is printed so it can be checked.
  * Sizing here has no notional cap, unlike backtest.run() (which caps at
    $10,000, 4x a $2,500 account). The script prints how many trades were
    above that and what the second half looks like with the cap applied. That
    line is information only; the verdict is on the rules as approved.
"""
import json
import sys

import numpy as np
import pandas as pd

import backtest as B

SYMS = ("SPY", "QQQ")
OPEN, SIGNAL_BAR, ENTRY, LAST_BAR, EARLY_LAST_BAR = 570, 595, 930, 955, 775
LOOKBACK, RISK, SLIP = 20, 25.0, 0.01
EARLY_VOL_RATIO = 0.05
MIN_PF, MAX_DD, MIN_TRADES = 1.2, 300, 100


def load_raw(data_dir, sym):
    r = json.load(open(f"{data_dir}/{sym}.json"))["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({k: q[k] for k in ["open", "high", "low", "close", "volume"]})
    df.index = pd.to_datetime(r["timestamp"], unit="s", utc=True).tz_convert(B.NY)
    return df.dropna().sort_index()


def sessions(raw):
    """One record per trading day with everything the rules need from that day."""
    mins = raw.index.hour * 60 + raw.index.minute
    reg = raw[(mins >= OPEN) & (mins < 960)]
    out, last_date = [], reg.index[-1].date()
    for date, day in reg.groupby(reg.index.date):
        m = np.asarray(day.index.hour * 60 + day.index.minute)
        if date == last_date and m[-1] < LAST_BAR:
            continue  # the fetch ended partway through this session
        first = day[(m >= OPEN) & (m < OPEN + 30)]
        win = day[(m >= ENTRY) & (m <= LAST_BAR)]
        early = win.empty or first.empty or win.volume.sum() < EARLY_VOL_RATIO * first.volume.sum()
        close_bar = day[m == (EARLY_LAST_BAR if early else LAST_BAR)]
        sig = day[m == SIGNAL_BAR]
        out.append(dict(
            date=date, early=early, win=win,
            close=close_bar.close.iloc[0] if len(close_bar) else day.close.iloc[-1],
            px10=sig.close.iloc[0] if len(sig) else None,
            rng=None if early else win.high.max() - win.low.min(),
            complete=(not early) and len(win) == 6))
    return out


def trades(raw, sym, cap=None):
    """All trades for one asset, plus a log of days that were not traded."""
    rows, skipped, ranges, prev_close = [], [], [], None
    for s in sessions(raw):
        reason = None
        if s["early"]:
            reason = "early close"
        elif prev_close is None:
            reason = "no previous close"
        elif len(ranges) < LOOKBACK:
            reason = f"fewer than {LOOKBACK} prior full sessions"
        elif s["px10"] is None:
            reason = "no 09:55 bar"
        elif not s["complete"] or s["win"].index[0].hour * 60 + s["win"].index[0].minute != ENTRY:
            reason = "15:30-15:55 window has missing bars"
        elif s["px10"] == prev_close:
            reason = "no move by 10:00"
        if reason is None:
            d = 1 if s["px10"] > prev_close else -1
            dist = float(np.mean(ranges[-LOOKBACK:]))
            w = s["win"]
            entry = w.open.iloc[0]
            stop = entry - d * dist
            hit = (w.low <= stop) if d > 0 else (w.high >= stop)
            exit_px = stop if hit.any() else w.close.iloc[-1]
            qty = RISK / dist
            if cap is not None:
                qty = min(qty, cap / entry)
            pnl = d * (exit_px - entry) * qty - 2 * SLIP * qty
            rows.append((w.index[-1], sym, pnl, d, bool(hit.any()), RISK / dist * entry))
        elif reason != f"fewer than {LOOKBACK} prior full sessions":
            skipped.append((s["date"], reason))
        if s["rng"] is not None and s["complete"]:
            ranges.append(s["rng"])
        prev_close = s["close"]
    return pd.DataFrame(rows, columns=["time", "sym", "pnl", "dir", "stopped", "notional"]), skipped


def months(a, b):
    return max((b - a).days / 30.4, 0.1)


def line(label, tr, m):
    s = B.stats(tr, m)
    if not s["trades"]:
        print(f"  {label}: no trades")
        return dict(trades=0, profit_factor=0, max_dd=0)
    print(f"  {label}: trades={s['trades']} win={s['win_rate']}% PF={s['profit_factor']} "
          f"net=${s['net']} net/month=${s['monthly_usd']} maxDD=${s['max_dd']} "
          f"stopped={int(tr.stopped.sum())}")
    return s


if __name__ == "__main__":
    data_dir = sys.argv[1]
    verdicts = {}
    for sym in SYMS:
        raw = load_raw(data_dir, sym)
        start, end = raw.index[0], raw.index[-1]
        mid = start + (end - start) / 2
        print(f"\n{sym}: {len(raw)} bars {start.date()} -> {end.date()}, split {mid.date()}")
        if months(start, end) < 23.5:
            print(f"  WARNING: {sym} has {months(start, end):.1f} months, not 24.")
        tr, skipped = trades(raw, sym)
        early = [str(d) for d, why in skipped if why == "early close"]
        other = [f"{d} ({why})" for d, why in skipped if why != "early close"]
        print(f"  early-close days skipped ({len(early)}): " + (", ".join(early) or "none"))
        print(f"  other days skipped ({len(other)}): " + (", ".join(other) or "none"))
        halves = (("first half (reference)", tr[tr.time < mid], months(start, mid)),
                  ("second half (verdict) ", tr[tr.time >= mid], months(mid, end)))
        for name, part, m in halves:
            res = line(f"{name} combined", part, m)
            line(f"{name} long    ", part[part.dir > 0], m)
            line(f"{name} short   ", part[part.dir < 0], m)
        verdicts[sym] = bool(res["trades"] >= MIN_TRADES and res["profit_factor"] >= MIN_PF
                             and res["max_dd"] < MAX_DD)
        over = int((tr.notional > B.MAX_NOTIONAL).sum())
        print(f"  information only: {over} of {len(tr)} trades were above ${B.MAX_NOTIONAL:,.0f} notional")
        capped, _ = trades(raw, sym, cap=B.MAX_NOTIONAL)
        line("information only, second half with that cap applied", capped[capped.time >= mid],
             months(mid, end))

    print(f"\nRule: second-half profit factor >= {MIN_PF} AND max drawdown < ${MAX_DD} "
          f"AND at least {MIN_TRADES} second-half trades (long and short combined)")
    for sym, ok in verdicts.items():
        print(f"  {sym}: {'PASS - eligible for paper trading' if ok else 'FAIL - do not paper trade, do not re-tune'}")
