# ibkr_client.py
from ib_insync import IB, ScannerSubscription, Stock, MarketOrder
import asyncio
import os

class IbClient:
    def __init__(self):
        self.ib = IB()

    # Port 4002 för paper, 4001 för live
    async def connect(self):
        if not self.ib.isConnected():
            try:
                await self.ib.connectAsync("127.0.0.1", 4002, clientId=1, timeout=30)
                print("✅ API Connected on 4002!")
            except Exception as e:
                print(f"❌ API connection failed: {e}")
        else:
            print("ℹ️ IBKR redan ansluten")

    async def place_order(self, symbol, side, qty, bot=None, chat_id=None):
        """
        side: 'BUY' eller 'SELL'
        qty:  heltal antal
        bot/chat_id: valfria, för att skicka status till Telegram
        """
        contract = Stock(symbol, "SMART", "USD")
        order = MarketOrder(side, qty)

        # Kör synkron ib.placeOrder i tråd
        trade = await asyncio.to_thread(self.ib.placeOrder, contract, order)
        print(f"📨 Order skickad: {trade}")

        # --- Korrekt koppling av events och signaturer ---
        # statusEvent -> callback(trade)
        def on_status(trade_):
            try:
                status = trade_.orderStatus.status or ""
                filled = trade_.orderStatus.filled or 0
                total  = getattr(trade_.order, "totalQuantity", 0) or 0
                msg = f"📊 Orderstatus {symbol}: {status}, fylld {filled}/{total}"
                print(msg)
                if bot and chat_id:
                    asyncio.get_running_loop().create_task(
                        bot.send_message(chat_id=chat_id, text=msg)
                    )
            except Exception as e:
                print(f"[on_status] fel: {e}")

        # filledEvent -> callback(trade)  (triggas när traden blir fylld)
        def on_filled(trade_):
            try:
                avg = float(trade_.orderStatus.avgFillPrice or 0.0)
                filled = float(trade_.orderStatus.filled or 0.0)
                total  = float(getattr(trade_.order, "totalQuantity", 0) or 0)
                sym = trade_.contract.symbol
                msg = f"✅ {sym}: Filled {filled}/{total} @ {avg:.2f}"
                print(msg)
                if bot and chat_id:
                    asyncio.get_running_loop().create_task(
                        bot.send_message(chat_id=chat_id, text=msg)
                    )
            except Exception as e:
                print(f"[on_filled] fel: {e}")

        # fillEvent -> callback(trade, fill)  (per enskild fill)
        def on_fill(trade_, fill):
            try:
                sym = trade_.contract.symbol
                px  = float(getattr(fill.execution, "price", 0.0) or 0.0)
                qty_ = float(getattr(fill.execution, "shares", 0.0) or 0.0)
                cum = float(trade_.orderStatus.filled or 0.0)
                total = float(getattr(trade_.order, "totalQuantity", 0) or 0)
                msg = f"🧾 Fill {sym}: {qty_} @ {px} (cum {cum}/{total})"
                print(msg)
                if bot and chat_id:
                    asyncio.get_running_loop().create_task(
                        bot.send_message(chat_id=chat_id, text=msg)
                    )
            except Exception as e:
                print(f"[on_fill] fel: {e}")

        # Rätt koppling:
        trade.statusEvent += on_status     # (trade)
        trade.filledEvent += on_filled     # (trade)
        trade.fillEvent   += on_fill       # (trade, fill)

        # Städa bort handlers efter fill/cancel för att undvika läckor
        def _detach(_trade):
            try:
                trade.statusEvent -= on_status
                trade.filledEvent -= on_filled
                trade.fillEvent   -= on_fill
            except Exception:
                pass

        trade.filledEvent   += _detach     # när fylld
        trade.cancelledEvent += _detach    # om avbruten

        return trade

    async def get_stocks(self, rows: int | None = None,
                         instrument: str | None = None,
                         locationCode: str | None = None,
                         scanCode: str | None = None):
        # Läs defaults från .env om ej skickat in
        rows = rows or int(os.getenv("UNIVERSE_ROWS", "30"))
        instrument = instrument or os.getenv("SCANNER_INSTRUMENT", "STK")
        locationCode = locationCode or os.getenv("SCANNER_LOCATION", "STK.NASDAQ")
        scanCode = scanCode or os.getenv("SCANNER_CODE", "MOST_ACTIVE")

        # liten paus så TWS hinner andas
        await asyncio.sleep(0.5)

        sub = ScannerSubscription(
            instrument=instrument,
            locationCode=locationCode,
            scanCode=scanCode,
            numberOfRows=rows
        )
        data = await self.ib.reqScannerDataAsync(sub)
        if not data:
            print("⚠️ Ingen scanner-data returnerad.")
            return []

        # Plocka symboler (unika, behåll ordning)
        seen, tickers = set(), []
        for d in data:
            sym = d.contractDetails.contract.symbol
            if sym not in seen:
                seen.add(sym)
                tickers.append(sym)

        print(f"✅ Hämtade {len(tickers)} aktier: {tickers}")
        return tickers

    async def scanner_parameters(self):
        scanner_xml = self.ib.reqScannerParameters()
        with open("scanner_parameters.xml", "w", encoding="utf-8") as f:
            f.write(scanner_xml)
        print("✅ Scanner parameters saved!")

    async def disconnect_ibkr(self):
        await asyncio.sleep(2)
        self.ib.disconnect()
        print("❌ API Disconnected!")

# --- Global instans att återanvända ---
ib_client = IbClient()
