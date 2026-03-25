#storage_utils.py
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from app.config import EVENTS_DIR, REPORTS_DIR, SNAPSHOT_DIR




def _market_lines(market_info: dict | None = None) -> list[str]:
    if not market_info:
        return [
            "Market phase       : -",
            "Swedish time       : -",
            "US market time     : -",
            "Session open       : -",
            "Regular market     : -",
        ]

    now_market = market_info.get("now_market")
    now_sweden = market_info.get("now_sweden")
    phase_sv = market_info.get("phase_sv", "-")
    phase = market_info.get("phase", "-")
    session_open = "JA" if market_info.get("market_open") else "NEJ"
    regular_open = "JA" if phase == "regular" else "NEJ"

    us_txt = now_market.strftime("%Y-%m-%d %H:%M:%S %Z") if now_market else "-"
    se_txt = now_sweden.strftime("%Y-%m-%d %H:%M:%S %Z") if now_sweden else "-"

    return [
        f"Market phase       : {phase_sv} ({phase})",
        f"Swedish time       : {se_txt}",
        f"US market time     : {us_txt}",
        f"Session open       : {session_open}",
        f"Regular market     : {regular_open}",
    ]

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def week_folder(dt: datetime) -> str:
    iso = dt.isocalendar()
    return f"week_{iso.week:02d}"


def year_folder(dt: datetime) -> str:
    return str(dt.year)


def daily_filename(dt: datetime, suffix: str) -> str:
    return dt.strftime("%Y-%m-%d") + suffix


def get_snapshot_path(dt: datetime | None = None) -> Path:
    dt = dt or now_utc()
    path = SNAPSHOT_DIR / year_folder(dt) / week_folder(dt)
    path.mkdir(parents=True, exist_ok=True)
    return path / daily_filename(dt, ".json")


def get_events_path(dt: datetime | None = None) -> Path:
    dt = dt or now_utc()
    path = EVENTS_DIR / year_folder(dt) / week_folder(dt)
    path.mkdir(parents=True, exist_ok=True)
    return path / "events.jsonl"


def get_report_path(dt: datetime | None = None) -> Path:
    dt = dt or now_utc()
    path = REPORTS_DIR / year_folder(dt) / week_folder(dt)
    path.mkdir(parents=True, exist_ok=True)
    return path / daily_filename(dt, ".txt")

def get_journal_path(dt: datetime | None = None) -> Path:
    dt = dt or now_utc()
    path = REPORTS_DIR / year_folder(dt) / week_folder(dt)
    path.mkdir(parents=True, exist_ok=True)
    return path / (dt.strftime("%Y-%m-%d") + "_journal.txt")


def atomic_json_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp_path, path)


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def overwrite_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp_path, path)

def append_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)

def append_event(
    event_type: str,
    *,
    symbol: str | None = None,
    name: str | None = None,
    reason: str | None = None,
    data: dict | None = None,
) -> Path:
    dt = now_utc()
    path = get_events_path(dt)

    row = {
        "ts": dt.isoformat(),
        "type": event_type,
        "symbol": symbol,
        "name": name,
        "reason": reason,
        "data": data or {},
    }

    append_jsonl(path, row)
    return path


def save_daily_snapshot(
    *,
    state: dict,
    summary: dict | None = None,
    scan_set: list[dict] | None = None,
    market_open: bool | None = None,
    portfolio: list[dict] | None = None,
) -> Path:
    dt = now_utc()
    path = get_snapshot_path(dt)

    payload = {
        "snapshot_ts": dt.isoformat(),
        "date": dt.strftime("%Y-%m-%d"),
        "market_open": market_open,
        "summary": deepcopy(summary or {}),
        "scan_set": deepcopy(scan_set or []),
        "portfolio": deepcopy(portfolio or []),
        "state": deepcopy(state or {}),
    }

    atomic_json_write(path, payload)
    return path


def save_portfolio_review(rows: list[dict], dt: datetime | None = None) -> Path:
    dt = dt or now_utc()
    path = SNAPSHOT_DIR / year_folder(dt) / week_folder(dt)
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / (dt.strftime("%Y-%m-%d") + "_portfolio.json")

    payload = {
        "snapshot_ts": dt.isoformat(),
        "portfolio": deepcopy(rows or []),
    }

    atomic_json_write(file_path, payload)
    return file_path



def _signal_label(signal: str) -> str:
    return (signal or "").strip().upper()


def _friendly_name(row: dict) -> str:
    symbol = row.get("symbol", "?")
    name = row.get("name") or row.get("companyName") or symbol
    if name == symbol:
        return symbol
    return f"{name} ({symbol})"


def _reason_lines(row: dict) -> list[str]:
    details = row.get("details", {}) or {}
    lines: list[str] = []

    news = (details.get("news", {}) or {}).get("news_sentiment_score", 0)
    if news > 0:
        lines.append("positive news sentiment")

    liquidity = (details.get("liquidity", {}) or {}).get("liquidity_score", 0)
    if liquidity > 0:
        lines.append("good liquidity")

    financials = details.get("financials", {}) or {}
    if financials.get("revenue_growth", 0) > 0:
        lines.append("strong revenue growth")
    if financials.get("profit_margin", 0) > 0:
        lines.append("healthy profit margin")
    if financials.get("debt_to_equity", 0) > 0:
        lines.append("good debt position")

    technicals = details.get("technicals", {}) or {}
    if technicals.get("volume_spike", 0) > 0:
        lines.append("volume spike")
    if technicals.get("rsi", 0) > 0:
        lines.append("supportive RSI")
    if technicals.get("price_trend", 0) > 0:
        lines.append("positive price trend")
    if technicals.get("momentum", 0) > 0:
        lines.append("positive momentum")
    if technicals.get("volatility", 0) > 0:
        lines.append("low volatility / stable profile")

    if not lines:
        lines.append("score supported by combined model factors")

    return lines[:4]


def build_daily_report(
    *,
    dt: datetime,
    market_open: bool,
    market_info: dict | None = None,
    universe_size: int,
    scan_set: list[dict],
    replacement_pool_size: int,
    rotations_out: list[dict] | None = None,
    rotations_in: list[dict] | None = None,
    orders: list[str] | None = None,
) -> str:
    rotations_out = rotations_out or []
    rotations_in = rotations_in or []
    orders = orders or []


    buy_rows = [
        row for row in scan_set
        if str(row.get("action") or "").strip().lower() == "buy_ready"
    ]

    hold_rows = [
        row for row in scan_set
        if str(row.get("action") or "").strip().lower() == "hold_candidate"
    ]

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("TRADING BOT DAILY REPORT")
    lines.append(f"Log date UTC: {dt.strftime('%Y-%m-%d')}")
    lines.append(f"Log time UTC: {dt.strftime('%H:%M:%S UTC')}")
    for line in _market_lines(market_info):
        lines.append(line)
    lines.append(f"Universe size: {universe_size}")
    lines.append(f"Scan set size: {len(scan_set)}")
    lines.append(f"Replacement pool: {replacement_pool_size}")
    lines.append("=" * 60)
    lines.append("")

    lines.append("SCAN SET")
    if scan_set:
        for row in scan_set:
            lines.append(f"- {_friendly_name(row)}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("ROTATION")
    lines.append("OUT")
    if rotations_out:
        for row in rotations_out:
            lines.append(
                f"- {_friendly_name(row)} → removed because {row.get('reason', 'rule triggered')}"
            )
    else:
        lines.append("- None")

    lines.append("")
    lines.append("IN")
    if rotations_in:
        for row in rotations_in:
            lines.append(f"- {_friendly_name(row)} → added as replacement candidate")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("BUY SIGNALS")
    if buy_rows:
        for row in buy_rows:
            lines.append(f"- {_friendly_name(row)}")
            lines.append(f"  Score: {row.get('total_score', 'n/a')}")
            lines.append("  Why:")
            for reason in _reason_lines(row):
                lines.append(f"  - {reason}")
            action = "Simulated only, market closed" if not market_open else "Eligible for execution"
            lines.append(f"  Action: {action}")
            lines.append("")
    else:
        lines.append("- None")
        lines.append("")

    lines.append("HOLD SIGNALS")
    if hold_rows:
        for row in hold_rows:
            lines.append(f"- {_friendly_name(row)}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("ORDERS")
    if orders:
        for order in orders:
            lines.append(f"- {order}")
    else:
        lines.append("- No real orders placed")
        if not market_open:
            lines.append("Reason: Market closed")

    return "\n".join(lines) + "\n"


def build_cycle_journal(
    *,
    dt: datetime,
    market_open: bool,
    market_info: dict | None = None,
    universe_size: int,
    scan_set: list[dict],
    replacement_pool_size: int,
    portfolio: list[dict] | None = None,
    rotations_out: list[dict] | None = None,
    rotations_in: list[dict] | None = None,
    orders: list[str] | None = None,
) -> str:
    portfolio = portfolio or []
    rotations_out = rotations_out or []
    rotations_in = rotations_in or []
    orders = orders or []

    buy_rows = [
        row for row in scan_set
        if str(row.get("action") or "").strip().lower() == "buy_ready"
    ]

    watch_rows = [
        row for row in scan_set
        if str(row.get("action") or "").strip().lower() == "watch"
    ]

    hold_rows = [
        row for row in scan_set
        if str(row.get("action") or "").strip().lower() == "hold_candidate"
    ]

    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("AUTOSCAN JOURNAL")

    lines.append("=" * 70)
    for line in _market_lines(market_info):
        lines.append(line)
    lines.append(f"Log timestamp UTC  : {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"Universe size      : {universe_size}")

    lines.append(f"Scan set size      : {len(scan_set)}")
    lines.append(f"Replacement pool   : {replacement_pool_size}")
    lines.append(f"Portfolio rows     : {len(portfolio)}")
    lines.append("")

    lines.append("HELD / PORTFOLIO REVIEW")
    if portfolio:
        for row in portfolio:
            sym = row.get("symbol", "?")
            signal = row.get("signal", "-")
            action = row.get("action", "-")
            quality = row.get("candidate_quality", row.get("quality", "-"))
            score = row.get("entry_score", row.get("score", "-"))
            timing = row.get("timing_state", "-")
            exit_reason = row.get("exit_reason", "-")
            lines.append(
                f"- {sym:6} | signal={signal} | action={action} | "
                f"quality={quality} | score={score} | timing={timing} | exit={exit_reason}"
            )
    else:
        lines.append("- None")
    lines.append("")

    lines.append("BUY READY")
    if buy_rows:
        for row in buy_rows:
            lines.append(
                f"- {row.get('symbol', '?'):6} | "
                f"score={row.get('total_score', 'n/a')} | "
                f"quality={row.get('candidate_quality', '-')} | "
                f"timing={row.get('timing_state', '-')}"
            )
    else:
        lines.append("- None")
    lines.append("")

    lines.append("WATCH")
    if watch_rows:
        for row in watch_rows:
            lines.append(
                f"- {row.get('symbol', '?'):6} | "
                f"score={row.get('total_score', 'n/a')} | "
                f"timing={row.get('timing_state', '-')}"
            )
    else:
        lines.append("- None")
    lines.append("")

    lines.append("HOLD")
    if hold_rows:
        for row in hold_rows:
            lines.append(f"- {row.get('symbol', '?')}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("ROTATION OUT")
    if rotations_out:
        for row in rotations_out:
            lines.append(
                f"- {row.get('symbol', '?')} | reason={row.get('reason', 'rule triggered')}"
            )
    else:
        lines.append("- None")
    lines.append("")

    lines.append("ROTATION IN")
    if rotations_in:
        for row in rotations_in:
            lines.append(f"- {row.get('symbol', '?')}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("ORDERS")
    if orders:
        for order in orders:
            lines.append(f"- {order}")
    else:
        lines.append("- None")
    lines.append("")
    lines.append("")

    return "\n".join(lines)



def save_daily_report(
    *,
    market_open: bool,
    market_info: dict | None = None,
    universe_size: int,
    scan_set: list[dict],
    replacement_pool_size: int,
    rotations_out: list[dict] | None = None,
    rotations_in: list[dict] | None = None,
    orders: list[str] | None = None,
) -> Path:
    dt = now_utc()
    report = build_daily_report(
        dt=dt,
        market_open=market_open,
        market_info=market_info,
        universe_size=universe_size,
        scan_set=scan_set,
        replacement_pool_size=replacement_pool_size,
        rotations_out=rotations_out,
        rotations_in=rotations_in,
        orders=orders,
    )
    path = get_report_path(dt)
    overwrite_text(path, report)
    return path


def save_cycle_journal(
    *,
    market_open: bool,
    market_info: dict | None = None,
    universe_size: int,
    scan_set: list[dict],
    replacement_pool_size: int,
    portfolio: list[dict] | None = None,
    rotations_out: list[dict] | None = None,
    rotations_in: list[dict] | None = None,
    orders: list[str] | None = None,
) -> Path:
    dt = now_utc()
    journal = build_cycle_journal(
        dt=dt,
        market_open=market_open,
        market_info=market_info,
        universe_size=universe_size,
        scan_set=scan_set,
        replacement_pool_size=replacement_pool_size,
        portfolio=portfolio,
        rotations_out=rotations_out,
        rotations_in=rotations_in,
        orders=orders,
    )
    path = get_journal_path(dt)
    append_text(path, journal)
    return path