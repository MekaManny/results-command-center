# Day-trading strategy backtests

Three rule-based 5-minute strategies tested on BTC, ETH, SPY and QQQ.

- `backtest.py` — bar-by-bar backtester and the three strategy definitions.
- `s3_fade.pine` — TradingView Pine v6 script for the top-ranked strategy.
- `fetch_alpaca.py` — downloads SPY/QQQ 5-minute bars from Alpaca, all hours (SIP feed since the CPI/FOMC test; the earlier results below were run on IEX bars).
- `walkforward.py` — out-of-sample test of the fade: tune on the first half, test on the second.
- `bullflag.py` — bull-flag continuation strategy and its walk-forward test (result below: FAIL).
- `cpi_fomc.py` — CPI/FOMC second-move strategy and its walk-forward test (result below: not enough trades to know).
- `crypto_overnight.py` — BTC-ETH Day Trader v2 rules on an overnight session, walk-forward (result below: FAIL on both).

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

## CPI/FOMC second-move walk-forward: not enough trades to know (run 2026-11-11)

**Do not paper trade. No re-tuning on this data.**

`cpi_fomc.py`, run once with rules fixed before any data was loaded. Events are
CPI releases (08:30 New York) and FOMC statements (14:00 New York) only. The
15 minutes after the release are skipped. Initial direction is the close of the
last bar of that window (08:40 / 14:10 bar) versus the close of the bar just
before the release (08:25 / 13:55 bar); up trades long, down trades short.
Pattern bars are regular-session bars from max(release + 15 min, 09:30) for the
wait window. A pullback is 1 to N consecutive bars closing against the initial
direction (close versus the bar's own open). If any pattern bar gives back the
retrace cap or more of the initial move, measured from the skip-window close,
the event is dead. Entry at the next open after the first bar following the
pullback closes back in the initial direction and beyond the pullback's far
side (above the pullback high for a long); stop just beyond the pullback
extreme (pullback low for a long); target 2R; one trade per event; no signal
bar at or after 15:30, flat on the 15:55 bar; $25 risk (notional capped at
$10,000); 0.01% per side. The 18 variants (wait 30/60/90 minutes, pullback of
up to 1/2/3 bars, retrace cap 38.2%/50%) were tuned on the first half only,
one pick for SPY+QQQ (minimum 10 combined first-half trades), and the pick was
run once on the second half.

Data: SPY and QQQ, Alpaca **SIP** feed (not IEX as in the earlier tests),
5-minute bars, all hours, 2024-11-11 to 2026-11-11, 502 sessions each, split
at 2025-11-11. IEX was dropped because it has the 08:25 and 08:40 pre-market
bars on only a minority of CPI mornings; on SIP every event had its reference
bars and no event was skipped.

| Asset | Half | Events | Trades | Win % | Profit factor | Max DD | Avg month | Rule |
|---|---|---|---|---|---|---|---|---|
| SPY | First (tuned) | 20 | 5 | 80.0 | 8.63 | $15 | +$10 | |
| SPY | Second (unseen) | 20 | 2 | 50.0 | 1.58 | $27 | +$1 | PASS by the rule, meaningless on 2 trades |
| QQQ | First (tuned) | 20 | 5 | 80.0 | 8.06 | $19 | +$11 | |
| QQQ | Second (unseen) | 20 | 1 | 0.0 | 0.00 | $26 | -$2 | **FAIL** |

Selection: 60-minute wait, 1-bar pullback, 50% retrace cap (exactly 10
combined first-half trades, the minimum; pullback length made no difference).

Promotion rule: second-half profit factor of at least 1.2 and max drawdown
under $150. SPY meets it on paper (1.58, $27) but on two trades, one winner
and one loser, netting $16 in 12 months. QQQ fails. **Verdict for both: not
enough trades to know. Do not paper trade, do not re-tune on this data.**

Why it is not evidence either way:

- The second half produced three trades in total across both assets.
- The ten first-half trades are the same five events on both assets, all
  between December 2024 and March 2025; neither asset traded from April to
  November 2025.
- Of 40 events per asset, 31 on each died at the retrace cap, so
  the pattern triggers about three or four times a year per asset.

Event calendar and per-event log (selected variant; initial direction, then
outcome). CPI dates are from the BLS release schedule and CPI archive: the
October 2025 CPI was never published (2025 lapse in appropriations), November
2025 moved to 2025-12-18 and January 2026 to 2026-02-13. FOMC dates are from
the federalreserve.gov meeting calendar; the 2025-08-22 notation vote had no
policy statement and is not an event.

| Date | Event | Half | SPY | QQQ |
|---|---|---|---|---|
| 2024-11-13 | CPI | First | up, retrace cap hit | up, retrace cap hit |
| 2024-12-11 | CPI | First | up, **traded** | up, **traded** |
| 2024-12-18 | FOMC | First | down, **traded** | down, **traded** |
| 2025-01-15 | CPI | First | up, **traded** | up, **traded** |
| 2025-01-29 | FOMC | First | down, **traded** | down, **traded** |
| 2025-02-12 | CPI | First | down, retrace cap hit | down, retrace cap hit |
| 2025-03-12 | CPI | First | up, retrace cap hit | up, retrace cap hit |
| 2025-03-19 | FOMC | First | up, **traded** | up, **traded** |
| 2025-04-10 | CPI | First | down, retrace cap hit | down, retrace cap hit |
| 2025-05-07 | FOMC | First | down, retrace cap hit | down, retrace cap hit |
| 2025-05-13 | CPI | First | up, retrace cap hit | up, retrace cap hit |
| 2025-06-11 | CPI | First | up, retrace cap hit | up, retrace cap hit |
| 2025-06-18 | FOMC | First | down, retrace cap hit | down, retrace cap hit |
| 2025-07-15 | CPI | First | up, retrace cap hit | up, retrace cap hit |
| 2025-07-30 | FOMC | First | down, retrace cap hit | up, retrace cap hit |
| 2025-08-12 | CPI | First | up, retrace cap hit | up, retrace cap hit |
| 2025-09-11 | CPI | First | down, retrace cap hit | down, retrace cap hit |
| 2025-09-17 | FOMC | First | down, retrace cap hit | down, retrace cap hit |
| 2025-10-24 | CPI | First | up, no setup | up, no setup |
| 2025-10-29 | FOMC | First | down, retrace cap hit | down, retrace cap hit |
| 2025-12-10 | FOMC | Second | up, retrace cap hit | up, retrace cap hit |
| 2025-12-18 | CPI | Second | up, retrace cap hit | up, retrace cap hit |
| 2026-01-13 | CPI | Second | up, retrace cap hit | up, retrace cap hit |
| 2026-01-28 | FOMC | Second | down, retrace cap hit | down, retrace cap hit |
| 2026-02-13 | CPI | Second | up, retrace cap hit | up, retrace cap hit |
| 2026-03-11 | CPI | Second | down, retrace cap hit | down, retrace cap hit |
| 2026-03-18 | FOMC | Second | down, no setup | down, no setup |
| 2026-04-10 | CPI | Second | down, retrace cap hit | down, retrace cap hit |
| 2026-04-29 | FOMC | Second | down, retrace cap hit | down, retrace cap hit |
| 2026-05-12 | CPI | Second | up, retrace cap hit | up, retrace cap hit |
| 2026-06-10 | CPI | Second | up, retrace cap hit | up, retrace cap hit |
| 2026-06-17 | FOMC | Second | down, **traded** | down, **traded** |
| 2026-07-14 | CPI | Second | up, retrace cap hit | up, retrace cap hit |
| 2026-07-29 | FOMC | Second | up, retrace cap hit | up, retrace cap hit |
| 2026-08-12 | CPI | Second | up, retrace cap hit | up, retrace cap hit |
| 2026-09-11 | CPI | Second | down, retrace cap hit | down, retrace cap hit |
| 2026-09-16 | FOMC | Second | down, retrace cap hit | down, retrace cap hit |
| 2026-10-14 | CPI | Second | down, **traded** | down, no setup |
| 2026-10-28 | FOMC | Second | down, retrace cap hit | down, retrace cap hit |
| 2026-11-10 | CPI | Second | down, retrace cap hit | down, retrace cap hit |

Reproduce (the fetch now uses the SIP feed, so re-running the older IEX-based
tests above will give slightly different numbers):

```
export APCA_API_KEY_ID=...  APCA_API_SECRET_KEY=...   # from your shell, never committed
python3 trading/fetch_alpaca.py <data_dir> 24
python3 trading/cpi_fomc.py <data_dir>
```

## BTC-ETH Day Trader v2, overnight session: FAIL on both (run 2026-11-13)

**Verdict: BTC — FAIL. ETH — FAIL. Do not paper trade the overnight session on
either asset. No re-tuning on this data.**

| Asset | Second-half overnight PF | Max DD | Trades | Pass bar | Verdict |
|---|---|---|---|---|---|
| BTC | 0.30 | $2,858 | 150 | PF >= 1.2, DD < $150, trades >= 10 | **FAIL** |
| ETH | 0.37 | $2,731 | 155 | PF >= 1.2, DD < $150, trades >= 10 | **FAIL** |

Run once, with every parameter held fixed from the morning variant.

Data: Alpaca crypto 5-minute bars, 2025-11-12 00:00 UTC to 2026-11-13 07:30
UTC. BTC/USD 105,381 bars (99.9% of 5-minute slots present, 21,272 with zero
volume). ETH/USD 101,138 bars (95.9% present, 46,569 with zero volume). Split
by New York date: first half 2025-11-11 to 2026-05-12, second half 2026-05-13
to 2026-11-13. Costs 0.06% per side on every fill.

| Asset | Session | Half | Trades | Win % | Profit factor | Net P&L | Max DD | Avg win | Avg loss | Largest loss |
|---|---|---|---|---|---|---|---|---|---|---|
| BTC | Overnight | First | 140 | 37.9 | 0.29 | -$2,534.38 | $2,584.74 | $19.94 | -$41.28 | -$61.65 |
| BTC | Overnight | **Second (the test)** | 150 | 43.3 | 0.30 | -$2,811.41 | $2,857.88 | $18.63 | -$47.32 | -$100.68 |
| ETH | Overnight | First | 143 | 34.3 | 0.28 | -$2,883.59 | $2,883.59 | $23.13 | -$42.73 | -$96.62 |
| ETH | Overnight | **Second (the test)** | 155 | 41.9 | 0.37 | -$2,730.66 | $2,730.66 | $24.46 | -$48.01 | -$469.62 |

Information only, not part of the verdict:

| Asset | Session | Half | Trades | Win % | Profit factor | Net P&L | Max DD | Avg win | Avg loss | Largest loss |
|---|---|---|---|---|---|---|---|---|---|---|
| BTC | Combined day (00:00–11:30, flat 15:55) | Second | 205 | 44.9 | 0.36 | -$3,360.37 | $3,405.82 | $20.52 | -$46.44 | -$100.68 |
| ETH | Combined day (00:00–11:30, flat 15:55) | Second | 208 | 44.2 | 0.44 | -$3,024.80 | $3,047.37 | $26.15 | -$46.81 | -$469.62 |
| BTC | Morning (port check) | First | 42 | 33.3 | 0.45 | -$512.21 | $545.14 | $29.92 | -$33.25 | -$44.53 |
| BTC | Morning (port check) | Second | 54 | 48.1 | 0.54 | -$548.38 | $591.49 | $24.66 | -$42.48 | -$82.70 |
| BTC | Morning, zero cost | Second | 54 | 48.1 | 1.21 | +$170.38 | $179.76 | $37.55 | -$28.78 | -$68.59 |
| ETH | Morning (port check) | First | 38 | 31.6 | 0.37 | -$595.09 | $595.09 | $28.98 | -$36.26 | -$53.52 |
| ETH | Morning (port check) | Second | 53 | 50.9 | 0.77 | -$244.22 | $508.49 | $30.20 | -$40.76 | -$65.77 |
| ETH | Morning, zero cost | Second | 53 | 52.8 | 1.58 | +$428.48 | $304.61 | $41.67 | -$29.53 | -$46.83 |

What the numbers say:

- **Costs decide it.** Second-half overnight positions averaged about $18,000
  notional (BTC $18,243, ETH $17,668), so a round trip cost about $21.50 in
  fees (BTC $21.89, ETH $21.20) against a $25 risk. The average win was about
  $19 to $24 after fees and the average loss about $47 to $48, with a win
  rate near 42%.
- **Exits** (second-half overnight): BTC 81 stops, 66 targets, 3 flat at
  09:30; ETH 79 stops, 71 targets, 5 flat.
- **The morning variant also fails here once costs are charged.** The
  TradingView result that passed the gate (BTC PF 2.63 on 14 trades, ETH PF
  4.64 on 9 trades, about one month) was run with commission 0. On this
  six-month second half the morning session at zero cost is PF 1.21 (BTC) and
  1.58 (ETH), both with max drawdown over $150; at 0.06% per side it is 0.54
  and 0.77. This is a port on Alpaca bars, not a TradingView re-run, and it is
  not a verdict on the morning variant, but it does not support wiring it.
- **Data caveats.** A large share of the bars carry zero volume (20% of BTC,
  46% of ETH), which affects VWAP. ETH's largest loss, -$469.62, is far beyond
  the $25 risk plus fees, which means a bar opened well through the stop; it
  was not checked whether that is a real move or a bad print in Alpaca's
  bars. Removing that one trade would not change the verdict.

`crypto_overnight.py` tests the BTC-ETH Day Trader v2 morning variant with
**only the session changed**: entries 00:00–09:30 New York, Monday to Friday,
flat by 09:30 (the morning variant enters 09:30–11:30 and is flat about
15:55). Every parameter is held fixed from the morning variant. Nothing is
tuned: the script has no grid. If the fixed rules fail, the verdict is FAIL
and there is no re-tuning on this data.

Rules, long only: EMA 9 crosses above EMA 21 on a 5-minute bar that also
closes above VWAP, has RSI(14) under 68 and closes above the 15-minute EMA 50;
entry at the next open; stop 1x ATR(14), floored at 0.05% of price; target
1.5x the stop distance; $25 risk, fractional size, notional capped at $25,000.

- Data: BTC/USD and ETH/USD 5-minute bars from Alpaca's crypto data API,
  12 months back by default. The actual date range and bar count per asset
  are printed by the run and go here.
- Costs: 0.06% of notional per side on every fill.
- Split: each asset's data is cut in half by calendar date. Both halves are
  reported (trades, win rate, profit factor, net P&L, max drawdown, average
  win and loss, largest loss). The second half is the confirmation.
- Pass bar per asset: second-half overnight profit factor of at least 1.2 AND
  max drawdown under $150 AND at least 10 second-half trades. PASS means a
  candidate to wire for paper; FAIL means do not paper trade that asset.
- For information only, not part of the verdict: the combined day (entries
  00:00–11:30, flat 15:55) on the second half, and the morning session
  itself as a check that this port matches the morning variant's result.

`btc-eth-day-trader-v2.pine` is the reference, copied in unchanged. The
script was checked against it line by line and matches it on: the crossover
on the signal bar with the three filters on that bar's close; the 15-minute
EMA 50 taken from the last completed 15-minute bar; entry at the next open;
stop and target measured from the signal bar's close, with
stopDist = max(1x ATR, 0.05% of close) and target = 1.5x stopDist, so the
target widens when the floor binds; size = min($25 / stopDist, $25,000 /
close); the bracket first able to fill on the bar after the entry bar;
Monday to Friday in New York time.

Where this test differs from a TradingView run of the Pine:

- **Costs.** The Pine has `commission_value=0`, so the morning result that
  passed the gate (BTC PF 2.63 on 14 trades, ETH PF 4.64 on 9 trades, about
  one month) was before costs. This test charges 0.06% per side as specified.
  The run also prints the morning session at zero cost; that row is the one
  comparable to the TradingView numbers.
- **Same-bar stop and target.** TradingView guesses the path inside the bar;
  here the stop always wins.
- **Data.** Alpaca bars and Alpaca volume for VWAP (daily reset at 00:00 UTC),
  not the TradingView chart's exchange. Alpaca omits 5-minute bars with no
  trades; the run prints how complete each series is.
- **Session inputs.** Overnight: last signal bar 09:20, last fill 09:25, flat
  at the 09:30 open. A 09:25 signal would fill at 09:30 with nothing left to
  flatten it, so it is excluded.

Reproduce (Alpaca rate-limited the keyless request on this run, so the fetch
asked for keys; they are typed at a hidden prompt and never saved):

```
python3 trading/crypto_overnight.py fetch <data_dir> 12
python3 trading/crypto_overnight.py run <data_dir>
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
