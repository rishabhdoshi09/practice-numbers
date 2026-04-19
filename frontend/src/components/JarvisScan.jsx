import React, { useState, useEffect, useRef, useCallback } from "react";
import clsx from "clsx";

const API    = process.env.REACT_APP_API_URL || "http://localhost:8000";
const WS_URL = API.replace("http", "ws") + "/ws/scan";

const ACTION_STYLE = {
  BUY:  { bar: "bg-buy",  text: "text-buy",  badge: "bg-buy/10 border-buy/30 text-buy"   },
  SELL: { bar: "bg-sell", text: "text-sell",  badge: "bg-sell/10 border-sell/30 text-sell"},
  HOLD: { bar: "bg-hold", text: "text-hold",  badge: "bg-hold/10 border-hold/30 text-hold"},
};

// ── Stock Card ─────────────────────────────────────────────────────────────────
function StockCard({ stock, onSelect }) {
  const style = ACTION_STYLE[stock.action] || ACTION_STYLE.HOLD;
  const sl    = typeof stock.stop_loss === "number" ? stock.stop_loss
              : stock.stop_loss?.price ?? null;
  return (
    <button
      onClick={() => onSelect(stock.symbol)}
      className="w-full text-left card hover:border-slate-500 transition-all duration-200 active:scale-[0.98]"
    >
      <div className="flex items-start justify-between mb-2">
        <div className="min-w-0 flex-1 pr-2">
          <p className="text-sm font-bold text-slate-100 leading-tight truncate">{stock.name}</p>
          <p className="text-xs text-slate-500">
            {stock.symbol.replace(".NS","")}&nbsp;·&nbsp;{stock.sector}
          </p>
        </div>
        <span className={clsx("badge border text-xs font-black shrink-0", style.badge)}>
          {stock.action}
        </span>
      </div>

      {/* Confidence bar */}
      <div className="flex items-center gap-2 mb-2">
        <div className="flex-1 h-1.5 bg-surface rounded-full overflow-hidden">
          <div
            className={clsx("h-full rounded-full transition-all duration-700", style.bar)}
            style={{ width: `${stock.confidence ?? 0}%` }}
          />
        </div>
        <span className={clsx("text-xs font-semibold font-mono", style.text)}>
          {(stock.confidence ?? 0).toFixed(0)}%
        </span>
      </div>

      <div className="flex justify-between text-xs text-slate-400">
        <span>₹{(stock.price || 0).toLocaleString("en-IN")}</span>
        {sl != null && (
          <span className="text-sell">Stop ₹{sl.toLocaleString("en-IN", { maximumFractionDigits: 1 })}</span>
        )}
        {stock.top_signal && (
          <span className="text-slate-500 truncate max-w-[90px]">{stock.top_signal}</span>
        )}
      </div>
    </button>
  );
}

// ── Summary Bar ────────────────────────────────────────────────────────────────
function SummaryBar({ summary, elapsed, scanTime, totalScanned, universeSize, isFullScan }) {
  const time = scanTime
    ? new Date(scanTime).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })
    : null;
  const buy  = summary?.buy_count  ?? summary?.buy  ?? 0;
  const sell = summary?.sell_count ?? summary?.sell ?? 0;
  const hold = summary?.hold_count ?? summary?.hold ?? 0;
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="badge bg-buy/10 border border-buy/30 text-buy">▲ {buy} BUY</span>
        <span className="badge bg-sell/10 border border-sell/30 text-sell">▼ {sell} SELL</span>
        <span className="badge bg-hold/10 border border-hold/30 text-hold">— {hold} WAIT</span>
        {isFullScan && (
          <span className="badge bg-sky-500/10 border border-sky-500/30 text-sky-400">
            🌐 Full NSE
          </span>
        )}
        <span className="text-xs text-slate-500 ml-auto">
          {totalScanned || (buy + sell + hold)} stocks
          {universeSize && universeSize !== totalScanned ? ` / ${universeSize} universe` : ""}
          {elapsed != null && ` · ${elapsed}s`}
          {time && ` · ${time}`}
        </span>
      </div>
    </div>
  );
}

// ── Sector Breakdown ───────────────────────────────────────────────────────────
function SectorBreakdown({ breakdown }) {
  if (!breakdown || !Object.keys(breakdown).length) return null;
  const sectors = Object.entries(breakdown)
    .sort((a, b) => b[1].total - a[1].total)
    .slice(0, 12);
  return (
    <div className="card space-y-2">
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Sector Breakdown</p>
      <div className="space-y-1.5">
        {sectors.map(([sec, d]) => (
          <div key={sec} className="flex items-center gap-2">
            <span className="text-xs text-slate-400 w-28 shrink-0 truncate">{sec}</span>
            <div className="flex-1 h-1.5 bg-surface rounded-full overflow-hidden flex gap-px">
              {d.buys > 0 && (
                <div className="bg-buy h-full rounded-l" style={{ width: `${d.buys / d.total * 100}%` }} />
              )}
              {d.sells > 0 && (
                <div className="bg-sell h-full" style={{ width: `${d.sells / d.total * 100}%` }} />
              )}
              {d.holds > 0 && (
                <div className="bg-hold h-full rounded-r" style={{ width: `${d.holds / d.total * 100}%` }} />
              )}
            </div>
            <span className="text-xs text-slate-500 w-6 text-right">{d.total}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────
export default function JarvisScan({ onSelectStock }) {
  const [scanData,    setScanData]    = useState(null);
  const [scanning,    setScanning]    = useState(false);
  const [tab,         setTab]         = useState("BUY");
  const [wsStatus,    setWsStatus]    = useState("disconnected");
  const [fullUniverse, setFullUniverse] = useState(true);
  const [universeInfo, setUniverseInfo] = useState(null);
  const [progress,    setProgress]    = useState({ done: 0, total: 0 });
  const wsRef = useRef(null);

  // ── Fetch universe info once ───────────────────────────────────────────────
  useEffect(() => {
    fetch(`${API}/scan/universe`)
      .then(r => r.json())
      .then(d => setUniverseInfo(d))
      .catch(() => {});
  }, []);

  // ── WebSocket: receive auto-pushed scan results ───────────────────────────
  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsStatus("live");
        const ping = setInterval(() => ws.readyState === 1 && ws.send("ping"), 30000);
        ws._pingInterval = ping;
      };

      ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === "scan_result" || data.type === "full_scan_result") {
          setScanData(data);
          setScanning(false);
        }
      };

      ws.onclose = () => {
        setWsStatus("disconnected");
        clearInterval(ws._pingInterval);
        setTimeout(connect, 3000);
      };

      ws.onerror = () => ws.close();
    };

    connect();
    return () => { wsRef.current?.close(); };
  }, []);

  // ── Manual scan trigger ───────────────────────────────────────────────────
  const triggerScan = useCallback(async () => {
    setScanning(true);
    setProgress({ done: 0, total: fullUniverse ? (universeInfo?.total || 200) : 50 });
    try {
      const endpoint = fullUniverse ? `${API}/scan/full?workers=8` : `${API}/scan`;
      const res  = await fetch(endpoint);
      const data = await res.json();
      setScanData(data);
    } catch (e) {
      console.error("Scan failed:", e);
    } finally {
      setScanning(false);
    }
  }, [fullUniverse, universeInfo]);

  // ── Derived data ──────────────────────────────────────────────────────────
  const stocks = tab === "BUY"  ? (scanData?.top_buys  || [])
               : tab === "SELL" ? (scanData?.top_sells || [])
               :                  (scanData?.holds     || []);

  const isFullScan = scanData?.scan_type === "full_universe";
  const totalCount = universeInfo?.total ?? 50;

  return (
    <div className="space-y-4 animate-slide-up">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <span className="text-sky-400">⚡</span> JARVIS Scanner
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {wsStatus === "live"
              ? <span className="text-buy">● Live — auto-updates at 9:15, 11:00, 13:00, 15:20 IST</span>
              : <span className="text-slate-500">○ Connecting…</span>}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {/* Full universe toggle */}
          <button
            onClick={() => setFullUniverse(!fullUniverse)}
            className={clsx(
              "text-xs px-2.5 py-1.5 rounded-lg font-semibold border transition-all",
              fullUniverse
                ? "bg-sky-500/20 text-sky-400 border-sky-500/30"
                : "bg-panel text-slate-500 border-border hover:text-slate-300"
            )}
            title={`Switch to ${fullUniverse ? "Nifty 50" : "Full NSE (~" + totalCount + " stocks)"}`}
          >
            {fullUniverse ? `🌐 ${totalCount}` : "N50"}
          </button>
          <button
            onClick={triggerScan}
            disabled={scanning}
            className="btn bg-sky-500/20 hover:bg-sky-500/30 text-sky-400 border border-sky-500/30 text-xs py-2"
          >
            {scanning ? (
              <span className="flex items-center gap-1.5">
                <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Scanning…
              </span>
            ) : "Scan Now"}
          </button>
        </div>
      </div>

      {/* Universe mode label */}
      {fullUniverse && universeInfo && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-sky-500/5 border border-sky-500/20">
          <span className="text-sky-400 text-base">🌐</span>
          <div className="text-xs">
            <span className="text-slate-300 font-semibold">{universeInfo.total} NSE equities</span>
            <span className="text-slate-500"> across {Object.keys(universeInfo.sectors || {}).length} sectors</span>
            <span className="text-slate-600"> · {universeInfo.source === "kite" ? "Kite live" : "fallback list"}</span>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!scanData && !scanning && (
        <div className="card flex flex-col items-center gap-4 py-10 text-center">
          <div className="text-4xl">⚡</div>
          <div>
            <p className="text-slate-300 font-semibold">JARVIS is ready</p>
            <p className="text-slate-500 text-sm mt-1">
              Auto-scan runs at 9:15 AM IST.<br />
              Tap <strong>Scan Now</strong> to run immediately.
            </p>
            {fullUniverse && (
              <p className="text-sky-400 text-xs mt-2">
                Full NSE mode: ~{totalCount} stocks · 8 parallel workers
              </p>
            )}
          </div>
          <button onClick={triggerScan} disabled={scanning}
            className="btn bg-sky-500 hover:bg-sky-400 text-white focus:ring-sky-500">
            Run {fullUniverse ? "Full NSE" : "Nifty 50"} Scan
          </button>
        </div>
      )}

      {/* Scanning state */}
      {scanning && (
        <div className="card flex flex-col items-center gap-3 py-8">
          <div className="relative w-12 h-12">
            <div className="absolute inset-0 rounded-full border-4 border-border" />
            <div className="absolute inset-0 rounded-full border-4 border-t-sky-400 animate-spin" />
          </div>
          <p className="text-slate-300 font-medium">
            {fullUniverse ? "Scanning full NSE universe…" : "Analysing Nifty 50…"}
          </p>
          <p className="text-xs text-slate-500">
            {fullUniverse
              ? `8 parallel sector workers · ~${totalCount} stocks`
              : "Running 8 signal engines on 50 stocks"}
          </p>
        </div>
      )}

      {/* Results */}
      {scanData && !scanning && (
        <>
          <SummaryBar
            summary={scanData.summary}
            elapsed={scanData.elapsed_sec}
            scanTime={scanData.scan_time}
            totalScanned={scanData.total_scanned}
            universeSize={scanData.universe_size}
            isFullScan={isFullScan}
          />

          {/* Tabs */}
          <div className="flex gap-1 bg-surface rounded-xl p-1">
            {["BUY", "SELL", "HOLD"].map((t) => {
              const c = scanData.summary;
              const n = t === "BUY" ? (c?.buy_count ?? c?.buy ?? 0)
                      : t === "SELL" ? (c?.sell_count ?? c?.sell ?? 0)
                      : (c?.hold_count ?? c?.hold ?? 0);
              return (
                <button key={t}
                  onClick={() => setTab(t)}
                  className={clsx(
                    "flex-1 text-xs font-semibold py-2 rounded-lg transition-all",
                    tab === t
                      ? t === "BUY" ? "bg-buy text-white"
                        : t === "SELL" ? "bg-sell text-white"
                        : "bg-hold text-white"
                      : "text-slate-500 hover:text-slate-300"
                  )}
                >
                  {t === "BUY" ? `▲ BUY (${n})` : t === "SELL" ? `▼ SELL (${n})` : `— WAIT (${n})`}
                </button>
              );
            })}
          </div>

          {/* Sector breakdown (full scan only) */}
          {isFullScan && <SectorBreakdown breakdown={scanData.sector_breakdown} />}

          {/* Stock cards */}
          <div className="space-y-2">
            {stocks.length === 0 && (
              <p className="text-center text-slate-500 text-sm py-6">
                No {tab} signals this scan.
              </p>
            )}
            {stocks.map((stock) => (
              <StockCard key={stock.symbol} stock={stock} onSelect={onSelectStock} />
            ))}
            {isFullScan && stocks.length >= 20 && (
              <p className="text-center text-xs text-slate-600 py-2">
                Showing top 20 of {tab === "BUY"
                  ? scanData.summary?.buy_count
                  : tab === "SELL" ? scanData.summary?.sell_count
                  : scanData.summary?.hold_count} signals
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
