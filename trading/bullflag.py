"""Walk-forward test of a bull-flag continuation strategy on 5-minute bars.

Usage: python3 trading/bullflag.py <data_dir>

<data_dir> holds the same files backtest.py reads: Binance monthly 5m kline
zips (BTCUSDT-*.zip, ETHUSDT-*.zip, 12 months) and SPY.json / QQQ.json from
fetch_alpaca.py (12 months).

Pattern (long only), checked on the close of every bar i:
  * impulse: over K bars ending at the pole-top bar, low-to-high rise of at
    least IMP x ATR(14) (ATR taken on the bar before the impulse starts); the
    pole-top bar holds the highest high of those K bars
  * flag: the next L bars (L = 3..10, shortest valid L wins) never trade above
    the pole top, give back less than RETR of the impulse (RETR <= 0.5), and
    the least-squares slope of their closes is down or flat (<= 0)
  * entry: bar i closes above the flag high (highest high of the flag bars);
    fill at the next open, as everywhere else in this backtester
  * stop: just below the flag low. Target: 2R from the actual fill.
ETFs: whole pattern inside one regular session, no entries after 15:30,
flat at 15:55 New York. Crypto: 24h, held until stop or target.
Engine, sizing and costs are backtest.run(): $25 risk, notional capped at
$10,000, 0.06% per side crypto, 0.01% per side ETFs, stop wins a shared bar.

Protocol (fixed before any second-half bar was looked at):
  1. Each asset's bars are cut in half by time. The halves are backtested as
     separate runs, so nothing from the second half can reach the first.
  2. The 18-variant GRID below is run on first halves only. Per asset class
     (BTC+ETH, SPY+QQQ) the variant with the best combined first-half profit
     factor and at least MIN_TRADES trades is selected.
  3. That one variant is run once on the second halves. No re-tuning.
  4. Per asset: PASS only if second-half profit factor >= 1.2 AND max
     drawdown < $150. Anything else is FAIL: do not paper trade it.
"""
import itertools
import sys

import numpy as np
import pandas as pd

import backtest as B

FLAG_MIN, FLAG_MAX, TGT_R = 3, 10, 2.0
GRID = [dict(k=k, imp=a, retr=r) for k, a, r in itertools.product((3, 5, 8), (3.0, 4.0, 5.0), (0.382, 0.5))]
CLASSES = {"crypto": ("BTC", "ETH"), "ETF": ("SPY", "QQQ")}
MIN_PF, MAX_DD, MIN_TRADES = 1.2, 150, 30


def rolling_slope(y, n):
    """Least-squares slope of the n values ending at each bar."""
    x = np.arange(n) - (n - 1) / 2
    out = np.full(len(y), np.nan)
    if len(y) >= n:
        out[n - 1:] = np.convolve(y, x[::-1], mode="valid") / (x ** 2).sum()
    return pd.Series(out, y.index)


def strat_bullflag(df, p, session):
    mins, day = B.prep(df)
    k = p["k"]
    a = B.atr(df)
    d = np.zeros(len(df), dtype=int)
    stop = np.full(len(df), np.nan)
    for L in range(FLAG_MIN, FLAG_MAX + 1):                 # breakout bar is i
        top = df.high.shift(L + 1)                          # pole top: bar i-L-1
        base = df.low.rolling(k).min().shift(L + 1)         # impulse low: bars i-L-k .. i-L-1
        height = top - base
        flag_hi = df.high.rolling(L).max().shift(1)         # flag: bars i-L .. i-1
        flag_lo = df.low.rolling(L).min().shift(1)
        slope = rolling_slope(df.close, L).shift(1)
        ok = (top >= df.high.rolling(k).max().shift(L + 1)) \
            & (height >= p["imp"] * a.shift(L + 1 + k)) \
            & (flag_hi <= top) \
            & ((top - flag_lo) < p["retr"] * height) \
            & (slope <= 0) \
            & (df.close > flag_hi)
        if session:
            ok &= (day == day.shift(L + k)) & (mins < 930)
        new = ok.values & (d == 0)
        d[new] = 1
        stop[new] = flag_lo.values[new] * (1 - 0.0001)
    if session:
        flat, per_day = (mins >= 955).values, 99
    else:
        flat, per_day = np.zeros(len(df), dtype=bool), 10 ** 6
    return d, stop, np.full(len(df), TGT_R), None, flat, per_day


def trades(df, sym, p):
    session = sym in CLASSES["ETF"]
    return B.run(df, sym, lambda d, q: strat_bullflag(d, q, session), p)


def months(df):
    return max((df.index[-1] - df.index[0]).days / 30.4, 0.1)


def line(label, tr, m):
    s = B.stats(tr, m)
    if not s["trades"]:
        print(f"  {label}: no trades")
        return dict(trades=0, profit_factor=0, max_dd=0)
    print(f"  {label}: trades={s['trades']} win={s['win_rate']}% PF={s['profit_factor']} "
          f"net/month=${s['monthly_usd']} maxDD=${s['max_dd']}")
    return s


if __name__ == "__main__":
    data_dir = sys.argv[1]
    data = {s: B.load_crypto(data_dir, s) for s in CLASSES["crypto"]}
    data.update({s: B.load_etf(data_dir, s) for s in CLASSES["ETF"]})
    halves = {}
    for s, df in data.items():
        mid = df.index[0] + (df.index[-1] - df.index[0]) / 2
        halves[s] = (df[df.index < mid], df[df.index >= mid])
        print(f"{s}: {len(df)} bars {df.index[0].date()} -> {df.index[-1].date()}, split {mid.date()}")
        if months(df) < 11.5:
            print(f"  WARNING: {s} has {months(df):.1f} months, not 12.")

    verdicts = {}
    for cls, syms in CLASSES.items():
        scored = []
        for p in GRID:                                      # first halves only
            tr = pd.concat([trades(halves[s][0], s, p) for s in syms])
            st = B.stats(tr, months(halves[syms[0]][0]))
            if st["trades"] >= MIN_TRADES:
                scored.append((st["profit_factor"], st["trades"], p))
        print(f"\n=== {cls} ===")
        if not scored:
            print(f"  No variant reached {MIN_TRADES} first-half trades: FAIL")
            verdicts.update({s: False for s in syms})
            continue
        best = max(scored, key=lambda x: (x[0], x[1]))[2]
        print(f"  Selected on first half: {best}")
        for s in syms:
            line(f"{s} first half (tuned)   ", trades(halves[s][0], s, best), months(halves[s][0]))
            o = line(f"{s} second half (unseen) ", trades(halves[s][1], s, best), months(halves[s][1]))
            verdicts[s] = bool(o["trades"] and o["profit_factor"] >= MIN_PF and o["max_dd"] < MAX_DD)

    print(f"\nRule: second-half profit factor >= {MIN_PF} AND max drawdown < ${MAX_DD}")
    for s, ok in verdicts.items():
        print(f"  {s}: {'PASS - eligible for paper trading' if ok else 'FAIL - do not paper trade, do not re-tune'}")
