"""
Swarm Scanner — parallel multi-worker equity universe scan.

Architecture (mirrors claude-flow "one task per agent" principle):
  - Universe split into sector buckets  →  each bucket = one agent task
  - ThreadPoolExecutor runs N workers concurrently (default 8)
  - Each worker runs the full 8-engine quant analysis on its slice
  - Coordinator merges, dedupes, and ranks all results

claude-flow integration:
  A companion script `scripts/swarm_orchestrate.sh` can be used to launch
  this scan via `claude-flow task` commands.  Inside each task claude-flow
  calls `POST /scan/bucket` which maps to `scan_bucket()` below.
  When claude-flow is not available the same logic runs natively via threads.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# How many parallel workers (sector buckets) to run
DEFAULT_WORKERS = 8
# Per-symbol timeout in seconds (skip if analysis hangs)
SYMBOL_TIMEOUT_SEC = 20


def run_swarm_scan(
    universe:    list[dict],
    data_engine,
    feature_engine,
    decision_engine,
    risk_engine,
    n_workers:   int = DEFAULT_WORKERS,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> dict:
    """
    Run a full parallel scan across the entire universe.

    Args:
        universe:       List of {symbol, name, sector} dicts
        *_engine:       Shared engine singletons (thread-safe reads)
        n_workers:      Number of concurrent worker threads
        on_progress:    Optional callback(done_count, total, current_symbol)

    Returns:
        Aggregated scan result dict (same schema as ScanEngine.run())
    """
    from backend.scanner.full_universe import bucket_by_sector

    total   = len(universe)
    buckets = bucket_by_sector(universe, n_workers=n_workers)
    logger.info(
        "Swarm scan: %d symbols across %d workers (%d buckets)",
        total, n_workers, len(buckets),
    )

    all_results:   list[dict] = []
    done_count = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = {
            pool.submit(
                _scan_bucket,
                bucket, data_engine, feature_engine, decision_engine, risk_engine,
            ): bucket
            for bucket in buckets
        }

        for fut in as_completed(futures):
            bucket = futures[fut]
            try:
                bucket_results = fut.result(timeout=600)
                all_results.extend(bucket_results)
                done_count += len(bucket)
                if on_progress:
                    on_progress(done_count, total, f"bucket of {len(bucket)}")
            except Exception as e:
                logger.warning("Bucket failed (%s): %s", bucket[0]["sector"] if bucket else "?", e)
                done_count += len(bucket)

    elapsed = round(time.time() - t0, 1)
    return _aggregate(all_results, universe, elapsed)


def _scan_bucket(
    bucket:          list[dict],
    data_engine,
    feature_engine,
    decision_engine,
    risk_engine,
) -> list[dict]:
    """Worker: analyse every symbol in one sector bucket."""
    results: list[dict] = []
    for item in bucket:
        sym = item["symbol"]
        try:
            df       = data_engine.get_ohlcv(sym)
            news     = data_engine.get_news(sym)
            price    = float(df["Close"].iloc[-1])
            features = feature_engine.compute(df, news)
            decision = decision_engine.decide(features["signals"], features)
            risk     = risk_engine.compute(
                df, current_price=price,
                atr=features["atr"],
                portfolio_value=1_000_000,
            )
            breakdown = decision.get("signal_breakdown", {})
            top_signal = (
                max(breakdown, key=lambda k: abs(breakdown[k].get("contribution", 0)))
                if breakdown else "—"
            )
            results.append({
                "symbol":     sym,
                "name":       item.get("name", sym),
                "sector":     item.get("sector", "Others"),
                "price":      round(price, 2),
                "action":     decision.get("action", "HOLD"),
                "confidence": decision.get("confidence", 0),
                "score":      decision.get("final_score", 0),
                "top_signal": top_signal,
                "signals_agree": decision.get("signals_agree", 0),
                "signal_breakdown": breakdown,
                "stop_loss":  risk.get("stop_loss", {}).get("price"),
                "risk_level": risk.get("risk_level", "MEDIUM"),
                "atr":        round(float(features.get("atr", 0)), 2),
                "rsi":        round(float(features.get("rsi", 50)), 1),
                "trend":      features.get("trend", "NEUTRAL"),
                "error":      None,
            })
        except Exception as e:
            results.append({
                "symbol":  sym,
                "name":    item.get("name", sym),
                "sector":  item.get("sector", "Others"),
                "action":  "ERROR",
                "error":   str(e)[:120],
            })
    return results


def _aggregate(results: list[dict], universe: list[dict], elapsed: float) -> dict:
    """Merge bucket results into the standard scan summary schema."""
    valid = [r for r in results if r.get("action") not in (None, "ERROR")]
    errors = [r for r in results if r.get("action") == "ERROR"]

    buys  = sorted(
        [r for r in valid if r.get("action") == "BUY"],
        key=lambda x: -x.get("confidence", 0),
    )
    sells = sorted(
        [r for r in valid if r.get("action") == "SELL"],
        key=lambda x: -x.get("confidence", 0),
    )
    holds = [r for r in valid if r.get("action") == "HOLD"]

    # Sector summary
    sector_breakdown: dict[str, dict] = {}
    for r in valid:
        sec = r.get("sector", "Others")
        if sec not in sector_breakdown:
            sector_breakdown[sec] = {"buys": 0, "sells": 0, "holds": 0, "total": 0}
        sector_breakdown[sec]["total"] += 1
        action = r.get("action", "HOLD").lower()
        if action in sector_breakdown[sec]:
            sector_breakdown[sec][action] += 1

    from datetime import datetime
    return {
        "scan_type":      "full_universe",
        "scan_time":      datetime.now().isoformat(),
        "elapsed_sec":    elapsed,
        "total_scanned":  len(valid),
        "universe_size":  len(universe),
        "total_errors":   len(errors),
        "summary": {
            "buy_count":  len(buys),
            "sell_count": len(sells),
            "hold_count": len(holds),
            "error_count": len(errors),
        },
        "sector_breakdown": sector_breakdown,
        "top_buys":    buys[:20],
        "top_sells":   sells[:20],
        "holds":       holds[:10],
        "all":         valid,
        "errors":      errors[:20],
    }


# ── claude-flow compatible single-bucket scan ──────────────────────────────────

def scan_bucket_by_symbols(
    symbols: list[str],
    meta:    dict[str, dict],
    data_engine,
    feature_engine,
    decision_engine,
    risk_engine,
) -> list[dict]:
    """
    Scan a specific list of symbols.
    Called by the /scan/bucket endpoint which claude-flow agents invoke.
    """
    bucket = [{"symbol": s, **meta.get(s, {"name": s, "sector": "Others"})}
              for s in symbols]
    return _scan_bucket(bucket, data_engine, feature_engine, decision_engine, risk_engine)
