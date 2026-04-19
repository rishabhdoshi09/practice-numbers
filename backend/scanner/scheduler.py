"""
JARVIS Scheduler — APScheduler jobs for automatic market scanning.

Schedule (IST):
  09:15  Market open scan  → top BUY/SELL calls for the day
  11:00  Mid-morning rescan (optional refresh)
  13:00  Midday pulse
  15:20  Pre-close scan
  15:30  End-of-day summary + P&L report
"""
from __future__ import annotations
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from backend.scanner.alerts import send_alerts

logger  = logging.getLogger(__name__)
IST     = pytz.timezone("Asia/Kolkata")

# Injected at startup
_scan_engine = None
_ws_broadcast = None    # async broadcast function set by main.py


def init_scheduler(scan_engine, ws_broadcast=None) -> BackgroundScheduler:
    """
    Create and start the APScheduler.
    Must be called after FastAPI app startup.
    """
    global _scan_engine, _ws_broadcast
    _scan_engine  = scan_engine
    _ws_broadcast = ws_broadcast

    scheduler = BackgroundScheduler(timezone=IST)

    # Market open — primary JARVIS call
    scheduler.add_job(
        _job_market_open,
        CronTrigger(hour=9, minute=15, timezone=IST),
        id="market_open",
        name="JARVIS Market Open Scan",
        replace_existing=True,
    )

    # Mid-morning refresh
    scheduler.add_job(
        _job_scan,
        CronTrigger(hour=11, minute=0, timezone=IST),
        id="midmorning",
        name="Mid-Morning Rescan",
        replace_existing=True,
    )

    # Midday pulse
    scheduler.add_job(
        _job_scan,
        CronTrigger(hour=13, minute=0, timezone=IST),
        id="midday",
        name="Midday Pulse",
        replace_existing=True,
    )

    # Pre-close
    scheduler.add_job(
        _job_scan,
        CronTrigger(hour=15, minute=20, timezone=IST),
        id="preclose",
        name="Pre-Close Scan",
        replace_existing=True,
    )

    # End of day summary
    scheduler.add_job(
        _job_eod_summary,
        CronTrigger(hour=15, minute=30, timezone=IST),
        id="eod_summary",
        name="End-of-Day Summary",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("JARVIS Scheduler started — 5 jobs scheduled (IST)")
    return scheduler


# ── Job functions ──────────────────────────────────────────────────────────────

def _job_market_open():
    """9:15 AM — full Nifty 50 scan with alerts."""
    logger.info("JARVIS: Market Open Scan starting...")
    result = _run_scan()
    if result:
        send_alerts(result, label="MARKET OPEN 9:15 AM")
        _broadcast(result)


def _job_scan():
    """Intraday refresh scans."""
    hour = datetime.now(IST).hour
    label = {11: "MID-MORNING 11:00", 13: "MIDDAY 1:00 PM", 15: "PRE-CLOSE 3:20 PM"}.get(hour, "RESCAN")
    logger.info("JARVIS: %s scan starting...", label)
    result = _run_scan()
    if result:
        send_alerts(result, label=label)
        _broadcast(result)


def _job_eod_summary():
    """3:30 PM — end of day summary."""
    logger.info("JARVIS: End-of-Day Summary")
    result = _scan_engine.last_result() if _scan_engine else None
    if result:
        send_alerts(result, label="END OF DAY 3:30 PM")
        _broadcast(result)


def _run_scan() -> dict | None:
    if not _scan_engine:
        logger.warning("ScanEngine not initialised")
        return None
    try:
        return _scan_engine.run()
    except Exception as e:
        logger.exception("Scheduled scan failed: %s", e)
        return None


def _broadcast(result: dict):
    """Push scan result to all connected WebSocket clients."""
    if _ws_broadcast:
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_ws_broadcast(result))
            loop.close()
        except Exception as e:
            logger.debug("WS broadcast error: %s", e)


def trigger_now(scan_engine) -> dict:
    """Manually trigger a scan right now (for testing or on-demand from API)."""
    global _scan_engine
    _scan_engine = scan_engine
    result = _run_scan()
    if result:
        send_alerts(result, label="ON-DEMAND SCAN")
    return result
