# chatgpt_client.py
import os, json, re
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes
from signals import buy_or_sell, execute_order

# NYTT: tider för status
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

load_dotenv()

ALLOW_SHORTS = os.getenv("ALLOW_SHORTS", "0").lower() in {"1","true","yes","on"}


STATE_PATH = os.getenv("STATE_PATH", "trade_state.json")

ONLY_TRADE_ON_SIGNAL_CHANGE = os.getenv("ONLY_TRADE_ON_SIGNAL_CHANGE","1").lower() in {"1","true","yes","on"}
COOLDOWN_MIN = int(os.getenv("COOLDOWN_MIN","30"))
MAX_POS_PER_SYMBOL = int(os.getenv("MAX_POS_PER_SYMBOL","0"))
MAX_BUYS_PER_DAY = int(os.getenv("MAX_BUYS_PER_DAY","1"))
MAX_SELLS_PER_DAY = int(os.getenv("MAX_SELLS_PER_DAY","2"))

def _load_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_state(state: dict):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass



# ---------------- Router prompt ----------------
ROUTER_SYS = (
    "Du är en strikt router. Läs användarens meddelande och svara ENBART med JSON.\n"
    'Format: {"intent":"stock_query|trade_intent|status|smalltalk|other",".tic":null|"TICKER","qty":null|int,"side":null|"BUY"|"SELL"}\n'
    "• Om meddelandet frågar om en aktie (pris/nyheter/analys) → intent=stock_query, försök hitta en ticker (t.ex. DQ).\n"
    "• Om meddelandet är en order (köp/sälj X av en ticker) → intent=trade_intent, fyll i ticker, qty, side.\n"
    "• Om det gäller status/koll (t.ex. 'status', 'läge', 'hur går det') → intent=status.\n"
    "• Om det är vanlig konversation → intent=smalltalk.\n"
    "• Annars → intent=other.\n"
    "Svara alltid som giltig JSON. Inga extra ord."
)

# --- Tidszoner för status ---
SE_TZ = ZoneInfo("Europe/Stockholm")
US_TZ = ZoneInfo("America/New_York")

def _is_us_market_open(now_et: datetime | None = None) -> bool:
    """
    Grov check för ordinarie RTH (NYSE/Nasdaq): Mån–Fre 09:30–16:00 ET.
    Helgdagar ignoreras i denna minimala version.
    """
    now_et = now_et or datetime.now(US_TZ)
    if now_et.weekday() >= 5:  # 5=lör, 6=sön
        return False
    start = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    end   = now_et.replace(hour=16, minute=0,  second=0, microsecond=0)
    return start <= now_et <= end


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
            "1–2 nyheter i lugn ton, och avsluta med neutral slutsats.\n"
            f"DATA:\n{json.dumps(payload, ensure_ascii=False)}"
        )
        return await self._chat("Du sammanfattar aktier kort och tydligt.", prompt)
    
    async def _handle_stock_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE, ticker: str):
        # Läs cache
        try:
            with open("Stock_info.json","r",encoding="utf-8") as f:
                data = json.load(f)
            stocks_by_symbol = {s["symbol"].upper(): s for s in data}
        except Exception:
            await update.message.reply_text("Kunde inte läsa Stock_info.json.")
            return

        stock = stocks_by_symbol.get(ticker.upper())
        if not stock:
            await update.message.reply_text(f"Hittar ingen data för {ticker} i Stock_info.json.")
            return

        summary = await self._summarize_stock(stock)
        await update.message.reply_text(summary)
        signal = buy_or_sell(stock)
        await update.message.reply_text(f"Signal: {signal}")


    # --- NYTT: status-svar som snygg sammanställning ---
    async def _send_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        ack = await update.message.reply_text("🔎 Kollar status…")

        ib_client = context.application.bot_data.get("ib")
        if not ib_client:
            return await ack.edit_text("❌ Ingen IB-klient i bot_data.")

        ib = ib_client.ib
        connected = ib.isConnected()

        now_se = datetime.now(SE_TZ)
        now_et = datetime.now(US_TZ)
        market_open = _is_us_market_open(now_et)

        pos_lines = []
        ord_lines = []
        try:
            if connected:
                # 🛠️ HÄR: hämta positioner asynkront
                positions = await ib.reqPositionsAsync()

# Filtrera bort 0-positioner och dubbletter
                nonzero = []
                seen = set()
                for p in positions:
                    qty = float(p.position or 0.0)
                    if abs(qty) < 1e-6:
                        continue  # hoppa över 0.0
                    key = p.contract.conId or (p.contract.symbol, p.contract.exchange)
                    if key in seen:
                        continue
                    seen.add(key)
                    nonzero.append(p)

                # Sortera så största absoluta innehav överst
                positions_sorted = sorted(
                    nonzero, key=lambda p: abs(float(p.position or 0.0)), reverse=True
                )

                max_rows = 10  # visa upp till 10
                for p in positions_sorted[:max_rows]:
                    sym = p.contract.symbol
                    qty = float(p.position or 0.0)
                    qty_str = str(int(qty)) if qty.is_integer() else f"{qty:.2f}"  # 20 istället för 20.0
                    avg = float(p.avgCost or 0.0)
                    pos_lines.append(f"• {sym}: {qty_str} @ {avg:.2f}")

                extra = len(positions_sorted) - min(len(positions_sorted), max_rows)
                if extra > 0:
                    pos_lines.append(f"… +{extra} till")



                # 🛠️ HÄR: trigga uppdatering av öppna ordrar innan vi läser cachen
                await ib.reqOpenOrdersAsync()
                for t in ib.openTrades()[:5]:
                    s = t.contract.symbol
                    side = t.order.action
                    qty = int(t.order.totalQuantity)
                    filled = int(t.orderStatus.filled or 0)
                    st = t.orderStatus.status or "?"
                    rth = "AH" if getattr(t.order, 'outsideRth', False) else "RTH"
                    ord_lines.append(f"• {s} {side} {filled}/{qty} ({st}, {rth})")
        except Exception as e:
            pos_lines = pos_lines or ["(kunde inte läsa positioner)"]
            ord_lines = ord_lines or [f"(kunde inte läsa öppna ordrar: {e})"]

        pos_text = "\n".join(pos_lines) if pos_lines else "–"
        ord_text = "\n".join(ord_lines) if ord_lines else "–"

        msg = (
            f"✅ IB connected: {connected}\n"
            f"🕒 SE {now_se:%Y-%m-%d %H:%M} | ET {now_et:%H:%M}\n"
            f"🏛️ US Market open: {'JA' if market_open else 'NEJ'} (ord. 15:30–22:00 SE)\n"
            f"\n📈 Positioner (topp):\n{pos_text}"
            f"\n\n🧾 Öppna ordrar:\n{ord_text}"
        )
        await ack.edit_text(msg)
    
    async def _send_tickers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            with open("Stock_info.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            await update.message.reply_text("Kunde inte läsa Stock_info.json.")
            return

        # Plocka och sortera tickers
        syms = sorted({(s.get("symbol") or "").upper() for s in data if s.get("symbol")})
        if not syms:
            await update.message.reply_text("Inga tickers hittades i Stock_info.json.")
            return

        # Senaste uppdateringstid
        try:
            import os
            from datetime import datetime
            from zoneinfo import ZoneInfo
            mtime = os.path.getmtime("Stock_info.json")
            ts = datetime.fromtimestamp(mtime, ZoneInfo("Europe/Stockholm"))
            updated = ts.strftime("%Y-%m-%d %H:%M")
        except Exception:
            updated = "okänd tid"

        # Format: 8–10 per rad
        lines = []
        chunk = 10
        for i in range(0, len(syms), chunk):
            lines.append("· " + " · ".join(syms[i:i+chunk]))

        msg = f"📦 Universum ({len(syms)} tickers) — uppd. {updated}\n" + "\n".join(lines)
        await update.message.reply_text(msg)
            
    async def ai_router(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (update.message.text or "").strip()
        if not text:
            return

        lower = text.lower()

        # 0) Snabb: systemstatus (kodsvar) – hanteras FÖRE all regex
        if lower in {"status", "läge", "hur går det"}:
            return await self._send_status(update, context)

        # 1) AI-prefix (frivilligt): allt som börjar med ".ai" går direkt till LLM
        if lower.startswith(".ai"):
            prompt = text[3:].strip() or "Hej!"
            reply = await self._chat("Du svarar hjälpsamt och kort på svenska.", prompt)
            await update.message.reply_text(reply)
            return
                
        # Snabbkommando: lista tickers ur Stock_info.json
        if lower in {"tickers", "/tickers", "universum", "lista", "aktier"}:
            return await self._send_tickers(update, context)

        # 2) Deterministisk trade-parse: "köp 10 aapl" / "sälj 5 nvda" (sv/en)
        # 2) Deterministisk trade-parse: "köp 10 aapl" / "sälj 20.0 nvda"
        m_trade = re.fullmatch(
            r"(köp|buy|sälj|sell)\s+(\d+(?:[.,]\d+)?)\s+([A-Za-z0-9.\-]{1,6})",
            text, re.IGNORECASE
        )
        if m_trade:
            side_word, qty_str, ticker = m_trade.groups()
            try:
                qty = int(float(qty_str.replace(",", ".")))  # tillåt 20.0 och 20,0
            except ValueError:
                await update.message.reply_text("❌ Ogiltigt antal.")
                return

            side = "BUY" if side_word.lower() in {"köp", "buy"} else "SELL"
            ticker = ticker.upper()

            # Läs cache (valfritt)
            stocks_by_symbol = {}
            try:
                with open("Stock_info.json","r",encoding="utf-8") as f:
                    data = json.load(f)
                stocks_by_symbol = {s["symbol"].upper(): s for s in data}
            except Exception:
                pass

            stock = stocks_by_symbol.get(ticker) or {"symbol": ticker, "name": ticker}

            ib = context.application.bot_data.get("ib")
            if not ib or not ib.ib.isConnected():
                await update.message.reply_text("⚠️ IBKR inte ansluten – ingen order lagd.")
                return

            # 🔒 Blockera oönskad short / sälj mer än du äger
            if side == "SELL" and not ALLOW_SHORTS:
                positions = await ib.ib.reqPositionsAsync()
                held = {p.contract.symbol.upper(): float(p.position or 0) for p in positions}
                pos = held.get(ticker, 0.0)

                if pos <= 0:
                    await update.message.reply_text(f" Skippar SÄLJ {ticker} – äger inte aktien.")
                    return

                if qty > pos:
                    await update.message.reply_text(
                        f"⛔ Du äger bara {int(pos)} {ticker}. Säg t.ex. 'sälj {int(pos)} {ticker}'."
                    )
                    return

               
            # ✅ Lägg order (gäller både BUY och SELL efter ev. validering)
            ack = await update.message.reply_text(
                f"⏳ Lägger order: {'KÖP' if side=='BUY' else 'SÄLJ'} {qty} {ticker} …"
            )
            trade = await execute_order(
                ib, stock, "Köp" if side == "BUY" else "Sälj", qty,
                bot=context.application.bot,
                chat_id=int(os.getenv("ADMIN_CHAT_ID") or 0),
            )
            if trade:
                await ack.edit_text(
                    f"📨 Order skickad: {trade.order.action} {int(trade.order.totalQuantity)} {ticker} "
                    f"(status: {trade.orderStatus.status})"
                )
            else:
                await ack.edit_text("Ingen order skickad.")
            return



        # 3) Ticker-snabbväg för lookup (exakt ticker eller "TICKER aktie")
        #    OBS: vi kör EFTER status/trade, och bara på rena ticker-meddelanden.
        m1 = re.fullmatch(r"([A-Za-z0-9.\-]{1,6})(?:\s+(aktie|stock))?", text, re.IGNORECASE)
        m2 = re.fullmatch(r"(aktie|stock)\s+([A-Za-z0-9.\-]{1,6})", text, re.IGNORECASE)
        if m1:
            return await self._handle_stock_query(update, context, m1.group(1).upper())
        if m2:
            return await self._handle_stock_query(update, context, m2.group(2).upper())

        # 4) Annars: låt GPT-routern tolka (stock_query / trade_intent / smalltalk)
        try:
            raw = await self._chat(ROUTER_SYS, text)
            parsed = json.loads(raw)
        except Exception:
            parsed = {"intent": "smalltalk", "ticker": None, "qty": None, "side": None}

        intent = parsed.get("intent")
        ticker = parsed.get("ticker")
        qty    = parsed.get("qty")
        side   = parsed.get("side")

        if intent == "status":
            return await self._send_status(update, context)

        # Läs cache för stock_query / trade_intent
        stocks_by_symbol = {}
        if intent in ("stock_query", "trade_intent"):
            try:
                with open("Stock_info.json","r",encoding="utf-8") as f:
                    data = json.load(f)
                stocks_by_symbol = {s["symbol"].upper(): s for s in data}
            except Exception:
                await update.message.reply_text("Kunde inte läsa Stock_info.json.")
                return

        if intent == "stock_query":
            if not ticker:
                await update.message.reply_text("Vilken ticker menar du?")
                return
            return await self._handle_stock_query(update, context, ticker.upper())

        if intent == "trade_intent":
            if not (ticker and isinstance(qty, int) and side in ("BUY", "SELL")):
                await update.message.reply_text("Kan du specificera t.ex. 'Köp 10 DQ' eller 'Sälj 5 DUO'?")
                return

            stock = stocks_by_symbol.get(ticker.upper())
            if not stock:
                await update.message.reply_text(f"Hittar ingen data för {ticker}.")
                return

            ib = context.application.bot_data.get("ib")
            if not ib or not ib.ib.isConnected():
                await update.message.reply_text("⚠️ IBKR inte ansluten – ingen order lagd.")
                return

            ack = await update.message.reply_text(
                f"⏳ Lägger order: {'KÖP' if side=='BUY' else 'SÄLJ'} {qty} {stock['symbol']} …"
            )
            trade = await execute_order(
                ib, stock, "Köp" if side == "BUY" else "Sälj", qty,
                bot=context.application.bot,
                chat_id=int(os.getenv("ADMIN_CHAT_ID") or 0),
            )
            if trade:
                await ack.edit_text(
                    f"📨 Order skickad: {trade.order.action} {int(trade.order.totalQuantity)} {stock['symbol']} "
                    f"(status: {trade.orderStatus.status})"
                )
            else:
                await ack.edit_text("Ingen order skickad.")
            return

        # 5) Smalltalk/fallback → AI
        if intent == "smalltalk":
            reply = await self._chat("Du svarar hjälpsamt och kort på svenska.", text)
            await update.message.reply_text(reply)
            return

        reply = await self._chat("Svara kort på svenska.", text)
        await update.message.reply_text(reply)
   
    # --------- Auto-scan för schemaläggaren (anropar din signal + ev order) ----------


async def auto_scan_and_trade(bot, ib_client, admin_chat_id: int):
    try:
        # 1) Läs universum
        with open("Stock_info.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        # 2) IB anslutning?
        if not ib_client or not ib_client.ib.isConnected():
            if admin_chat_id:
                await bot.send_message(admin_chat_id, "⚠️ IBKR inte ansluten – hoppar över autoscan.")
            return

        AUTOTRADE = os.getenv("AUTOTRADE", "0").lower() in {"1","on","true","yes"}
        AUTO_QTY  = int(os.getenv("AUTO_QTY", "10"))

        # 3) Hämta positioner en gång
        positions = await ib_client.ib.reqPositionsAsync()
        held = {p.contract.symbol.upper(): float(p.position or 0) for p in positions}

        # 4) Ladda & rensa state per dag
        state = _load_state()
        today = datetime.now(US_TZ).date().isoformat()
        if state.get("day") != today:
            state = {"day": today, "symbols": {}}
        symbols_state = state.setdefault("symbols", {})

        for stock in data:
            sym = (stock.get("symbol") or "").upper()
            if not sym:
                continue

            signal = buy_or_sell(stock)

            # (valfritt) skicka alltid signal till chat
            if admin_chat_id:
                await bot.send_message(admin_chat_id, f"{sym} – Signal: {signal}")

            # Hämta symbol-state
            sst = symbols_state.setdefault(sym, {})
            last_signal = sst.get("last_signal")
            last_ts_iso = sst.get("last_trade_ts")
            last_trade_dt = None
            if last_ts_iso:
                try:
                    last_trade_dt = datetime.fromisoformat(last_ts_iso)
                except Exception:
                    last_trade_dt = None

            buys_today = int(sst.get("buys_today", 0))
            sells_today = int(sst.get("sells_today", 0))

            # 5) Spärr: handla bara på signaländring
            if ONLY_TRADE_ON_SIGNAL_CHANGE and last_signal == signal:
                # ingen ändring → ingen affär
                continue

            # 6) Spärr: cooldown per ticker
            if last_trade_dt and (datetime.now(US_TZ) - last_trade_dt) < timedelta(minutes=COOLDOWN_MIN):
                # inom cooldown → hoppa
                continue

            trade = None

            if AUTOTRADE and signal in {"Köp", "Sälj"}:
                qty = AUTO_QTY
                pos = held.get(sym, 0.0)

                # 7) Max affärer per dag per riktning
                if signal == "Köp" and buys_today >= MAX_BUYS_PER_DAY:
                    # redan max köp idag
                    continue
                if signal == "Sälj" and sells_today >= MAX_SELLS_PER_DAY:
                    # redan max sälj idag
                    continue

                # 8) Positionstak vid köp
                if signal == "Köp" and MAX_POS_PER_SYMBOL > 0:
                    # köp inte över cap
                    max_add = int(MAX_POS_PER_SYMBOL - pos)
                    if max_add <= 0:
                        # redan vid/över taket
                        continue
                    qty = min(qty, max_add)

                # 9) Hindra oönskad short
                if signal == "Sälj" and not ALLOW_SHORTS:
                    if pos <= 0:
                        if admin_chat_id:
                            await bot.send_message(admin_chat_id, f"⛔ Kan inte sälja {sym} – du äger inte aktien.")
                        continue
                    qty = min(qty, int(pos))
                    if qty <= 0:
                        continue

                # 10) Lägg order
                trade = await execute_order(
                    ib_client, stock, signal, qty=qty,
                    bot=bot, chat_id=admin_chat_id
                )

                # Om order gick iväg, uppdatera state
                if trade:
                    sst["last_trade_ts"] = datetime.now(US_TZ).isoformat()
                    if signal == "Köp":
                        sst["buys_today"] = buys_today + 1
                    else:
                        sst["sells_today"] = sells_today + 1
                    sst["last_signal"] = signal
                    symbols_state[sym] = sst
                    _save_state(state)

            # (valfritt) feedback
            if admin_chat_id:
                if trade is not None:
                    await bot.send_message(
                        admin_chat_id,
                        f"Order skickad: {trade.order.action} {int(trade.order.totalQuantity)} {sym} "
                        f"(status: {trade.orderStatus.status})"
                    )
                else:
                    # tyst läge går att välja, men detta hjälper vid felsökning
                    await bot.send_message(admin_chat_id, f"{sym} – Ingen order ({signal}).")

    except Exception as e:
        if admin_chat_id:
            await bot.send_message(admin_chat_id, f"❌ auto_scan_and_trade fel: {e}")
