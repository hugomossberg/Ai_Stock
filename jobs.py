# jobs.py
import os
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from yfinance_stock import analyse_stock
from chatgpt_client import auto_scan_and_trade

def env_bool(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, "1" if default else "0")).lower() in {"1","true","on","yes"}

def setup_jobs(app, ib_client):
    refresh_minutes = int(os.getenv("REFRESH_MINUTES", "10"))
    autoscan = env_bool("AUTOSCAN", False)
    admin_chat_id = int(os.getenv("ADMIN_CHAT_ID", "0") or 0)

    scheduler = AsyncIOScheduler()

    # 1) Uppdatera Stock_info.json regelbundet
    async def run_analyse():
        await analyse_stock(ib_client)

    scheduler.add_job(
        run_analyse, "interval",
        minutes=refresh_minutes,
        coalesce=True, max_instances=1,
        next_run_time=datetime.now() + timedelta(seconds=5),
        misfire_grace_time=60
    )

    # 2) Valfritt: autoscan/trade strax efter
    if autoscan:
        async def run_autoscan():
            await auto_scan_and_trade(app.bot, ib_client, admin_chat_id)

        scheduler.add_job(
            run_autoscan, "interval",
            minutes=refresh_minutes,
            coalesce=True, max_instances=1,
            next_run_time=datetime.now() + timedelta(seconds=30),
            misfire_grace_time=60
        )

    scheduler.start()
    return scheduler
