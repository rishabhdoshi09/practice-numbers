"""
Alert system for JARVIS morning calls.
Channels: terminal (always), email (optional), future: WhatsApp/Telegram.
"""
from __future__ import annotations
import os
import smtplib
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

ALERT_EMAIL_FROM    = os.getenv("ALERT_EMAIL_FROM", "")
ALERT_EMAIL_TO      = os.getenv("ALERT_EMAIL_TO", "")
ALERT_EMAIL_PASS    = os.getenv("ALERT_EMAIL_PASS", "")   # Gmail App Password
ALERT_EMAIL_ENABLED = bool(ALERT_EMAIL_FROM and ALERT_EMAIL_TO and ALERT_EMAIL_PASS)


# ── Terminal alert ─────────────────────────────────────────────────────────────

def terminal_alert(scan_result: dict, label: str = "MARKET OPEN"):
    """Print a formatted JARVIS-style summary to the terminal."""
    now      = datetime.now().strftime("%d %b %Y  %H:%M IST")
    buys     = scan_result.get("top_buys",  [])
    sells    = scan_result.get("top_sells", [])
    elapsed  = scan_result.get("elapsed_sec", 0)
    summary  = scan_result.get("summary", {})

    CYAN  = "\033[96m"
    GREEN = "\033[92m"
    RED   = "\033[91m"
    YELLOW= "\033[93m"
    BOLD  = "\033[1m"
    RESET = "\033[0m"

    border = "═" * 62
    print(f"\n{CYAN}{BOLD}{border}{RESET}")
    print(f"{CYAN}{BOLD}  ⚡  SIMPLEQUANT JARVIS — {label}{RESET}")
    print(f"{CYAN}  {now}  |  {scan_result['total_scanned']} stocks in {elapsed}s{RESET}")
    print(f"{CYAN}{border}{RESET}")

    print(f"\n{GREEN}{BOLD}  ▲ TOP BUY CALLS ({summary.get('buy_count',0)} total){RESET}")
    for i, s in enumerate(buys[:5], 1):
        print(f"  {i}. {BOLD}{s['name']:<22}{RESET} {s['symbol']:<16} "
              f"{GREEN}BUY{RESET}  conf={s['confidence']:.0f}%  "
              f"₹{s['price']:>8.2f}  stop=₹{s['stop_loss']:>8.2f}  "
              f"[{s['sector']}]")

    print(f"\n{RED}{BOLD}  ▼ TOP SELL CALLS ({summary.get('sell_count',0)} total){RESET}")
    for i, s in enumerate(sells[:5], 1):
        print(f"  {i}. {BOLD}{s['name']:<22}{RESET} {s['symbol']:<16} "
              f"{RED}SELL{RESET} conf={s['confidence']:.0f}%  "
              f"₹{s['price']:>8.2f}  stop=₹{s['stop_loss']:>8.2f}  "
              f"[{s['sector']}]")

    print(f"\n{YELLOW}  — WAIT: {summary.get('hold_count',0)} stocks{RESET}")
    print(f"{CYAN}{border}{RESET}\n")


# ── Email alert ────────────────────────────────────────────────────────────────

def email_alert(scan_result: dict, subject: str = "SimpleQuant JARVIS — Morning Calls"):
    """Send HTML email with scan results. Requires Gmail App Password in .env."""
    if not ALERT_EMAIL_ENABLED:
        return

    buys  = scan_result.get("top_buys",  [])
    sells = scan_result.get("top_sells", [])

    def rows(stocks, color):
        return "".join(
            f"<tr>"
            f"<td style='padding:6px 12px'><b>{s['name']}</b></td>"
            f"<td style='padding:6px 12px;color:{color};font-weight:bold'>{s['action']}</td>"
            f"<td style='padding:6px 12px'>{s['confidence']:.0f}%</td>"
            f"<td style='padding:6px 12px'>₹{s['price']:,.2f}</td>"
            f"<td style='padding:6px 12px;color:#ef4444'>₹{s['stop_loss']:,.2f}</td>"
            f"<td style='padding:6px 12px'>{s['sector']}</td>"
            f"</tr>"
            for s in stocks[:5]
        )

    header = """
    <th style='padding:6px 12px;text-align:left;background:#1e293b;color:#94a3b8'>Stock</th>
    <th style='padding:6px 12px;background:#1e293b;color:#94a3b8'>Signal</th>
    <th style='padding:6px 12px;background:#1e293b;color:#94a3b8'>Confidence</th>
    <th style='padding:6px 12px;background:#1e293b;color:#94a3b8'>Price</th>
    <th style='padding:6px 12px;background:#1e293b;color:#94a3b8'>Stop Loss</th>
    <th style='padding:6px 12px;background:#1e293b;color:#94a3b8'>Sector</th>
    """

    html = f"""
    <html><body style='font-family:Inter,sans-serif;background:#0f172a;color:#e2e8f0;padding:24px'>
    <h2 style='color:#38bdf8'>⚡ SimpleQuant JARVIS</h2>
    <p style='color:#94a3b8'>{datetime.now().strftime("%d %b %Y %H:%M IST")} —
    {scan_result['total_scanned']} stocks scanned in {scan_result['elapsed_sec']}s</p>

    <h3 style='color:#22c55e'>▲ Top BUY Calls</h3>
    <table style='border-collapse:collapse;width:100%'>
    <tr>{header}</tr>{rows(buys, '#22c55e')}</table>

    <h3 style='color:#ef4444'>▼ Top SELL Calls</h3>
    <table style='border-collapse:collapse;width:100%'>
    <tr>{header}</tr>{rows(sells, '#ef4444')}</table>

    <p style='color:#475569;font-size:12px;margin-top:24px'>
    SimpleQuant — Paper trading only. Not financial advice.</p>
    </body></html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = ALERT_EMAIL_FROM
        msg["To"]      = ALERT_EMAIL_TO
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(ALERT_EMAIL_FROM, ALERT_EMAIL_PASS)
            server.sendmail(ALERT_EMAIL_FROM, ALERT_EMAIL_TO, msg.as_string())
        logger.info("Email alert sent to %s", ALERT_EMAIL_TO)
    except Exception as e:
        logger.warning("Email alert failed: %s", e)


def send_alerts(scan_result: dict, label: str = "MARKET OPEN"):
    """Fire all configured alert channels."""
    terminal_alert(scan_result, label)
    email_alert(scan_result, f"SimpleQuant JARVIS — {label}")
