import re
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.tg_bot.handlers.stock_query import handle_stock_query
from app.tg_bot.handlers.tickers import send_tickers
from app.tg_bot.handlers.status import send_status
from app.tg_bot.handlers.sell import sell_all, sell_one

log_chat = logging.getLogger("chat")


class TelegramRouter:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (update.message.text or "").strip()
        low = text.lower()

        if low.startswith("ticker "):
            sym = text.split(None, 1)[1].strip().rstrip("?").upper()
            log_chat.info("[query] user=%s ticker=%s (via 'ticker')", update.effective_user.username, sym)
            return await handle_stock_query(update, context, sym, self.llm_client)

        m = re.fullmatch(r"([A-Za-z]{2,5}(?:[.\-][A-Za-z]+)?)\??", text)
        if m:
            sym = m.group(1).upper()
            log_chat.info("[query] user=%s ticker=%s", update.effective_user.username, sym)
            return await handle_stock_query(update, context, sym, self.llm_client)

        if text in {"!", "n", "📰", "p"}:
            return await update.message.reply_text("Premarket/nyhets-trigger är inte kopplad här ännu.")

        if low in {"status", "/status"}:
            return await send_status(update, context)

        if low in {"tickers", "/tickers", "t"}:
            return await send_tickers(update, context)

        if low in {"sellall", "/sellall"}:
            return await sell_all(update, context)

        m = re.fullmatch(r"sell\s+([A-Za-z]{1,5})\s*(\d+)?", text, re.IGNORECASE)
        if m:
            sym = m.group(1).upper()
            qty = int(m.group(2)) if m.group(2) else None
            return await sell_one(update, context, sym, qty)

        m = re.fullmatch(r"([A-Za-z]{1,5})(?:[.\-][A-Za-z]+)?\??", text)
        if m:
            return await handle_stock_query(update, context, m.group(1).upper(), self.llm_client)

        return await update.message.reply_text(
            "Kommandon:\n"
            "• status – visa portfölj/ordrar\n"
            "• tickers (eller 't') – visa universum och ägda\n"
            "• sellall – stäng alla positioner\n"
            "• sell TICKER [antal] – sälj en position\n"
            "• TICKER – snabb koll (t.ex. TSLA, NVDA?, SQQQ)"
        )