from ib_insync import IB, Stock, MarketOrder, LimitOrder, ScannerSubscription
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
                print("API connected on 4002")
            except Exception as e:
                print(f"API connection failed: {e}")
        else:
            print("IBKR already connected")

    async def _get_reference_price(self, contract):
        price = None

        try:
            ticker = self.ib.reqMktData(contract, "", False, False)
            await asyncio.sleep(1.5)

            price = (
                ticker.last
                or ticker.marketPrice()
                or ticker.close
                or ticker.bid
                or ticker.ask
            )
        except Exception:
            price = None
        finally:
            try:
                self.ib.cancelMktData(contract)
            except Exception:
                pass

        try:
            if price is not None:
                price = float(price)
                if price > 0:
                    return price
        except Exception:
            pass

        return None

    async def place_order(self, symbol, side, qty, bot=None, chat_id=None):
        contract = Stock(symbol, "SMART", "USD")

        try:
            qualified = await self.ib.qualifyContractsAsync(contract)
            if not qualified:
                print(f"Could not qualify contract for {symbol}")
                return None
            contract = qualified[0]
        except Exception as e:
            print(f"qualifyContracts failed for {symbol}: {e}")
            return None

        ref_price = await self._get_reference_price(contract)

        use_limit_orders = os.getenv("USE_LIMIT_ORDERS", "1").strip().lower() in {
            "1", "true", "yes", "on"
        }

        if use_limit_orders and ref_price:
            buy_buffer = float(os.getenv("BUY_LIMIT_BUFFER_PCT", "0.002"))
            sell_buffer = float(os.getenv("SELL_LIMIT_BUFFER_PCT", "0.002"))

            if side.upper() == "BUY":
                limit_price = round(ref_price * (1 + buy_buffer), 2)
            else:
                limit_price = round(ref_price * (1 - sell_buffer), 2)

            order = LimitOrder(side.upper(), qty, limit_price)
            print(
                f"ORDER     {side.upper():<5} {symbol:<6} x{qty:<3} "
                f"LIMIT   @ {limit_price:<8} ref={ref_price}"
            )
        else:
            order = MarketOrder(side.upper(), qty)
            print(
                f"ORDER     {side.upper():<5} {symbol:<6} x{qty:<3} MARKET"
            )

        trade = self.ib.placeOrder(contract, order)

        def on_status(trade_):
            status = trade_.orderStatus.status
            filled = trade_.orderStatus.filled
            remaining = trade_.orderStatus.remaining
            avg_fill = trade_.orderStatus.avgFillPrice
            print(
                f"STATUS    {symbol:<6} {status:<10} | "
                f"filled={filled} | remaining={remaining} | avg_fill={avg_fill}"
            )

        def on_filled(trade_):
            avg_fill = trade_.orderStatus.avgFillPrice
            print(f"FILLED    {symbol:<6} done       | avg_fill={avg_fill}")

        def on_fill(trade_, fill):
            execu = fill.execution
            print(
                f"FILL      {symbol:<6} {execu.side:<4} | "
                f"shares={execu.shares} | price={execu.price}"
            )

        def _detach(trade_=None):
            try:
                trade.statusEvent -= on_status
            except Exception:
                pass
            try:
                trade.filledEvent -= on_filled
            except Exception:
                pass
            try:
                trade.fillEvent -= on_fill
            except Exception:
                pass
            try:
                trade.filledEvent -= _detach
            except Exception:
                pass
            try:
                trade.cancelledEvent -= _detach
            except Exception:
                pass

        trade.statusEvent += on_status
        trade.filledEvent += on_filled
        trade.fillEvent += on_fill
        trade.filledEvent += _detach
        trade.cancelledEvent += _detach

        await asyncio.sleep(0.75)

        status = (trade.orderStatus.status or "").lower()
        if status in {"cancelled", "inactive"}:
            print(f"Order cancelled immediately for {trade.contract.symbol}: {trade.orderStatus.status}")
            _detach(trade)
            return None

        return trade

    async def get_stocks(
        self,
        rows: int | None = None,
        instrument: str | None = None,
        locationCode: str | None = None,
        scanCode: str | None = None,
    ):
        rows = rows or int(os.getenv("UNIVERSE_ROWS", "30"))
        instrument = instrument or os.getenv("SCANNER_INSTRUMENT", "STK")
        locationCode = locationCode or os.getenv("SCANNER_LOCATION", "STK.NASDAQ")
        scanCode = scanCode or os.getenv("SCANNER_CODE", "MOST_ACTIVE")

        await asyncio.sleep(0.5)

        sub = ScannerSubscription(
            instrument=instrument,
            locationCode=locationCode,
            scanCode=scanCode,
            numberOfRows=rows,
        )
        data = await self.ib.reqScannerDataAsync(sub)
        if not data:
            print("No scanner data returned")
            return []

        seen, tickers = set(), []
        for d in data:
            sym = d.contractDetails.contract.symbol
            if sym not in seen:
                seen.add(sym)
                tickers.append(sym)

        print(f"Fetched {len(tickers)} symbols: {tickers}")
        return tickers

    async def scanner_parameters(self):
        scanner_xml = self.ib.reqScannerParameters()
        with open("scanner_parameters.xml", "w", encoding="utf-8") as f:
            f.write(scanner_xml)
        print("Scanner parameters saved")

    async def disconnect_ibkr(self):
        await asyncio.sleep(2)
        self.ib.disconnect()
        print("API disconnected")


# Global instans att återanvända
ib_client = IbClient()