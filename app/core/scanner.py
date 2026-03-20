import json
import logging
import asyncio

from app.config import STOCK_INFO_PATH
from app.core.market_profile import PROFILE, MARKET_PROFILE
import yfinance as yf

log = logging.getLogger("scanner")


def _to_float(x, default=None):
    try:
        if isinstance(x, str):
            x = x.strip().replace(",", ".")
        return float(x)
    except Exception:
        return default


def _fetch_yf_snapshot(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = t.info or {}

    latest_close = (
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or info.get("previousClose")
    )

    stock = {
        "symbol": ticker,
        "name": info.get("shortName") or info.get("longName") or ticker,
        "latestClose": latest_close,
        "PE": info.get("trailingPE") or info.get("forwardPE"),
        "marketCap": info.get("marketCap"),
        "beta": info.get("beta"),
        "trailingEps": info.get("trailingEps"),
        "dividendYield": info.get("dividendYield"),
        "sector": info.get("sector"),
        "News": [],
    }

    try:
        news = t.news or []
        for n in news[:3]:
            stock["News"].append({
                "content": {
                    "title": n.get("title", ""),
                    "summary": n.get("summary", "") or "",
                    "publisher": n.get("publisher", ""),
                    "link": n.get("link", ""),
                }
            })
    except Exception:
        pass

    return stock


def _is_good_snapshot(stock: dict) -> tuple[bool, str | None]:
    price = _to_float(stock.get("latestClose"))
    market_cap = _to_float(stock.get("marketCap"))
    name = (stock.get("name") or "").lower()
    symbol = (stock.get("symbol") or "").upper()

    min_price = PROFILE["min_price"]
    min_market_cap = PROFILE["min_market_cap"]

    leveraged_hints = [
        "2x", "3x", "ultra", "ultrapro", "daily",
        "bull", "bear", "short", "leveraged"
    ]

    if price is None:
        return False, "saknar pris"
    if price < min_price:
        return False, f"pris under {min_price}"

    if market_cap is None:
        return False, "saknar market cap"
    if market_cap < min_market_cap:
        return False, f"market cap under {min_market_cap}"

    if symbol in {"TSLL", "TSLQ", "SQQQ"}:
        return False, "leveraged/inverse ETF"

    if any(hint in name for hint in leveraged_hints):
        return False, "leveraged/inverse ETF"

    return True, None


def _write_stock_info(rows: list[dict]):
    with open(STOCK_INFO_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def _read_stock_info() -> list[dict] | None:
    try:
        with open(STOCK_INFO_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _fallback_tickers() -> list[str]:
    if PROFILE["currency"] == "SEK":
        return ["VOLV-B.ST", "ERIC-B.ST", "SEB-A.ST", "ATCO-A.ST", "ABB.ST", "SWED-A.ST"]
    return ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "AMD", "TSLA", "NFLX", "INTC", "QCOM", "AVGO"]


def _looks_swedish(contract, contract_details) -> bool:
    currency = (getattr(contract, "currency", "") or "").upper()
    primary_exchange = (getattr(contract, "primaryExchange", "") or "").upper()
    exchange = (getattr(contract, "exchange", "") or "").upper()
    local_symbol = (getattr(contract, "localSymbol", "") or "").upper()
    long_name = (getattr(contract_details, "longName", "") or "").upper()
    market_name = (getattr(contract_details, "marketName", "") or "").upper()

    if currency != "SEK":
        return False

    swedish_markers = {"OMS", "SFB", "SMART"}
    if primary_exchange in swedish_markers:
        return True
    if exchange in swedish_markers:
        return True

    if ".ST" in local_symbol:
        return True

    if "SWEDEN" in long_name or "SWEDEN" in market_name:
        return True

    return True


def _normalize_se_symbol(symbol: str, local_symbol: str = "", long_name: str = "") -> str:
    raw_symbol = (symbol or "").upper().strip()
    raw_local = (local_symbol or "").upper().strip()
    raw_name = (long_name or "").upper().strip()

    if raw_symbol.endswith(".ST"):
        return raw_symbol

    combo = " ".join(part for part in [raw_symbol, raw_local, raw_name] if part)

    series_candidates = [
        (" A", "-A.ST"),
        (" B", "-B.ST"),
        (" SER. A", "-A.ST"),
        (" SER. B", "-B.ST"),
        (" SERIES A", "-A.ST"),
        (" SERIES B", "-B.ST"),
    ]

    for needle, suffix in series_candidates:
        if needle in combo:
            return f"{raw_symbol}{suffix}"

    return f"{raw_symbol}.ST"


def _to_yf_symbol(symbol: str, local_symbol: str = "", long_name: str = "") -> str:
    if PROFILE["currency"] == "SEK":
        if local_symbol.endswith(".ST"):
            return local_symbol.upper()
        return _normalize_se_symbol(symbol, local_symbol, long_name)
    return (symbol or "").upper().strip()


async def _ib_scanner(ib_client, limit: int) -> list[str]:
    try:
        from ib_insync import ScannerSubscription

        sub = ScannerSubscription()
        sub.instrument = PROFILE["scanner_instrument"]
        sub.locationCode = PROFILE["scanner_location"]
        sub.scanCode = PROFILE["scanner_code"]

        items = await ib_client.ib.reqScannerDataAsync(sub, [])

        seen = set()
        out = []

        for it in items[: limit * 10]:
            cd = getattr(it, "contractDetails", None)
            if not cd or not getattr(cd, "contract", None):
                continue

            c = cd.contract
            sym = (getattr(c, "symbol", "") or "").upper().strip()
            local_symbol = (getattr(c, "localSymbol", "") or "").upper().strip()
            long_name = (getattr(cd, "longName", "") or "").strip()
            currency = (getattr(c, "currency", "") or "").upper().strip()
            exchange = (getattr(c, "exchange", "") or "").upper().strip()
            primary_exchange = (getattr(c, "primaryExchange", "") or "").upper().strip()
            market_name = (getattr(cd, "marketName", "") or "").strip()

            if not sym:
                continue

            log.info(
                "[scanner] RAW IB sym=%s local=%s currency=%s exch=%s primary=%s longName=%s marketName=%s",
                sym,
                local_symbol,
                currency,
                exchange,
                primary_exchange,
                long_name,
                market_name,
            )

            if MARKET_PROFILE == "SE":
                if not _looks_swedish(c, cd):
                    log.info("[scanner] Skippar ej svensk kandidat: %s", sym)
                    continue
                yf_symbol = _to_yf_symbol(sym, local_symbol, long_name)
            else:
                yf_symbol = sym

            if yf_symbol not in seen:
                seen.add(yf_symbol)
                out.append(yf_symbol)

            if len(out) >= max(10, limit * 3):
                break

        log.info("[scanner] IB scanner gav %d filtrerade symboler", len(out))
        return out

    except Exception as e:
        log.error("[scanner] IB scanner misslyckades: %s", e)
        return []


async def refresh_stock_info(ib_client, limit: int = 50) -> list[dict]:
    tickers = []

    if ib_client and ib_client.ib.isConnected():
        tickers = await _ib_scanner(ib_client, limit)

    if tickers:
        log.info("[scanner] Använder IB-scanner (%d tickers).", len(tickers))
    else:
        log.warning("[scanner] IB-scanner gav 0 tickers.")
        old = _read_stock_info()
        if isinstance(old, list) and old:
            log.warning("[scanner] Behåller gammal Stock_info.json (%d rader).", len(old))
            return old

        log.warning("[scanner] Ingen gammal fil finns och IB gav 0 tickers.")
        return []

    rows = []
    max_fetch = min(len(tickers), limit * 3)

    for i, sym in enumerate(tickers[: limit * 3], start=1):
        try:
            log.info("[scanner] Hämtar %s (%d/%d)", sym, i, max_fetch)
            stock = _fetch_yf_snapshot(sym)

            ok, reason = _is_good_snapshot(stock)
            if not ok:
                log.info("[scanner] Skippar %s → %s", sym, reason)
                continue

            rows.append(stock)

            if len(rows) >= limit:
                break

            await asyncio.sleep(0.05)

        except Exception as e:
            log.warning("[scanner] Misslyckades med %s: %s", sym, e)

    if not rows:
        old = _read_stock_info()
        if isinstance(old, list) and old:
            log.warning("[scanner] Ingen ny data – behåller befintlig Stock_info.json (%d rader).", len(old))
            return old

        log.warning("[scanner] Ingen ny data och ingen gammal fil finns.")
        return []

    _write_stock_info(rows)
    log.info("[scanner] Stock_info.json uppdaterad (%d rader).", len(rows))
    return rows


async def ensure_stock_info(ib_client, min_count: int = 10) -> list[dict]:
    data = _read_stock_info()
    if not isinstance(data, list) or len(data) < min_count:
        log.info("[scanner] Stock_info.json saknas/korrupt/otillräcklig – bygger om…")
        data = await refresh_stock_info(ib_client, limit=max(min_count, 12))
    return data or []