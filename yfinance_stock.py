import yfinance
import asyncio
from ibkr_client import IbClient


async def analyse_stock():
    ib_client = IbClient()
    await ib_client.connect()  # Ansluter till IBKR API
    tickers = await ib_client.get_stocks()
    results = []  # Samlar data från varje ticker

    for symbol in tickers:
        ticker = yfinance.Ticker(symbol)
        # Använd 'get' på info för att undvika KeyError om värdet saknas
        stock_data = {
            "name": ticker.info.get("shortName"),
            "sector": ticker.info.get("sector"),
            "previousClose": ticker.info.get("previousClose"),
            "close": ticker.info.get("close"),
            "daysLow": ticker.info.get("daysLow"),
            "daysHigh": ticker.info.get("daysHigh"),
            "52WeekLow": ticker.info.get("52WeekLow"),
            "52WeekHigh": ticker.info.get("52WeekHigh"),
        }
        print(f"Analyserar aktie: {stock_data['name']}")
        print(f"Sektor: {stock_data['sector']}")
        print(f"Previous Close: {stock_data['previousClose']}")
        print(f"Close: {stock_data['close']}")
        print(f"Days Low: {stock_data['daysLow']}")
        print(f"Days High: {stock_data['daysHigh']}")
        print(f"52 Week Low: {stock_data['52WeekLow']}")
        print(f"52 Week High: {stock_data['52WeekHigh']}\n")
        results.append(stock_data)
    ib_client.scanner_parameters()
    return results
