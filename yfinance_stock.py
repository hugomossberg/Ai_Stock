# yfinance_stock.py
import yfinance as yf
import json
import pandas as pd
from helpers import convert_keys_to_str

async def analyse_stock(ib_client):
    tickers = await ib_client.get_stocks()  # Hämtar aktielistan
    results = []

    for symbol in tickers:
        ticker_obj = yf.Ticker(symbol)

        # Hantera 404-fel
        try:
            info = ticker_obj.info
            if not info:
                print(f"⚠️ Ingen data hittades för {symbol}, hoppar över...")
                continue

        except Exception as e:
            print(f"❌ Fel vid hämtning av {symbol}: {e}")
            continue  # Hoppa över den här aktien om fel uppstår

        # Hämta senaste stängningspris
        history_df = ticker_obj.history(period="1mo")
        latest_close = history_df["Close"].iloc[-1] if not history_df.empty else None

        # Hämta nyheter och kvartalsrapporter
        news_for_you = ticker_obj.news
        quarterly_financial = ticker_obj.quarterly_financials
        quarterly_balance = ticker_obj.quarterly_balance_sheet
        quarterly_cashflow = ticker_obj.quarterly_cashflow

        stock_data = {
            "symbol": symbol,
            "quarterlyFinance": quarterly_financial.to_dict() if quarterly_financial is not None else None,
            "quarterlyBalance": quarterly_balance.to_dict() if quarterly_balance is not None else None,
            "quarterlyCashflow": quarterly_cashflow.to_dict() if quarterly_cashflow is not None else None,
            "name": info.get("shortName", "Okänd"),
            "sector": info.get("sector", "Okänd"),
            "previousClose": info.get("previousClose"),
            "priceToEarningsRatio": info.get("priceToEarningsRatio"),
            "priceToBookRatio": info.get("priceToBookRatio"),
            "marketCap": info.get("marketCap"),
            "PE": info.get("trailingPE"),
            "beta": info.get("beta"),
            "trailingEps": info.get("trailingEps"),
            "dividendYield": info.get("dividendYield"),
            "latestClose": latest_close,
            "News": news_for_you
        }

        print(f"✅ {symbol}: {stock_data['latestClose']}")
        #print(f"✅ {symbol}: {stock_data}['News']")


        results.append(stock_data)

    # Spara till JSON-fil
    converted_results = convert_keys_to_str(results)
    with open("Stock_info.json", "w") as final:
        json.dump(converted_results, final, indent=4, default=str, allow_nan=True)

    print("📁 Stock data sparad i Stock_info.json!")
    return results
