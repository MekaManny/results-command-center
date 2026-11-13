"""Overnight-session walk-forward of the BTC-ETH Day Trader v2 rules (5-minute bars).

Usage:
  python3 trading/crypto_overnight.py fetch <data_dir> [months_back=12]
  python3 trading/crypto_overnight.py run   <data_dir>

`fetch` downloads BTC/USD and ETH/USD 5-minute bars from Alpaca's crypto data
API into <data_dir>/BTCUSD_5m.csv and ETHUSD_5m.csv. Alpaca serves historical
crypto bars without credentials; if APCA_API_KEY_ID / APCA_API_SECRET_KEY are
set in the environment they are sent, and they are never written anywhere.

Only the session differs from the morning variant. Every number in PARAMS is
the morning variant's and is not tuned here: there is no grid in this file.

Rules (long only, one position per asset):
  signal, all true on the close of one 5-minute bar:
    * EMA(9) crosses above EMA(21) on that bar
    * close above the daily VWAP (hlc3 x volume, reset at 00:00 UTC)
    * RSI(14) below 68
    * close above the EMA(50) of the last completed 15-minute bar
  entry   next bar's open
  stop    signal close - stopDist, where
          stopDist = max(1.0 x ATR(14), 0.05% of the signal close)
  target  signal close + 1.5 x stopDist (so it widens when the floor binds)
  size    min($25 / stopDist, $25,000 / signal close), fractional
  exit    stop, target, or the open of the first bar at or after the flat
          time. As in the Pine backtest, the bracket is placed on the close
          of the entry bar, so it can first fill on the bar AFTER the entry
          bar. A bar that opens beyond the stop or target fills at that open.
          The stop wins a bar that touches both.
  costs   0.06% of notional on every fill (entry and exit)

Checked line by line against trading/btc-eth-day-trader-v2.pine. Known
differences from a TradingView run of that script:
  * costs: the Pine has commission_value=0; this test charges 0.06% per side
  * a bar that touches both stop and target: TradingView guesses the path
    inside the bar from its open; here the stop always wins
  * bars and VWAP volume are Alpaca's, not the TradingView chart's exchange
  * the Pine's flat-by-close and trade-window inputs are set per session below

Sessions (New York time, signal bar Monday to Friday):
  overnight  signal bars 00:00-09:20, fills by 09:25, flat at 09:30   <- the test
  combined   signal bars 00:00-11:25, flat at 15:55                   <- information only
  morning    signal bars 09:30-11:25, flat at 15:55                   <- port check only

Protocol:
  1. Indicators are causal and run once over the whole series. Trades are
     assigned to a half by entry date; the split is the middle calendar date.
     Every position is flat the day it opens, so no trade spans the split.
  2. Per asset: PASS only if the SECOND-half overnight profit factor is >= 1.2
     AND max drawdown is < $150 AND there are at least 10 second-half trades.
     Anything else is FAIL: do not paper trade that asset. No re-tuning.
"""
import datetime as dt
import getpass
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

NY = "America/New_York"
URL = "https://data.alpaca.markets/v1beta3/crypto/us/bars"
SYMBOLS = {"BTC": "BTC/USD", "ETH": "ETH/USD"}

PARAMS = dict(ema_fast=9, ema_slow=21, rsi_len=14, rsi_max=68.0, htf_min=15, htf_ema=50,
              atr_len=14, stop_atr=1.0, stop_floor=0.0005, tgt_atr=1.5,
              risk=25.0, max_notional=25_000.0, cost=0.0006)

# name: (first signal minute, signal minutes end before, flat minute) in New York time
SESSIONS = {"overnight": (0, 570, 570), "combined": (0, 690, 955), "morning": (570, 690, 955)}
MIN_PF, MAX_DD, MIN_TRADES = 1.2, 150.0, 10
WARMUP = 600  # bars before the first signal is allowed


# ---------------------------------------------------------------- data

def fetch(data_dir, months):
    headers = {}
    if os.environ.get("APCA_API_KEY_ID") and os.environ.get("APCA_API_SECRET_KEY"):
        headers = {"APCA-API-KEY-ID": os.environ["APCA_API_KEY_ID"],
                   "APCA-API-SECRET-KEY": os.environ["APCA_API_SECRET_KEY"]}
    now = dt.datetime.now(dt.timezone.utc)
    end = (now - dt.timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    start = (now - dt.timedelta(days=30.5 * months)).strftime("%Y-%m-%dT00:00:00Z")
    os.makedirs(data_dir, exist_ok=True)
    for sym, pair in SYMBOLS.items():
        bars, token = [], None
        while True:
            q = dict(symbols=pair, timeframe="5Min", start=start, end=end, limit=10000, sort="asc")
            if token:
                q["page_token"] = token
            page = None
            while page is None:
                req = urllib.request.Request(URL + "?" + urllib.parse.urlencode(q), headers=headers)
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


def load(data_dir, sym):
    df = pd.read_csv(os.path.join(data_dir, f"{sym}USD_5m.csv"))
    df.index = pd.to_datetime(df.pop("time"), utc=True)
    return df[~df.index.duplicated()].sort_index()


# ---------------------------------------------------------------- indicators

def rma(x, n):
    return x.ewm(alpha=1 / n, adjust=False).mean()


def ema(x, n):
    return x.ewm(span=n, adjust=False).mean()


def indicators(df, p):
    c = df.close
    ef, es = ema(c, p["ema_fast"]), ema(c, p["ema_slow"])
    cross = (ef > es) & (ef.shift(1) <= es.shift(1))
    chg = c.diff()
    rsi = 100 - 100 / (1 + rma(chg.clip(lower=0), p["rsi_len"]) / rma(-chg.clip(upper=0), p["rsi_len"]))
    tr = pd.concat([df.high - df.low, (df.high - c.shift()).abs(), (df.low - c.shift()).abs()], axis=1).max(axis=1)
    atr = rma(tr, p["atr_len"])
    utc_day = df.index.floor("D")
    pv = ((df.high + df.low + c) / 3 * df.volume).groupby(utc_day).cumsum()
    vwap = pv / df.volume.groupby(utc_day).cumsum().replace(0, np.nan)
    # 15-minute EMA, known only once its bar has closed (no look-ahead)
    step = pd.Timedelta(minutes=p["htf_min"])
    htf = ema(c.resample(step).last().dropna(), p["htf_ema"])
    htf.index = htf.index + step
    bar_close = df.index + pd.Timedelta(minutes=5)
    htf_ema = pd.Series(htf.reindex(htf.index.union(bar_close)).ffill().reindex(bar_close).values, df.index)
    sig = cross & (c > vwap) & (rsi < p["rsi_max"]) & (c > htf_ema)
    sig.iloc[:WARMUP] = False
    return sig.fillna(False).values, atr.values


# ---------------------------------------------------------------- engine

def run(df, sym, session, p):
    first, last, flat_min = SESSIONS[session]
    sig, atr = indicators(df, p)
    ny = df.index.tz_convert(NY)
    mins = (ny.hour * 60 + ny.minute).values
    wday = ny.weekday.values
    day = ny.date
    o, h, l, c = df.open.values, df.high.values, df.low.values, df.close.values
    t = df.index
    trades, pos = [], False
    for i in range(1, len(df)):
        if not pos and sig[i - 1] and wday[i - 1] < 5 and first <= mins[i - 1] < last:
            flat_ts = (pd.Timestamp(day[i - 1]) + pd.Timedelta(minutes=flat_min)).tz_localize(NY)
            a = atr[i - 1]
            if t[i] < flat_ts and np.isfinite(a) and a > 0:
                entry, ref = o[i], c[i - 1]
                dist = max(p["stop_atr"] * a, p["stop_floor"] * ref)
                stop, tgt = ref - dist, ref + dist * p["tgt_atr"] / p["stop_atr"]
                qty = max(min(p["risk"] / dist, p["max_notional"] / ref), 0.0001)
                pos, i_in = True, i
        if pos:
            px = reason = None
            if t[i] >= flat_ts:
                px, reason = o[i], "flat"
            elif i > i_in and l[i] <= stop:
                px, reason = min(stop, o[i]), "stop"
            elif i > i_in and h[i] >= tgt:
                px, reason = max(tgt, o[i]), "target"
            if px is not None:
                fees = p["cost"] * qty * (entry + px)
                trades.append(dict(sym=sym, session=session, entry_time=t[i_in], exit_time=t[i],
                                   entry=entry, exit=px, qty=qty, notional=qty * entry, reason=reason,
                                   fees=fees, pnl=(px - entry) * qty - fees))
                pos = False
    cols = ["sym", "session", "entry_time", "exit_time", "entry", "exit", "qty", "notional", "reason", "fees", "pnl"]
    return pd.DataFrame(trades, columns=cols)


def stats(tr):
    if len(tr) == 0:
        return dict(trades=0, win_pct=np.nan, pf=np.nan, net=0.0, max_dd=0.0,
                    avg_win=np.nan, avg_loss=np.nan, largest_loss=np.nan)
    pnl = tr.sort_values("entry_time").pnl
    eq = pnl.cumsum()
    w, ls = pnl[pnl > 0], pnl[pnl <= 0]
    return dict(trades=len(pnl), win_pct=round(100 * len(w) / len(pnl), 1),
                pf=round(w.sum() / -ls.sum(), 2) if ls.sum() < 0 else float("inf"),
                net=round(pnl.sum(), 2), max_dd=round((eq.cummax().clip(lower=0) - eq).max(), 2),
                avg_win=round(w.mean(), 2) if len(w) else np.nan,
                avg_loss=round(ls.mean(), 2) if len(ls) else np.nan,
                largest_loss=round(ls.min(), 2) if len(ls) else np.nan)


def verdict(s):
    ok = s["trades"] >= MIN_TRADES and s["pf"] >= MIN_PF and s["max_dd"] < MAX_DD
    return "PASS" if ok else "FAIL"


# ---------------------------------------------------------------- report

def main_run(data_dir):
    pd.set_option("display.width", 250)
    data = {s: load(data_dir, s) for s in SYMBOLS}
    all_trades, rows, verdicts = [], {}, {}
    print("Parameters (held fixed from the morning variant):", PARAMS)
    for sym, df in data.items():
        ny = df.index.tz_convert(NY)
        d0, d1 = ny[0].date(), ny[-1].date()
        split = d0 + (d1 - d0) / 2
        expected = int((df.index[-1] - df.index[0]) / pd.Timedelta(minutes=5)) + 1
        print(f"\n{sym}: {len(df)} bars, {df.index[0]} -> {df.index[-1]} UTC "
              f"({100 * len(df) / expected:.1f}% of 5-minute slots present, "
              f"{int((df.volume == 0).sum())} zero-volume bars)")
        print(f"{sym}: first half {d0} to {split - dt.timedelta(days=1)}, second half {split} to {d1} (New York dates)")
        for session in SESSIONS:
            tr = run(df, sym, session, PARAMS)
            all_trades.append(tr)
            second = tr.entry_time.dt.tz_convert(NY).dt.date >= split if len(tr) else []
            halves = {"first": tr[~second] if len(tr) else tr, "second": tr[second] if len(tr) else tr}
            for half, part in halves.items():
                if session == "combined" and half == "first":
                    continue
                rows[f"{sym} {session} {half} half"] = stats(part)
            if session == "morning":
                free = run(df, sym, session, {**PARAMS, "cost": 0.0})
                rows[f"{sym} morning second half, ZERO cost"] = stats(
                    free[free.entry_time.dt.tz_convert(NY).dt.date >= split] if len(free) else free)
            if session == "overnight":
                s2 = rows[f"{sym} overnight second half"]
                verdicts[sym] = verdict(s2)
                if len(halves["second"]):
                    x = halves["second"]
                    print(f"{sym} overnight second half: avg notional ${x.notional.mean():,.0f}, "
                          f"avg fees ${x.fees.mean():.2f} per round trip, exits {x.reason.value_counts().to_dict()}")
    print("\n" + pd.DataFrame(rows).T.to_string())
    print("\n'combined' is information only and 'morning' is a port check; neither affects the verdict.")
    print("The ZERO-cost morning row is the one comparable to the TradingView backtest (commission 0).")
    print(f"\nPass bar: overnight second-half PF >= {MIN_PF}, max DD < ${MAX_DD:.0f}, trades >= {MIN_TRADES}")
    for sym, v in verdicts.items():
        s = rows[f"{sym} overnight second half"]
        print(f"VERDICT {sym}: {v}  (PF {s['pf']}, max DD ${s['max_dd']}, {s['trades']} trades)")
    out = os.path.join(data_dir, "crypto_overnight_trades.csv")
    pd.concat(all_trades).to_csv(out, index=False)
    print(f"\nTrade log: {out}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "fetch":
        fetch(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 12)
    elif len(sys.argv) == 3 and sys.argv[1] == "run":
        main_run(sys.argv[2])
    else:
        sys.exit(__doc__)
