# main.py
import os
import asyncio
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import nest_asyncio
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()
nest_asyncio.apply()

logging.getLogger("ib_insync").setLevel(logging.ERROR)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0") or 0)

from ibkr_client import ib_client
from chatgpt_client import OpenAi, auto_scan_and_trade
from yfinance_stock import analyse_stock

open_ai = OpenAi()

async def disconnect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ib_client:
        await ib_client.disconnect_ibkr()
        await update.message.reply_text("IBKR API disconnected!")
    else:
        await update.message.reply_text("IBKR API är redan nedkopplad.")

async def run_auto_trade(app):
    try:
        admin_chat_id = int(os.getenv("ADMIN_CHAT_ID", "0") or 0)
        await auto_scan_and_trade(
            bot=app.bot,
            ib_client=ib_client,
            admin_chat_id=admin_chat_id
        )
    except Exception as e:
        print(f"❌ Auto-trade fel: {e}")

async def main():
    await ib_client.connect()

    # Hämtar/sparar din JSON (kan kommenteras bort om du inte vill köra vid start)
    await analyse_stock(ib_client)

    # Telegram-app
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Dela instanser globalt till handlers
    app.bot_data["ib"] = ib_client
    app.bot_data["open_ai"] = open_ai

    # Handlers
    app.add_handler(CommandHandler("dc", disconnect_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, open_ai.ai_router))

    # Scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: asyncio.create_task(run_auto_trade(app)),
                      "interval", minutes=15, id="auto_trade")
    scheduler.start()
    print("scheduler startad")

    await app.run_polling()
    await ib_client.disconnect_ibkr()

if __name__ == "__main__":
    asyncio.run(main())
