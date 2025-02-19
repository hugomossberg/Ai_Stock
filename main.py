import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import nest_asyncio

load_dotenv()

nest_asyncio.apply()

from chatgpt_client import chat_gpt
from ibkr_client import IbClient


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ib_client = None


async def chat_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Svara på alla meddelanden med ChatGPT."""
    user_message = update.message.text
    response = chat_gpt(user_message)
    await update.message.reply_text(response)


async def ask_ai_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fråga om aktiens data via IBKR API."""
    user_message = update.message.text  # Hämta texten från användarens meddelande
    if user_message:
        await update.message.reply_text(f"Hämtar aktier med ticker {user_message}...")
        tickers = await ib_client.get_stocks([user_message])
        if tickers:
            await update.message.reply_text(
                f"Hämtade {len(tickers)} aktier: {', '.join(tickers)}"
            )
        else:
            await update.message.reply_text("Inga aktier hittades.")


async def disconnect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Koppla från IBKR API via Telegram."""
    if ib_client:
        ib_client.disconnect_ibkr()
        await update.message.reply_text("IBKR API disconnected!")
    else:
        await update.message.reply_text("IBKR API är redan nedkopplad.")


async def main():
    global ib_client
    ib_client = IbClient()
    await ib_client.connect()  # Använd den asynkrona anslutningsmetoden
    tickers = await ib_client.get_stocks()
    ib_client.scanner_parameters()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_response))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, ask_ai_stock)
    )  # fråga om aktier till ai
    app.add_handler(CommandHandler("dc", disconnect_command))

    await app.run_polling()  # Startar Telegram-boten

    ib_client.disconnect_ibkr()


if __name__ == "__main__":
    asyncio.run(main())
