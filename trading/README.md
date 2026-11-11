# Day-trading strategy backtests

Three rule-based 5-minute strategies tested on BTC, ETH, SPY and QQQ.

- `backtest.py` — bar-by-bar backtester and the three strategy definitions.
- `s3_fade.pine` — TradingView Pine v6 script for the top-ranked strategy.
- `fetch_alpaca.py` — downloads 6+ months of SPY/QQQ 5-minute bars from Alpaca (IEX feed).
- `walkforward.py` — out-of-sample test of the fade: tune on the first half, test on the second.

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
reported on, so its numbers are in-sample and optimistic. Nothing here has
passed a six-month out-of-sample test.

## Out-of-sample test (not yet run on 6+ months of data)

```
export APCA_API_KEY_ID=...  APCA_API_SECRET_KEY=...   # from your shell, never committed
python3 trading/fetch_alpaca.py <data_dir> 12
python3 trading/walkforward.py <data_dir>
```

`walkforward.py` picks one parameter set on the first half of the sessions,
runs it untouched on the second half, and prints a verdict. Promotion rule:
out-of-sample profit factor of at least 1.2 and max drawdown under $150.
If it fails, the strategy is dropped; it is not re-tuned on the test half.

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
