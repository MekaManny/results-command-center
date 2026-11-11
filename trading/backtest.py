"""Bar-by-bar backtest of three rule-based 5-minute day-trading strategies.

Usage: python3 trading/backtest.py <data_dir>

<data_dir> must hold Binance monthly 5m kline zips (BTCUSDT-YYYY-MM.zip,
ETHUSDT-YYYY-MM.zip, from data.binance.vision) and Yahoo chart JSON
(SPY.json, QQQ.json, interval=5m&range=60d).

Execution model (deliberately conservative):
  * signals are evaluated on the close of a bar, fills happen at the next open
  * stop and target are resting orders; if both are inside one bar, the stop wins
  * a gap through the stop fills at the open, not at the stop price
  * costs are charged per side on notional: crypto 0.06%, ETFs 0.01%
  * fixed $25 risk per trade, notional capped at 4x a $2,500 account
"""
import glob
import json
import sys
import zipfile

import numpy as np
import pandas as pd

ACCOUNT = 2500.0
RISK = 25.0
MAX_NOTIONAL = 4 * ACCOUNT
COST = {"BTC": 0.0006, "ETH": 0.0006, "SPY": 0.0001, "QQQ": 0.0001}
NY = "America/New_York"


# ---------- data ----------
def load_crypto(data_dir, sym):
    frames = []
    for path in sorted(glob.glob(f"{data_dir}/{sym}USDT-*.zip")):
        with zipfile.ZipFile(path) as z:
            frames.append(pd.read_csv(z.open(z.namelist()[0]), header=None, usecols=range(6)))
    df = pd.concat(frames)
    df.columns = ["t", "open", "high", "low", "close", "volume"]
    unit = "us" if df["t"].iloc[0] > 1e14 else "ms"
    df.index = pd.to_datetime(df["t"], unit=unit, utc=True).dt.tz_convert(NY)
    return df.drop(columns="t").sort_index()


def load_etf(data_dir, sym):
    r = json.load(open(f"{data_dir}/{sym}.json"))["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({k: q[k] for k in ["open", "high", "low", "close", "volume"]})
    df.index = pd.to_datetime(r["timestamp"], unit="s", utc=True).tz_convert(NY)
    df = df.dropna()
    mins = df.index.hour * 60 + df.index.minute
    return df[(mins >= 570) & (mins < 960)]  # regular session only


# ---------- indicators (same maths as Pine ta.*) ----------
def rma(x, n):
    return x.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def ema(x, n):
    return x.ewm(span=n, adjust=False, min_periods=n).mean()


def atr(df, n=14):
    pc = df.close.shift()
    tr = pd.concat([df.high - df.low, (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    return rma(tr, n)


def adx(df, n=14):
    up, dn = df.high.diff(), -df.low.diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), df.index)
    a = atr(df, n)
    pdi, mdi = 100 * rma(plus, n) / a, 100 * rma(minus, n) / a
    return rma(100 * (pdi - mdi).abs() / (pdi + mdi), n)


def rsi(x, n):
    d = x.diff()
    return 100 - 100 / (1 + rma(d.clip(lower=0), n) / rma(-d.clip(upper=0), n))


def session_vwap(df, day):
    pv = (df[["high", "low", "close"]].mean(axis=1) * df.volume).groupby(day).cumsum()
    return pv / df.volume.groupby(day).cumsum()


# ---------- strategies: each returns dir, stop price, target (R multiple or price), flat ----------
def prep(df):
    idx = df.index
    mins = pd.Series(idx.hour * 60 + idx.minute, idx)
    day = pd.Series(idx.date, idx)
    return mins, day


def strat_orb(df, p):
    """Opening-range breakout of the 09:30-10:00 New York range."""
    mins, day = prep(df)
    in_or = (mins >= 570) & (mins < 570 + p["or_min"])
    orh = df.high.where(in_or).groupby(day).transform("max")
    orl = df.low.where(in_or).groupby(day).transform("min")
    width = (orh - orl) / orl
    window = (mins >= 570 + p["or_min"]) & (mins < 720)
    ok = window & (width >= p["min_w"]) & (width <= p["max_w"])
    long_ = ok & (df.close > orh) & (df.close.shift() <= orh)
    short = ok & (df.close < orl) & (df.close.shift() >= orl)
    d = np.where(long_, 1, np.where(short, -1, 0))
    mid = (orh + orl) / 2
    stop = mid
    return d, stop.values, np.full(len(df), p["tgt_r"]), None, (mins >= 955).values, 1


def strat_trend(df, p):
    """VWAP + EMA trend pullback."""
    mins, day = prep(df)
    e9, e21, a, dx = ema(df.close, 9), ema(df.close, 21), atr(df), adx(df)
    vw = session_vwap(df, day)
    window = (mins >= 600) & (mins < 900)
    strong = dx >= p["adx"]
    long_ = window & strong & (df.close > vw) & (e9 > e21) & (df.low <= e21) & (df.close > e9) & (df.close > df.open)
    short = window & strong & (df.close < vw) & (e9 < e21) & (df.high >= e21) & (df.close < e9) & (df.close < df.open)
    d = np.where(long_, 1, np.where(short, -1, 0))
    stop = np.where(d > 0, df.close - p["stop_atr"] * a, df.close + p["stop_atr"] * a)
    return d, stop, np.full(len(df), p["tgt_r"]), None, (mins >= 955).values, 2


def strat_fade(df, p):
    """Bollinger/RSI(2) fade back to the 20-bar mean in non-trending tape."""
    mins, day = prep(df)
    a, dx, r2 = atr(df), adx(df), rsi(df.close, 2)
    mid = df.close.rolling(20).mean()
    sd = df.close.rolling(20).std(ddof=0)
    window = (mins >= 600) & (mins < 930)
    quiet = dx < p["adx"]
    long_ = window & quiet & (df.close < mid - p["bb"] * sd) & (r2 < 10)
    short = window & quiet & (df.close > mid + p["bb"] * sd) & (r2 > 90)
    d = np.where(long_, 1, np.where(short, -1, 0))
    stop = np.where(d > 0, df.close - p["stop_atr"] * a, df.close + p["stop_atr"] * a)
    return d, stop, None, mid.values, (mins >= 955).values, 3


# ---------- engine ----------
def run(df, sym, strat, p, max_hold=None):
    d, stop_a, tgt_r, tgt_px, flat, max_per_day = strat(df, p)
    o, h, l, c = (df[k].values for k in ["open", "high", "low", "close"])
    days = df.index.date
    cost = COST[sym]
    trades, pos, n_today, cur_day = [], 0, 0, None
    for i in range(1, len(df)):
        if days[i] != cur_day:
            cur_day, n_today = days[i], 0
        if pos == 0 and d[i - 1] != 0 and not flat[i - 1] and not flat[i] and n_today < max_per_day \
                and days[i - 1] == days[i]:
            entry, stop = o[i], stop_a[i - 1]
            dist = (entry - stop) * d[i - 1]
            if not np.isfinite(dist) or dist < entry * 0.0005:
                continue
            tgt = entry + d[i - 1] * tgt_r[i - 1] * dist if tgt_px is None else tgt_px[i - 1]
            if (tgt - entry) * d[i - 1] < 0.5 * dist:
                continue
            qty = min(RISK / dist, MAX_NOTIONAL / entry)
            pos, t_in, n_today = d[i - 1], i, n_today + 1
        if pos != 0:
            exit_px = None
            if pos > 0:
                if l[i] <= stop:
                    exit_px = min(stop, o[i])
                elif h[i] >= tgt:
                    exit_px = max(tgt, o[i]) if i > t_in else tgt
            else:
                if h[i] >= stop:
                    exit_px = max(stop, o[i])
                elif l[i] <= tgt:
                    exit_px = min(tgt, o[i]) if i > t_in else tgt
            if exit_px is None and (flat[i] or (max_hold and i - t_in >= max_hold)):
                exit_px = c[i]
            if exit_px is not None:
                pnl = pos * (exit_px - entry) * qty - cost * qty * (entry + exit_px)
                trades.append((df.index[i], sym, pnl))
                pos = 0
    return pd.DataFrame(trades, columns=["time", "sym", "pnl"])


def stats(tr, months):
    if len(tr) == 0:
        return dict(trades=0)
    tr = tr.sort_values("time")
    eq = tr.pnl.cumsum()
    dd = (eq.cummax().clip(lower=0) - eq).max()
    wins, losses = tr.pnl[tr.pnl > 0].sum(), -tr.pnl[tr.pnl <= 0].sum()
    monthly = tr.pnl.sum() / months
    return dict(trades=len(tr), win_rate=round(100 * (tr.pnl > 0).mean(), 1),
                profit_factor=round(wins / losses, 2) if losses else float("inf"),
                net=round(tr.pnl.sum()), max_dd=round(dd), max_dd_pct=round(100 * dd / ACCOUNT, 1),
                monthly_usd=round(monthly), monthly_pct=round(100 * monthly / ACCOUNT, 1),
                ret_over_dd=round(tr.pnl.sum() / dd, 2) if dd else float("inf"))


STRATS = {
    "S1 ORB": (strat_orb, dict(or_min=30, min_w=0.002, max_w=0.02, tgt_r=2.0), None),
    "S2 Trend pullback": (strat_trend, dict(adx=25, stop_atr=1.5, tgt_r=2.0), None),
    "S3 Mean-reversion fade": (strat_fade, dict(adx=20, bb=2.0, stop_atr=1.5), 12),
    # Picked from 12 variants on the same 60 days of ETF data: in-sample, treat as optimistic.
    "S3b Fade, tuned for SPY/QQQ": (strat_fade, dict(adx=25, bb=2.0, stop_atr=2.5), 12),
}

if __name__ == "__main__":
    data_dir = sys.argv[1]
    data = {"BTC": load_crypto(data_dir, "BTC"), "ETH": load_crypto(data_dir, "ETH"),
            "SPY": load_etf(data_dir, "SPY"), "QQQ": load_etf(data_dir, "QQQ")}
    for s, df in data.items():
        print(f"{s}: {len(df)} bars {df.index[0]} -> {df.index[-1]}")
    split = data["BTC"].index[len(data["BTC"]) // 2]
    pd.set_option("display.width", 250)
    for name, (fn, p, hold) in STRATS.items():
        rows = {}
        res = {s: run(df, s, fn, p, hold) for s, df in data.items()}
        for s in ["BTC", "ETH"]:
            rows[f"{s} 12m"] = stats(res[s], 12)
            rows[f"{s} first 6m"] = stats(res[s][res[s].time < split], 6)
            rows[f"{s} last 6m"] = stats(res[s][res[s].time >= split], 6)
        for s in ["SPY", "QQQ"]:
            months = (data[s].index[-1] - data[s].index[0]).days / 30.4
            rows[f"{s} {months:.1f}m"] = stats(res[s], months)
        rows["BTC+ETH 12m"] = stats(pd.concat([res["BTC"], res["ETH"]]), 12)
        rows[f"SPY+QQQ {months:.1f}m"] = stats(pd.concat([res["SPY"], res["QQQ"]]), months)
        print(f"\n=== {name} {p} ===")
        print(pd.DataFrame(rows).T.to_string())
