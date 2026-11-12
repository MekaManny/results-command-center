"""Walk-forward test of a CPI / FOMC "second move" strategy on SPY and QQQ 5-minute bars.

Usage: python3 trading/cpi_fomc.py <data_dir>

<data_dir> holds SPY.json and QQQ.json from `fetch_alpaca.py <data_dir> 24`
(24 months, all hours: the 08:30 CPI release is measured on pre-market bars).

Events (official calendars, listed in EVENTS below):
  * CPI releases, 08:30 New York (bls.gov release schedule and CPI archive)
  * FOMC statements, 14:00 New York (federalreserve.gov FOMC calendar)

Rules, checked bar by bar on the event day only:
  * Skip window: the 15 minutes after the release. Nothing in it can be a
    pullback bar or an entry.
  * Initial direction: close of the last bar of the skip window (08:40 / 14:10
    bar) versus the close of the bar just before the release (08:25 / 13:55).
    Up = long only, down = short only. The size of that change is the
    "initial move".
  * Pattern bars are regular-session bars from max(release + 15 min, 09:30)
    for WAIT minutes.
  * Pullback: a run of 1..PB consecutive bars closing against the initial
    direction (close vs the bar's own open). A longer run is not a pullback.
  * Retrace cap: no pattern bar may give back RETR or more of the initial
    move, measured from the skip-window close. If one does, the event is dead.
  * Entry: the first bar after the run closes back in the initial direction
    AND closes beyond the run's far side (above the pullback high for a long,
    below the pullback low for a short). Fill at the next open. If that bar
    does not qualify the run is discarded and a new pullback may form.
  * One trade per event at most. No signal bar starting at or after 15:30,
    flat on the 15:55 bar.
  * Stop just beyond the pullback extreme (pullback low for a long), target
    2R from the fill.
Engine, sizing and costs are backtest.run(): $25 risk, notional capped at
$10,000, 0.01% per side, stop wins a shared bar.

Protocol (fixed before any bar was loaded):
  1. Each asset's bars are cut in half by time. The halves are separate runs.
  2. The 18-variant GRID (WAIT x PB x RETR) is run on first halves only. The
     variant with the best combined SPY+QQQ first-half profit factor and at
     least MIN_TRADES combined first-half trades is selected. If none has
     MIN_TRADES: FAIL for insufficient sample, second half is never run.
  3. The pick is run once on the second halves. No re-tuning.
  4. Per asset: PASS only if second-half profit factor >= 1.2 AND max
     drawdown < $150.
"""
import datetime as dt
import itertools
import json
import sys

import numpy as np
import pandas as pd

import backtest as B

CPI = """2024-11-13 2024-12-11 2025-01-15 2025-02-12 2025-03-12 2025-04-10 2025-05-13 2025-06-11
2025-07-15 2025-08-12 2025-09-11 2025-10-24 2025-12-18 2026-01-13 2026-02-13 2026-03-11
2026-04-10 2026-05-12 2026-06-10 2026-07-14 2026-08-12 2026-09-11 2026-10-14 2026-11-10""".split()
FOMC = """2024-11-07 2024-12-18 2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17
2025-10-29 2025-12-10 2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16
2026-10-28""".split()
EVENTS = sorted([(d, "CPI", 8 * 60 + 30) for d in CPI] + [(d, "FOMC", 14 * 60) for d in FOMC])

SKIP_MIN, TGT_R, OPEN, LAST_SIGNAL, FLAT = 15, 2.0, 570, 930, 955
GRID = [dict(wait=w, pb=n, retr=r) for w, n, r in itertools.product((30, 60, 90), (1, 2, 3), (0.382, 0.5))]
SYMS = ("SPY", "QQQ")
MIN_PF, MAX_DD, MIN_TRADES = 1.2, 150, 10


def load_raw(data_dir, sym):
    """All-hours bars (backtest.load_etf keeps the regular session only)."""
    r = json.load(open(f"{data_dir}/{sym}.json"))["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({k: q[k] for k in ["open", "high", "low", "close", "volume"]})
    df.index = pd.to_datetime(r["timestamp"], unit="s", utc=True).tz_convert(B.NY)
    return df.dropna().sort_index()


def regular(df):
    mins = df.index.hour * 60 + df.index.minute
    return df[(mins >= OPEN) & (mins < 960)]


def event_setup(raw, date, rel_min):
    """Initial direction and move for one event, or a reason it cannot be measured."""
    day = raw[raw.index.date == dt.date.fromisoformat(date)]
    if day.empty:
        return None, "no bars that day"
    mins = day.index.hour * 60 + day.index.minute
    pre = day[(mins >= rel_min - 5) & (mins < rel_min)]
    win = day[(mins >= rel_min + SKIP_MIN - 5) & (mins < rel_min + SKIP_MIN)]
    if pre.empty or win.empty:
        return None, "missing the bar before the release or the last skip-window bar"
    c_pre, c_win = pre.close.iloc[-1], win.close.iloc[-1]
    if c_win == c_pre:
        return None, "no initial move"
    return (c_pre, c_win), None


def signals(reg, raw, p, log=None):
    """Signal arrays for backtest.run() over the regular-session frame `reg`."""
    n = len(reg)
    d = np.zeros(n, dtype=int)
    stop = np.full(n, np.nan)
    mins = np.asarray(reg.index.hour * 60 + reg.index.minute)
    dates = np.asarray(reg.index.date)
    o, h, l, c = (reg[k].values for k in ["open", "high", "low", "close"])
    if n == 0:
        return d, stop, mins
    lo, hi = reg.index[0].date(), reg.index[-1].date()
    for date, kind, rel in EVENTS:
        day = dt.date.fromisoformat(date)
        if not (lo <= day <= hi):
            continue
        setup, why = event_setup(raw, date, rel)
        if setup is None:
            if log is not None:
                log.append((date, kind, "-", f"skipped: {why}"))
            continue
        c_pre, c_win = setup
        move = c_win - c_pre
        s = 1 if move > 0 else -1
        cap_level = c_win - p["retr"] * move
        start = max(rel + SKIP_MIN, OPEN)
        idx = np.where((dates == day) & (mins >= start) & (mins < start + p["wait"]) & (mins < LAST_SIGNAL))[0]
        run_n, run_far, run_ext, outcome = 0, None, None, "no setup"
        for j in idx:
            adverse = l[j] if s > 0 else h[j]
            if s * (adverse - cap_level) <= 0:
                outcome = "dead: retrace cap hit"
                break
            body = s * (c[j] - o[j])
            if body < 0:                                    # bar closes against the initial direction
                far, ext = (h[j], l[j]) if s > 0 else (l[j], h[j])
                run_far = far if run_n == 0 else (max(run_far, far) if s > 0 else min(run_far, far))
                run_ext = ext if run_n == 0 else (min(run_ext, ext) if s > 0 else max(run_ext, ext))
                run_n += 1
                continue
            if 1 <= run_n <= p["pb"] and body > 0 and s * (c[j] - run_far) > 0:
                d[j] = s
                stop[j] = run_ext * (1 - s * 0.0001)
                outcome = "signal"
                break
            run_n = 0
        if log is not None:
            log.append((date, kind, "up" if s > 0 else "down", outcome))
    return d, stop, mins


def trades(reg, raw, sym, p, log=None):
    def strat(df, q):
        d, stop, mins = signals(df, raw, q, log)
        return d, stop, np.full(len(df), TGT_R), None, mins >= FLAT, 1
    return B.run(reg, sym, strat, p)


def months(df):
    return max((df.index[-1] - df.index[0]).days / 30.4, 0.1)


def line(label, tr, m):
    s = B.stats(tr, m)
    if not s["trades"]:
        print(f"  {label}: no trades")
        return dict(trades=0, profit_factor=0, max_dd=0)
    print(f"  {label}: trades={s['trades']} win={s['win_rate']}% PF={s['profit_factor']} "
          f"net=${s['net']} net/month=${s['monthly_usd']} maxDD=${s['max_dd']}")
    return s


if __name__ == "__main__":
    data_dir = sys.argv[1]
    halves = {}
    for s in SYMS:
        raw = load_raw(data_dir, s)
        mid = raw.index[0] + (raw.index[-1] - raw.index[0]) / 2
        parts = (raw[raw.index < mid], raw[raw.index >= mid])
        halves[s] = [(regular(x), x) for x in parts]
        print(f"{s}: {len(raw)} bars {raw.index[0].date()} -> {raw.index[-1].date()}, split {mid.date()}")
        if months(raw) < 23.5:
            print(f"  WARNING: {s} has {months(raw):.1f} months, not 24.")
        for name, (reg, _) in zip(("first", "second"), halves[s]):
            ev = [f"{d} {k}" for d, k, _ in EVENTS if reg.index[0].date() <= dt.date.fromisoformat(d) <= reg.index[-1].date()]
            print(f"  {name} half events ({len(ev)}): " + ", ".join(ev))

    print("\n=== Tuning, first halves only ===")
    scored = []
    for p in GRID:
        tr = pd.concat([trades(*halves[s][0], s, p) for s in SYMS])
        st = B.stats(tr, months(halves[SYMS[0]][0][0]))
        pf = st.get("profit_factor", 0)
        print(f"  {p}: trades={st['trades']} PF={pf}")
        if st["trades"] >= MIN_TRADES:
            scored.append((pf, st["trades"], p))
    verdicts = {}
    if not scored:
        print(f"\nNo variant reached {MIN_TRADES} first-half trades: FAIL for insufficient sample. Second half not run.")
        verdicts = {s: False for s in SYMS}
    else:
        best = max(scored, key=lambda x: (x[0], x[1]))[2]
        print(f"\nSelected on first half: {best}")
        for s in SYMS:
            for name, (reg, raw), tag in zip(("first half (tuned)  ", "second half (unseen)"), halves[s], (0, 1)):
                log = []
                res = line(f"{s} {name}", trades(reg, raw, s, best, log), months(reg))
                for row in log:
                    print("      " + " | ".join(row))
                if tag:
                    verdicts[s] = bool(res["trades"] and res["profit_factor"] >= MIN_PF and res["max_dd"] < MAX_DD)

    print(f"\nRule: second-half profit factor >= {MIN_PF} AND max drawdown < ${MAX_DD}")
    for s, ok in verdicts.items():
        print(f"  {s}: {'PASS - eligible for paper trading' if ok else 'FAIL - do not paper trade, do not re-tune'}")
