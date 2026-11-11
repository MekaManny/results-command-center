"""Download 5-minute SPY and QQQ bars from Alpaca (IEX feed) for the backtester.

Usage: python3 trading/fetch_alpaca.py <data_dir> [months_back=12]

Credentials are read from the environment, never from this file:
  APCA_API_KEY_ID, APCA_API_SECRET_KEY

Output is <data_dir>/SPY.json and QQQ.json in the Yahoo chart layout that
backtest.load_etf() already reads.
"""
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

URL = "https://data.alpaca.markets/v2/stocks/{sym}/bars"


def fetch(sym, start, end, headers):
    bars, token = [], None
    while True:
        q = dict(timeframe="5Min", start=start, end=end, feed="iex", adjustment="split", limit=10000)
        if token:
            q["page_token"] = token
        req = urllib.request.Request(URL.format(sym=sym) + "?" + urllib.parse.urlencode(q), headers=headers)
        with urllib.request.urlopen(req, timeout=60) as r:
            page = json.load(r)
        bars += page.get("bars") or []
        token = page.get("next_page_token")
        if not token:
            return bars


def main():
    data_dir = sys.argv[1]
    months = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    try:
        headers = {"APCA-API-KEY-ID": os.environ["APCA_API_KEY_ID"],
                   "APCA-API-SECRET-KEY": os.environ["APCA_API_SECRET_KEY"]}
    except KeyError as e:
        sys.exit(f"Set {e.args[0]} in the environment first.")
    now = dt.datetime.now(dt.timezone.utc)
    end = (now - dt.timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")  # free plan: no last 15 minutes
    start = (now - dt.timedelta(days=30.5 * months)).strftime("%Y-%m-%dT00:00:00Z")
    for sym in ("SPY", "QQQ"):
        bars = fetch(sym, start, end, headers)
        ts = [int(dt.datetime.fromisoformat(b["t"].replace("Z", "+00:00")).timestamp()) for b in bars]
        quote = {k: [b[a] for b in bars] for k, a in
                 [("open", "o"), ("high", "h"), ("low", "l"), ("close", "c"), ("volume", "v")]}
        out = {"chart": {"result": [{"meta": {"symbol": sym, "source": "alpaca-iex"},
                                     "timestamp": ts, "indicators": {"quote": [quote]}}]}}
        with open(os.path.join(data_dir, f"{sym}.json"), "w") as f:
            json.dump(out, f)
        print(f"{sym}: {len(bars)} bars {bars[0]['t']} -> {bars[-1]['t']}")


if __name__ == "__main__":
    main()
