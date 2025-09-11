# main.py
import os, asyncio, logging
from dotenv import load_dotenv
import nest_asyncio
from telegram.request import HTTPXRequest
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from chatgpt_client import auto_scan_and_trade


from ibkr_client import ib_client
from chatgpt_client import OpenAi
from jobs import setup_jobs

load_dotenv()
nest_asyncio.apply()
logging.getLogger("ib_insync").setLevel(logging.ERROR)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN saknas i .env")

open_ai = OpenAi()

async def disconnect_command(update, context):
    if ib_client:
        await ib_client.disconnect_ibkr()
        await update.message.reply_text("IBKR API disconnected!")
    else:
        await update.message.reply_text("IBKR API är redan nedkopplad.")

async def main():
    # 1) IBKR
    await ib_client.connect()

    # 2) Telegram-app (med timeouts)
    request = HTTPXRequest(
        connect_timeout=20.0, read_timeout=40.0, write_timeout=40.0,
        pool_timeout=20.0, connection_pool_size=50
    )
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).request(request).build()

    # Dela resurser
    app.bot_data["ib"] = ib_client
    app.bot_data["open_ai"] = open_ai

    # Handlers
    app.add_handler(CommandHandler("dc", disconnect_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, open_ai.ai_router))

    # 3) Schemalägg jobb
    setup_jobs(app, ib_client)
    print("scheduler startad")

    # 4) Kör boten
    await app.run_polling()

    # 5) Städning
    await ib_client.disconnect_ibkr()

if __name__ == "__main__":
    asyncio.run(main())
