"""
Full NSE Equity Universe.

Primary source (when Kite is authenticated):
  kite.instruments("NSE")  →  ~2000 EQ symbols, loaded via kite_provider.load_instruments()

Fallback (yfinance session):
  Nifty 500 + Nifty MidSmallcap400 composite list (~700 symbols)
  Downloaded from NSE's publicly available bhavcopy/index CSV files via yfinance.

Sector bucketing is used by the parallel swarm scanner to assign each worker
a different slice of the market.
"""
from __future__ import annotations
import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)


# ── Fallback: Nifty 500 + popular mid/small caps beyond Nifty 50 ──────────────
# Nifty 50 is already in universe.py; this extends it.
NIFTY_MIDCAP_SYMBOLS: list[dict] = [
    # Banking / NBFC
    {"symbol": "BANDHANBNK.NS",  "name": "Bandhan Bank",           "sector": "Banking"},
    {"symbol": "FEDERALBNK.NS",  "name": "Federal Bank",           "sector": "Banking"},
    {"symbol": "IDFCFIRSTB.NS",  "name": "IDFC First Bank",        "sector": "Banking"},
    {"symbol": "CANBK.NS",       "name": "Canara Bank",            "sector": "Banking"},
    {"symbol": "BANKBARODA.NS",  "name": "Bank of Baroda",         "sector": "Banking"},
    {"symbol": "PNB.NS",         "name": "Punjab National Bank",   "sector": "Banking"},
    {"symbol": "UNIONBANK.NS",   "name": "Union Bank",             "sector": "Banking"},
    {"symbol": "YESBANK.NS",     "name": "Yes Bank",               "sector": "Banking"},
    {"symbol": "RBLBANK.NS",     "name": "RBL Bank",               "sector": "Banking"},
    {"symbol": "KARURVYSYA.NS",  "name": "Karur Vysya Bank",       "sector": "Banking"},
    {"symbol": "CHOLAFIN.NS",    "name": "Cholamandalam Finance",  "sector": "NBFC"},
    {"symbol": "MUTHOOTFIN.NS",  "name": "Muthoot Finance",        "sector": "NBFC"},
    {"symbol": "M&MFIN.NS",      "name": "M&M Financial",          "sector": "NBFC"},
    {"symbol": "LICHSGFIN.NS",   "name": "LIC Housing Finance",    "sector": "NBFC"},
    {"symbol": "PNBHOUSING.NS",  "name": "PNB Housing Finance",    "sector": "NBFC"},
    {"symbol": "MANAPPURAM.NS",  "name": "Manappuram Finance",     "sector": "NBFC"},
    # IT
    {"symbol": "LTIM.NS",        "name": "LTIMindtree",            "sector": "IT"},
    {"symbol": "MPHASIS.NS",     "name": "Mphasis",                "sector": "IT"},
    {"symbol": "COFORGE.NS",     "name": "Coforge",                "sector": "IT"},
    {"symbol": "PERSISTENT.NS",  "name": "Persistent Systems",     "sector": "IT"},
    {"symbol": "LTTS.NS",        "name": "L&T Technology",         "sector": "IT"},
    {"symbol": "KPITTECH.NS",    "name": "KPIT Technologies",      "sector": "IT"},
    {"symbol": "TATAELXSI.NS",   "name": "Tata Elxsi",             "sector": "IT"},
    {"symbol": "HEXAWARE.NS",    "name": "Hexaware",               "sector": "IT"},
    {"symbol": "NIITLTD.NS",     "name": "NIIT",                   "sector": "IT"},
    # Pharma / Healthcare
    {"symbol": "TORNTPHARM.NS",  "name": "Torrent Pharma",         "sector": "Pharma"},
    {"symbol": "BIOCON.NS",      "name": "Biocon",                 "sector": "Pharma"},
    {"symbol": "LUPIN.NS",       "name": "Lupin",                  "sector": "Pharma"},
    {"symbol": "AUROPHARMA.NS",  "name": "Aurobindo Pharma",       "sector": "Pharma"},
    {"symbol": "ALKEM.NS",       "name": "Alkem Labs",             "sector": "Pharma"},
    {"symbol": "GLAXO.NS",       "name": "GSK Pharma",             "sector": "Pharma"},
    {"symbol": "PFIZER.NS",      "name": "Pfizer India",           "sector": "Pharma"},
    {"symbol": "SANOFI.NS",      "name": "Sanofi India",           "sector": "Pharma"},
    {"symbol": "METROPOLIS.NS",  "name": "Metropolis Healthcare",  "sector": "Healthcare"},
    {"symbol": "LALPATHLAB.NS",  "name": "Dr Lal PathLabs",        "sector": "Healthcare"},
    {"symbol": "FORTIS.NS",      "name": "Fortis Healthcare",      "sector": "Healthcare"},
    {"symbol": "MAXHEALTH.NS",   "name": "Max Healthcare",         "sector": "Healthcare"},
    {"symbol": "AARTIIND.NS",    "name": "Aarti Industries",       "sector": "Chemicals"},
    {"symbol": "PIDILITIND.NS",  "name": "Pidilite Industries",    "sector": "Chemicals"},
    {"symbol": "DEEPAKNTR.NS",   "name": "Deepak Nitrite",         "sector": "Chemicals"},
    {"symbol": "NAVINFLUOR.NS",  "name": "Navin Fluorine",         "sector": "Chemicals"},
    {"symbol": "FINEORG.NS",     "name": "Fine Organic",           "sector": "Chemicals"},
    # Auto & Auto Ancillaries
    {"symbol": "MOTHERSON.NS",   "name": "Motherson Sumi",         "sector": "Auto Ancillary"},
    {"symbol": "BOSCHLTD.NS",    "name": "Bosch India",            "sector": "Auto Ancillary"},
    {"symbol": "BHARATFORG.NS",  "name": "Bharat Forge",           "sector": "Auto Ancillary"},
    {"symbol": "EXIDEIND.NS",    "name": "Exide Industries",       "sector": "Auto Ancillary"},
    {"symbol": "AMARARAJA.NS",   "name": "Amara Raja Energy",      "sector": "Auto Ancillary"},
    {"symbol": "MRF.NS",         "name": "MRF",                    "sector": "Auto Ancillary"},
    {"symbol": "APOLLOTYRE.NS",  "name": "Apollo Tyres",           "sector": "Auto Ancillary"},
    {"symbol": "TVSMOTOR.NS",    "name": "TVS Motor",              "sector": "Auto"},
    {"symbol": "ASHOKLEY.NS",    "name": "Ashok Leyland",          "sector": "Auto"},
    {"symbol": "FORCEMOT.NS",    "name": "Force Motors",           "sector": "Auto"},
    # FMCG / Consumer
    {"symbol": "DABUR.NS",       "name": "Dabur India",            "sector": "FMCG"},
    {"symbol": "MARICO.NS",      "name": "Marico",                 "sector": "FMCG"},
    {"symbol": "COLPAL.NS",      "name": "Colgate-Palmolive",      "sector": "FMCG"},
    {"symbol": "GODREJCP.NS",    "name": "Godrej Consumer",        "sector": "FMCG"},
    {"symbol": "EMAMILTD.NS",    "name": "Emami",                  "sector": "FMCG"},
    {"symbol": "BAJAJCON.NS",    "name": "Bajaj Consumer",         "sector": "FMCG"},
    {"symbol": "PGHH.NS",        "name": "P&G Hygiene",            "sector": "FMCG"},
    {"symbol": "JUBLFOOD.NS",    "name": "Jubilant FoodWorks",     "sector": "Consumer"},
    {"symbol": "DEVYANI.NS",     "name": "Devyani International",  "sector": "Consumer"},
    {"symbol": "TRENT.NS",       "name": "Trent",                  "sector": "Consumer"},
    {"symbol": "VCATVL.NS",      "name": "Vedant Fashions",        "sector": "Consumer"},
    {"symbol": "PAGEIND.NS",     "name": "Page Industries",        "sector": "Consumer"},
    {"symbol": "KALYANKJIL.NS",  "name": "Kalyan Jewellers",       "sector": "Consumer"},
    {"symbol": "MANYAVAR.NS",    "name": "Vedant Fashions",        "sector": "Consumer"},
    # Energy / Oil & Gas
    {"symbol": "IOC.NS",         "name": "Indian Oil Corp",        "sector": "Energy"},
    {"symbol": "HINDPETRO.NS",   "name": "HPCL",                   "sector": "Energy"},
    {"symbol": "GAIL.NS",        "name": "GAIL India",             "sector": "Energy"},
    {"symbol": "PETRONET.NS",    "name": "Petronet LNG",           "sector": "Energy"},
    {"symbol": "INDIAMART.NS",   "name": "IndiaMart",              "sector": "Technology"},
    {"symbol": "NAUKRI.NS",      "name": "Info Edge",              "sector": "Technology"},
    {"symbol": "ZOMATO.NS",      "name": "Zomato",                 "sector": "Technology"},
    {"symbol": "PAYTM.NS",       "name": "Paytm",                  "sector": "Technology"},
    {"symbol": "POLICYBZR.NS",   "name": "PB Fintech",             "sector": "Technology"},
    {"symbol": "DELHIVERY.NS",   "name": "Delhivery",              "sector": "Technology"},
    {"symbol": "NYKAA.NS",       "name": "FSN E-Commerce (Nykaa)", "sector": "Technology"},
    # Metals / Mining
    {"symbol": "VEDL.NS",        "name": "Vedanta",                "sector": "Metals"},
    {"symbol": "NMDC.NS",        "name": "NMDC",                   "sector": "Metals"},
    {"symbol": "SAIL.NS",        "name": "SAIL",                   "sector": "Metals"},
    {"symbol": "NATIONALUM.NS",  "name": "National Aluminium",     "sector": "Metals"},
    {"symbol": "RATNAMANI.NS",   "name": "Ratnamani Metals",       "sector": "Metals"},
    # Infra / Construction / Real Estate
    {"symbol": "DLF.NS",         "name": "DLF",                    "sector": "Real Estate"},
    {"symbol": "GODREJPROP.NS",  "name": "Godrej Properties",      "sector": "Real Estate"},
    {"symbol": "OBEROIRLTY.NS",  "name": "Oberoi Realty",          "sector": "Real Estate"},
    {"symbol": "PHOENIXLTD.NS",  "name": "Phoenix Mills",          "sector": "Real Estate"},
    {"symbol": "SOBHA.NS",       "name": "Sobha",                  "sector": "Real Estate"},
    {"symbol": "PRESTIGE.NS",    "name": "Prestige Estates",       "sector": "Real Estate"},
    {"symbol": "NCC.NS",         "name": "NCC",                    "sector": "Infra"},
    {"symbol": "KNRCON.NS",      "name": "KNR Constructions",      "sector": "Infra"},
    {"symbol": "PNC.NS",         "name": "PNC Infratech",          "sector": "Infra"},
    {"symbol": "IRCON.NS",       "name": "IRCON International",    "sector": "Infra"},
    {"symbol": "RVNL.NS",        "name": "Rail Vikas Nigam",       "sector": "Infra"},
    {"symbol": "IRFC.NS",        "name": "Indian Railway Finance", "sector": "NBFC"},
    # Power / Utilities
    {"symbol": "TATAPOWER.NS",   "name": "Tata Power",             "sector": "Power"},
    {"symbol": "TORNTPOWER.NS",  "name": "Torrent Power",          "sector": "Power"},
    {"symbol": "CESC.NS",        "name": "CESC",                   "sector": "Power"},
    {"symbol": "NHPC.NS",        "name": "NHPC",                   "sector": "Power"},
    {"symbol": "SJVN.NS",        "name": "SJVN",                   "sector": "Power"},
    {"symbol": "ADANIGREEN.NS",  "name": "Adani Green Energy",     "sector": "Power"},
    {"symbol": "ADANIPOWER.NS",  "name": "Adani Power",            "sector": "Power"},
    # Insurance / Diversified Financials
    {"symbol": "ICICIGI.NS",     "name": "ICICI Lombard",          "sector": "Insurance"},
    {"symbol": "ICICIPRULI.NS",  "name": "ICICI Prudential Life",  "sector": "Insurance"},
    {"symbol": "BAJAJHLDNG.NS",  "name": "Bajaj Holdings",         "sector": "Conglomerate"},
    {"symbol": "ANGELONE.NS",    "name": "Angel One",              "sector": "NBFC"},
    {"symbol": "CDSL.NS",        "name": "CDSL",                   "sector": "NBFC"},
    {"symbol": "BSE.NS",         "name": "BSE",                    "sector": "NBFC"},
    # Cement
    {"symbol": "AMBUJACEM.NS",   "name": "Ambuja Cements",         "sector": "Cement"},
    {"symbol": "ACC.NS",         "name": "ACC",                    "sector": "Cement"},
    {"symbol": "SHREECEM.NS",    "name": "Shree Cement",           "sector": "Cement"},
    {"symbol": "DALMIACHEM.NS",  "name": "Dalmia Bharat",          "sector": "Cement"},
    {"symbol": "RAMCOCEM.NS",    "name": "Ramco Cements",          "sector": "Cement"},
    # Defence / Aerospace
    {"symbol": "HAL.NS",         "name": "HAL",                    "sector": "Defence"},
    {"symbol": "BEML.NS",        "name": "BEML",                   "sector": "Defence"},
    {"symbol": "MAZDOCK.NS",     "name": "Mazagon Dock",           "sector": "Defence"},
    {"symbol": "COCHINSHIP.NS",  "name": "Cochin Shipyard",        "sector": "Defence"},
    {"symbol": "PARAS.NS",       "name": "Paras Defence",          "sector": "Defence"},
    # Telecom / Media
    {"symbol": "IDEA.NS",        "name": "Vodafone Idea",          "sector": "Telecom"},
    {"symbol": "INDUSTOWER.NS",  "name": "Indus Towers",           "sector": "Telecom"},
    {"symbol": "HFCL.NS",        "name": "HFCL",                   "sector": "Telecom"},
    {"symbol": "ZEEL.NS",        "name": "Zee Entertainment",      "sector": "Media"},
    {"symbol": "PVRINOX.NS",     "name": "PVR INOX",               "sector": "Media"},
    # Textiles
    {"symbol": "PAGEIND.NS",     "name": "Page Industries",        "sector": "Textiles"},
    {"symbol": "WELSPUNIND.NS",  "name": "Welspun India",          "sector": "Textiles"},
    {"symbol": "TRIDENT.NS",     "name": "Trident",                "sector": "Textiles"},
    {"symbol": "RAYMOND.NS",     "name": "Raymond",                "sector": "Textiles"},
    # Agri / Fertilisers
    {"symbol": "UPL.NS",         "name": "UPL",                    "sector": "Agri"},
    {"symbol": "COROMANDEL.NS",  "name": "Coromandel Intl",        "sector": "Agri"},
    {"symbol": "PIIND.NS",       "name": "PI Industries",          "sector": "Agri"},
    {"symbol": "ATUL.NS",        "name": "Atul",                   "sector": "Chemicals"},
    {"symbol": "GSFC.NS",        "name": "Gujarat State Fertilizers","sector": "Agri"},
    {"symbol": "NFL.NS",         "name": "National Fertilizers",   "sector": "Agri"},
    # Logistics / Transport
    {"symbol": "CONCOR.NS",      "name": "Container Corp",         "sector": "Logistics"},
    {"symbol": "BLUEDART.NS",    "name": "Blue Dart",              "sector": "Logistics"},
    {"symbol": "VRL.NS",         "name": "VRL Logistics",          "sector": "Logistics"},
    {"symbol": "TCI.NS",         "name": "TCI",                    "sector": "Logistics"},
    # Hotels / Travel
    {"symbol": "INDHOTEL.NS",    "name": "Indian Hotels",          "sector": "Hotels"},
    {"symbol": "LEMONTRE.NS",    "name": "Lemon Tree Hotels",      "sector": "Hotels"},
    {"symbol": "EIHOTEL.NS",     "name": "EIH (Oberoi Hotels)",    "sector": "Hotels"},
    {"symbol": "MAHINDCIE.NS",   "name": "Mahindra CIE",           "sector": "Auto Ancillary"},
    {"symbol": "SCHAEFFLER.NS",  "name": "Schaeffler India",       "sector": "Auto Ancillary"},
    {"symbol": "TIMKEN.NS",      "name": "Timken India",           "sector": "Auto Ancillary"},
]

# Deduplicate by symbol
_seen: set[str] = set()
_deduped: list[dict] = []
for _item in NIFTY_MIDCAP_SYMBOLS:
    if _item["symbol"] not in _seen:
        _seen.add(_item["symbol"])
        _deduped.append(_item)
NIFTY_MIDCAP_SYMBOLS = _deduped


def get_full_universe(kite=None) -> list[dict]:
    """
    Return the full tradeable NSE equity universe.

    Priority:
      1. Kite instruments API  (~2000 EQ symbols, when authenticated)
      2. NSE public CSV        (~1800 EQ symbols, fetched/cached daily)
      3. Static fallback list  (~200 curated symbols)
    """
    from backend.scanner.universe import NIFTY50

    if kite is not None:
        try:
            from backend.data_engine.kite_provider import (
                load_instruments, _meta_map,
            )
            tokens = load_instruments(kite)
            if len(tokens) > 100:
                nifty_meta = {s["symbol"]: s for s in NIFTY50 + NIFTY_MIDCAP_SYMBOLS}
                result: list[dict] = []
                # NSE first, then BSE
                nse_syms = sorted(s for s in tokens if s.endswith(".NS"))
                bse_syms = sorted(s for s in tokens if s.endswith(".BO"))
                for sym in nse_syms + bse_syms:
                    meta   = nifty_meta.get(sym)
                    raw    = _meta_map.get(sym, {})
                    name   = meta["name"]   if meta else raw.get("name", sym.split(".")[0])
                    sector = meta["sector"] if meta else "Others"
                    result.append({"symbol": sym, "name": name, "sector": sector})
                logger.info("Full universe: %d NSE+BSE equities (Kite)", len(result))
                return result
        except Exception as e:
            logger.warning("Could not load Kite universe: %s — trying NSE public", e)

    # Try NSE public CSV (~1800 EQ symbols, cached 24h)
    try:
        from backend.scanner.nse_public import fetch_nse_all_equities
        nse_list = fetch_nse_all_equities()
        if len(nse_list) > 100:
            # Enrich with curated name/sector overrides from static list
            override = {s["symbol"]: s for s in NIFTY50 + NIFTY_MIDCAP_SYMBOLS}
            enriched: list[dict] = []
            for item in nse_list:
                ov = override.get(item["symbol"])
                enriched.append({
                    "symbol": item["symbol"],
                    "name":   ov["name"]   if ov else item["name"],
                    "sector": ov["sector"] if ov and ov["sector"] != "Others" else item["sector"],
                })
            logger.info("Full universe: %d NSE equities (NSE public CSV)", len(enriched))
            return enriched
    except Exception as e:
        logger.warning("NSE public fetch failed: %s — using static fallback", e)

    # Static fallback: Nifty 50 + midcap extension
    combined = {s["symbol"]: s for s in NIFTY50 + NIFTY_MIDCAP_SYMBOLS}
    result = list(combined.values())
    logger.info("Full universe: %d symbols (static fallback)", len(result))
    return result


def bucket_by_sector(universe: list[dict], n_workers: int = 8) -> list[list[dict]]:
    """
    Split universe into n_workers sector-affinity buckets.

    Stocks with the same sector tend to be in the same bucket; remaining
    stocks are round-robined across buckets.  Each bucket is a list of
    dicts with {symbol, name, sector}.
    """
    # Group by sector
    sector_groups: dict[str, list[dict]] = {}
    for item in universe:
        sector_groups.setdefault(item["sector"], []).append(item)

    buckets: list[list[dict]] = [[] for _ in range(n_workers)]
    bucket_idx = 0
    for sector, stocks in sorted(sector_groups.items(), key=lambda x: -len(x[1])):
        # Assign each sector's stocks to the least-loaded bucket
        target = min(range(n_workers), key=lambda i: len(buckets[i]))
        for stock in stocks:
            # If this bucket would grow too large, spread to neighbours
            assigned = min(range(n_workers), key=lambda i: len(buckets[i]))
            buckets[assigned].append(stock)

    # Remove empty buckets
    return [b for b in buckets if b]


def get_symbols_only(universe: list[dict]) -> list[str]:
    return [s["symbol"] for s in universe]
