#stock_query.py
import logging

from app.core.signals import buy_or_sell
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

    summary = await llm_client.summarize_stock(stock)
    signal = buy_or_sell(stock)
    msg = f"📈 {ticker}\n{summary}\n\nSignal: {signal}"
    await update.message.reply_text(msg)