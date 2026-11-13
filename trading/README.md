# Day-trading strategy backtests

Three rule-based 5-minute strategies tested on BTC, ETH, SPY and QQQ.

- `backtest.py` — bar-by-bar backtester and the three strategy definitions.
- `s3_fade.pine` — TradingView Pine v6 script for the top-ranked strategy.
- `fetch_alpaca.py` — downloads SPY/QQQ 5-minute bars from Alpaca, all hours (SIP feed since the CPI/FOMC test; the earlier results below were run on IEX bars).
- `walkforward.py` — out-of-sample test of the fade: tune on the first half, test on the second.
- `bullflag.py` — bull-flag continuation strategy and its walk-forward test (result below: FAIL).
- `cpi_fomc.py` — CPI/FOMC second-move strategy and its walk-forward test (result below: not enough trades to know).
- `trendline_break.py` — trendline break-and-retest strategy and its walk-forward test (below: **not yet run, no verdict**).

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

## Trendline break and retest walk-forward: NOT YET RUN (script added 2026-11-13)

**Verdict per asset: BTC, ETH, SPY, QQQ — none yet. Do not paper trade any of
them until the run below is recorded here.**

`trendline_break.py`, rules fixed before any data was loaded. The idea is from
a YouTube Short (Tori Trades, "The Trendline Break Setup"), which gives no win
rate or track record and enters on any break of a hand-drawn line. This is a
stricter mechanical version: nothing is drawn by hand or judged by eye.

Exact rules, described for a short (break of an uptrend line). A long is the
mirror image: break of a downtrend line through lower highs. Long and short
are reported separately.

- **Pivots.** A pivot low is a bar whose low is strictly below the lows of the
  K bars on each side (K=2 is the 5-bar swing). It is usable only once
  confirmed, K bars later.
- **Trendline.** When a pivot low confirms, it is paired with the most recent
  earlier confirmed pivot low at least SEP bars before it. If the newer low is
  higher and no bar since the older one has closed below the line through
  them, that is the uptrend line. Otherwise there is no uptrend line until a
  later pivot low makes one.
- **Break.** The first 5-minute close below the line. The line is then frozen
  and extended at the same slope.
- **Retest and entry.** Within WIN bars after the break bar, a bar's high must
  reach the frozen line, and that bar or a later one must close below the
  line. Entry is short at that close. No confirmation inside WIN bars: no
  trade.
- **Opposing line.** After entry it is re-drawn each time a pivot high
  confirms: through that pivot and the most recent earlier anchor at least
  SEP bars before it, if that anchor is higher. Otherwise it is left alone.
- **Exit.** The first later 5-minute close above the opposing line, filled at
  that close. SPY and QQQ are also flat at the close of the 15:55 New York bar
  (or the last bar of an early-close session). Crypto has no time stop.
- **Risk and size.** $25 divided by the distance from the entry price to the
  opposing line at entry.
- **Costs.** 0.06% per side crypto, 0.01% per side ETFs.

Ambiguities and how they were resolved:

- **The opposing line at entry.** The brief defines it through two pivots
  formed after the break, but entry comes at most WIN bars after the break,
  before two such pivots can confirm. So the first opposing line runs through
  the highest high between the trendline's second pivot and the break bar (the
  top before the break) and the highest high from the bar after the break to
  the entry bar (the retest high). The retest high must be the lower of the
  two or there is no trade. SEP does not apply to this first line; it does
  apply to every later re-draw.
- **Fills at the close.** Entry and exit fill at the signal bar's close, as
  the brief says, not at the next open as in the other tests here.
- **No hard stop.** The exit needs a close beyond the line, so a loss can be
  larger than $25. The largest loss is reported.
- **Size limits.** Notional is capped at $10,000 and a trade is skipped when
  the entry-to-line distance is under 0.05% of price, both as in the other
  tests. Without them a retest that closes just under the line would size to
  an enormous position.
- **One position per asset.** A setup that confirms while a position is open
  is dropped.
- **A new pivot that is not a higher low** removes the current uptrend line.
  A broken line is used once.
- **SPY and QQQ** use regular-session bars only. Both pivots, the break, the
  retest and the entry must be in the same session, and there is no entry on
  the 15:55 bar.
- **Crypto bars.** Alpaca omits 5-minute bars with no trades. Bar counts (K,
  SEP, WIN) are over the bars that exist.

Walk-forward: each asset's bars are cut in half by time and the halves run
separately. The 27 variants (K 2/3/5, SEP 10/20/30, WIN 5/10/20) are run on
first halves only. One variant is picked per asset class (BTC+ETH, SPY+QQQ):
best combined first-half profit factor, long and short together, with at
least 30 first-half trades. It is run once on the second halves.

Pass bar per asset: second-half profit factor of at least 1.2 AND max
drawdown under $150 AND at least 10 second-half trades, long and short
together. Anything else is FAIL: do not paper trade, no re-tuning on this
data.

Data: BTC/USD and ETH/USD from Alpaca's crypto data API, SPY and QQQ from
Alpaca's SIP feed, 5-minute bars, 12 months. The actual date ranges, bar
counts and split dates are printed by the run and go here.

Reproduce (crypto bars need no key; SPY/QQQ do):

```
export APCA_API_KEY_ID=...  APCA_API_SECRET_KEY=...   # from your shell, never committed
python3 trading/trendline_break.py fetch <data_dir> 12
python3 trading/fetch_alpaca.py <data_dir> 12
python3 trading/trendline_break.py <data_dir>
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
