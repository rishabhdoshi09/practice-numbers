"""
Fetch the complete NSE equity list from NSE India's public CSV.

URL: https://archives.nseindia.com/content/equities/EQUITY_L.csv
Cache: .nse_equity_list.json  (refreshed daily)

Returns list of {symbol, name, sector} where symbol has .NS suffix.
Sector defaults to "Others" since the CSV doesn't carry sector — the caller
can enrich with yfinance info_cache if needed.
"""
from __future__ import annotations
import csv
import io
import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

_NSE_CSV_URL   = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
_BSE_CSV_URL   = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w?Group=&Scripcode=&industry=&segment=Equity&status=Active"
_CACHE_FILE    = ".nse_equity_list.json"
_CACHE_TTL     = 86_400   # 24 hours
_REQUEST_TIMEOUT = 15

# Known sector mapping from popular index constituents — used to enrich raw CSV
_SECTOR_HINTS: dict[str, str] = {
    # Banking
    "HDFCBANK": "Banking", "ICICIBANK": "Banking", "SBIN": "Banking",
    "KOTAKBANK": "Banking", "AXISBANK": "Banking", "BANDHANBNK": "Banking",
    "FEDERALBNK": "Banking", "IDFCFIRSTB": "Banking", "CANBK": "Banking",
    "BANKBARODA": "Banking", "PNB": "Banking", "UNIONBANK": "Banking",
    "YESBANK": "Banking", "RBLBANK": "Banking", "INDUSINDBK": "Banking",
    "AUBANK": "Banking", "KARURVYSYA": "Banking", "DCBBANK": "Banking",
    "EQUITASBNK": "Banking", "UJJIVANSFB": "Banking", "SURYODAY": "Banking",
    # NBFC / Finance
    "BAJFINANCE": "NBFC", "BAJAJFINSV": "NBFC", "CHOLAFIN": "NBFC",
    "MUTHOOTFIN": "NBFC", "LICHSGFIN": "NBFC", "PNBHOUSING": "NBFC",
    "MANAPPURAM": "NBFC", "ANGELONE": "NBFC", "CDSL": "NBFC", "BSE": "NBFC",
    "IRFC": "NBFC", "M&MFIN": "NBFC", "SHRIRAMFIN": "NBFC",
    # IT
    "TCS": "IT", "INFY": "IT", "WIPRO": "IT", "HCLTECH": "IT",
    "TECHM": "IT", "LTIM": "IT", "MPHASIS": "IT", "COFORGE": "IT",
    "PERSISTENT": "IT", "LTTS": "IT", "KPITTECH": "IT", "TATAELXSI": "IT",
    "HEXAWARE": "IT", "OFSS": "IT", "NIITLTD": "IT",
    # Pharma
    "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma",
    "DIVISLAB": "Pharma", "TORNTPHARM": "Pharma", "BIOCON": "Pharma",
    "LUPIN": "Pharma", "AUROPHARMA": "Pharma", "ALKEM": "Pharma",
    "GLAXO": "Pharma", "PFIZER": "Pharma", "SANOFI": "Pharma",
    # Healthcare
    "APOLLOHOSP": "Healthcare", "METROPOLIS": "Healthcare",
    "LALPATHLAB": "Healthcare", "FORTIS": "Healthcare", "MAXHEALTH": "Healthcare",
    # FMCG
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG",
    "DABUR": "FMCG", "MARICO": "FMCG", "COLPAL": "FMCG",
    "GODREJCP": "FMCG", "EMAMILTD": "FMCG", "PGHH": "FMCG",
    "BAJAJCON": "FMCG", "VBL": "FMCG", "TATACONSUM": "FMCG",
    # Auto
    "MARUTI": "Auto", "TATAMOTORS": "Auto", "M&M": "Auto",
    "BAJAJ-AUTO": "Auto", "HEROMOTOCO": "Auto", "TVSMOTOR": "Auto",
    "ASHOKLEY": "Auto", "FORCEMOT": "Auto", "EICHERMOT": "Auto",
    # Auto Ancillary
    "MOTHERSON": "Auto Ancillary", "BOSCHLTD": "Auto Ancillary",
    "BHARATFORG": "Auto Ancillary", "EXIDEIND": "Auto Ancillary",
    "AMARARAJA": "Auto Ancillary", "MRF": "Auto Ancillary",
    "APOLLOTYRE": "Auto Ancillary", "SCHAEFFLER": "Auto Ancillary",
    "TIMKEN": "Auto Ancillary", "MAHINDCIE": "Auto Ancillary",
    # Energy
    "RELIANCE": "Energy", "ONGC": "Energy", "IOC": "Energy",
    "BPCL": "Energy", "HINDPETRO": "Energy", "GAIL": "Energy",
    "PETRONET": "Energy", "MRPL": "Energy", "HPCL": "Energy",
    # Power
    "NTPC": "Power", "POWERGRID": "Power", "TATAPOWER": "Power",
    "TORNTPOWER": "Power", "CESC": "Power", "NHPC": "Power",
    "SJVN": "Power", "ADANIGREEN": "Power", "ADANIPOWER": "Power",
    "RPOWER": "Power", "JSWENERGY": "Power",
    # Metals
    "TATASTEEL": "Metals", "JSWSTEEL": "Metals", "HINDALCO": "Metals",
    "VEDL": "Metals", "NMDC": "Metals", "SAIL": "Metals",
    "NATIONALUM": "Metals", "RATNAMANI": "Metals", "APLAPOLLO": "Metals",
    # Cement
    "ULTRACEMCO": "Cement", "AMBUJACEM": "Cement", "ACC": "Cement",
    "SHREECEM": "Cement", "DALMIACHEM": "Cement", "RAMCOCEM": "Cement",
    # Consumer
    "ASIANPAINT": "Consumer", "TITAN": "Consumer", "JUBLFOOD": "Consumer",
    "DEVYANI": "Consumer", "TRENT": "Consumer", "PAGEIND": "Consumer",
    "KALYANKJIL": "Consumer", "MANYAVAR": "Consumer",
    # Real Estate
    "DLF": "Real Estate", "GODREJPROP": "Real Estate",
    "OBEROIRLTY": "Real Estate", "PHOENIXLTD": "Real Estate",
    "SOBHA": "Real Estate", "PRESTIGE": "Real Estate", "BRIGADE": "Real Estate",
    # Infra / Construction
    "LT": "Infra", "NCC": "Infra", "KNRCON": "Infra",
    "IRCON": "Infra", "RVNL": "Infra", "NBCC": "Infra",
    "HCC": "Infra", "PNCINFRA": "Infra",
    # Telecom
    "BHARTIARTL": "Telecom", "IDEA": "Telecom",
    "INDUSTOWER": "Telecom", "HFCL": "Telecom",
    # Technology / Internet
    "INDIAMART": "Technology", "NAUKRI": "Technology", "ZOMATO": "Technology",
    "PAYTM": "Technology", "POLICYBZR": "Technology",
    "DELHIVERY": "Technology", "NYKAA": "Technology",
    # Insurance
    "ICICIGI": "Insurance", "ICICIPRULI": "Insurance",
    "HDFCLIFE": "Insurance", "SBILIFE": "Insurance",
    "LICI": "Insurance",
    # Chemicals
    "AARTIIND": "Chemicals", "PIDILITIND": "Chemicals",
    "DEEPAKNTR": "Chemicals", "NAVINFLUOR": "Chemicals",
    "FINEORG": "Chemicals", "ATUL": "Chemicals",
    "VINATIORGA": "Chemicals", "TATACHEM": "Chemicals",
    # Agri / Fertilisers
    "UPL": "Agri", "COROMANDEL": "Agri", "PIIND": "Agri",
    "GSFC": "Agri", "NFL": "Agri", "CHAMBLFERT": "Agri",
    # Defence
    "HAL": "Defence", "BEML": "Defence", "MAZDOCK": "Defence",
    "COCHINSHIP": "Defence", "BEL": "Defence",
    # Logistics
    "CONCOR": "Logistics", "BLUEDART": "Logistics", "VRL": "Logistics",
    "TCI": "Logistics", "ALLCARGO": "Logistics",
    # Media
    "ZEEL": "Media", "PVRINOX": "Media", "SUNTV": "Media",
    # Hotels
    "INDHOTEL": "Hotels", "LEMONTRE": "Hotels", "EIHOTEL": "Hotels",
    # Textiles
    "WELSPUNIND": "Textiles", "TRIDENT": "Textiles", "RAYMOND": "Textiles",
    # Conglomerate
    "BAJAJHLDNG": "Conglomerate", "ADANIENT": "Conglomerate",
}


def _cache_valid() -> bool:
    if not os.path.exists(_CACHE_FILE):
        return False
    return time.time() - os.path.getmtime(_CACHE_FILE) < _CACHE_TTL


def _load_cache() -> Optional[list[dict]]:
    try:
        with open(_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(data: list[dict]) -> None:
    try:
        with open(_CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning("Could not save NSE equity cache: %s", e)


def _sector_for(raw_symbol: str) -> str:
    return _SECTOR_HINTS.get(raw_symbol.upper(), "Others")


def fetch_nse_all_equities(force: bool = False) -> list[dict]:
    """
    Download the complete NSE equity list CSV and return as
    [{symbol: 'XYZ.NS', name: '...', sector: '...'}].

    Results are cached for 24 hours.  Falls back to an empty list on failure
    so callers can merge with the static fallback list.
    """
    if not force and _cache_valid():
        cached = _load_cache()
        if cached:
            logger.debug("NSE equity list: loaded %d from cache", len(cached))
            return cached

    logger.info("Fetching NSE equity list from %s …", _NSE_CSV_URL)
    try:
        import urllib.request
        req = urllib.request.Request(
            _NSE_CSV_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/csv,*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.nseindia.com/",
            },
        )
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")

        result: list[dict] = []
        seen: set[str] = set()
        reader = csv.DictReader(io.StringIO(raw))
        for row in reader:
            raw_sym = (row.get("SYMBOL") or row.get(" SYMBOL") or "").strip()
            name    = (row.get("NAME OF COMPANY") or row.get(" NAME OF COMPANY") or "").strip().title()
            series  = (row.get("SERIES") or row.get(" SERIES") or "").strip()
            if not raw_sym or series != "EQ":
                continue
            ns_sym = raw_sym + ".NS"
            if ns_sym in seen:
                continue
            seen.add(ns_sym)
            result.append({
                "symbol": ns_sym,
                "name":   name or raw_sym,
                "sector": _sector_for(raw_sym),
            })

        if len(result) > 100:
            logger.info("NSE equity list: fetched %d symbols", len(result))
            _save_cache(result)
            return result
        else:
            logger.warning("NSE CSV too small (%d rows) — discarding", len(result))
            return []

    except Exception as e:
        logger.warning("NSE equity CSV fetch failed: %s", e)
        return []
