import math
from typing import Optional

import yfinance as yf


def fetch_price_history(symbol: str, period: str = "6mo", interval: str = "1d"):
    """
    Hämtar historiska candles via yfinance.
    Returnerar en pandas DataFrame eller None om tomt/fel.
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=False)
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None


def _safe_float(value, default=None):
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except Exception:
        return default


def compute_sma(series, window: int) -> Optional[float]:
    if series is None or len(series) < window:
        return None
    value = series.rolling(window=window).mean().iloc[-1]
    return _safe_float(value)


def compute_rsi(series, window: int = 14) -> Optional[float]:
    if series is None or len(series) < window + 1:
        return None

    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()

    last_gain = avg_gain.iloc[-1]
    last_loss = avg_loss.iloc[-1]

    if last_loss is None:
        return None

    last_gain = _safe_float(last_gain)
    last_loss = _safe_float(last_loss)

    if last_gain is None or last_loss is None:
        return None

    if last_loss == 0:
        return 100.0

    rs = last_gain / last_loss
    rsi = 100 - (100 / (1 + rs))
    return _safe_float(rsi)


def compute_atr(df, window: int = 14) -> Optional[float]:
    if df is None or len(df) < window + 1:
        return None

    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = tr1.combine(tr2, max).combine(tr3, max)
    atr = true_range.rolling(window=window).mean().iloc[-1]
    return _safe_float(atr)


def compute_momentum(series, lookback: int = 20) -> Optional[float]:
    if series is None or len(series) < lookback + 1:
        return None

    current = _safe_float(series.iloc[-1])
    past = _safe_float(series.iloc[-1 - lookback])

    if current is None or past is None or past == 0:
        return None

    return ((current / past) - 1.0) * 100.0


def build_technical_snapshot(symbol: str):
    """
    Returnerar technicals-dict för symbolen.
    """
    df = fetch_price_history(symbol, period="6mo", interval="1d")
    if df is None or df.empty:
        return {}

    close = df["Close"]
    volume = df["Volume"]

    price = _safe_float(close.iloc[-1])
    sma20 = compute_sma(close, 20)
    sma50 = compute_sma(close, 50)
    rsi14 = compute_rsi(close, 14)
    atr14 = compute_atr(df, 14)
    avg_volume_20 = compute_sma(volume, 20)
    momentum_20 = compute_momentum(close, 20)
    momentum_60 = compute_momentum(close, 60)

    volume_now = _safe_float(volume.iloc[-1])
    volume_ratio = None
    if volume_now is not None and avg_volume_20 not in (None, 0):
        volume_ratio = volume_now / avg_volume_20

    atr_pct = None
    if atr14 is not None and price not in (None, 0):
        atr_pct = (atr14 / price) * 100.0

    avg_dollar_volume_20 = None
    if price not in (None, 0) and avg_volume_20 not in (None, 0):
        avg_dollar_volume_20 = price * avg_volume_20

    return {
        "price": price,
        "sma20": sma20,
        "sma50": sma50,
        "rsi14": rsi14,
        "atr14": atr14,
        "atr_pct": atr_pct,
        "volume": volume_now,
        "avg_volume_20": avg_volume_20,
        "avg_dollar_volume_20": avg_dollar_volume_20,
        "volume_ratio": volume_ratio,
        "momentum_20": momentum_20,
        "momentum_60": momentum_60,
    }