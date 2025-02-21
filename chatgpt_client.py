import re
import json
import openai
import os
from dotenv import load_dotenv
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

API_KEY = os.getenv("CHATGPT_API")


async def chat_gpt(user_message):
    try:
        client = openai.OpenAI(api_key=API_KEY)  # Ange API-nyckeln här

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "Jag är en noggran ai som gillar detaljer",
                },
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content  # Returnera GPT-svaret

    except openai.OpenAIError as e:
        print(f"OpenAI API-fel: {e}")
        return "Ett fel uppstod vid anropet till OpenAI."
    except Exception as e:
        print(f"Ett oväntat fel uppstod: {e}")
        return "Ett oväntat fel inträffade."


async def chat_response(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:  # se till att den importen finns
    user_message = update.message.text
    response = await chat_gpt(user_message)
    await update.message.reply_text(response)


async def ask_ai_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        response = await chat_gpt(update.message.text)
        await update.message.reply_text(response)
        await update.message.reply_text(f"ChatGPT-svar: {response}")
        return
    except Exception as e:
        await update.message.reply_text(f"Ett fel uppstod: {str(e)}")
        return
