# Day-trading strategy backtests

Three rule-based 5-minute strategies tested on BTC, ETH, SPY and QQQ.

- `backtest.py` — bar-by-bar backtester and the three strategy definitions.
- `s3_fade.pine` — TradingView Pine v6 script for the top-ranked strategy.
- `fetch_alpaca.py` — downloads 6+ months of SPY/QQQ 5-minute bars from Alpaca (IEX feed).
- `walkforward.py` — out-of-sample test of the fade: tune on the first half, test on the second.
- `bullflag.py` — bull-flag continuation strategy and its walk-forward test (result below: FAIL).

## Reproduce

Download Binance monthly 5m kline zips for `BTCUSDT` and `ETHUSDT` from
`data.binance.vision` (saved as `BTCUSDT-YYYY-MM.zip`) and Yahoo chart JSON for
SPY and QQQ (`interval=5m&range=60d`, saved as `SPY.json`, `QQQ.json`) into one
directory, then:

```
python3 trading/backtest.py <data_dir>
```

## Assumptions

- $25 fixed risk per trade, notional capped at $10,000 (4x a $2,500 account).
- Signal on bar close, fill at next open; stop wins if stop and target share a bar.
- Costs per side: 0.06% crypto, 0.01% ETFs.

## Results (run 2026-11-11)

Crypto: 2025-11-01 to 2026-10-31 (12 months). ETFs: 2026-08-18 to 2026-11-10
(60 sessions — Yahoo serves only 60 days of 5m bars, so the ETF sample is
shorter than six months).

| Strategy | Market | Trades | Win % | Profit factor | Max DD | Avg month |
|---|---|---|---|---|---|---|
| S1 opening-range breakout | BTC+ETH | 559 | 37.0 | 0.72 | $3,285 | -$235 |
| S1 opening-range breakout | SPY+QQQ | 98 | 34.7 | 0.70 | $539 | -$158 |
| S2 VWAP/EMA trend pullback | BTC+ETH | 499 | 34.1 | 0.61 | $3,964 | -$310 |
| S2 VWAP/EMA trend pullback | SPY+QQQ | 57 | 43.9 | 1.06 | $207 | +$11 |
| S3 fade (first-pass parameters) | BTC+ETH | 791 | 35.5 | 0.37 | $8,458 | -$705 |
| S3 fade (first-pass parameters) | SPY+QQQ | 97 | 51.5 | 0.98 | $171 | -$5 |
| S3b fade (tuned) | SPY+QQQ | 117 | 60.7 | 1.68 | $91 | +$117 |

S3b's parameters were chosen from 12 variants on the same 60 sessions it is
reported on, so its numbers are in-sample and optimistic. It later failed the
out-of-sample test below.

## Out-of-sample test: FAIL (run 2026-11-11)

Data: Alpaca IEX feed, SPY + QQQ 5-minute bars, 252 sessions from 2025-11-10
to 2026-11-10, split at 2026-05-13. $25 risk per trade.

| Test | Period | Trades | Win % | Profit factor | Max DD | Avg month |
|---|---|---|---|---|---|---|
| Tuned on first half (ADX<20, BB 2.5, stop 1.5 ATR), in-sample | 2025-11-10 to 2026-05-12 | 89 | 48.3 | 1.21 | $278 | +$24 |
| Same parameters, out-of-sample | 2026-05-13 to 2026-11-10 | 82 | 43.9 | 0.69 | $360 | -$38 |
| Shipped S3b (ADX<25, BB 2.0, stop 2.5 ATR), data it never saw | 2025-11-10 to 2026-08-17 | 508 | 48.0 | 0.80 | $1,144 | -$87 |
| Shipped S3b, its own tuning window | 2026-08-18 to 2026-11-10 | 117 | 60.7 | 1.65 | $95 | +$113 |

Promotion rule: out-of-sample profit factor of at least 1.2 and max drawdown
under $150. Result: 0.69 and $360, so the fade is **not** promoted to paper
trading. The earlier 60-session result was a product of in-sample tuning: the
same parameters lose money on the nine months before that window. The
strategy is not to be re-tuned on this data.

Reproduce:

```
export APCA_API_KEY_ID=...  APCA_API_SECRET_KEY=...   # from your shell, never committed
python3 trading/fetch_alpaca.py <data_dir> 12
python3 trading/walkforward.py <data_dir>
```

## Bull-flag continuation walk-forward: FAIL on all four (run 2026-11-11)

**Do not paper trade. No re-tuning on this data.**

`bullflag.py`, run once with rules fixed before any data was loaded. Long only:
an impulse of at least 3, 4 or 5 ATR over 3, 5 or 8 bars; a 3 to 10 bar flag
that stays under the impulse high, retraces less than 38.2% or 50% of it and
has a flat or falling close slope; entry at the next open after a close above
the flag high; stop just below the flag low; target 2R; $25 risk; 0.06% per
side crypto, 0.01% per side ETFs. The 18 variants were tuned on the first half
only, one pick per asset class (BTC+ETH, SPY+QQQ, minimum 30 first-half
trades), and the pick was run once on the second half.

Data: BTC and ETH, Binance 5-minute bars, 2025-10-31 to 2026-10-31, split at
2026-05-02. SPY and QQQ, Alpaca IEX 5-minute bars, 2025-11-11 to 2026-11-11,
split at 2026-05-13.

| Asset | Half | Trades | Win % | Profit factor | Max DD | Avg month | Verdict |
|---|---|---|---|---|---|---|---|
| BTC | First (tuned) | 29 | 48.3 | 1.22 | $153 | +$16 | |
| BTC | Second (unseen) | 42 | 38.1 | 0.60 | $420 | -$51 | **FAIL** |
| ETH | First (tuned) | 33 | 24.2 | 0.42 | $531 | -$71 | |
| ETH | Second (unseen) | 31 | 45.2 | 0.99 | $217 | -$1 | **FAIL** |
| SPY | First | no variant selected | | | | | **FAIL** |
| QQQ | First | no variant selected | | | | | **FAIL** |

Crypto selection: impulse of 4 ATR over 5 bars, 50% retrace cap.

SPY and QQQ: no variant reached 30 trades in the first half, so nothing was
selected and the second half was never run. The most active variant (3 ATR
over 8 bars, 50% retrace cap) made 26 first-half trades across both (11 SPY,
15 QQQ) at a profit factor of 0.40.

Promotion rule: second-half profit factor of at least 1.2 and max drawdown
under $150. No asset met it.

Reproduce (crypto zips as in "Reproduce" above, for 2025-11 to 2026-10):

```
export APCA_API_KEY_ID=...  APCA_API_SECRET_KEY=...   # from your shell, never committed
python3 trading/fetch_alpaca.py <data_dir> 12
python3 trading/bullflag.py <data_dir>
```

## Pine script check

There is no official headless Pine compiler. `s3_fade.pine` was reviewed by
hand against the v6 reference and passes two third-party checkers
(`pinescript-v6-validator`, `pynescript`), which is weaker than a real compile.
To confirm in TradingView:

1. Open SPY (then QQQ) on a 5-minute chart with extended hours off.
2. Pine Editor → paste the script → Save → Add to chart. Confirm no errors or
   warnings in the editor console.
3. Confirm the mean and both bands plot, and trade markers appear only
   between 10:00 and 15:55 New York time.
4. In Strategy Tester, compare the List of Trades with the backtester for the
   same dates: entry times should match bar for bar, stops sit 2.5 ATR from
   the signal close, and every position is flat by the 15:55 close.
   Small differences are expected because TradingView uses consolidated
   prices and the backtest uses Yahoo or IEX bars.
