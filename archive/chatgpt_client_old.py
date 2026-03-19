import os, json, re, logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime
from zoneinfo import ZoneInfo

from tg_bot.handlers.stock_query import handle_stock_query
from tg_bot.handlers.tickers import send_tickers
from tg_bot.handlers.status import send_status
from tg_bot.handlers.sell import sell_all, sell_one

load_dotenv()

log_chat = logging.getLogger("chat")
log_scan = logging.getLogger("autoscan")
log_scanner = logging.getLogger("scanner")

SE_TZ = ZoneInfo("Europe/Stockholm")
US_TZ = ZoneInfo("America/New_York")

def _is_us_market_open(now_et=None) -> bool:
    now_et = now_et or datetime.now(US_TZ)
    if now_et.weekday() >= 5:
        return False
    start = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    end   = now_et.replace(hour=16, minute=0,  second=0, microsecond=0)
    return start <= now_et <= end


# ---------- LLM-klient (valfri, används för korta summeringar) ----------
class OpenAi:
    def __init__(self):
        self.api_key = os.getenv("CHATGPT_API")

    async def _chat(self, system: str, user: str) -> str:
        """
        Helt frivillig. Om du inte har CHATGPT_API satt kommer vi bara
        returnera en tom sträng så botten fungerar ändå.
        """
        if not self.api_key:
            return ""
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            r = client.chat.completions.create(
                model="gpt-4o-2024-08-06",
                messages=[{"role":"system","content":system},{"role":"user","content":user}],
            )
            return r.choices[0].message.content or ""
        except Exception:
            return ""

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
            "1–2 nyheter i lugn ton, och avsluta med neutral slutsats.\n"
            f"DATA:\n{json.dumps(payload, ensure_ascii=False)}"
        )
        txt = await self._chat("Du sammanfattar aktier kort och tydligt.", prompt)
        return txt or "(ingen summering)"

    # ---------- Telegram ROUTER ----------
    async def ai_router(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Enkel textrouter för Telegram:
        - 'status'      → portfölj + ordrar
        - 'tickers'/'t' → universum + vad som ägs
        - 'sellall'     → stänger alla öppna positioner (marknadsorder)
        - en ticker     → snabb summering + signal (t.ex. TSLA, NVDA?, sqqq)
        - annars        → kort hjälptext
        """
        text = (update.message.text or "").strip()
        low  = text.lower()

                # "ticker TSLA" eller "ticker tsla?"
        if low.startswith("ticker "):
            sym = text.split(None, 1)[1].strip().rstrip("?").upper()
            log_chat.info(f"[query] user=%s ticker=%s (via 'ticker')", update.effective_user.username, sym)
            return await handle_stock_query(update, context, sym, self)

        # gissa ticker? (minst 2 tecken för att undvika 'n'/'!' osv)
        m = re.fullmatch(r"([A-Za-z]{2,5}(?:[.\-][A-Za-z]+)?)\??", text)
        if m:
            sym = m.group(1).upper()
            log_chat.info(f"[query] user=%s ticker=%s", update.effective_user.username, sym)
            return await handle_stock_query(update, context, sym, self)

        if text in {"!", "n", "📰", "p"}:
            # TODO: koppla mot din autoscan-funktion om du vill
            return await update.message.reply_text("Premarket/nyhets-trigger är inte kopplad här ännu.")

        if low in {"status", "/status"}:
            return await send_status(update, context)

        if low in {"tickers", "/tickers", "t"}:
            return await send_tickers(update, context)

        if low in {"sellall", "/sellall"}:
            return await sell_all(update, context)

        m = re.fullmatch(r"sell\s+([A-Za-z]{1,5})\s*(\d+)?", text, re.IGNORECASE)
        if m:
            sym = m.group(1).upper()
            qty = int(m.group(2)) if m.group(2) else None
            return await sell_one(update, context, sym, qty)

        # gissa ticker? (A–Z 1–5 tecken, ev. ? i slutet)
        m = re.fullmatch(r"([A-Za-z]{1,5})(?:[.\-][A-Za-z]+)?\??", text)
        if m:
            return await handle_stock_query(update, context, m.group(1).upper(), self)

    
        # fallback
        return await update.message.reply_text(
            "Kommandon:\n"
            "• status – visa portfölj/ordrar\n"
            "• tickers (eller 't') – visa universum och ägda\n"
            "• sellall – stäng alla positioner\n"
            "• sell TICKER [antal] – sälj en position\n"
            "• TICKER – snabb koll (t.ex. TSLA, NVDA?, SQQQ)"
        )

   