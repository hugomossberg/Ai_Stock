from app.data.fmp_client import FMPClient


class MarketDataService:
    def __init__(self):
        self.fmp = FMPClient()

    def get_quote(self, symbol: str) -> dict:
        q = self.fmp.quote(symbol) or {}
        return {
            "symbol": q.get("symbol", symbol),
            "price": q.get("price"),
            "change": q.get("change"),
            "changePercent": q.get("changesPercentage") or q.get("changePercentage"),
            "volume": q.get("volume"),
            "dayLow": q.get("dayLow"),
            "dayHigh": q.get("dayHigh"),
            "yearHigh": q.get("yearHigh"),
            "yearLow": q.get("yearLow"),
            "marketCap": q.get("marketCap"),
            "avgVolume": q.get("avgVolume"),
            "open": q.get("open"),
            "previousClose": q.get("previousClose"),
        }

    def get_batch_quotes(self, symbols: list[str]) -> dict[str, dict]:
        out = {}

        try:
            rows = self.fmp.batch_quote(symbols) or []
            for q in rows:
                sym = q.get("symbol")
                if not sym:
                    continue
                out[sym] = {
                    "symbol": sym,
                    "price": q.get("price"),
                    "change": q.get("change"),
                    "changePercent": q.get("changesPercentage") or q.get("changePercentage"),
                    "volume": q.get("volume"),
                    "marketCap": q.get("marketCap"),
                    "avgVolume": q.get("avgVolume"),
                }
            if out:
                return out
        except Exception:
            pass

        try:
            rows = self.fmp.batch_quote_short(symbols) or []
            for q in rows:
                sym = q.get("symbol")
                if not sym:
                    continue
                out[sym] = {
                    "symbol": sym,
                    "price": q.get("price"),
                    "change": q.get("change"),
                    "changePercent": q.get("changePercentage"),
                    "volume": q.get("volume"),
                    "marketCap": None,
                    "avgVolume": None,
                }
            if out:
                return out
        except Exception:
            pass

        for sym in symbols:
            try:
                q = self.get_quote(sym)
                if q:
                    out[sym] = q
            except Exception:
                continue

        return out

    def get_profile(self, symbol: str) -> dict:
        p = self.fmp.profile(symbol) or {}
        return {
            "symbol": symbol,
            "name": p.get("companyName"),
            "sector": p.get("sector"),
            "industry": p.get("industry"),
            "country": p.get("country"),
            "exchange": p.get("exchange"),
            "marketCap": p.get("marketCap"),
            "beta": p.get("beta"),
            "lastDividend": p.get("lastDividend"),
            "currency": p.get("currency"),
            "isEtf": p.get("isEtf"),
            "isActivelyTrading": p.get("isActivelyTrading"),
        }

    def get_fundamentals(self, symbol: str) -> dict:
        km = self.fmp.key_metrics_ttm(symbol) or {}
        rt = self.fmp.ratios_ttm(symbol) or {}
        return {
            "symbol": symbol,
            "pe": rt.get("priceToEarningsRatioTTM") or rt.get("priceEarningsRatioTTM") or rt.get("peRatioTTM"),
            "pb": rt.get("priceToBookRatioTTM"),
            "ps": rt.get("priceToSalesRatioTTM"),
            "roe": km.get("returnOnEquityTTM") or rt.get("returnOnEquityTTM"),
            "roa": km.get("returnOnAssetsTTM") or rt.get("returnOnAssetsTTM"),
            "currentRatio": rt.get("currentRatioTTM"),
            "debtToEquity": rt.get("debtToEquityRatioTTM") or rt.get("debtEquityRatioTTM"),
            "epsTTM": rt.get("netIncomePerShareTTM"),
            "fcfPerShareTTM": rt.get("freeCashFlowPerShareTTM") or km.get("freeCashFlowPerShareTTM"),
            "marketCap": km.get("marketCapTTM") or km.get("marketCap"),
            "dividendYieldTTM": rt.get("dividendYieldTTM"),
            "dividendPerShareTTM": rt.get("dividendPerShareTTM"),
        }
   
    def screen_stocks(self, **filters) -> list[dict]:
        return self.fmp.screener(**filters) or []