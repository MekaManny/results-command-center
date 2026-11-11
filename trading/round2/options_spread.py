"""Strategy 1: weekly SPY bull put credit spread, $1 wide, priced from real
historical option trades (Alpaca options bars, available from Feb 2024).

Rules:
  entry day : first US trading day of each week, in the last hour (15:00-16:00 ET)
  filter    : if trend=True, only when SPY close > SMA(50) of daily closes
  expiry    : last trading day of the following week (normally Friday, ~11 days)
  strikes   : short put K = floor(S * (1 - m * sigma * sqrt(T))), long put K - 1
              S = SPY close on entry day, sigma = stdev of the last 20 daily log
              returns, T = trading days from entry to expiry
  size      : 1 spread. Worst case is $100 - credit (about $60-$95), which is
              the smallest defined risk SPY offers; it cannot be cut to $25.
  exits     : mode "managed": each later day in the last hour, close if the
              spread costs <= 50% of the credit (profit target) or
              >= credit + $0.25 (a $25 loss); otherwise settle at expiry.
              mode "hold": settle at expiry only.
  expiry    : worth max(0, min(1, K - SPY close)); closed for that value if > 0
  skip      : either leg has no trade in the entry hour, or credit outside
              $0.05-$0.95
  costs     : $0.03 slippage per spread plus $0.10 fees on every open and close
              (nothing on a spread that expires worthless)

Grid (12 variants): m {0.25, 0.75, 1.25} x trend {False, True} x mode {managed, hold}

Prices are last trades inside an hourly bar, not quotes, so the two legs can
be a few minutes apart. Early assignment is ignored.
"""
import itertools
import json
import math
import os
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

GRID = [dict(m=m, trend=t, mode=x) for m, t, x in
        itertools.product((0.25, 0.75, 1.25), (False, True), ("managed", "hold"))]
MS = sorted({p["m"] for p in GRID})
TXN_COST = 3.10          # dollars per spread per open/close: $0.03 slippage + $0.10 fees
STOP_LOSS = 0.25         # dollars of spread price
URL = "https://data.alpaca.markets/v1beta1/options/bars"


def occ(expiry, strike):
    return f"SPY{expiry:%y%m%d}P{int(round(strike * 1000)):08d}"


def schedule(spy, start, end):
    """One planned trade per week and per m: entry day, expiry, strikes."""
    days = spy.index
    week = days.to_series().dt.to_period("W-SUN")
    first = days[(week != week.shift(1)).values]
    last = pd.Series(days, index=week.values).groupby(level=0).last()
    sigma = np.log(spy.close).diff().rolling(20).std()
    sma50 = spy.close.rolling(50).mean()
    rows = []
    for d in first:
        nxt = d.to_period("W-SUN") + 1
        if d < pd.Timestamp(start) or nxt not in last.index or last[nxt] > pd.Timestamp(end):
            continue
        exp = last[nxt]
        if exp.to_period("W-SUN").end_time.normalize() - exp > pd.Timedelta(days=3):
            continue                                     # incomplete final week of data
        t_days = len(days[(days > d) & (days <= exp)])
        s, sg = spy.close[d], sigma[d]
        for m in MS:
            k = math.floor(s * (1 - m * sg * math.sqrt(t_days)))
            rows.append(dict(entry=d, expiry=exp, m=m, short=k, long=k - 1, spot=s,
                             uptrend=bool(s > sma50[d]), settle=spy.close[exp]))
    return pd.DataFrame(rows)


def fetch_week(cache_dir, entry, expiry, symbols):
    path = os.path.join(cache_dir, f"opt-{entry:%Y%m%d}.json")
    if os.path.exists(path):
        return json.load(open(path))
    headers = {"APCA-API-KEY-ID": os.environ["APCA_API_KEY_ID"],
               "APCA-API-SECRET-KEY": os.environ["APCA_API_SECRET_KEY"]}
    bars, token = {}, None
    while True:
        q = dict(symbols=",".join(symbols), timeframe="1Hour", start=f"{entry:%Y-%m-%d}",
                 end=f"{expiry + pd.Timedelta(days=1):%Y-%m-%d}", limit=10000)
        if token:
            q["page_token"] = token
        req = urllib.request.Request(URL + "?" + urllib.parse.urlencode(q), headers=headers)
        with urllib.request.urlopen(req, timeout=60) as r:
            page = json.load(r)
        for s, b in (page.get("bars") or {}).items():
            bars.setdefault(s, []).extend(b)
        token = page.get("next_page_token")
        if not token:
            break
    json.dump(bars, open(path, "w"))
    return bars


def last_hour_prices(bars):
    """{symbol: {date: close of the 15:00-16:00 New York bar}}"""
    out = {}
    for s, bs in bars.items():
        if not bs:
            continue
        t = pd.to_datetime([b["t"] for b in bs], utc=True).tz_convert("America/New_York")
        ser = pd.Series([b["c"] for b in bs], index=t)
        ser = ser[ser.index.hour == 15]
        out[s] = {ts.normalize().tz_localize(None): v for ts, v in ser.items()}
    return out


def load_prices(cache_dir, plan):
    prices = {}
    for (entry, expiry), g in plan.groupby(["entry", "expiry"]):
        syms = sorted({occ(expiry, k) for k in pd.concat([g.short, g.long])})
        prices.update(last_hour_prices(fetch_week(cache_dir, entry, expiry, syms)))
    return prices


def run(spy, plan, prices, p):
    days = spy.index
    out, skipped = [], 0
    for r in plan[plan.m == p["m"]].itertuples():
        if p["trend"] and not r.uptrend:
            continue
        ps, pl = prices.get(occ(r.expiry, r.short), {}), prices.get(occ(r.expiry, r.long), {})
        if r.entry not in ps or r.entry not in pl:
            skipped += 1
            continue
        credit = ps[r.entry] - pl[r.entry]
        if not 0.05 <= credit <= 0.95:
            skipped += 1
            continue
        exit_day, value = r.expiry, min(1.0, max(0.0, r.short - r.settle))
        if p["mode"] == "managed":
            for d in days[(days > r.entry) & (days < r.expiry)]:
                if d in ps and d in pl:
                    v = min(1.0, max(0.0, ps[d] - pl[d]))
                    if v <= 0.5 * credit or v >= credit + STOP_LOSS:
                        exit_day, value = d, v
                        break
        closed_early = exit_day != r.expiry or value > 0
        pnl = (credit - value) * 100 - TXN_COST - (TXN_COST if closed_early else 0)
        out.append((r.entry, exit_day, "SPY", pnl, credit))
    df = pd.DataFrame(out, columns=["entry", "exit", "sym", "pnl", "credit"])
    df.attrs["skipped"] = skipped
    return df
