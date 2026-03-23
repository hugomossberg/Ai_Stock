import logging
import os

_USE_COLOR = not bool(os.getenv("NO_COLOR", "").strip())

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"

_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_BLUE = "\033[34m"
_CYAN = "\033[36m"
_GRAY = "\033[90m"


def _c(text: str, color: str = "", bold: bool = False, dim: bool = False) -> str:
    if not _USE_COLOR:
        return str(text)

    prefix = ""
    if bold:
        prefix += _BOLD
    if dim:
        prefix += _DIM
    prefix += color
    return f"{prefix}{text}{_RESET}"

def is_debug() -> bool:
    return os.getenv("DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def debug_log(log: logging.Logger, msg: str, *args):
    if is_debug():
        log.info(msg, *args)


def fmt_sym_list(items: list[str]) -> str:
    return ", ".join(items) if items else "-"


def log_section(log: logging.Logger, title: str):
    line = "-" * 78
    log.info("%s", _c(line, _GRAY))
    log.info("%s", _c(title, _CYAN, bold=True))
    log.info("%s", _c(line, _GRAY))


def _to_float(value, default=None):
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        return float(value)
    except Exception:
        return default


def _fmt_price(value) -> str:
    v = _to_float(value, None)
    if v is None:
        return "-"
    return f"{v:.2f}"


def _fmt_score(value) -> str:
    try:
        v = int(value)
    except Exception:
        return "-"

    if v <= -999:
        return _c(str(v), _RED, bold=True)
    if v > 0:
        return _c(f"{v:+d}", _GREEN, bold=True)
    if v < 0:
        return _c(f"{v:+d}", _RED, bold=True)
    return _c(f"{v:+d}", _YELLOW)


def log_signal_line(log: logging.Logger, label: str, sym: str, qty: int, price, score):
    label = (label or "").strip().upper()

    if label == "BUY":
        sig_txt = _c("BUY       ", _GREEN, bold=True)
    elif label == "ADD":
        sig_txt = _c("ADD       ", _GREEN, bold=True)
    elif label == "EXIT":
        sig_txt = _c("EXIT      ", _RED, bold=True)
    elif label == "EXIT SOON":
        sig_txt = _c("EXIT SOON ", _YELLOW, bold=True)
    elif label == "EXIT WATCH":
        sig_txt = _c("EXIT WATCH", _CYAN, bold=True)
    elif label == "WATCH":
        sig_txt = _c("WATCH     ", _CYAN, bold=True)
    elif label == "WAIT":
        sig_txt = _c("WAIT      ", _BLUE, bold=True)
    elif label == "CHECK":
        sig_txt = _c("CHECK     ", _RED, bold=True)
    else:
        sig_txt = _c("HOLD      ", _YELLOW, bold=True)

    sym_txt = _c(f"{sym:<6}", _CYAN, bold=True)
    qty_txt = _c(f"x{qty:<2}", _BLUE)
    price_txt = _c(f"price {_fmt_price(price):>7}", _GRAY)
    score_txt = f"score {_fmt_score(score)}"

    log.info("%s %s %s | %s | %s", sig_txt, sym_txt, qty_txt, price_txt, score_txt)


def short_reason_line(row: dict) -> str:
    sym = row.get("symbol", "?")
    action = str(row.get("action") or "").lower()
    score = row.get("total_score")
    entry_score = row.get("entry_score")
    quality = row.get("candidate_quality")
    reasons = row.get("entry_reasons") or []

    above_sma = "price_above_sma20" in reasons
    below_sma = "price_below_sma20" in reasons
    trend_up = "sma20_above_or_equal_sma50" in reasons
    good_rsi = any(r in reasons for r in {"healthy_rsi", "acceptable_rsi"})
    high_rsi = "slightly_extended_rsi" in reasons
    good_volume = "ok_volume_confirmation" in reasons
    strong_momentum = any(r in reasons for r in {"strong_short_momentum", "strong_medium_momentum"})
    controlled_vol = "controlled_volatility" in reasons

    tags = []

    if action == "buy_ready":
        if above_sma:
            tags.append("above SMA20")
        if trend_up:
            tags.append("uptrend")
        if good_rsi:
            tags.append("good RSI")
        elif high_rsi:
            tags.append("slightly high RSI")
        if good_volume:
            tags.append("good volume")
        if strong_momentum:
            tags.append("strong momentum")
        if controlled_vol:
            tags.append("controlled volatility")

        return f"{sym}: buy setup | score {score} | entry {entry_score} | q {quality} | " + ", ".join(tags[:4])

    if action == "watch":
        if below_sma:
            tags.append("below SMA20")
        elif above_sma:
            tags.append("above SMA20")
        if trend_up:
            tags.append("uptrend")
        if good_rsi:
            tags.append("ok RSI")
        elif high_rsi:
            tags.append("high RSI")
        if good_volume:
            tags.append("good volume")
        if strong_momentum:
            tags.append("momentum present")

        return f"{sym}: watch setup | score {score} | entry {entry_score} | q {quality} | " + ", ".join(tags[:4])

    if action in {"exit_ready", "sell_candidate", "exit_watch"}:
        if below_sma:
            tags.append("below SMA20")
        if not trend_up:
            tags.append("weak trend")
        if high_rsi:
            tags.append("extended")

        return f"{sym}: exit setup | score {score} | entry {entry_score} | q {quality} | " + ", ".join(tags[:4])

    return f"{sym}: {action} | score {score} | entry {entry_score} | q {quality}"