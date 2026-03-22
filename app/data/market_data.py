#market_data.py
import time
import math
from typing import Any

from app.data.fmp_client import FMPClient


class MarketDataService:
    def __init__(self):
        self.fmp = FMPClient()

        # Enkel intern cache: {key: (timestamp, value)}
        self._cache: dict[tuple, tuple[float, Any]] = {}

        # TTL per datatyp
        self._ttl = {
            "quote": 120,           # 2 min
            "batch_quotes": 60,     # 1 min
            "profile": 24 * 3600,   # 24 h
            "fundamentals": 12 * 3600,  # 12 h
            "financials": 12 * 3600,    # 12 h
            "screener": 300,        # 5 min
            "news": 1800,           # 30 min
        }

    # ---------- cache helpers ----------

    def _cache_get(self, key: tuple, ttl: int):
        cached = self._cache.get(key)
        if not cached:
            return None

        ts, value = cached
        if time.time() - ts <= ttl:
            return value

        self._cache.pop(key, None)
        return None

    def _cache_set(self, key: tuple, value: Any):
        self._cache[key] = (time.time(), value)
        return value

    def _normalize_symbol(self, symbol: str) -> str:
        return (symbol or "").upper().strip()

    def _safe_float(self, x, default=None):
        try:
            if x is None:
                return default
            if isinstance(x, str):
                x = x.strip().replace(",", ".")
            val = float(x)
            if math.isnan(val):
                return default
            return val
        except Exception:
            return default

    # ---------- quote ----------

    def get_quote(self, symbol: str) -> dict:
        symbol = self._normalize_symbol(symbol)
        cache_key = ("quote", symbol)

        cached = self._cache_get(cache_key, self._ttl["quote"])
        if cached is not None:
            return cached

        q = self.fmp.quote(symbol) or {}
        out = {
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
        return self._cache_set(cache_key, out)

    def get_batch_quotes(self, symbols: list[str]) -> dict[str, dict]:
        symbols = [self._normalize_symbol(s) for s in symbols if s]
        if not symbols:
            return {}

        # Cacha på sorterad symbol-lista
        cache_key = ("batch_quotes", tuple(sorted(symbols)))
        cached = self._cache_get(cache_key, self._ttl["batch_quotes"])
        if cached is not None:
            return cached

        out: dict[str, dict] = {}

        # Försök 1: batch_quote
        try:
            rows = self.fmp.batch_quote(symbols) or []
            for q in rows:
                sym = self._normalize_symbol(q.get("symbol"))
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
                    "open": q.get("open"),
                    "previousClose": q.get("previousClose"),
                }

            if out:
                # uppdatera även enkel quote-cache
                for sym, data in out.items():
                    self._cache_set(("quote", sym), data)
                return self._cache_set(cache_key, out)
        except Exception:
            pass

        # Försök 2: batch_quote_short
        try:
            rows = self.fmp.batch_quote_short(symbols) or []
            for q in rows:
                sym = self._normalize_symbol(q.get("symbol"))
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
                    "open": None,
                    "previousClose": None,
                }

            if out:
                for sym, data in out.items():
                    self._cache_set(("quote", sym), data)
                return self._cache_set(cache_key, out)
        except Exception:
            pass

        # Försök 3: en och en
        for sym in symbols:
            try:
                q = self.get_quote(sym)
                if q:
                    out[sym] = q
            except Exception:
                continue

        return self._cache_set(cache_key, out)

    # ---------- profile ----------

    def get_profile(self, symbol: str) -> dict:
        symbol = self._normalize_symbol(symbol)
        cache_key = ("profile", symbol)

        cached = self._cache_get(cache_key, self._ttl["profile"])
        if cached is not None:
            return cached

        p = self.fmp.profile(symbol) or {}
        out = {
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
        return self._cache_set(cache_key, out)

    # ---------- fundamentals ----------

    def get_fundamentals(self, symbol: str) -> dict:
        symbol = self._normalize_symbol(symbol)
        cache_key = ("fundamentals", symbol)

        cached = self._cache_get(cache_key, self._ttl["fundamentals"])
        if cached is not None:
            return cached

        km = {}
        rt = {}

        try:
            km = self.fmp.key_metrics_ttm(symbol) or {}
        except Exception:
            km = {}

        try:
            rt = self.fmp.ratios_ttm(symbol) or {}
        except Exception:
            rt = {}

        out = {
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
        return self._cache_set(cache_key, out)

    # ---------- screener ----------

    def screen_stocks(self, **filters) -> list[dict]:
        # Cache på filterinnehållet
        filter_key = tuple(sorted(filters.items()))
        cache_key = ("screener", filter_key)

        cached = self._cache_get(cache_key, self._ttl["screener"])
        if cached is not None:
            return cached

        rows = self.fmp.screener(**filters) or []
        return self._cache_set(cache_key, rows)

    # ---------- news ----------

    def get_stock_news(self, symbol: str, limit: int = 3) -> list[dict]:
        symbol = self._normalize_symbol(symbol)
        cache_key = ("news", symbol, limit)

        cached = self._cache_get(cache_key, self._ttl["news"])
        if cached is not None:
            return cached

        rows = self.fmp.stock_news(symbols=symbol, limit=limit) or []
        return self._cache_set(cache_key, rows)

    # ---------- financials ----------

    def get_financials(self, symbol: str) -> dict:
        symbol = self._normalize_symbol(symbol)
        cache_key = ("financials", symbol)

        cached = self._cache_get(cache_key, self._ttl["financials"])
        if cached is not None:
            return cached

        # Mindre aggressiv än tidigare:
        # 1) growth
        # 2) ratios
        # 3) financial_scores
        # 4) key_metrics
        # 5) income_statement endast som fallback för revenue growth
        growth = {}
        ratios = {}
        scores = {}
        key = {}
        income = []

        try:
            growth = self.fmp.financial_growth(symbol) or {}
        except Exception:
            growth = {}

        try:
            ratios = self.fmp.ratios(symbol) or {}
        except Exception:
            ratios = {}

        try:
            scores = self.fmp.financial_scores(symbol) or {}
        except Exception:
            scores = {}

        try:
            key = self.fmp.key_metrics(symbol) or {}
        except Exception:
            key = {}

        # bara om revenueGrowth saknas
        raw_growth = growth.get("revenueGrowth")
        if raw_growth is None:
            try:
                income = self.fmp.income_statement(symbol, period="annual", limit=2) or []
            except Exception:
                income = []

        revenue_growth = None

        if raw_growth is not None:
            try:
                revenue_growth = float(raw_growth)
                if -1 < revenue_growth < 1:
                    revenue_growth *= 100
            except Exception:
                revenue_growth = None

        if revenue_growth is None and len(income) >= 2:
            try:
                rev_curr = float(income[0]["revenue"])
                rev_prev = float(income[1]["revenue"])
                if rev_prev:
                    revenue_growth = 100 * (rev_curr - rev_prev) / rev_prev
            except Exception:
                pass

        out = {
            "revenueGrowth": revenue_growth,
            "profitMargin": (
                ratios.get("netProfitMargin")
                or ratios.get("netProfitMarginRatio")
            ),
            "grossMargin": (
                ratios.get("grossProfitMargin")
                or ratios.get("grossProfitMarginRatio")
            ),
            "debtToEquity": (
                ratios.get("debtToEquity")
                or ratios.get("debtEquityRatio")
                or ratios.get("debtToEquityRatio")
            ),
            "currentRatio": ratios.get("currentRatio"),
            "roe": (
                key.get("returnOnEquity")
                or ratios.get("returnOnEquity")
            ),
            "roa": (
                key.get("returnOnAssets")
                or ratios.get("returnOnAssets")
            ),
            "freeCashFlowPerShare": (
                key.get("freeCashFlowPerShare")
                or key.get("freeCashFlowPerShareTTM")
            ),
            "altmanZ": (
                scores.get("altmanZScore")
                or scores.get("altmanZ")
            ),
            "piotroski": (
                scores.get("piotroskiScore")
                or scores.get("piotroski")
            ),
        }

        return self._cache_set(cache_key, out)