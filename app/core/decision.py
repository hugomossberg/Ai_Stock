#decision.py
def should_buy(analysis):
    if not analysis.get("filters", {}).get("allowed", True):
        return False

    technicals = analysis.get("details", {}).get("technicals", {})
    price_trend = technicals.get("price_trend", 0)
    momentum = technicals.get("momentum", 0)
    rsi = technicals.get("rsi", 0)

    if price_trend <= -2:
        return False

    if momentum <= -2 and rsi <= -1:
        return False

    return analysis["total_score"] >= 3