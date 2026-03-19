from datetime import datetime
from zoneinfo import ZoneInfo
from ib_insync import MarketOrder

US_TZ = ZoneInfo("America/New_York")


def is_us_market_open(now_et=None) -> bool:
    now_et = now_et or datetime.now(US_TZ)
    if now_et.weekday() >= 5:
        return False
    start = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    end = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    return start <= now_et <= end


async def sell_all(update, context):
    ib_client = context.application.bot_data.get("ib")
    if not ib_client:
        return await update.message.reply_text("Ingen IB-klient i bot_data.")

    ib = ib_client.ib
    if not ib.isConnected():
        return await update.message.reply_text("IB ej ansluten.")

    is_open = is_us_market_open()

    try:
        positions = await ib.reqPositionsAsync()
    except Exception as e:
        return await update.message.reply_text(f"Kunde inte läsa positioner: {e}")

    sent = []
    skipped = []

    for p in positions:
        qty = float(p.position or 0.0)
        if abs(qty) < 1e-6:
            continue

        if not float(abs(qty)).is_integer():
            skipped.append(f"• {p.contract.symbol}: fractional {abs(qty)}")
            continue

        action = "SELL" if qty > 0 else "BUY"
        order = MarketOrder(action, int(abs(qty)))

        try:
            order.outsideRth = False if is_open else True
        except Exception:
            pass

        try:
            contract = p.contract
            contract.exchange = "SMART"
            ib.placeOrder(contract, order)
            sent.append(f"• {contract.symbol} {action} {int(abs(qty))}")
        except Exception as e:
            skipped.append(f"• {p.contract.symbol}: {e}")

    if not sent and not skipped:
        return await update.message.reply_text("Inga positioner att stänga.")

    msg = []
    if sent:
        msg.append("📤 Skickade stängningsorder:\n" + "\n".join(sent))
    if skipped:
        msg.append("⚠️ Skippade:\n" + "\n".join(skipped))

    await update.message.reply_text("\n\n".join(msg))


async def sell_one(update, context, symbol: str, qty: int | None = None):
    ib_client = context.application.bot_data.get("ib")
    if not ib_client:
        return await update.message.reply_text("Ingen IB-klient i bot_data.")

    ib = ib_client.ib
    if not ib.isConnected():
        return await update.message.reply_text("IB ej ansluten.")

    try:
        positions = await ib.reqPositionsAsync()
    except Exception as e:
        return await update.message.reply_text(f"Kunde inte läsa positioner: {e}")

    pos = None
    for p in positions:
        if (p.contract.symbol or "").upper() == symbol.upper() and abs(float(p.position or 0.0)) > 1e-6:
            pos = p
            break

    if not pos:
        return await update.message.reply_text(f"Hittade ingen öppen position i {symbol}.")

    current_qty = float(pos.position or 0.0)

    if not float(abs(current_qty)).is_integer():
        return await update.message.reply_text(
            f"{symbol} har fractional position ({current_qty}), sälj manuellt i TWS."
        )

    sell_qty = int(abs(current_qty)) if qty is None else min(int(abs(current_qty)), qty)
    action = "SELL" if current_qty > 0 else "BUY"
    order = MarketOrder(action, sell_qty)

    try:
        contract = pos.contract
        contract.exchange = "SMART"
        ib.placeOrder(contract, order)
        return await update.message.reply_text(f"📤 Skickade order: {action} {sell_qty} {symbol}")
    except Exception as e:
        return await update.message.reply_text(f"Kunde inte sälja {symbol}: {e}")