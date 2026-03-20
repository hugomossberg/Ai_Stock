#signals.py
from app.core.analyzer import analyze_stock
from app.core.decision import decide_signal


def get_signal_analysis(stock_data):
    analysis = analyze_stock(stock_data)
    analysis["signal"] = decide_signal(analysis)
    return analysis


def buy_or_sell(stock_data):
    analysis = get_signal_analysis(stock_data)
    return analysis["signal"]


def signal_to_side(signal):
    if signal == "Köp":
        return "BUY"
    if signal == "Sälj":
        return "SELL"
    return None

def get_signal_analysis(stock_data):
    analysis = analyze_stock(stock_data)
    analysis["signal"] = decide_signal(analysis)
    return analysis

async def execute_order(ib_client, stock, signal, qty=10, bot=None, chat_id=None):
    side = signal_to_side(signal)
    if side is None:
        return None

    trade = await ib_client.place_order(
        stock["symbol"],
        side,
        qty,
        bot=bot,
        chat_id=chat_id,
    )
    return trade