# chatgpt_client.py
import os, json, re
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes
from signals import buy_or_sell, execute_order

load_dotenv()

# ---------------- Router prompt ----------------
ROUTER_SYS = (
    "Du är en strikt router. Läs användarens meddelande och svara ENBART med JSON.\n"
    'Format: {"intent":"stock_query|trade_intent|smalltalk|other","ticker":null|"TICKER","qty":null|int,"side":null|"BUY"|"SELL"}\n'
    "• Om meddelandet frågar om en aktie (pris/nyheter/analys) → intent=stock_query, försök hitta en ticker (t.ex. DQ).\n"
    "• Om meddelandet är en order (köp/sälj X av en ticker) → intent=trade_intent, fyll i ticker, qty, side.\n"
    "• Om det är vanlig konversation → intent=smalltalk.\n"
    "• Annars → intent=other.\n"
    "Svara alltid som giltig JSON. Inga extra ord."
)

class OpenAi:
    def __init__(self):
        self.api_key = os.getenv("CHATGPT_API")

    async def _chat(self, system: str, user: str) -> str:
        import openai
        client = openai.OpenAI(api_key=self.api_key)
        r = client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
        )
        return r.choices[0].message.content

    async def _summarize_stock(self, stock: dict) -> str:
        payload = {
            "symbol": stock.get("symbol"),
            "name": stock.get("name"),
            "latestClose": stock.get("latestClose"),
            "PE": stock.get("PE"),
            "marketCap": stock.get("marketCap"),
            "beta": stock.get("beta"),
            "eps": stock.get("trailingEps"),
            "dividendYield": stock.get("dividendYield"),
            "sector": stock.get("sector"),
            "news": [
                {
                    "title": (n.get("content",{}) or {}).get("title",""),
                    "summary": (n.get("content",{}) or {}).get("summary",""),
                }
                for n in (stock.get("News") or [])[:2]
            ],
        }
        prompt = (
            "Svara kort (max 6 meningar) på svenska: pris, P/E, mcap, risk (beta), "
            "1–2 nyheter i lugn ton, och avsluta med neutral slutsats (ej rådgivning).\n"
            f"DATA:\n{json.dumps(payload, ensure_ascii=False)}"
        )
        return await self._chat("Du sammanfattar aktier kort och tydligt.", prompt)

    async def ai_router(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (update.message.text or "").strip()

        # 1) Låt AI:n tala om vad användaren vill
        try:
            raw = await self._chat(ROUTER_SYS, text)
            parsed = json.loads(raw)
        except Exception:
            parsed = {"intent":"smalltalk","ticker":None,"qty":None,"side":None}

        intent = parsed.get("intent")
        ticker = parsed.get("ticker")
        qty    = parsed.get("qty")
        side   = parsed.get("side")

        # 2) Läs in cache om det behövs
        stocks_by_symbol = {}
        if intent in ("stock_query","trade_intent"):
            try:
                with open("Stock_info.json","r",encoding="utf-8") as f:
                    data = json.load(f)
                stocks_by_symbol = {s["symbol"].upper(): s for s in data}
            except Exception:
                await update.message.reply_text("Kunde inte läsa Stock_info.json.")
                return

        # 3) Intent-grenar
        if intent == "stock_query":
            if not ticker:
                await update.message.reply_text("Vilken ticker menar du?")
            else:
                stock = stocks_by_symbol.get(ticker.upper())
                if not stock:
                    await update.message.reply_text(f"Hittar ingen data för {ticker}.")
                else:
                    summary = await self._summarize_stock(stock)
                    await update.message.reply_text(summary)
                    signal = buy_or_sell(stock)  # din regelbaserade signal
                    await update.message.reply_text(f"Signal: {signal}")
            return

        if intent == "trade_intent":
            # Säkerhetsräcken
            if not (ticker and isinstance(qty, int) and side in ("BUY","SELL")):
                await update.message.reply_text("Specificera t.ex. 'Köp 10 DQ' eller 'Sälj 5 DUO'.")
                return
            stock = stocks_by_symbol.get(ticker.upper())
            if not stock:
                await update.message.reply_text(f"Hittar ingen data för {ticker}.")
                return

            ib = context.application.bot_data.get("ib")
            if not ib or not ib.ib.isConnected():
                await update.message.reply_text("⚠️ IBKR inte ansluten – ingen order lagd.")
                return

            # OBS: lägg gärna till bekräftelseflöde innan livehandel!
            trade = await execute_order(ib, stock, "Köp" if side=="BUY" else "Sälj", qty)
            await update.message.reply_text(f"Order skickad: {trade}")
            return

        if intent == "smalltalk":
            reply = await self._chat("Du svarar hjälpsamt och kort på svenska.", text)
            await update.message.reply_text(reply)
            return

        # fallback
        reply = await self._chat("Svara kort på svenska.", text)
        await update.message.reply_text(reply)


# --------- Auto-scan för schemaläggaren (anropar din signal + ev order) ----------
async def auto_scan_and_trade(bot, ib_client, admin_chat_id: int):
    try:
        with open("Stock_info.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        for stock in data:
            signal = buy_or_sell(stock)
            if admin_chat_id:
                await bot.send_message(chat_id=admin_chat_id, text=f"{stock['symbol']} - Signal: {signal}")
            if not ib_client or not ib_client.ib.isConnected():
                if admin_chat_id:
                    await bot.send_message(chat_id=admin_chat_id, text="⚠️ IBKR inte ansluten – hoppar över order.")
                continue
            trade = await execute_order(ib_client, stock, signal, qty=10)
            if trade is not None and admin_chat_id:
                await bot.send_message(chat_id=admin_chat_id, text=f"{stock['symbol']} - Order placerad: {trade}")
            elif admin_chat_id:
                await bot.send_message(chat_id=admin_chat_id, text=f"{stock['symbol']} - Ingen order, signal: Håll")
    except Exception as e:
        if admin_chat_id:
            await bot.send_message(chat_id=admin_chat_id, text=f"❌ auto_scan_and_trade fel: {e}")
