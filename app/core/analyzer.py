from app.core.scoring import (
    score_pe,
    score_eps,
    score_dividend,
    score_beta,
    score_revenue_growth,
    score_profit_margin,
    score_debt_to_equity,
    score_news,
    score_price_trend,
    score_rsi,
    score_volume_spike,
    score_volatility,
    score_momentum,
    score_liquidity,
)
from app.core.technicals import build_technical_snapshot
from app.core.filters import precheck_stock


WEIGHTS = {
    "fundamentals": 1.0,
    "financials": 1.0,
    "news": 0.5,
    "technicals": 1.5,
    "liquidity": 1.2,
}


def _weighted_int(value, weight):
    return int(round(value * weight))


def evaluate_fundamentals(stock_data):
    details = {
        "pe": score_pe(stock_data),
        "eps": score_eps(stock_data),
        "dividend": score_dividend(stock_data),
        "beta": score_beta(stock_data),
    }
    total = sum(details.values())
    return total, details


def evaluate_financials(stock_data):
    finance_data = stock_data.get("quarterlyFinance", {})

    details = {
        "revenue_growth": score_revenue_growth(finance_data),
        "profit_margin": score_profit_margin(finance_data),
        "debt_to_equity": score_debt_to_equity(finance_data),
    }
    total = sum(details.values())
    return total, details


def evaluate_news(stock_data):
    score, raw_sentiment = score_news(stock_data)
    details = {
        "news_sentiment_score": score,
        "raw_sentiment": raw_sentiment,
    }
    return score, details


def evaluate_technicals(stock_data):
    symbol = stock_data.get("symbol")
    technicals = build_technical_snapshot(symbol) if symbol else {}

    details = {
        "price_trend": score_price_trend(technicals),
        "rsi": score_rsi(technicals),
        "volume_spike": score_volume_spike(technicals),
        "volatility": score_volatility(technicals),
        "momentum": score_momentum(technicals),
    }

    total = sum(details.values())
    return total, details, technicals


def evaluate_liquidity(technicals):
    score = score_liquidity(technicals)
    details = {
        "liquidity_score": score,
        "avg_dollar_volume_20": technicals.get("avg_dollar_volume_20"),
    }
    return score, details


def analyze_stock(stock_data):
    fundamentals_score, fundamentals_details = evaluate_fundamentals(stock_data)
    financials_score, financials_details = evaluate_financials(stock_data)
    news_score, news_details = evaluate_news(stock_data)
    technicals_score, technicals_details, technicals_raw = evaluate_technicals(stock_data)
    liquidity_score, liquidity_details = evaluate_liquidity(technicals_raw)

    filter_result = precheck_stock(stock_data, technicals_raw)

    weighted_scores = {
        "fundamentals": _weighted_int(fundamentals_score, WEIGHTS["fundamentals"]),
        "financials": _weighted_int(financials_score, WEIGHTS["financials"]),
        "news": _weighted_int(news_score, WEIGHTS["news"]),
        "technicals": _weighted_int(technicals_score, WEIGHTS["technicals"]),
        "liquidity": _weighted_int(liquidity_score, WEIGHTS["liquidity"]),
    }

    total_score = sum(weighted_scores.values())

    return {
        "symbol": stock_data.get("symbol"),
        "total_score": total_score,
        "scores": weighted_scores,
        "raw_scores": {
            "fundamentals": fundamentals_score,
            "financials": financials_score,
            "news": news_score,
            "technicals": technicals_score,
            "liquidity": liquidity_score,
        },
        "details": {
            "fundamentals": fundamentals_details,
            "financials": financials_details,
            "news": news_details,
            "technicals": technicals_details,
            "liquidity": liquidity_details,
        },
        "raw_technicals": technicals_raw,
        "filters": filter_result,
    }