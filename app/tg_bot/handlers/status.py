from datetime import datetime
from zoneinfo import ZoneInfo

SE_TZ = ZoneInfo("Europe/Stockholm")
US_TZ = ZoneInfo("America/New_York")


def is_us_market_open(now_et=None) -> bool:
    now_et = now_et or datetime.now(US_TZ)
    if now_et.weekday() >= 5:
        return False
    start = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    end = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    return start <= now_et <= end


async def send_status(update, context):
    ack = await update.message.reply_text("🔎 Kollar status…")
    ib_client = context.application.bot_data.get("ib")
    if not ib_client:
        return await ack.edit_text("Ingen IB-klient i bot_data.")

    ib = ib_client.ib
    connected = ib.isConnected()

    now_se = datetime.now(SE_TZ)
    now_et = datetime.now(US_TZ)
    market_open = is_us_market_open(now_et)

    pos_lines = []
    ord_lines = []

    try:
        if connected:
            positions = await ib.reqPositionsAsync()

            nonzero = []
            seen = set()
            for p in positions:
                qty = float(p.position or 0.0)
                if abs(qty) < 1e-6:
                    continue
                key = p.contract.conId or (p.contract.symbol, p.contract.exchange)
                if key in seen:
                    continue
                seen.add(key)
                nonzero.append(p)

            positions_sorted = sorted(
                nonzero,
                key=lambda p: abs(float(p.position or 0.0)),
                reverse=True,
            )

            max_rows = 10
            for p in positions_sorted[:max_rows]:
                sym = p.contract.symbol
                qty = float(p.position or 0.0)
                qty_str = str(int(qty)) if float(qty).is_integer() else f"{qty:.2f}"
                avg = float(p.avgCost or 0.0)
                pos_lines.append(f"• {sym}: {qty_str} @ {avg:.2f}")

            extra = len(positions_sorted) - min(len(positions_sorted), max_rows)
            if extra > 0:
                pos_lines.append(f"… +{extra} till")

            await ib.reqOpenOrdersAsync()
            for t in ib.openTrades()[:5]:
                s = t.contract.symbol
                side = t.order.action
                qty = int(t.order.totalQuantity)
                filled = int(t.orderStatus.filled or 0)
                st = t.orderStatus.status or "?"
                rth = "AH" if getattr(t.order, "outsideRth", False) else "RTH"
                ord_lines.append(f"• {s} {side} {filled}/{qty} ({st}, {rth})")

    except Exception as e:
        if not pos_lines:
            pos_lines = ["(kunde inte läsa positioner)"]
        if not ord_lines:
            ord_lines = [f"(kunde inte läsa öppna ordrar: {e})"]

    pos_text = "\n".join(pos_lines) if pos_lines else "–"
    ord_text = "\n".join(ord_lines) if ord_lines else "–"

    msg = (
        f"✅ IB connected: {connected}\n"
        f"   SE {now_se:%Y-%m-%d %H:%M} | ET {now_et:%H:%M}\n"
        f"   US Market open: {'JA' if market_open else 'NEJ'} (ord. 15:30–22:00 SE)\n"
        f"\nPositioner (topp):\n{pos_text}"
        f"\n\nÖppna ordrar:\n{ord_text}"
    )

    await ack.edit_text(msg)