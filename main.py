import json
import requests
import os
import sys
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from chatgpt_client import chat_gpt
from ibkr_client import IbClient

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Skapa en global variabel för IBKR API-klienten
ib_client = None


async def chat_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Svara på alla meddelanden med ChatGPT"""
    user_message = update.message.text
    response = chat_gpt(user_message)
    await update.message.reply_text(response)


async def disconnect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Koppla från IBKR API via Telegram"""
    if ib_client:
        ib_client.disconnect_ibkr()
        await update.message.reply_text("IBKR API disconnected!")
    else:
        await update.message.reply_text("IBKR API är redan nedkopplad.")


def main():
    global ib_client

    # Starta IBKR
    ib_client = IbClient()
    tickers = ib_client.get_stocks()
    print(tickers)

    # Starta Telegram
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_response))
    app.add_handler(CommandHandler("dc", disconnect_command))

    try:
        app.run_polling()
    finally:
        # Disconnect IBKR API om programmet stängs
        ib_client.disconnect_ibkr()


if __name__ == "__main__":
    main()
