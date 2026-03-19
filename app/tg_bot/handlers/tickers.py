from app.tg_bot.stock_data import get_all_symbols, get_stock_info_updated_time


async def send_tickers(update, context):
    try:
        syms_all = get_all_symbols()
    except Exception:
        await update.message.reply_text("Kunde inte läsa Stock_info.json.")
        return

    held_syms = set()
    ib_client = context.application.bot_data.get("ib")
    if ib_client and ib_client.ib.isConnected():
        try:
            positions = await ib_client.ib.reqPositionsAsync()
            for p in positions:
                qty = float(p.position or 0.0)
                if abs(qty) > 1e-6:
                    held_syms.add((p.contract.symbol or "").upper())
        except Exception:
            pass

    scan_syms = [s for s in syms_all if s and s not in held_syms]
    port_syms = sorted(held_syms)

    try:
        updated = get_stock_info_updated_time()
    except Exception:
        updated = "okänd tid"

    def chunk_lines(items, chunk=12, max_items=120):
        items = items[:max_items]
        lines = []
        for i in range(0, len(items), chunk):
            lines.append("· " + " · ".join(items[i:i+chunk]))
        return "\n".join(lines) if items else "–"

    msg_parts = []
    msg_parts.append(f" Universum (ej ägda): {len(scan_syms)}\n{chunk_lines(scan_syms)}")
    msg_parts.append(f" Portfölj (ägda): {len(port_syms)}\n{chunk_lines(port_syms)}")
    msg_parts.append(f" Stock_info.json uppdaterad: {updated}")
    await update.message.reply_text("\n\n".join(msg_parts))