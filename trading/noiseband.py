"""Walk-forward test of noise-band intraday momentum on SPY and QQQ 5-minute bars.

Usage: python3 trading/noiseband.py <data_dir>

<data_dir> holds SPY.json and QQQ.json from `fetch_alpaca.py <data_dir> 24`
(24 months, Alpaca SIP feed). Bars are labelled by their start time, New York.
Only regular-session bars (09:30-15:55) are used.

Rules (approved 2026-11-13, fixed before the run, nothing tuned):
  * Normal move: for each half-hour check time, the average over the prior 14
    full sessions of |price at that time / that day's open - 1|. "Price at
    10:00" is the close of the 09:55 bar, and so on. Today is never included.
  * Bands: upper = max(today's open, previous close) x (1 + normal move);
    lower = min(today's open, previous close) x (1 - normal move). Today's
    open is the open of the 09:30 bar; the previous close is the close of the
    previous session's 15:55 bar (12:55 bar after an early close).
  * VWAP: intraday, from the 09:30 bar through the current bar, typical price
    (high + low + close) / 3 weighted by volume.
  * Checks happen only on the half-hour, 10:00 through 15:30, on the close of
    the bar that ends at that time. Every fill is the next bar's open.
  * Entry when flat: close above the upper band = long; below the lower band
    = short.
  * Exit: a long exits when the close is below the higher of the upper band
    and VWAP; a short exits when the close is above the lower of the lower
    band and VWAP.
  * Flat at the close of the 15:55 bar regardless.
  * Re-entry later the same day and flipping sides are allowed. A position
    closed at a check cannot be reopened on the same side at that same check.
  * Sizing: shares = $25 / (entry price x normal move at the entry check),
    capped at $10,000 notional. There is no fixed stop: one normal move
    against the position costs about $25, and a bad day can lose more.
  * Costs: 1 cent per share slippage on each side, no commission.
  * Early-close days are not traded and are left out of the 14-session
    average. A day is an early close if it is on the NYSE calendar below OR
    either asset's data flags it (15:30-15:55 volume under 5% of 09:30-09:55
    volume). Flagged days are skipped for both assets and printed.

Protocol:
  1. Each asset's 24 months are cut in half by time. Nothing is tuned, so the
     first half is reported for reference only.
  2. Long and short are reported separately, with the largest single loss;
     the verdict is on the two combined.
  3. Per asset: PASS only if second-half profit factor >= 1.2 AND max drawdown
     < $300 AND at least 100 second-half trades.
  4. Run once. No changes after seeing the output.

Pinned gaps:
  * Bar-based fills with no real bid/ask behind them.
  * The 15:55 bar's close is the last trade before 16:00, not the official
    closing-auction price.
  * The NYSE calendar was added to the early-close rule after the approved
    wording ("any day either asset flags"), because the volume flag alone
    missed a half-day on each asset in the last-half-hour test.
"""
import datetime as dt
import json
import sys

import numpy as np
import pandas as pd

import backtest as B

SYMS = ("SPY", "QQQ")
OPEN, LAST_BAR, EARLY_LAST_BAR = 570, 955, 775
CHECKS = list(range(595, 930, 30))          # bars starting 09:55 ... 15:25 (close 10:00 ... 15:30)
LOOKBACK, RISK, SLIP = 14, 25.0, 0.01
EARLY_VOL_RATIO = 0.05
MIN_PF, MAX_DD, MIN_TRADES = 1.2, 300, 100
# NYSE 1:00 p.m. closes, Nov 2022 onward (NYSE Group holiday and early-closings calendars).
# The 2022-2024 dates were added for the earlier-window run; no rule or number changed.
NYSE_EARLY = {dt.date.fromisoformat(d) for d in
              ("2022-11-25", "2023-07-03", "2023-11-24", "2024-07-03",
               "2024-11-29", "2024-12-24", "2025-07-03", "2025-11-28", "2025-12-24", "2026-11-27", "2026-12-24")}


def load_regular(data_dir, sym):
    r = json.load(open(f"{data_dir}/{sym}.json"))["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({k: q[k] for k in ["open", "high", "low", "close", "volume"]})
    df.index = pd.to_datetime(r["timestamp"], unit="s", utc=True).tz_convert(B.NY)
    df = df.dropna().sort_index()
    mins = df.index.hour * 60 + df.index.minute
    return df[(mins >= OPEN) & (mins < 960)]


def days_of(reg):
    """date -> (minutes array, day frame); a final partial session is dropped."""
    out, last_date = {}, reg.index[-1].date()
    for date, day in reg.groupby(reg.index.date):
        m = np.asarray(day.index.hour * 60 + day.index.minute)
        if date == last_date and m[-1] < LAST_BAR:
            continue
        out[date] = (m, day)
    return out


def volume_flags(days):
    flagged = set()
    for date, (m, day) in days.items():
        first = day.volume[(m >= OPEN) & (m < OPEN + 30)].sum()
        late = day.volume[(m >= 930) & (m <= LAST_BAR)].sum()
        if first == 0 or late < EARLY_VOL_RATIO * first:
            flagged.add(date)
    return flagged


def trades(days, sym, early):
    rows, skipped, hist, prev_close = [], [], [], None
    for date in sorted(days):
        m, day = days[date]
        pos_of = {int(x): i for i, x in enumerate(m)}
        o, h, l, c, v = (day[k].values for k in ["open", "high", "low", "close", "volume"])
        if date in early:
            skipped.append((date, "early close"))
            if EARLY_LAST_BAR in pos_of:
                prev_close = c[pos_of[EARLY_LAST_BAR]]
            continue
        full = OPEN in pos_of and LAST_BAR in pos_of and all(x in pos_of and x + 5 in pos_of for x in CHECKS)
        if not full:
            skipped.append((date, "missing bars"))
            prev_close = c[-1]
            continue
        day_open = o[pos_of[OPEN]]
        moves = np.array([abs(c[pos_of[x]] / day_open - 1) for x in CHECKS])
        if prev_close is not None and len(hist) >= LOOKBACK:
            sigma = np.mean(hist[-LOOKBACK:], axis=0)
            up = max(day_open, prev_close) * (1 + sigma)
            lo = min(day_open, prev_close) * (1 - sigma)
            vwap = np.cumsum((h + l + c) / 3 * v) / np.maximum(np.cumsum(v), 1e-9)
            pos, entry, qty, capped = 0, None, None, False

            def close_out(px, t):
                pnl = pos * (px - entry) * qty - 2 * SLIP * qty
                rows.append((t, sym, pnl, pos, capped))

            for j, x in enumerate(CHECKS):
                k = pos_of[x]
                px_c, vw, nxt = c[k], vwap[k], pos_of[x + 5]
                exited = 0
                if pos > 0 and px_c < max(up[j], vw):
                    close_out(o[nxt], day.index[nxt]); exited, pos = 1, 0
                elif pos < 0 and px_c > min(lo[j], vw):
                    close_out(o[nxt], day.index[nxt]); exited, pos = -1, 0
                if pos == 0:
                    want = 1 if px_c > up[j] else (-1 if px_c < lo[j] else 0)
                    if want and want != exited and sigma[j] > 0:
                        entry = o[nxt]
                        full_qty = RISK / (entry * sigma[j])
                        qty = min(full_qty, B.MAX_NOTIONAL / entry)
                        pos, capped = want, qty < full_qty
            if pos != 0:
                close_out(c[pos_of[LAST_BAR]], day.index[pos_of[LAST_BAR]])
        elif prev_close is None:
            skipped.append((date, "no previous close"))
        hist.append(moves)
        prev_close = c[pos_of[LAST_BAR]]
    return pd.DataFrame(rows, columns=["time", "sym", "pnl", "dir", "capped"]), skipped


def months(a, b):
    return max((b - a).days / 30.4, 0.1)


def line(label, tr, m):
    s = B.stats(tr, m)
    if not s["trades"]:
        print(f"  {label}: no trades")
        return dict(trades=0, profit_factor=0, max_dd=0)
    print(f"  {label}: trades={s['trades']} win={s['win_rate']}% PF={s['profit_factor']} "
          f"net=${s['net']} net/month=${s['monthly_usd']} maxDD=${s['max_dd']} "
          f"largest loss=${tr.pnl.min():.2f} size-capped={int(tr.capped.sum())}")
    return s


if __name__ == "__main__":
    data_dir = sys.argv[1]
    regs = {s: load_regular(data_dir, s) for s in SYMS}
    days = {s: days_of(regs[s]) for s in SYMS}
    flags = {s: volume_flags(days[s]) for s in SYMS}
    lo_d = min(min(d) for d in days.values())
    hi_d = max(max(d) for d in days.values())
    calendar = {d for d in NYSE_EARLY if lo_d <= d <= hi_d}
    early = calendar | flags["SPY"] | flags["QQQ"]
    print("Early-close days skipped for both assets:", ", ".join(str(d) for d in sorted(early)) or "none")
    for s in SYMS:
        print(f"  flagged by {s} volume: " + (", ".join(str(d) for d in sorted(flags[s])) or "none"))
    print("  on the NYSE calendar: " + (", ".join(str(d) for d in sorted(calendar)) or "none"))
    extra = sorted(early - calendar)
    if extra:
        print("  NOTE, flagged by volume but not on the calendar: " + ", ".join(str(d) for d in extra))

    verdicts = {}
    for sym in SYMS:
        reg = regs[sym]
        start, end = reg.index[0], reg.index[-1]
        mid = start + (end - start) / 2
        print(f"\n{sym}: {len(reg)} regular-session bars {start.date()} -> {end.date()}, split {mid.date()}")
        if months(start, end) < 23.5:
            print(f"  WARNING: {sym} has {months(start, end):.1f} months, not 24.")
        tr, skipped = trades(days[sym], sym, early)
        other = [f"{d} ({why})" for d, why in skipped if why != "early close"]
        print(f"  other days skipped ({len(other)}): " + (", ".join(other) or "none"))
        print(f"  days with at least one trade: {tr.time.dt.date.nunique()} of {len(days[sym])}")
        for name, part, m in (("first half (reference)", tr[tr.time < mid], months(start, mid)),
                              ("second half (verdict) ", tr[tr.time >= mid], months(mid, end))):
            res = line(f"{name} combined", part, m)
            line(f"{name} long    ", part[part.dir > 0], m)
            line(f"{name} short   ", part[part.dir < 0], m)
        verdicts[sym] = bool(res["trades"] >= MIN_TRADES and res["profit_factor"] >= MIN_PF
                             and res["max_dd"] < MAX_DD)

    print(f"\nRule: second-half profit factor >= {MIN_PF} AND max drawdown < ${MAX_DD} "
          f"AND at least {MIN_TRADES} second-half trades (long and short combined)")
    for sym, ok in verdicts.items():
        print(f"  {sym}: {'PASS - eligible for paper trading' if ok else 'FAIL - do not paper trade, do not re-tune'}")
