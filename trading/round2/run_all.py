"""Run the walk-forward test for all three round-2 strategies.

Usage: python3 trading/round2/run_all.py <data_dir>

<data_dir> needs SPY-1d.json and QQQ-1d.json (Yahoo chart, interval=1d&range=6y)
and Binance daily kline zips (BTCUSDT-1d-YYYY-MM.zip, ETHUSDT-1d-YYYY-MM.zip).
Option bars are downloaded from Alpaca on first use and cached in <data_dir>;
that needs APCA_API_KEY_ID and APCA_API_SECRET_KEY in the environment.
"""
import sys

import common as C
import options_spread as O
import rotation as R
import swing as S

DAILY = ("2022-11-01", "2024-11-01", "2026-10-31")      # four years, split in the middle
OPTIONS = ("2024-02-05", "2025-06-16", "2026-10-30")    # all option history Alpaca has, split in the middle

if __name__ == "__main__":
    data_dir = sys.argv[1]
    data = C.load_all(data_dir)
    results = []

    plan = O.schedule(data["SPY"], OPTIONS[0], OPTIONS[2])
    prices = O.load_prices(data_dir, plan)
    results.append(C.walk_forward("S1 SPY weekly put credit spread", O.GRID,
                                  lambda p: O.run(data["SPY"], plan, prices, p), *OPTIONS))
    results.append(C.walk_forward("S2 Daily pullback swing (SPY, QQQ, BTC, ETH)", S.GRID,
                                  lambda p: S.run(data, p), *DAILY))
    results.append(C.walk_forward("S3 Weekly momentum rotation (SPY, QQQ, BTC, ETH)", R.GRID,
                                  lambda p: R.run(data, p), *DAILY, min_trades=10))
    for r in results:
        C.report(r)

    print("\n=== Ranking by out-of-sample net profit / max drawdown ===")
    def score(r):
        o = r["oos"]
        return o["net"] / o["max_dd"] if o["max_dd"] else float("inf") if o["net"] > 0 else float("-inf")
    for i, r in enumerate(sorted(results, key=score, reverse=True), 1):
        print(f"{i}. {r['name']}: {score(r):+.2f}  ({'PASS' if r['passed'] else 'FAIL'})")
    if "--detail" in sys.argv:
        for r in results:
            print(f"\n--- {r['name']}: first-half result of every variant ---")
            for p, s in r["all_is"]:
                print(f"  {p}: {C.fmt(s)}")
