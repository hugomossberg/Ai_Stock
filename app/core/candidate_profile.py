from app.core.scoring import _safe_float


def _flag(flags: list[str], value: str):
    if value and value not in flags:
        flags.append(value)


def _quality_from_score(candidate_score: int, risk_flags: list[str], positive_flags: list[str]) -> str:
    risk_penalty = len(risk_flags)
    positive_bonus = len(positive_flags)

    adjusted = candidate_score + positive_bonus - risk_penalty

    if adjusted >= 8:
        return "A"
    if adjusted >= 4:
        return "B"
    if adjusted >= 1:
        return "C"
    return "D"


def _detect_setup_type(technicals: dict, stage1_details: dict, stage2_details: dict) -> str:
    price_trend = int(stage1_details.get("price_trend", 0) or 0)
    momentum = int(stage1_details.get("momentum", 0) or 0)
    rsi_score = int(stage1_details.get("rsi", 0) or 0)

    price = _safe_float(technicals.get("price"))
    sma20 = _safe_float(technicals.get("sma20"))
    sma50 = _safe_float(technicals.get("sma50"))
    rsi14 = _safe_float(technicals.get("rsi14"))

    revenue_growth = int(stage2_details.get("revenue_growth", 0) or 0)
    profit_margin = int(stage2_details.get("profit_margin", 0) or 0)

    # Stark trend upp
    if price is not None and sma20 is not None and sma50 is not None:
        if price > sma20 > sma50 and momentum >= 1:
            if rsi14 is not None and rsi14 >= 52:
                return "trend_continuation"

    # Tidigt breakout-läge
    if price_trend >= 1 and momentum >= 1:
        return "early_breakout"

    # Översåld rebound
    if rsi14 is not None and rsi14 < 35 and momentum >= -1:
        return "oversold_rebound"

    # Tydligt svagt
    if price_trend <= -1 and momentum <= -1:
        return "weak_breakdown"

    # Bra fundamentals men neutral tekniskt
    if revenue_growth >= 1 or profit_margin >= 1 or rsi_score == 0:
        return "range_neutral"

    return "low_quality_noise"


def build_candidate_profile(
    stock: dict,
    technicals: dict,
    candidate_score: int,
    stage1_details: dict,
    stage2_details: dict,
    stage3_details: dict,
) -> dict:
    stock = stock or {}
    technicals = technicals or {}
    stage1_details = stage1_details or {}
    stage2_details = stage2_details or {}
    stage3_details = stage3_details or {}

    positive_flags: list[str] = []
    risk_flags: list[str] = []

    price = _safe_float(technicals.get("price"))
    sma20 = _safe_float(technicals.get("sma20"))
    sma50 = _safe_float(technicals.get("sma50"))
    rsi14 = _safe_float(technicals.get("rsi14"))
    atr_pct = _safe_float(technicals.get("atr_pct"))
    volume_ratio = _safe_float(technicals.get("volume_ratio"))
    avg_dollar_volume_20 = _safe_float(technicals.get("avg_dollar_volume_20"))
    momentum_20 = _safe_float(technicals.get("momentum_20"))
    momentum_60 = _safe_float(technicals.get("momentum_60"))

    revenue_growth = int(stage2_details.get("revenue_growth", 0) or 0)
    profit_margin = int(stage2_details.get("profit_margin", 0) or 0)
    debt_to_equity = int(stage2_details.get("debt_to_equity", 0) or 0)

    news_sentiment_score = int(stage3_details.get("news_sentiment_score", 0) or 0)
    raw_sentiment = _safe_float(stage3_details.get("raw_sentiment"), 0.0) or 0.0

    # -------- Positiva flaggor --------
    if price is not None and sma20 is not None and sma50 is not None and price > sma20 > sma50:
        _flag(positive_flags, "strong_trend")
        _flag(positive_flags, "price_above_sma_stack")

    if rsi14 is not None and 50 <= rsi14 <= 70:
        _flag(positive_flags, "good_rsi_zone")

    if volume_ratio is not None and volume_ratio >= 1.3:
        _flag(positive_flags, "volume_confirmation")

    if momentum_20 is not None and momentum_20 > 5:
        _flag(positive_flags, "strong_momentum")

    if momentum_60 is not None and momentum_60 > 10:
        _flag(positive_flags, "strong_medium_term_momentum")

    if avg_dollar_volume_20 is not None and avg_dollar_volume_20 >= 15_000_000:
        _flag(positive_flags, "healthy_liquidity")

    if revenue_growth >= 1 or profit_margin >= 1 or debt_to_equity >= 1:
        _flag(positive_flags, "good_financials")

    if news_sentiment_score > 0 or raw_sentiment > 0.10:
        _flag(positive_flags, "positive_news")

    # -------- Risk flaggor --------
    missing_core = any(
        technicals.get(key) is None
        for key in ("price", "sma20", "sma50", "rsi14")
    )
    if missing_core:
        _flag(risk_flags, "missing_data")

    if rsi14 is not None and rsi14 > 78:
        _flag(risk_flags, "extended_rsi")
        _flag(risk_flags, "overstretched")

    if rsi14 is not None and rsi14 < 28:
        _flag(risk_flags, "oversold")

    if atr_pct is not None and atr_pct > 6:
        _flag(risk_flags, "high_volatility")

    if avg_dollar_volume_20 is not None and avg_dollar_volume_20 < 5_000_000:
        _flag(risk_flags, "thin_liquidity")

    if price is not None and sma20 is not None and sma50 is not None:
        if price < sma20 and sma20 < sma50:
            _flag(risk_flags, "price_below_trend")

    if revenue_growth < 0 or profit_margin < 0 or debt_to_equity < 0:
        _flag(risk_flags, "weak_financials")

    if news_sentiment_score < 0 or raw_sentiment < -0.10:
        _flag(risk_flags, "negative_news")

    setup_type = _detect_setup_type(technicals, stage1_details, stage2_details)
    candidate_quality = _quality_from_score(candidate_score, risk_flags, positive_flags)

    # -------- Retention score --------
    retention_score = int(candidate_score)

    if candidate_quality == "A":
        retention_score += 3
    elif candidate_quality == "B":
        retention_score += 1
    elif candidate_quality == "D":
        retention_score -= 2

    retention_score += len(positive_flags)
    retention_score -= len(risk_flags)

    # Bonus för trend
    if "strong_trend" in positive_flags:
        retention_score += 2

    # Straff för stora problem
    if "missing_data" in risk_flags:
        retention_score -= 2
    if "price_below_trend" in risk_flags:
        retention_score -= 2
    if "thin_liquidity" in risk_flags:
        retention_score -= 2

    # -------- Replacement score --------
    replacement_score = retention_score

    # Favorisera nya riktigt bra kandidater
    if setup_type in {"trend_continuation", "early_breakout"}:
        replacement_score += 2

    if "volume_confirmation" in positive_flags:
        replacement_score += 1

    if "overstretched" in risk_flags:
        replacement_score -= 1

    return {
        "candidate_quality": candidate_quality,
        "setup_type": setup_type,
        "positive_flags": positive_flags,
        "risk_flags": risk_flags,
        "retention_score": retention_score,
        "replacement_score": replacement_score,
    }