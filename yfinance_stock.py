# yfinance_stock.py
import yfinance as yf
import asyncio


async def analyse_stock(ib_client):
    # Använd den skickade ib_client-instansen (förväntas redan vara ansluten)
    tickers = await ib_client.get_stocks()
    results = []  # Lista för att samla all data

    for symbol in tickers:
        ticker_obj = yf.Ticker(symbol)
        info = ticker_obj.info
        history_df = ticker_obj.history(period="max")
        if not history_df.empty:
            latest_close = history_df["Close"].iloc[-1]
        else:
            latest_close = None

        stock_data = {
            "symbol": symbol,
            "name": info.get("shortName"),
            "sector": info.get("sector"),
            "previousClose": info.get("previousClose"),
            "latestClose": latest_close,
            "daysLow": info.get("daysLow"),
            "daysHigh": info.get("daysHigh"),
            "52WeekLow": info.get("52WeekLow"),
            "52WeekHigh": info.get("52WeekHigh"),
            "history": history_df,
        }

        print(f"Analyserar aktie: {stock_data['name']}")
        print(f"Sektor: {stock_data['sector']}")
        print(f"Previous Close: {stock_data['previousClose']}")
        print(f"Latest Close: {stock_data['latestClose']}")
        print(f"Days Low: {stock_data['daysLow']}")
        print(f"Days High: {stock_data['daysHigh']}")
        print(f"52 Week Low: {stock_data['52WeekLow']}")
        print(f"52 Week High: {stock_data['52WeekHigh']}\n")
        results.append(stock_data)

    # Exempel: om du vill hämta scanner-parametrar, gör det här
    await ib_client.scanner_parameters()
    return results
