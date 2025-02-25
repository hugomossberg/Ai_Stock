import re
import json
import openai
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
from helpers import send_long_message
from signals import buy_or_sell, execute_order
from ibkr_client import IbClient

load_dotenv()
API_KEY = os.getenv("CHATGPT_API")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # Chat ID där automatiserade meddelanden ska skickas

# Skapa en global IBKR-klient (återanvänds för alla order)
ib_client = IbClient()

class OpenAi:
    def __init__(self):
        self.api_key = API_KEY

    async def chat_gpt(self, user_message):
        try:
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model="gpt-4o-2024-08-06",
                messages=[
                    {"role": "system", "content": "Jag är en noggran ai som gillar detaljer"},
                    {"role": "user", "content": user_message},
                ],
            )
            return response.choices[0].message.content
        except openai.OpenAIError as e:
            print(f"OpenAI API-fel: {e}")
            return "Ett fel uppstod vid anropet till OpenAI."
        except Exception as e:
            print(f"Ett oväntat fel uppstod: {e}")
            return "Ett oväntat fel inträffade."

    async def chat_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_message = update.message.text
        response = await self.chat_gpt(user_message)
        await update.message.reply_text(response)

    async def ask_ai_stock(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        print("ask_ai_stock har anropats!")
        with open("Stock_info.json", "r", encoding="utf-8") as json_open:
            data = json.load(json_open)
        # Extrahera aktiesymbol från användarens meddelande
        match = re.search(r"\b[A-Z]{2,}\b", update.message.text)
        symbol = match.group(0) if match else update.message.text.upper()
        print(f"🔍 Extraherad symbol: {symbol}")
        print(f"📃 Alla tillgängliga symboler: {[stock['symbol'] for stock in data]}")
        found = False
        for stock in data:
            if stock["symbol"].upper() == symbol:
                found = True
                print(f"✅ Match hittad för: {stock['symbol']}")

                # 1. Skicka ut nyhetsartiklarna
                news_list = stock.get("News")
                if news_list:
                    news_text = ""
                    for news in news_list:
                        title = news["content"].get("title", "Ingen titel")
                        summary = news["content"].get("summary", "Ingen sammanfattning")
                        news_text += f"News: {title}\nSammanfattning: {summary}\n\n"
                    await send_long_message(context.bot, update.effective_chat.id, news_text)
                else:
                    await update.message.reply_text("Inga nyhetsartiklar för denna aktie.")

                # 2. Skicka ut rapportdata (kvartalsrapporter)
                report_text = (
                    f"Quarters:\n{json.dumps(stock['quarterlyFinance'], indent=2)}\n\n"
                    f"Balance:\n{json.dumps(stock['quarterlyBalance'], indent=2)}\n\n"
                    f"Cashflow:\n{json.dumps(stock['quarterlyCashflow'], indent=2)}"
                )
                await send_long_message(context.bot, update.effective_chat.id, report_text)

                # 3. Visa övriga nyckeltal
                await update.message.reply_text(f"Stock Name: {stock['name']}:")
                await update.message.reply_text(f"Latest Close: {stock['latestClose']}")
                await update.message.reply_text(f"P/E: {stock['PE']}")
                await update.message.reply_text(f"Market Cap: {stock['marketCap']}")
                await update.message.reply_text(f"Volatilitet: {stock['beta']}")
                await update.message.reply_text(f"EPS: {stock['trailingEps']}")
                await update.message.reply_text(f"Utdelning: {stock['dividendYield']}")
                await update.message.reply_text(f"Sektor: {stock.get('sector', 'okänd')}")
                # 4. Generera och visa signalen
                signal = buy_or_sell(stock)
                await update.message.reply_text(f"Signal: {signal}")
                # 5. Utför order om signalen är "Köp" eller "Sälj"
                trade = await execute_order(ib_client, stock, signal, qty=10)
                if trade is not None:
                    await update.message.reply_text(f"Order placerad: {trade}")
                else:
                    await update.message.reply_text("Ingen order placerad, signalen är 'Håll'.")
                break

        if not found:
            print(f"❌ Aktie med symbolen {symbol} hittades INTE i JSON!")
            try:
                response = await self.chat_gpt(update.message.text)
                await update.message.reply_text(response)
            except Exception as e:
                await update.message.reply_text(f"Ett fel uppstod: {str(e)}")

# Schemalagd funktion för automatisk skanning och orderplacering
async def auto_scan_and_trade(context: ContextTypes.DEFAULT_TYPE):
    with open("Stock_info.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    for stock in data:
        signal = buy_or_sell(stock)
        await context.bot.send_message(chat_id=os.getenv("ADMIN_CHAT_ID"), text=f"{stock['symbol']} - Signal: {signal}")
        trade = await execute_order(ib_client, stock, signal, qty=10)
        if trade is not None:
            await context.bot.send_message(chat_id=os.getenv("ADMIN_CHAT_ID"), text=f"{stock['symbol']} - Order placerad: {trade}")
        else:
            await context.bot.send_message(chat_id=os.getenv("ADMIN_CHAT_ID"), text=f"{stock['symbol']} - Ingen order, signal: Håll")


# Starta APScheduler för att automatisera aktieskanning var 15:e minut
