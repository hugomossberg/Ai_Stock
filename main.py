# main.py
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

import logging

logging.getLogger("ib_insync").setLevel(logging.ERROR)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ib_client = None


async def disconnect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ib_client:
        await ib_client.disconnect_ibkr()
        await update.message.reply_text("IBKR API disconnected!")
    else:
        await update.message.reply_text("IBKR API är redan nedkopplad.")




async def main():
    global ib_client
    from ibkr_client import IbClient
    from chatgpt_client import OpenAi, auto_scan_and_trade
    from yfinance_stock import analyse_stock

    
 
    # Lokal import för att undvika cirkulära beroenden
    open_ai = OpenAi()
    ib_client = IbClient()
    
    await ib_client.connect()
    
    
    await analyse_stock(ib_client)



    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("dc", disconnect_command))
    app.add_handler(MessageHandler(filters.ALL, open_ai.ask_ai_stock))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, open_ai.chat_response))

    
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler()
    # Notera: Eftersom scheduler inte har en Telegram context, skickar vi ADMIN_CHAT_ID med meddelanden.
    scheduler.add_job(lambda: asyncio.create_task(auto_scan_and_trade(context=None)), 'interval', minutes=15)

    scheduler.start()
    print(f"scheduler start: {scheduler.start}")


    
    await app.run_polling()

    await ib_client.disconnect_ibkr()


if __name__ == "__main__":

    asyncio.run(main())
