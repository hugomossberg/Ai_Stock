def should_buy(analysis):
    if not analysis.get("filters", {}).get("allowed", True):
        return False

    technicals = analysis.get("details", {}).get("technicals", {})
    price_trend = technicals.get("price_trend", 0)
    momentum = technicals.get("momentum", 0)

    # hård blockering om trend + momentum är tydligt svaga
    if price_trend <= -2 and momentum <= -1:
        return False

    return analysis["total_score"] >= 3


def should_sell(analysis):
    return analysis["total_score"] <= -3


def decide_signal(analysis):
    if should_buy(analysis):
        return "Köp"
    if should_sell(analysis):
        return "Sälj"
    return "Håll"