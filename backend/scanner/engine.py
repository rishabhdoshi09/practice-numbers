"""
ScanEngine: parallel analysis of every Nifty 50 stock.
Produces a ranked BUY / SELL / HOLD list in under 15 seconds.
"""
from __future__ import annotations
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Callable, Optional

from backend.feature_engine import FeatureEngine
from backend.decision_engine import DecisionEngine
from backend.risk_engine import RiskEngine
from backend.scanner.universe import NIFTY50_SYMBOLS, SYMBOL_META

logger = logging.getLogger(__name__)

# Reuse engine instances — they are stateless per call
_feature  = FeatureEngine()
_decision = DecisionEngine()
_risk     = RiskEngine()


class ScanEngine:
    """Scans the full Nifty 50 universe and ranks opportunities."""

    def __init__(self, data_engine):
        self._data = data_engine
        self._last_result: Optional[dict] = None
        self._last_scan_time: Optional[datetime] = None

    def run(
        self,
        symbols: list[str] = NIFTY50_SYMBOLS,
        max_workers: int = 10,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> dict:
        """
        Scan all symbols in parallel.

        Args:
            symbols:      List of NSE tickers to scan.
            max_workers:  Thread pool size (10 = ~5s for Nifty 50).
            on_progress:  Callback(done, total, symbol) for live progress updates.

        Returns:
            Ranked scan result dict.
        """
        t_start = time.time()
        total   = len(symbols)
        done    = 0
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(self._analyse_one, sym): sym for sym in symbols}
            for future in as_completed(futures):
                sym = futures[future]
                done += 1
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.warning("Scan failed for %s: %s", sym, e)
                if on_progress:
                    on_progress(done, total, sym)

        elapsed = round(time.time() - t_start, 2)

        # Sort each bucket by confidence descending
        buys  = sorted([r for r in results if r["action"] == "BUY"],  key=lambda x: -x["confidence"])
        sells = sorted([r for r in results if r["action"] == "SELL"], key=lambda x: -x["confidence"])
        holds = sorted([r for r in results if r["action"] == "HOLD"], key=lambda x: -abs(x["score"]))

        scan_result = {
            "scan_time":     datetime.now().isoformat(),
            "elapsed_sec":   elapsed,
            "total_scanned": len(results),
            "universe_size": total,
            "summary": {
                "buy_count":  len(buys),
                "sell_count": len(sells),
                "hold_count": len(holds),
            },
            "top_buys":  buys[:10],
            "top_sells": sells[:10],
            "holds":     holds[:5],
            "all":       sorted(results, key=lambda x: -x["confidence"]),
        }

        self._last_result    = scan_result
        self._last_scan_time = datetime.now()
        logger.info("Scan complete: %d stocks in %.2fs — %d BUY, %d SELL, %d HOLD",
                    len(results), elapsed, len(buys), len(sells), len(holds))
        return scan_result

    def last_result(self) -> Optional[dict]:
        return self._last_result

    # ── Private ────────────────────────────────────────────────────────────────

    def _analyse_one(self, symbol: str) -> Optional[dict]:
        """Run full pipeline on one symbol — runs in a thread."""
        try:
            df    = self._data.get_ohlcv(symbol)
            news  = self._data.get_news(symbol)
            price = float(df["Close"].iloc[-1])

            features = _feature.compute(df, news)
            decision = _decision.decide(features["signals"], features)
            risk     = _risk.compute(df, current_price=price, atr=features["atr"])

            meta = SYMBOL_META.get(symbol, {})

            # Find strongest contributing signal
            breakdown  = decision.get("signal_breakdown", {})
            top_signal = (
                max(breakdown, key=lambda k: abs(breakdown[k].get("contribution", 0)))
                if breakdown else "—"
            )

            return {
                "symbol":      symbol,
                "name":        meta.get("name", symbol),
                "sector":      meta.get("sector", "—"),
                "price":       round(price, 2),
                "action":      decision["action"],
                "confidence":  decision["confidence"],
                "risk_level":  decision["risk_level"],
                "score":       decision["final_score"],
                "top_signal":  top_signal,
                "stop_loss":   risk["stop_loss"]["price"],
                "var_95_pct":  risk["var"]["var_95_pct"],
                "signals_agree": decision["signals_agree"],
                "recommended_inr": risk["position_sizing"]["recommended_inr"],
            }
        except Exception as e:
            logger.debug("_analyse_one failed %s: %s", symbol, e)
            return None
