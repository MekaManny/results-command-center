"""'Day Trading for Dummies' SPY/QQQ options strategy: walk-forward test.

Usage:
  python3 trading/dfd_options.py fetch <data_dir> [months_back=12]
  python3 trading/dfd_options.py run   <data_dir>

Credentials come from the environment (APCA_API_KEY_ID, APCA_API_SECRET_KEY)
or, if unset, from a hidden prompt. They are never written to disk.

Rules (fixed before any data was loaded):
  direction : first 15 minutes of the regular session (09:30, 09:35 and 09:40
              five-minute bars, New York time). Close of the 09:40 bar below
              the 09:30 open -> buy a put; above -> buy a call; equal -> no trade.
  entry     : 09:45, one trade per day at most, 1 contract.
  expiry    : the next trading session's expiry (never 0DTE).
  strike    : absolute delta closest to the target (0.45 as specified).
  exit      : stop at a 50% loss of premium, target at a 100% gain, whichever
              is hit first; otherwise flat at 15:55 the same day.
  costs     : $0.65 per contract per side.

What Alpaca's history does and does not have, and what was pinned as a result:
  * Option prices are Alpaca historical option bars at 1-minute granularity.
    These are aggregates of real trades. No price is modelled.
  * Alpaca has no historical option bid/ask. `fetch` probes the quotes
    endpoint once and records the answer. Entry is therefore the first real
    trade of the 09:45 minute (the 09:45 bar's open), not the ask, and exits
    are trade prices, not the bid. Results are optimistic by roughly half the
    spread on each side.
  * Alpaca has no historical greeks. Delta is the Black-Scholes delta implied
    by each contract's own real 09:45 trade price against the underlying's
    09:45 open (zero rate, so only price, spot and strike enter). This is a
    calculated delta used only to choose the strike.
  * A contract with no trade in the 09:45 minute cannot be chosen. A day with
    no eligible contract is skipped and counted.
  * Stop and target are checked against each 1-minute bar's low and high from
    the 09:45 bar on. If both are inside one bar the stop wins. A bar that
    opens through a level fills at its open. Otherwise fills are at the level.
  * Time exit is the open of the option's 15:55 bar, or the last trade before
    15:55 if it did not trade in that minute (counted as a stale exit).
  * Sessions without a 15:55 underlying bar (half days) are skipped, as is the
    final session (its next expiry is not in the data).

Walk-forward: sessions split in two equal halves by date. The 27-variant grid
(stop 40/50/60%, target 75/100/150%, delta 0.35/0.45/0.55) is scored on the
first half only, per asset, by profit factor (minimum 30 first-half trades).
That one variant is run once on the second half. PASS needs second-half profit
factor >= 1.2 AND max drawdown < $150 AND at least 10 second-half trades.
The as-specified 50/100/0.45 rules are also shown on both halves for reference;
the verdict is on the selected variant only.
"""
import datetime as dt
import getpass
import itertools
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

import backtest as B

SYMS = ("SPY", "QQQ")
GRID = [dict(stop=s, tgt=g, delta=d) for s, g, d in
        itertools.product((0.40, 0.50, 0.60), (0.75, 1.00, 1.50), (0.35, 0.45, 0.55))]
BASE = dict(stop=0.50, tgt=1.00, delta=0.45)
DELTAS = sorted({p["delta"] for p in GRID})
COMMISSION = 0.65 * 2
BAND = 0.025                     # candidate strikes within 2.5% of spot, $1 apart
MIN_PF, MAX_DD, MIN_OOS_TRADES, MIN_IS_TRADES = 1.2, 150, 10, 30
OPT = "https://data.alpaca.markets/v1beta1/options/"


# ---------- pure logic (shared by fetch and run) ----------
def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def abs_delta(price, spot, strike, kind):
    """Black-Scholes |delta| implied by a real price; zero rate. None if no solution."""
    intrinsic = max(0.0, spot - strike if kind == "C" else strike - spot)
    if price <= intrinsic or price >= (spot if kind == "C" else strike):
        return None
    def value(v):
        d1 = math.log(spot / strike) / v + v / 2
        call = spot * ncdf(d1) - strike * ncdf(d1 - v)
        return call if kind == "C" else call - spot + strike
    lo, hi = 1e-6, 5.0
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if value(mid) < price else (lo, mid)
    d1 = math.log(spot / strike) / lo + lo / 2
    return ncdf(d1) if kind == "C" else ncdf(-d1)


def occ(sym, expiry, kind, strike):
    return f"{sym}{expiry:%y%m%d}{kind}{int(round(strike * 1000)):08d}"


def strike_of(symbol):
    return int(symbol[-8:]) / 1000


_HM = {}


def hhmm(bar):
    """New York HH:MM of a bar's UTC timestamp."""
    t = bar["t"]
    if t not in _HM:
        _HM[t] = pd.Timestamp(t).tz_convert(B.NY).strftime("%H:%M")
    return _HM[t]


def plan(df):
    """One row per tradable session: date, direction, spot at 09:45, expiry."""
    days = sorted(set(df.index.date))
    by_day = {d: g for d, g in df.groupby(df.index.date)}
    rows, counts = [], dict(sessions=len(days), flat=0, half_or_gappy=0, last=0)
    for i, d in enumerate(days):
        day = by_day[d]
        m = {t.hour * 60 + t.minute: j for j, t in enumerate(day.index)}
        if not all(k in m for k in (570, 575, 580, 585, 955)):
            counts["half_or_gappy"] += 1
            continue
        if i + 1 == len(days):
            counts["last"] += 1
            continue
        o, c = day.open.iloc[m[570]], day.close.iloc[m[580]]
        if c == o:
            counts["flat"] += 1
            continue
        rows.append(dict(date=d, kind="C" if c > o else "P", spot=day.open.iloc[m[585]], expiry=days[i + 1]))
    return rows, counts


def pick(open_bars, spot, kind, target):
    """Contract whose implied |delta| is closest to target, among those that traded at 09:45."""
    best = None
    for symbol, bars in open_bars.items():
        bar = next((b for b in bars if hhmm(b) == "09:45"), None)
        if bar is None:
            continue
        k = strike_of(symbol)
        d = abs_delta(bar["o"], spot, k, kind)
        if d is None:
            continue
        key = (abs(d - target), abs(k - spot))
        if best is None or key < best[0]:
            best = (key, symbol, bar["o"], d)
    return best and best[1:]


def simulate(bars, entry, p):
    """Exit price and reason for one long option from the 09:45 bar on."""
    stop, tgt = entry * (1 - p["stop"]), entry * (1 + p["tgt"])
    last, first = None, True
    for b in sorted(bars, key=lambda b: b["t"]):
        hm = hhmm(b)
        if hm < "09:45":
            continue
        if hm >= "15:55":
            return (b["o"], "time") if hm == "15:55" else (last, "time-stale")
        if b["l"] <= stop:
            return (stop if first else min(stop, b["o"])), "stop"
        if b["h"] >= tgt:
            return (tgt if first else max(tgt, b["o"])), "target"
        last, first = b["c"], False
    return last, "time-stale"


# ---------- fetch ----------
def creds():
    key = os.environ.get("APCA_API_KEY_ID") or getpass.getpass("Alpaca key ID: ")
    sec = os.environ.get("APCA_API_SECRET_KEY") or getpass.getpass("Alpaca secret key: ")
    return {"APCA-API-KEY-ID": key.strip(), "APCA-API-SECRET-KEY": sec.strip()}


def get(url, q, headers):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url + "?" + urllib.parse.urlencode(q), headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r:
                time.sleep(0.32)                     # stay under 200 requests a minute
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 3:
                raise
            time.sleep(20)


def option_bars(symbols, start, end, headers):
    bars, token = {}, None
    while True:
        q = dict(symbols=",".join(symbols), timeframe="1Min", start=start.isoformat(), end=end.isoformat(), limit=10000)
        if token:
            q["page_token"] = token
        page = get(OPT + "bars", q, headers)
        for s, b in (page.get("bars") or {}).items():
            bars.setdefault(s, []).extend(b)
        token = page.get("next_page_token")
        if not token:
            return bars


def cached(path, make):
    if os.path.exists(path):
        return json.load(open(path))
    out = make()
    json.dump(out, open(path, "w"))
    return out


def fetch(data_dir, months):
    import fetch_alpaca as F
    headers = creds()
    cache = os.path.join(data_dir, "dfd")
    os.makedirs(cache, exist_ok=True)
    today = dt.datetime.now(dt.timezone.utc).date()
    end = f"{today}T00:00:00Z"                       # completed sessions only
    start = f"{today - dt.timedelta(days=round(30.5 * months))}T00:00:00Z"
    probe = None
    for sym in SYMS:
        path = os.path.join(data_dir, f"{sym}.json")
        bars = F.fetch(sym, start, end, headers)
        ts = [int(dt.datetime.fromisoformat(b["t"].replace("Z", "+00:00")).timestamp()) for b in bars]
        quote = {k: [b[a] for b in bars] for k, a in
                 [("open", "o"), ("high", "h"), ("low", "l"), ("close", "c"), ("volume", "v")]}
        json.dump({"chart": {"result": [{"meta": {"symbol": sym, "source": "alpaca-sip"},
                                         "timestamp": ts, "indicators": {"quote": [quote]}}]}}, open(path, "w"))
        rows, _ = plan(B.load_etf(data_dir, sym))
        print(f"{sym}: {len(bars)} five-minute bars, {len(rows)} sessions to price")
        for n, r in enumerate(rows, 1):
            t0 = pd.Timestamp(f"{r['date']} 09:45", tz=B.NY)
            lo, hi = math.ceil(r["spot"] * (1 - BAND)), math.floor(r["spot"] * (1 + BAND))
            cands = [occ(sym, r["expiry"], r["kind"], k) for k in range(lo, hi + 1)]
            tag = os.path.join(cache, f"{sym}-{r['date']:%Y%m%d}")
            opens = cached(tag + "-open.json", lambda: option_bars(cands, t0, t0 + pd.Timedelta(minutes=1), headers))
            chosen = sorted({c[0] for c in (pick(opens, r["spot"], r["kind"], d) for d in DELTAS) if c})
            if chosen:
                cached(tag + "-day.json", lambda: option_bars(
                    chosen, t0, pd.Timestamp(f"{r['date']} 16:00", tz=B.NY), headers))
                if probe is None:
                    try:
                        page = get(OPT + "quotes", dict(symbols=chosen[0], start=t0.isoformat(),
                                                        end=(t0 + pd.Timedelta(minutes=1)).isoformat(), limit=5), headers)
                        got = sum(len(v) for v in (page.get("quotes") or {}).values())
                        probe = f"HTTP 200, {got} quotes returned for {chosen[0]}"
                    except urllib.error.HTTPError as e:
                        probe = f"HTTP {e.code} (no historical option quotes)"
            if n % 25 == 0 or n == len(rows):
                print(f"  {sym} {n}/{len(rows)}")
    json.dump(dict(quotes_probe=probe, fetched=str(dt.datetime.now(dt.timezone.utc)), months=months),
              open(os.path.join(cache, "meta.json"), "w"))
    print(f"Historical option quotes probe: {probe}\nDone. Now: python3 trading/dfd_options.py run {data_dir}")


# ---------- run ----------
def load_days(sym, rows, cache):
    """Attach each session's cached option bars and its pick per delta target."""
    for r in rows:
        tag = os.path.join(cache, f"{sym}-{r['date']:%Y%m%d}")
        r["have"] = os.path.exists(tag + "-open.json")
        if not r["have"]:
            continue
        opens = json.load(open(tag + "-open.json"))
        r["picks"] = {d: pick(opens, r["spot"], r["kind"], d) for d in DELTAS}
        r["day"] = json.load(open(tag + "-day.json")) if os.path.exists(tag + "-day.json") else {}


def trades(sym, rows, p):
    out, skipped, stale, missing = [], 0, 0, 0
    for r in rows:
        if not r["have"]:
            missing += 1
            continue
        c = r["picks"][p["delta"]]
        if not c:
            skipped += 1
            continue
        symbol, entry, delta = c
        exit_px, why = simulate(r["day"].get(symbol, []), entry, p)
        if exit_px is None:
            skipped += 1
            continue
        stale += why == "time-stale"
        pnl = (exit_px - entry) * 100 - COMMISSION
        out.append((pd.Timestamp(r["date"], tz=B.NY), sym, pnl, symbol, entry, exit_px, why, round(delta, 3)))
    df = pd.DataFrame(out, columns=["time", "sym", "pnl", "contract", "entry", "exit", "why", "delta"])
    df.attrs.update(skipped=skipped, stale=stale, missing=missing)
    return df


def line(label, tr, months):
    s = B.stats(tr, months)
    if not s["trades"]:
        print(f"  {label}: no trades")
        return s
    print(f"  {label}: trades={s['trades']} win={s['win_rate']}% PF={s['profit_factor']} "
          f"net/month=${tr.pnl.sum() / months:.0f} maxDD=${s['max_dd']} "
          f"(avg premium ${tr.entry.mean() * 100:.0f}, stops {sum(tr.why == 'stop')}, "
          f"targets {sum(tr.why == 'target')}, time {sum(tr.why.str.startswith('time'))})")
    return s


def run(data_dir):
    cache = os.path.join(data_dir, "dfd")
    meta = json.load(open(os.path.join(cache, "meta.json")))
    print("Data granularity: underlying = Alpaca SIP 5-minute bars; options = Alpaca historical option bars, "
          "1-minute, real trades.")
    print(f"Historical option quotes probe: {meta['quotes_probe']}")
    if str(meta["quotes_probe"]).startswith("HTTP 200") and ", 0 quotes" not in meta["quotes_probe"]:
        print("STOP: bid/ask history exists. The rules call for ask/bid fills; this run uses trade prices. "
              "Do not use this result.")
    verdicts = {}
    for sym in SYMS:
        df = B.load_etf(data_dir, sym)
        rows, n = plan(df)
        days = sorted(set(df.index.date))
        split = pd.Timestamp(days[len(days) // 2], tz=B.NY)
        first, last = pd.Timestamp(days[0], tz=B.NY), pd.Timestamp(days[-1], tz=B.NY)
        m1, m2 = max((split - first).days / 30.4, 0.1), max((last - split).days / 30.4, 0.1)
        print(f"\n=== {sym}: {n['sessions']} sessions {days[0]} -> {days[-1]}, split at {split.date()} ===")
        print(f"  no trade: flat first bar {n['flat']}, half day or missing bars {n['half_or_gappy']}, final session {n['last']}")
        load_days(sym, rows, cache)
        scored = []
        for p in GRID:
            tr = trades(sym, rows, p)
            s = B.stats(tr[tr.time < split], m1)
            if s["trades"] >= MIN_IS_TRADES:
                scored.append((s["profit_factor"], -GRID.index(p), p, tr))
        base = trades(sym, rows, BASE)
        print(f"  as specified {BASE}: no eligible contract on {base.attrs['skipped']} days, "
              f"option data missing on {base.attrs['missing']}, stale time exits {base.attrs['stale']}")
        line("as specified, first half ", base[base.time < split], m1)
        line("as specified, second half", base[base.time >= split], m2)
        if not scored:
            print(f"  No variant reached {MIN_IS_TRADES} first-half trades. VERDICT {sym}: FAIL")
            verdicts[sym] = "FAIL"
            continue
        _, _, p, tr = max(scored, key=lambda x: (x[0], x[1]))
        print(f"  selected on first half: {p}")
        line("selected, first half (tuned)  ", tr[tr.time < split], m1)
        o = line("selected, second half (unseen)", tr[tr.time >= split], m2)
        ok = o["trades"] >= MIN_OOS_TRADES and o["profit_factor"] >= MIN_PF and o["max_dd"] < MAX_DD
        verdicts[sym] = "PASS" if ok else "FAIL"
        print(f"  VERDICT {sym}: {verdicts[sym]} (rule: second-half PF >= {MIN_PF}, max DD < ${MAX_DD}, "
              f">= {MIN_OOS_TRADES} trades)")
        tr.to_csv(os.path.join(cache, f"{sym}-trades.csv"), index=False)
    print("\n" + "; ".join(f"{s}: {v}" for s, v in verdicts.items()) +
          ". FAIL means do not paper trade. No re-tuning on this data either way.")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("fetch", "run"):
        sys.exit(__doc__)
    if sys.argv[1] == "fetch":
        fetch(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 12)
    else:
        run(sys.argv[2])
