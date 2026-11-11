"""Out-of-sample test of the S3 fade on SPY + QQQ.

Usage: python3 trading/walkforward.py <data_dir>

Protocol (fixed before looking at the test half):
  1. Split the sessions in two equal halves by date.
  2. On the first half only, pick the parameter set with the best combined
     SPY+QQQ profit factor from the same 12-variant grid used originally
     (needs at least 30 trades).
  3. Run that one parameter set, untouched, on the second half.
  4. Promote to paper trading only if the second half has profit factor >= 1.2
     and max drawdown < $150. No re-tuning on the second half.

Also reports the shipped S3b parameters on every session before 2026-08-18:
those were tuned on 2026-08-18..2026-11-10, so earlier data is unseen by them.
"""
import itertools
import sys

import pandas as pd

import backtest as B

GRID = [dict(adx=a, bb=b, stop_atr=s) for a, b, s in itertools.product((20, 25, 100), (2.0, 2.5), (1.5, 2.5))]
S3B = dict(adx=25, bb=2.0, stop_atr=2.5)
TUNED_FROM = pd.Timestamp("2026-08-18", tz=B.NY)
MIN_PF, MAX_DD, MIN_TRADES = 1.2, 150, 30


def trades(data, p):
    return pd.concat([B.run(df, s, B.strat_fade, p, 12) for s, df in data.items()])


def months(a, b):
    return max((b - a).days / 30.4, 0.1)


def show(label, tr, m):
    s = B.stats(tr, m)
    if not s["trades"]:
        print(f"{label}: no trades")
        return s
    print(f"{label}: trades={s['trades']} win={s['win_rate']}% PF={s['profit_factor']} "
          f"maxDD=${s['max_dd']} avg/month=${s['monthly_usd']} ({s['monthly_pct']}% of $2,500)")
    return s


if __name__ == "__main__":
    data = {s: B.load_etf(sys.argv[1], s) for s in ("SPY", "QQQ")}
    first, last = data["SPY"].index[0], data["SPY"].index[-1]
    days = sorted(set(data["SPY"].index.date))
    split = pd.Timestamp(days[len(days) // 2], tz=B.NY)
    print(f"{len(days)} sessions {first.date()} -> {last.date()}; split at {split.date()}")
    if len(days) < 120:
        print("WARNING: fewer than ~6 months of sessions; this run does not satisfy the test.")

    results = [(p, trades(data, p)) for p in GRID]
    scored = []
    for p, tr in results:
        s = B.stats(tr[tr.time < split], months(first, split))
        if s["trades"] >= MIN_TRADES:
            scored.append((s["profit_factor"], p, tr))
    best_pf, best_p, best_tr = max(scored, key=lambda x: x[0])

    print(f"\nSelected on first half: {best_p}")
    show("  In-sample (first half)     ", best_tr[best_tr.time < split], months(first, split))
    oos = show("  Out-of-sample (second half)", best_tr[best_tr.time >= split], months(split, last))

    print(f"\nShipped S3b {S3B}")
    tr = trades(data, S3B)
    show("  Before 2026-08-18 (unseen by its tuning)", tr[tr.time < TUNED_FROM], months(first, TUNED_FROM))
    show("  From 2026-08-18 (its tuning window)     ", tr[tr.time >= TUNED_FROM], months(TUNED_FROM, last))

    ok = oos["trades"] and oos["profit_factor"] >= MIN_PF and oos["max_dd"] < MAX_DD
    print(f"\nVERDICT: {'PASS - promote to paper trading' if ok else 'FAIL - do not trade, do not re-tune on this data'} "
          f"(rule: out-of-sample PF >= {MIN_PF} and max DD < ${MAX_DD})")
