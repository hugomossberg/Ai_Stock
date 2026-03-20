#filters.py

from app.core.market_profile import PROFILE

def _safe_float(value, default=None):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.strip()
            if value.lower() in {"inf", "infinity", "nan", ""}:
                return default
        return float(value)
    except Exception:
        return default


LEVERAGED_ETF_HINTS = [
    "2x", "3x", "ultra", "ultrapro", "daily", "bull", "bear", "short", "leveraged"
]


def is_probably_leveraged_or_inverse(stock_data):
    name = (stock_data.get("name") or "").lower()
    symbol = (stock_data.get("symbol") or "").upper()

    if symbol in {"TSLL", "TSLQ", "SQQQ"}:
        return True

    return any(hint in name for hint in LEVERAGED_ETF_HINTS)


def passes_price_filter(stock_data, min_price=None):
    min_price = PROFILE["min_price"] if min_price is None else min_price
    price = _safe_float(stock_data.get("latestClose"))
    if price is None:
        return False, "saknar pris"
    if price < min_price:
        return False, f"pris under {min_price}"
    return True, None

def passes_market_cap_filter(stock_data, min_market_cap=None):
    min_market_cap = PROFILE["min_market_cap"] if min_market_cap is None else min_market_cap
    market_cap = _safe_float(stock_data.get("marketCap"))
    if market_cap is None:
        return False, "saknar market cap"
    if market_cap < min_market_cap:
        return False, f"market cap under {min_market_cap}"
    return True, None


def passes_instrument_filter(stock_data):
    if is_probably_leveraged_or_inverse(stock_data):
        return False, "leveraged/inverse ETF"
    return True, None

def passes_liquidity_filter(technicals, min_avg_cash_volume=None):
    min_avg_cash_volume = (
        PROFILE["min_avg_cash_volume"]
        if min_avg_cash_volume is None
        else min_avg_cash_volume
    )

    adv = _safe_float(
        technicals.get("avg_cash_volume_20")
        or technicals.get("avg_dollar_volume_20")
    )

    if adv is None:
        return False, "saknar avg cash volume"

    if adv < min_avg_cash_volume:
        return False, f"avg cash volume under {min_avg_cash_volume}"

    return True, None


def passes_volatility_filter(technicals, max_atr_pct=8.0):
    atr_pct = _safe_float(technicals.get("atr_pct"))
    if atr_pct is None:
        return True, None
    if atr_pct > max_atr_pct:
        return False, f"ATR% över {max_atr_pct}"
    return True, None


def precheck_stock(stock_data, technicals):
    checks = {}

    ok, reason = passes_price_filter(stock_data)
    checks["price"] = {"ok": ok, "reason": reason}

    ok2, reason2 = passes_market_cap_filter(stock_data)
    checks["market_cap"] = {"ok": ok2, "reason": reason2}

    ok3, reason3 = passes_instrument_filter(stock_data)
    checks["instrument"] = {"ok": ok3, "reason": reason3}

    ok4, reason4 = passes_liquidity_filter(technicals)
    checks["liquidity"] = {"ok": ok4, "reason": reason4}

    ok5, reason5 = passes_volatility_filter(technicals)
    checks["volatility"] = {"ok": ok5, "reason": reason5}

    allowed = all(item["ok"] for item in checks.values())

    reasons = [item["reason"] for item in checks.values() if item["reason"]]
    return {
        "allowed": allowed,
        "checks": checks,
        "reasons": reasons,
    }