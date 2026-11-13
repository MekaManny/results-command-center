"""Walk-forward test of a mechanical trendline-break-and-retest strategy (5-minute bars).

Usage:
  python3 trading/trendline_break.py fetch <data_dir> [months_back=12]   # BTC/USD, ETH/USD from Alpaca
  python3 trading/fetch_alpaca.py <data_dir> 12                          # SPY, QQQ (SIP feed, needs keys)
  python3 trading/trendline_break.py <data_dir>

Source idea: Tori Trades, "The Trendline Break Setup" (YouTube Short). The
video's entry is any break of a hand-drawn line. This is a stricter version
with nothing drawn by hand. Everything below is fixed in code.

Rules. Described for a SHORT (break of an uptrend line); a LONG is the mirror
image (break of a downtrend line through lower highs).

  Pivots     A pivot low is a bar whose low is strictly below the lows of the
             K bars on each side (K=2 is the 5-bar swing). It is confirmed,
             and usable, only K bars later.
  Trendline  When a pivot low L2 confirms, L1 is the most recent earlier
             confirmed pivot low at least SEP bars before it. If L2 is higher
             than L1 and no bar from L1 to now has closed below the line
             through them, that is the uptrend line. Otherwise there is no
             uptrend line until a later pivot low makes one. A newer valid
             line replaces the old one.
  Break      The first bar that closes below the line. The line is then
             frozen and extended at the same slope.
  Retest     Within WIN bars after the break bar: some bar's high reaches the
             frozen line (the retest), and that bar or a later one closes
             below the line (the confirmation). Enter short AT THAT CLOSE.
             No confirmation inside WIN bars: no trade.
  Opposing   At entry no two confirmed pivot highs exist after the break yet,
  line       so the first opposing line runs through A, the highest high from
             L2 to the break bar (the top before the break), and B, the
             highest high from the bar after the break to the entry bar (the
             retest high). B must be lower than A or there is no trade. After
             entry, each newly confirmed pivot high P re-draws the line
             through P and the most recent earlier anchor (A, B or a later
             pivot high) that is at least SEP bars before P, provided that
             anchor is higher than P. Otherwise the line is left as it is.
  Size       $25 / (opposing line at entry - entry price), notional capped at
             $10,000 as in the other tests. Skipped if that distance is under
             0.05% of price (the repo's usual floor) or not positive.
  Exit       The first later bar that closes above the opposing line, filled
             at that close. There is no hard stop, so a loss can exceed $25.
             SPY/QQQ are also flat at the close of the 15:55 bar (or of the
             session's last bar on an early close).
  Costs      0.06% per side crypto, 0.01% per side ETFs.
  Other      One position per asset. Setups that confirm while a position is
             open are dropped. SPY/QQQ use regular-session bars only, and both
             pivots, the break, the retest and the entry must all be in the
             same session; no entry on the 15:55 bar. Crypto runs 24h with no
             time stop; bars Alpaca omits (no trades) are simply absent, and
             bar counts are over the bars that exist.

Protocol (fixed before any second-half bar was looked at):
  1. Each asset's bars are cut in half by time and the halves are backtested
     as separate runs, so nothing from the second half can reach the first.
  2. The 27-variant GRID (K, SEP, WIN) is run on first halves only. Per asset
     class (BTC+ETH, SPY+QQQ) the variant with the best combined first-half
     profit factor, long and short together, and at least MIN_SELECT trades
     is selected.
  3. That one variant is run once on the second halves. No re-tuning.
  4. Per asset: PASS only if second-half profit factor >= 1.2 AND max
     drawdown < $150 AND at least 10 second-half trades (long and short
     together). Anything else is FAIL: do not paper trade it.
"""
import datetime as dt
import getpass
import itertools
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

import backtest as B

RISK, MAX_NOTIONAL, MIN_DIST = 25.0, 10_000.0, 0.0005
GRID = [dict(k=k, sep=s, win=w) for k, s, w in itertools.product((2, 3, 5), (10, 20, 30), (5, 10, 20))]
CLASSES = {"crypto": ("BTC", "ETH"), "ETF": ("SPY", "QQQ")}
MIN_PF, MAX_DD, MIN_TRADES, MIN_SELECT = 1.2, 150.0, 10, 30
CRYPTO_URL = "https://data.alpaca.markets/v1beta3/crypto/us/bars"


# ---------------------------------------------------------------- data

def fetch_crypto(data_dir, months):
    headers = {}
    if os.environ.get("APCA_API_KEY_ID") and os.environ.get("APCA_API_SECRET_KEY"):
        headers = {"APCA-API-KEY-ID": os.environ["APCA_API_KEY_ID"],
                   "APCA-API-SECRET-KEY": os.environ["APCA_API_SECRET_KEY"]}
    now = dt.datetime.now(dt.timezone.utc)
    end = (now - dt.timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    start = (now - dt.timedelta(days=30.5 * months)).strftime("%Y-%m-%dT00:00:00Z")
    os.makedirs(data_dir, exist_ok=True)
    for sym in CLASSES["crypto"]:
        pair, bars, token = f"{sym}/USD", [], None
        while True:
            q = dict(symbols=pair, timeframe="5Min", start=start, end=end, limit=10000, sort="asc")
            if token:
                q["page_token"] = token
            page = None
            while page is None:
                req = urllib.request.Request(CRYPTO_URL + "?" + urllib.parse.urlencode(q), headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=60) as r:
                        page = json.load(r)
                except urllib.error.HTTPError as e:
                    body = e.read().decode("utf-8", "replace")[:300]
                    if e.code in (401, 403) and not headers:
                        print(f"Alpaca wants keys for crypto bars (HTTP {e.code}). Typed keys are hidden and not saved.")
                        headers = {"APCA-API-KEY-ID": getpass.getpass("Alpaca key ID: ").strip(),
                                   "APCA-API-SECRET-KEY": getpass.getpass("Alpaca secret key: ").strip()}
                    else:
                        sys.exit(f"Alpaca HTTP {e.code} for {pair}: {body}")
            bars += (page.get("bars") or {}).get(pair) or []
            token = page.get("next_page_token")
            if not token:
                break
        if not bars:
            sys.exit(f"{sym}: Alpaca returned no bars")
        df = pd.DataFrame(bars)[["t", "o", "h", "l", "c", "v"]]
        df.columns = ["time", "open", "high", "low", "close", "volume"]
        df.to_csv(os.path.join(data_dir, f"{sym}USD_5m.csv"), index=False)
        print(f"{sym}: {len(df)} bars {df.time.iloc[0]} -> {df.time.iloc[-1]}")


def load_crypto(data_dir, sym):
    df = pd.read_csv(os.path.join(data_dir, f"{sym}USD_5m.csv"))
    df.index = pd.to_datetime(df.pop("time"), utc=True).dt.tz_convert(B.NY)
    return df[~df.index.duplicated()].sort_index()


# ---------------------------------------------------------------- engine

def pivots(x, k, sess, sign):
    """sign=+1: pivot highs of x; sign=-1: pivot lows. Strict on both sides, same session."""
    v, n = sign * x, len(x)
    ok = np.zeros(n, dtype=bool)
    ok[k:n - k] = True
    for j in range(1, k + 1):
        ok[k:n - k] &= (v[k:n - k] > v[k - j:n - k - j]) & (v[k:n - k] > v[k + j:n - k + j])
    ok[k:n - k] &= sess[:n - 2 * k] == sess[2 * k:]
    return ok


def run(df, sym, p):
    """One independent backtest. Returns a DataFrame of trades: time, sym, dir, pnl, reason."""
    k, sep, win = p["k"], p["sep"], p["win"]
    etf = sym in CLASSES["ETF"]
    h, l, c = df.high.values, df.low.values, df.close.values
    n = len(df)
    if etf:
        mins = (df.index.hour * 60 + df.index.minute).values
        sess = pd.factorize(df.index.date)[0]
        flat = mins >= 955
        flat[:-1] |= sess[1:] != sess[:-1]                 # early closes: flat on the session's last bar
    else:
        sess, flat = np.zeros(n, dtype=int), np.zeros(n, dtype=bool)
    cost = B.COST[sym]
    # Work in a mirrored frame per direction: side 0 = short (uptrend line through lows),
    # side 1 = long (downtrend line through highs, handled by negating prices).
    # In the mirrored frame every setup is "line through pivot lows breaks downward".
    lo = [l, -h]            # series the entry line's pivots come from
    hi = [h, -l]            # series the opposing line's anchors come from
    cl = [c, -c]
    piv_lo = [pivots(l, k, sess, -1), pivots(h, k, sess, +1)]
    piv_hi = [pivots(h, k, sess, +1), pivots(l, k, sess, -1)]
    lows = [[], []]         # confirmed pivot indices, per side
    line = [None, None]     # active entry line: (i0, y0, slope, i_l2)
    pend = [None, None]     # frozen broken line awaiting retest: (i0, y0, slope, i_l2, i_break, retested)
    pos = None              # dict(side, entry, qty, anchors=[(i, y)...], opp=(i0, y0, slope), t)
    trades = []

    for i in range(n):
        j = i - k
        if i > 0 and sess[i] != sess[i - 1]:               # new session: nothing carries over (ETFs)
            lows, line, pend = [[], []], [None, None], [None, None]
        for s in (0, 1):
            # 1. pivots confirmed by this bar's close
            if j >= 0 and piv_lo[s][j] and sess[j] == sess[i]:
                if pend[s] is None:
                    line[s] = None
                    for a in reversed(lows[s]):
                        if j - a >= sep:
                            y0, y1 = lo[s][a], lo[s][j]
                            if y1 > y0:
                                m = (y1 - y0) / (j - a)
                                if (cl[s][a:i + 1] >= y0 + m * np.arange(i + 1 - a)).all():
                                    line[s] = (a, y0, m, j)
                            break
                lows[s].append(j)
            if pos is not None and pos["side"] == s and j >= 0 and piv_hi[s][j] and j > pos["anchors"][-1][0]:
                y = hi[s][j]
                for a, ya in reversed(pos["anchors"]):
                    if j - a >= sep:
                        if ya > y:
                            pos["opp"] = (a, ya, (y - ya) / (j - a))
                        break
                pos["anchors"].append((j, y))
        # 2. exit
        if pos is not None and i > pos["i"]:
            s = pos["side"]
            a, ya, m = pos["opp"]
            reason = "flat" if flat[i] else ("line" if cl[s][i] > ya + m * (i - a) else None)
            if reason:
                d = -1 if s == 0 else 1
                pnl = d * (c[i] - pos["entry"]) * pos["qty"] - cost * pos["qty"] * (pos["entry"] + c[i])
                trades.append((pos["t"], sym, "short" if s == 0 else "long", pnl, reason))
                pos = None
        for s in (0, 1):
            # 3. retest and confirmation of a broken line
            if pend[s] is not None:
                a, y0, m, i_l2, i_b, retested = pend[s]
                if i - i_b > win:
                    pend[s] = None
                else:
                    lv = y0 + m * (i - a)
                    retested = retested or hi[s][i] >= lv
                    pend[s] = (a, y0, m, i_l2, i_b, retested)
                    if retested and cl[s][i] < lv:
                        pend[s] = None
                        if pos is None and not flat[i]:
                            ia = i_l2 + int(np.argmax(hi[s][i_l2:i_b + 1]))
                            ib = i_b + 1 + int(np.argmax(hi[s][i_b + 1:i + 1]))
                            ya, yb = hi[s][ia], hi[s][ib]
                            if yb < ya:
                                mo = (yb - ya) / (ib - ia)
                                dist = yb + mo * (i - ib) - cl[s][i]
                                if dist >= MIN_DIST * c[i]:
                                    pos = dict(side=s, i=i, t=df.index[i], entry=c[i],
                                               qty=min(RISK / dist, MAX_NOTIONAL / c[i]),
                                               anchors=[(ia, ya), (ib, yb)], opp=(ia, ya, mo))
            # 4. break of the active line
            elif line[s] is not None:
                a, y0, m, i_l2 = line[s]
                if cl[s][i] < y0 + m * (i - a):
                    pend[s] = (a, y0, m, i_l2, i, False)
                    line[s] = None
    return pd.DataFrame(trades, columns=["time", "sym", "dir", "pnl", "reason"])


# ---------------------------------------------------------------- report

def stats(tr):
    if len(tr) == 0:
        return dict(trades=0, win_pct=np.nan, pf=np.nan, net=0.0, max_dd=0.0,
                    avg_win=np.nan, avg_loss=np.nan, largest_loss=np.nan)
    pnl = tr.sort_values("time").pnl
    eq = pnl.cumsum()
    w, ls = pnl[pnl > 0], pnl[pnl <= 0]
    return dict(trades=len(pnl), win_pct=round(100 * len(w) / len(pnl), 1),
                pf=round(w.sum() / -ls.sum(), 2) if ls.sum() < 0 else float("inf"),
                net=round(pnl.sum(), 2), max_dd=round((eq.cummax().clip(lower=0) - eq).max(), 2),
                avg_win=round(w.mean(), 2) if len(w) else np.nan,
                avg_loss=round(ls.mean(), 2) if len(ls) else np.nan,
                largest_loss=round(ls.min(), 2) if len(ls) else np.nan)


def main(data_dir):
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 200)
    data = {s: load_crypto(data_dir, s) for s in CLASSES["crypto"]}
    data.update({s: B.load_etf(data_dir, s) for s in CLASSES["ETF"]})
    halves = {}
    for s, df in data.items():
        mid = df.index[0] + (df.index[-1] - df.index[0]) / 2
        halves[s] = (df[df.index < mid], df[df.index >= mid])
        print(f"{s}: {len(df)} bars {df.index[0].date()} -> {df.index[-1].date()}, split {mid.date()} "
              f"({len(halves[s][0])} / {len(halves[s][1])} bars)")

    rows, verdicts = {}, {}
    for cls, syms in CLASSES.items():
        grid_rows, best, best_first = [], None, None
        for p in GRID:
            first = {s: run(halves[s][0], s, p) for s in syms}
            st = stats(pd.concat(first.values()))
            grid_rows.append({**p, **{k: st[k] for k in ("trades", "win_pct", "pf", "net", "max_dd")}})
            if st["trades"] >= MIN_SELECT and (best is None or st["pf"] > best[1]):
                best, best_first = (p, st["pf"]), first
        print(f"\n=== {cls}: first-half grid, {' + '.join(syms)} combined (selection data only) ===")
        print(pd.DataFrame(grid_rows).to_string(index=False))
        if best is None:
            print(f"{cls}: no variant reached {MIN_SELECT} first-half trades. Nothing selected, second half not run.")
            for s in syms:
                verdicts[s] = "FAIL (no variant selected)"
            continue
        p = best[0]
        print(f"{cls}: selected {p} (first-half PF {best[1]}). Running it once on the second halves.")
        for s in syms:
            second = run(halves[s][1], s, p)
            for half, tr in (("first (tuned)", best_first[s]), ("second (unseen)", second)):
                rows[f"{s} {half} all"] = stats(tr)
                rows[f"{s} {half} long"] = stats(tr[tr.dir == "long"])
                rows[f"{s} {half} short"] = stats(tr[tr.dir == "short"])
            st = rows[f"{s} second (unseen) all"]
            ok = st["trades"] >= MIN_TRADES and st["pf"] >= MIN_PF and st["max_dd"] < MAX_DD
            verdicts[s] = f"{'PASS' if ok else 'FAIL'} (PF {st['pf']}, max DD ${st['max_dd']}, {st['trades']} trades)"
            second.to_csv(os.path.join(data_dir, f"trendline_break_{s}_second_half.csv"), index=False)
    if rows:
        print("\n" + pd.DataFrame(rows).T.to_string())
    print(f"\nPass bar: second-half PF >= {MIN_PF}, max DD < ${MAX_DD:.0f}, trades >= {MIN_TRADES} (long and short together)")
    for s, v in verdicts.items():
        print(f"VERDICT {s}: {v}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "fetch":
        fetch_crypto(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 12)
    elif len(sys.argv) == 2:
        main(sys.argv[1])
    else:
        sys.exit(__doc__)
