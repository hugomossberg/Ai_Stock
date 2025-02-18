import json
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import yfinance as yf
from chatgpt_client import chat_gpt

load_dotenv()



TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


async def chat_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Svara på alla meddelanden med ChatGPT"""
    user_message = update.message.text  # Hämta användarens textmeddelande
    response = chat_gpt(user_message)  # Skicka till OpenAI API
    await update.message.reply_text(response)  # Skicka tillbaka svaret till chatten



async def stock_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) == 0:
        await update.message.reply_text("Använd: /stock <TICKER>")
        return

    ticker = context.args[0].upper()
    stock = yf.Ticker(ticker)

    try:
        price = stock.history(period="1d")["Close"].iloc[-1]
        await update.message.reply_text(f"Senaste pris för {ticker}: {price:.2f} USD")
    except IndexError:
        await update.message.reply_text("Kunde inte hämta data, kontrollera att du angav rätt ticker.")

    


def main():
 

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("stock", stock_price))



    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_response))
    app.run_polling()

if __name__ == "__main__":
    main()

