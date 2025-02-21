# main.py
import os
import json
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
from yfinance_stock import analyse_stock

import nest_asyncio

load_dotenv()
nest_asyncio.apply()

import logging

logging.getLogger("ib_insync").setLevel(logging.ERROR)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ib_client = None


async def chat_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from chatgpt_client import chat_gpt  # se till att den importen finns

    user_message = update.message.text
    response = chat_gpt(user_message)
    await update.message.reply_text(response)


import re


async def ask_ai_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from chatgpt_client import chat_gpt

    json_open = open("Stock_info.json")
    data = json.load(json_open)

    # Försök extrahera ett ord med endast stora bokstäver
    match = re.search(r"\b[A-Z]{2,}\b", update.message.text)
    if match:
        symbol = match.group(0)
    else:
        symbol = update.message.text.upper()

    for stock in data:
        if stock["symbol"] == symbol:
            await update.message.reply_text(f"Aktieinfo för {stock['name']}:")
            await update.message.reply_text(f"Latest Close: {stock['latestClose']}")
            print("Kollar symbol:", stock["symbol"])
            if stock["symbol"] == update.message.text.upper():
                print("Match hittad för:", stock["symbol"])
                ...
            return

    await update.message.reply_text("Aktie med symbolen: " + symbol + " hittades inte.")
    try:
        response = chat_gpt(update.message.text)
        await update.message.reply_text(response)
        await update.message.reply_text(f"ChatGPT-svar: {response}")
        return
    except Exception as e:
        await update.message.reply_text(f"Ett fel uppstod: {str(e)}")
        return


async def disconnect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ib_client:
        await ib_client.disconnect_ibkr()
        await update.message.reply_text("IBKR API disconnected!")
    else:
        await update.message.reply_text("IBKR API är redan nedkopplad.")


async def main():
    global ib_client
    from ibkr_client import IbClient  # Lokal import för att undvika cirkulära beroenden

    ib_client = IbClient()
    await ib_client.connect()

    # Skicka in den redan anslutna IbClient-instansen
    await analyse_stock(ib_client)
    # Du kan bearbeta analyzed_stocks vidare om du vill

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_response))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ask_ai_stock))
    app.add_handler(CommandHandler("dc", disconnect_command))

    await app.run_polling()
    await ib_client.disconnect_ibkr()


if __name__ == "__main__":

    asyncio.run(main())
