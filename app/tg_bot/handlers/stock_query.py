# stock_query.py
import logging

from app.core.signals import get_signal_analysis
from app.tg_bot.stock_data import get_stock_by_symbol

log_chat = logging.getLogger("chat")


async def handle_stock_query(update, context, ticker: str, llm_client):
    try:
        stock = get_stock_by_symbol(ticker)
    except Exception as e:
        log_chat.warning("Stock_info.json fel: %s", e)
        await update.message.reply_text("Kunde inte läsa Stock_info.json.")
        return

    if not stock:
        log_chat.info("[query-result] %s NOT_FOUND", ticker)
        await update.message.reply_text(f"Hittar ingen data för {ticker} i Stock_info.json.")
        return

    lc = stock.get("latestClose")
    pe = stock.get("PE")
    mc = stock.get("marketCap")
    log_chat.info("[query-result] %s OK latestClose=%s PE=%s mcap=%s", ticker, lc, pe, mc)

    try:
        analysis = get_signal_analysis(stock)
    except Exception as e:
        log_chat.warning("Signalanalys misslyckades för %s: %s", ticker, e)
        analysis = {
            "symbol": ticker,
            "signal": "Håll",
            "total_score": 0,
            "scores": {
                "fundamentals": 0,
                "financials": 0,
                "news": 0,
            },
            "details": {},
            "error": str(e),
        }

    signal = analysis["signal"]
    total_score = analysis.get("total_score", 0)
    scores = analysis.get("scores", {})

    try:
        summary = await llm_client.summarize_stock(stock)
    except Exception as e:
        log_chat.warning("LLM-summering misslyckades för %s: %s", ticker, e)
        summary = "Kunde inte skapa AI-sammanfattning just nu."

    msg = (
        f"📈 {ticker}\n"
        f"{summary}\n\n"
        f"Signal: {signal}\n"
        f"Total score: {total_score}\n"
        f"Fundamentals: {scores.get('fundamentals', 0)}\n"
        f"Financials: {scores.get('financials', 0)}\n"
        f"News: {scores.get('news', 0)}"
    )

    await update.message.reply_text(msg)