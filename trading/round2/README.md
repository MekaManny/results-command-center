# Round 2: three new strategies, walk-forward from the start

Round 1 (see `../README.md`) failed out of sample. Every strategy here was run
through the same fixed protocol: declare a small parameter grid, pick the
variant with the best first-half profit factor, and judge only that variant's
second-half result. Promotion rule: second-half profit factor of at least 1.2
and max drawdown under $150. Nothing was re-tuned after the second half was seen.

## Out-of-sample table (run 2026-11-11)

| Strategy | Half | Period | Trades | Win % | Profit factor | Max DD | Avg month | Verdict |
|---|---|---|---|---|---|---|---|---|
| S1 SPY weekly put credit spread | In-sample | 2024-02-05 to 2025-06-15 | 52 | 69.2 | 0.85 | $448 | -$10.2 | |
| S1 SPY weekly put credit spread | Out-of-sample | 2025-06-16 to 2026-10-30 | 54 | 68.5 | 0.79 | $574 | -$15.9 | **FAIL** |
| S2 Daily pullback swing | In-sample | 2022-11-01 to 2024-10-31 | 73 | 69.9 | 1.95 | $51 | +$10.6 | |
| S2 Daily pullback swing | Out-of-sample | 2024-11-01 to 2026-10-31 | 75 | 72.0 | 1.78 | $78 | +$10.7 | **PASS** |
| S3 Weekly momentum rotation | In-sample | 2022-11-01 to 2024-10-31 | 31 | 54.8 | 2.03 | $80 | +$12.9 | |
| S3 Weekly momentum rotation | Out-of-sample | 2024-11-01 to 2026-10-31 | 22 | 31.8 | 1.46 | $157 | +$5.6 | **FAIL** |

Ranking by out-of-sample net profit over max drawdown: S2 (+3.28), S3 (+0.85),
S1 (-0.46).

S2 and S3 are at $25 risk per trade. S1 is one $1-wide spread per trade, whose
worst case is $100 minus the credit (about $60-$95); SPY offers nothing smaller,
so S1 could not be sized to a true $25 maximum loss.

### What the S2 pass does and does not mean

- It earns about $11 a month at $25 risk: 0.4% a month on $2,500. It clears the
  promotion rule, but at this size it is nowhere near a path to doubling the
  account.
- It is long only, and the test half was a rising market (SPY +32%, QQQ +42%).
  Out of sample, SPY made $169 of the $257; ETH lost $9.
- Max drawdown is measured on closed trades, not intraday lows.
- All eight grid variants were profitable in both halves, which is some
  evidence the result is not a single lucky parameter set.
- Up to four positions can be open at once, about $2,900 of notional in the
  worst case. On a $1,000 account, scale risk to $10 a trade.

## Data and costs

- SPY, QQQ daily bars: Yahoo. BTC, ETH daily bars: Binance spot (UTC days).
- SPY option prices: Alpaca hourly option bars (real trades, from Feb 2024).
  All 852 option contracts the test needed had data.
- Costs per side: 0.01% ETFs, 0.10% crypto. Options: $3.10 per spread on every
  open and close ($0.03 slippage plus $0.10 fees). A broker charging $0.65 per
  contract would add $1.30 to each of those.
- Daily strategies use four years so each half has enough trades; options use
  all the history Alpaca has (33 months).

## S1 - SPY weekly put credit spread (`options_spread.py`)

- **Entry:** first trading day of each week, last hour of the session. Sell one
  put spread expiring on the last trading day of the following week.
- **Strikes:** short put at `floor(S * (1 - m * sigma * sqrt(T)))`, long put $1
  lower. `S` is the SPY close, `sigma` the standard deviation of the last 20
  daily log returns, `T` the trading days to expiry.
- **Selected variant:** `m = 0.25`, only when SPY is above its 50-day SMA, hold
  to expiry. The other exit mode tested closes at 50% of the credit or at a $25
  loss.
- **Skip:** either leg has no trade in the entry hour, or credit outside
  $0.05-$0.95.
- **Result:** all 12 variants lost in the first half. Before costs the spreads
  made $0-$5 per trade; the $3-$6 of round-trip costs is larger than that.
- **Kill:** already dead. Do not trade.

## S2 - Daily pullback swing (`swing.py`, `s2_pullback_swing.pine`)

Markets: SPY, QQQ, BTC, ETH. Daily bars, long only, one position per market.

- **Entry:** on the daily close, if close > SMA(100) and RSI(2) < 10, buy at the
  next open.
- **Stop:** resting stop 2 x ATR(14) below the entry price (ATR from the signal
  day). A gap below the stop fills at the open.
- **Exit:** when a daily close is above SMA(5), or on the 10th bar in the
  trade, sell at the next open. There is no profit target.
- **Size:** `$25 / (2 x ATR)` units, capped at $2,500 notional. No leverage.
- **Do not trade when:** close is at or below SMA(100) (the entry rule already
  enforces this).
- **Kill conditions** (stop trading and do not re-tune):
  1. closed-trade drawdown reaches $150 at $25 risk, or
  2. profit factor is below 1.0 after the first 30 live trades, or
  3. 8 losses in a row (twice the first-half worst streak of 4).

## S3 - Weekly momentum rotation (`rotation.py`)

- **Decision:** after the close of the last US trading day of each week, rank
  SPY, QQQ, BTC, ETH by return over the last 84 calendar days.
- **Hold:** the top-ranked market if its return is positive, otherwise cash.
  Enter at that market's next daily open, after any old position is closed.
- **Stop:** 2 x ATR(14) below entry, not trailed (selected variant).
- **Exit:** stop hit, or the market stops being top-ranked at a weekly decision.
- **Size:** `$25 / (2 x ATR)`, capped at $2,500 notional.
- **Result:** profitable out of sample (PF 1.46) but its $157 drawdown is over
  the $150 limit, so it fails. Only 22 trades in the test half.
- **Kill:** not promoted.

## Pine script status

`s2_pullback_swing.pine` has not been compiled in TradingView. It passes the
third-party `pinescript-v6-validator`, which is weak evidence. To confirm:
paste into the Pine Editor on a daily SPY chart, check for no errors, then
compare the Strategy Tester trade list with `swing.py` for the same dates.
Expect small differences: TradingView daily bars for SPY/QQQ are
dividend-adjustable and crypto prices differ by exchange.

## Reproduce

```
export APCA_API_KEY_ID=...  APCA_API_SECRET_KEY=...   # needed only for option bars
python3 trading/round2/run_all.py <data_dir> --detail
```

`<data_dir>` needs `SPY-1d.json` and `QQQ-1d.json` (Yahoo chart API,
`interval=1d&range=6y`) and Binance daily kline zips named
`BTCUSDT-1d-YYYY-MM.zip` / `ETHUSDT-1d-YYYY-MM.zip` from 2021-06 onward.
