"""
Volume Profile Engine — core calculation module.

Computes the full volume distribution across price levels for a given
OHLCV DataFrame and identifies key market structure levels:

  POC  — Point of Control: price level with the highest volume
  VAH  — Value Area High: upper boundary of 70% volume zone
  VAL  — Value Area Low:  lower boundary of 70% volume zone
  HVN  — High Volume Nodes: peaks in volume distribution (acceptance zones)
  LVN  — Low Volume Nodes: troughs in volume distribution (rejection zones)
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass, field


@dataclass
class VolumeProfile:
    poc:       float
    vah:       float
    val:       float
    hvn:       list[float]
    lvn:       list[float]
    bins:      list[float]          # bin midpoint prices
    volumes:   list[float]          # volume at each bin
    bin_size:  float
    total_vol: float
    va_vol:    float

    # ── Convenience helpers ────────────────────────────────────────────────
    def nearest_lvn_above(self, price: float) -> float | None:
        above = [l for l in sorted(self.lvn) if l > price]
        return above[0] if above else None

    def nearest_lvn_below(self, price: float) -> float | None:
        below = [l for l in sorted(self.lvn) if l < price]
        return below[-1] if below else None

    def nearest_hvn_above(self, price: float) -> float | None:
        above = [h for h in sorted(self.hvn) if h > price]
        return above[0] if above else None

    def nearest_hvn_below(self, price: float) -> float | None:
        below = [h for h in sorted(self.hvn) if h < price]
        return below[-1] if below else None

    def price_zone(self, price: float) -> str:
        """Classify where the given price sits relative to the value area."""
        if price > self.vah:
            return "ABOVE_VA"
        elif price < self.val:
            return "BELOW_VA"
        else:
            return "INSIDE_VA"

    def in_hvn(self, price: float, tolerance: float = 0.002) -> bool:
        return any(abs(price - h) / h < tolerance for h in self.hvn)

    def in_lvn(self, price: float, tolerance: float = 0.002) -> bool:
        return any(abs(price - l) / l < tolerance for l in self.lvn)

    def to_dict(self) -> dict:
        return {
            "poc":       round(self.poc,       2),
            "vah":       round(self.vah,       2),
            "val":       round(self.val,       2),
            "hvn":       [round(h, 2) for h in self.hvn],
            "lvn":       [round(l, 2) for l in self.lvn],
            "bins":      [round(b, 2) for b in self.bins],
            "volumes":   [round(v, 0) for v in self.volumes],
            "bin_size":  round(self.bin_size,  2),
            "total_vol": round(self.total_vol, 0),
            "va_vol":    round(self.va_vol,    0),
        }


def calculate_volume_profile(
    df:            pd.DataFrame,
    n_bins:        int   = 50,
    value_area_pct: float = 0.70,
    hvn_sigma:     float = 1.2,    # std deviations above mean → HVN
    lvn_sigma:     float = 0.5,    # std deviations below mean → LVN
) -> VolumeProfile:
    """
    Build a volume profile from OHLCV data.

    Volume is distributed across price bins proportionally to the
    fraction of each candle's range that falls within each bin.

    Args:
        df:             OHLCV DataFrame (columns: Open, High, Low, Close, Volume)
        n_bins:         Number of price bins (resolution)
        value_area_pct: Fraction of total volume that defines the Value Area
        hvn_sigma:      Bins above (mean + hvn_sigma×std) are High Volume Nodes
        lvn_sigma:      Bins below (mean - lvn_sigma×std) are Low Volume Nodes

    Returns:
        VolumeProfile dataclass
    """
    if df.empty or len(df) < 5:
        raise ValueError("Need at least 5 rows to compute a volume profile")

    price_lo = float(df["Low"].min())
    price_hi = float(df["High"].max())
    if price_hi <= price_lo:
        raise ValueError("All candles have the same price range")

    bin_size = (price_hi - price_lo) / n_bins
    edges    = np.linspace(price_lo, price_hi, n_bins + 1)
    centers  = (edges[:-1] + edges[1:]) / 2
    vols     = np.zeros(n_bins)

    # Distribute each candle's volume across overlapping bins
    for _, row in df.iterrows():
        low  = float(row["Low"])
        high = float(row["High"])
        vol  = float(row["Volume"])
        if vol <= 0:
            continue

        # Clamp to overall range
        low  = max(low,  price_lo)
        high = min(high, price_hi)
        rng  = high - low

        if rng == 0:
            idx = int(np.clip((low - price_lo) / bin_size, 0, n_bins - 1))
            vols[idx] += vol
        else:
            s_bin = int(np.clip((low  - price_lo) / bin_size, 0, n_bins - 1))
            e_bin = int(np.clip((high - price_lo) / bin_size, 0, n_bins - 1))
            for b in range(s_bin, e_bin + 1):
                b_lo = price_lo + b * bin_size
                b_hi = b_lo + bin_size
                overlap = min(high, b_hi) - max(low, b_lo)
                if overlap > 0:
                    vols[b] += vol * (overlap / rng)

    total_vol = float(vols.sum())
    if total_vol == 0:
        raise ValueError("Total volume is zero — check data")

    # ── POC ───────────────────────────────────────────────────────────────
    poc_idx = int(np.argmax(vols))
    poc     = float(centers[poc_idx])

    # ── Value Area (expand outward from POC until target_vol reached) ────
    target_vol = total_vol * value_area_pct
    va_vol     = float(vols[poc_idx])
    upper_idx  = poc_idx
    lower_idx  = poc_idx

    while va_vol < target_vol:
        can_up = upper_idx < n_bins - 1
        can_dn = lower_idx > 0
        if not can_up and not can_dn:
            break
        up_v = float(vols[upper_idx + 1]) if can_up else -1.0
        dn_v = float(vols[lower_idx - 1]) if can_dn else -1.0
        if up_v >= dn_v:
            upper_idx += 1
            va_vol    += float(vols[upper_idx])
        else:
            lower_idx -= 1
            va_vol    += float(vols[lower_idx])

    vah = float(centers[upper_idx])
    val = float(centers[lower_idx])

    # ── HVN / LVN ─────────────────────────────────────────────────────────
    mean_vol = float(np.mean(vols))
    std_vol  = float(np.std(vols))

    hvn_threshold = mean_vol + hvn_sigma * std_vol
    lvn_threshold = max(0, mean_vol - lvn_sigma * std_vol)

    hvn_prices = [float(centers[i]) for i in range(n_bins)
                  if vols[i] >= hvn_threshold]
    lvn_prices = [float(centers[i]) for i in range(n_bins)
                  if 0 < vols[i] <= lvn_threshold]

    # Merge neighbouring HVN/LVN clusters (price within 2 bins = same node)
    hvn_prices = _merge_clusters(hvn_prices, bin_size * 2.5)
    lvn_prices = _merge_clusters(lvn_prices, bin_size * 2.5)

    return VolumeProfile(
        poc=poc, vah=vah, val=val,
        hvn=hvn_prices, lvn=lvn_prices,
        bins=centers.tolist(), volumes=vols.tolist(),
        bin_size=bin_size,
        total_vol=total_vol,
        va_vol=va_vol,
    )


def _merge_clusters(prices: list[float], gap: float) -> list[float]:
    """Merge neighbouring levels that are within *gap* of each other."""
    if not prices:
        return []
    sorted_p = sorted(prices)
    clusters: list[list[float]] = [[sorted_p[0]]]
    for p in sorted_p[1:]:
        if p - clusters[-1][-1] <= gap:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    return [float(np.mean(c)) for c in clusters]


def fetch_vp_ohlcv(symbol: str, timeframe: str = "1d", lookback: int = 60) -> pd.DataFrame:
    """
    Fetch OHLCV data for VP calculation.

    timeframe: '5m' | '15m' | '1d'
    lookback:  number of periods (candles) to use
    """
    import yfinance as yf

    tf_map = {
        "5m":  ("5d",    "5m"),
        "15m": ("1mo",   "15m"),
        "1d":  ("1y",    "1d"),
    }
    period, interval = tf_map.get(timeframe, ("1y", "1d"))

    df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No data returned for {symbol} ({timeframe})")

    df.columns = [c.capitalize() for c in df.columns]
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    return df.tail(lookback)
