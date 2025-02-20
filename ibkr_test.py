import time
from ib_insync import IB, ScannerSubscription
import asyncio


class IbClient:
    def __init__(self):
        self.ib = IB()

    async def connect(self):
        """Ansluter asynkront till IBKR API."""
        await self.ib.connectAsync("127.0.0.1", 4001, clientId=1, timeout=60)
        print("✅ API Connected!")

    def scanner_parameters(self):
        """Hämtar scanner-parametrar från IBKR och sparar i en XML-fil."""
        scanner_xml = self.ib.reqScannerParameters()  # Synkront anrop
        with open("scanner_parameters.xml", "w", encoding="utf-8") as file:
            file.write(scanner_xml)
        print("✅ Scanner parameters saved!")

    async def get_stocks(self):
        """Hämtar aktier från IBKR scanner."""
        await asyncio.sleep(2)

        subscription = ScannerSubscription(
            instrument="STK",
            locationCode="STK.US.MAJOR",
            scanCode="TOP_PERC_LOSE",
        )

        scan_data = await self.ib.reqScannerDataAsync(subscription)
        if not scan_data:
            print("⚠️ Ingen scanner-data returnerad! Kontrollera IBKR API.")
            return []
        tickers = [data.contractDetails.contract.symbol for data in scan_data]
        print(f"✅ Hämtade {len(tickers)} aktier: {tickers}")
        return tickers

    def disconnect_ibkr(self):
        """Stänger IBKR API-anslutningen."""
        time.sleep(
            2
        )  # OBS: time.sleep() blockerar event loopen; överväg asyncio.sleep() om det behövs.
        self.ib.disconnect()
        print("❌ API Disconnected!")


# "MOST_ACTIVE", # fungerade
# "HIGH_OPEN_GAP", # nej
# "LOW_OPEN_GAP", # nej
# "TOP_PERC_GAIN", # fungerade
# "TOP_PERC_LOSE", # fungerade
