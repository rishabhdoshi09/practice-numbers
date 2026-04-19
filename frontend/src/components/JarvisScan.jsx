import React, { useState, useEffect, useRef, useCallback } from "react";
import clsx from "clsx";
import { fetchAnalysis } from "../utils/api";
import { fmtINR } from "../utils/format";

const WS_URL = (process.env.REACT_APP_API_URL || "http://localhost:8000")
  .replace("http", "ws") + "/ws/scan";

const ACTION_STYLE = {
  BUY:  { bar: "bg-buy",  text: "text-buy",  badge: "bg-buy/10 border-buy/30 text-buy"  },
  SELL: { bar: "bg-sell", text: "text-sell",  badge: "bg-sell/10 border-sell/30 text-sell" },
  HOLD: { bar: "bg-hold", text: "text-hold",  badge: "bg-hold/10 border-hold/30 text-hold" },
};

function StockCard({ stock, onSelect }) {
  const style = ACTION_STYLE[stock.action] || ACTION_STYLE.HOLD;
  return (
    <button
      onClick={() => onSelect(stock.symbol)}
      className="w-full text-left card hover:border-slate-500 transition-all duration-200 active:scale-[0.98]"
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <p className="text-sm font-bold text-slate-100 leading-tight">{stock.name}</p>
          <p className="text-xs text-slate-500">{stock.symbol.replace(".NS","")}&nbsp;·&nbsp;{stock.sector}</p>
        </div>
        <span className={clsx("badge border text-xs font-black", style.badge)}>
          {stock.action}
        </span>
      </div>

      {/* Confidence bar */}
      <div className="flex items-center gap-2 mb-2">
        <div className="flex-1 h-1.5 bg-surface rounded-full overflow-hidden">
          <div className={clsx("h-full rounded-full transition-all duration-700", style.bar)}
               style={{ width: `${stock.confidence}%` }} />
        </div>
        <span className={clsx("text-xs font-semibold font-mono", style.text)}>
          {stock.confidence.toFixed(0)}%
        </span>
      </div>

      <div className="flex justify-between text-xs text-slate-400">
        <span>₹{stock.price.toLocaleString("en-IN")}</span>
        <span className="text-sell">Stop ₹{stock.stop_loss.toLocaleString("en-IN")}</span>
        <span className="text-slate-500">{stock.top_signal}</span>
      </div>
    </button>
  );
}

function SummaryBar({ summary, elapsed, scanTime }) {
  const time = scanTime ? new Date(scanTime).toLocaleTimeString("en-IN", { hour:"2-digit", minute:"2-digit" }) : null;
  return (
    <div className="flex items-center gap-3 flex-wrap">
      <div className="flex gap-2">
        <span className="badge bg-buy/10 border border-buy/30 text-buy">▲ {summary?.buy_count || 0} BUY</span>
        <span className="badge bg-sell/10 border border-sell/30 text-sell">▼ {summary?.sell_count || 0} SELL</span>
        <span className="badge bg-hold/10 border border-hold/30 text-hold">— {summary?.hold_count || 0} WAIT</span>
      </div>
      {elapsed && (
        <span className="text-xs text-slate-500 ml-auto">
          {summary?.buy_count + summary?.sell_count + summary?.hold_count} stocks · {elapsed}s
          {time && ` · ${time}`}
        </span>
      )}
    </div>
  );
}

export default function JarvisScan({ onSelectStock }) {
  const [scanData,  setScanData]  = useState(null);
  const [scanning,  setScanning]  = useState(false);
  const [tab,       setTab]       = useState("BUY");
  const [wsStatus,  setWsStatus]  = useState("disconnected");
  const wsRef = useRef(null);

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
        if (data.type === "scan_result") setScanData(data);
      };

      ws.onclose = () => {
        setWsStatus("disconnected");
        clearInterval(ws._pingInterval);
        setTimeout(connect, 3000);   // auto-reconnect
      };

      ws.onerror = () => ws.close();
    };

    connect();
    return () => { wsRef.current?.close(); };
  }, []);

  // ── Manual scan trigger ───────────────────────────────────────────────────
  const triggerScan = useCallback(async () => {
    setScanning(true);
    try {
      const res = await fetch((process.env.REACT_APP_API_URL || "http://localhost:8000") + "/scan");
      const data = await res.json();
      setScanData(data);
    } catch (e) {
      console.error("Scan failed:", e);
    } finally {
      setScanning(false);
    }
  }, []);

  const stocks = tab === "BUY"  ? (scanData?.top_buys  || [])
               : tab === "SELL" ? (scanData?.top_sells || [])
               :                  (scanData?.holds     || []);

  return (
    <div className="space-y-4 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
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
          </div>
          <button onClick={triggerScan} disabled={scanning}
            className="btn bg-sky-500 hover:bg-sky-400 text-white focus:ring-sky-500">
            Run Market Scan
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
          <p className="text-slate-300 font-medium">Analysing Nifty 50…</p>
          <p className="text-xs text-slate-500">Running 8 signal engines on 50 stocks</p>
        </div>
      )}

      {/* Results */}
      {scanData && !scanning && (
        <>
          <SummaryBar
            summary={scanData.summary}
            elapsed={scanData.elapsed_sec}
            scanTime={scanData.scan_time}
          />

          {/* Tabs */}
          <div className="flex gap-1 bg-surface rounded-xl p-1">
            {["BUY", "SELL", "HOLD"].map((t) => (
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
                {t === "BUY" ? `▲ BUY (${scanData.summary?.buy_count})` :
                 t === "SELL" ? `▼ SELL (${scanData.summary?.sell_count})` :
                 `— WAIT (${scanData.summary?.hold_count})`}
              </button>
            ))}
          </div>

          {/* Stock cards */}
          <div className="space-y-2">
            {stocks.length === 0 && (
              <p className="text-center text-slate-500 text-sm py-6">No {tab} signals this scan.</p>
            )}
            {stocks.map((stock) => (
              <StockCard key={stock.symbol} stock={stock} onSelect={onSelectStock} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
