import React, { useState, useEffect } from "react";
import clsx from "clsx";

const API = process.env.REACT_APP_API_URL || "http://localhost:8000";

const BUCKET_CONFIG = {
  breakout: {
    icon: "🚀",
    label: "Breakout",
    subtitle: "Strong move + volume confirmation",
    border: "border-buy/30",
    bg: "bg-buy/5",
    badge: "bg-buy/10 border-buy/30 text-buy",
    bar: "bg-buy",
  },
  momentum: {
    icon: "💪",
    label: "Momentum",
    subtitle: "Trend continuation, structure intact",
    border: "border-sky-500/30",
    bg: "bg-sky-500/5",
    badge: "bg-sky-500/10 border-sky-500/30 text-sky-400",
    bar: "bg-sky-400",
  },
  base: {
    icon: "🧱",
    label: "Base Formation",
    subtitle: "Consolidation — setup forming",
    border: "border-hold/30",
    bg: "bg-hold/5",
    badge: "bg-hold/10 border-hold/30 text-hold",
    bar: "bg-hold",
  },
  weak: {
    icon: "⚠️",
    label: "Losing Momentum",
    subtitle: "Breakdown / failed breakout",
    border: "border-sell/30",
    bg: "bg-sell/5",
    badge: "bg-sell/10 border-sell/30 text-sell",
    bar: "bg-sell",
  },
};

function StockRow({ stock, cfg, onSelect }) {
  return (
    <button
      onClick={() => onSelect && onSelect(stock.symbol)}
      className="w-full flex items-center gap-3 py-2.5 border-b border-border/50 last:border-0 text-left hover:bg-white/5 transition-colors rounded-lg px-2"
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-slate-100">{stock.name}</span>
          <span className="text-xs text-slate-500">{stock.symbol.replace(".NS", "")}</span>
        </div>
        <p className="text-xs text-slate-500 mt-0.5">{stock.sector} · via {stock.top_signal}</p>
      </div>
      <div className="text-right shrink-0">
        <p className="text-sm font-bold text-slate-100">₹{stock.price.toLocaleString("en-IN")}</p>
        <p className="text-xs text-sell">Stop ₹{stock.stop_loss.toLocaleString("en-IN")}</p>
      </div>
      <div className="w-12 shrink-0">
        <div className="h-1 bg-surface rounded-full overflow-hidden mb-1">
          <div className={clsx("h-full rounded-full", cfg.bar)}
               style={{ width: `${stock.confidence}%` }} />
        </div>
        <p className="text-xs text-slate-500 text-right">{stock.confidence.toFixed(0)}%</p>
      </div>
    </button>
  );
}

function BucketCard({ bucketKey, stocks, onSelect }) {
  const cfg = BUCKET_CONFIG[bucketKey];
  if (!stocks?.length) return null;
  return (
    <div className={clsx("rounded-2xl border p-4", cfg.border, cfg.bg)}>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xl">{cfg.icon}</span>
        <div>
          <p className="text-sm font-bold text-slate-100">{cfg.label}</p>
          <p className="text-xs text-slate-500">{cfg.subtitle}</p>
        </div>
        <span className={clsx("badge border ml-auto", cfg.badge)}>{stocks.length}</span>
      </div>
      <div>
        {stocks.map((s) => (
          <StockRow key={s.symbol} stock={s} cfg={cfg} onSelect={onSelect} />
        ))}
      </div>
    </div>
  );
}

export default function DailyReport({ onSelectStock }) {
  const [report,  setReport]  = useState(null);
  const [loading, setLoading] = useState(false);
  const [view,    setView]    = useState("cards"); // "cards" | "markdown"

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/report/daily`);
      const data = await res.json();
      setReport(data);
    } catch (e) {
      console.error("Report failed:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-4 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-100">📰 Daily Street Pulse</h2>
          {report && (
            <p className="text-xs text-slate-500 mt-0.5">{report.date} · {report.time}</p>
          )}
        </div>
        <div className="flex gap-1">
          <button onClick={() => setView(view === "cards" ? "markdown" : "cards")}
            className="text-xs px-3 py-1.5 bg-panel border border-border rounded-lg text-slate-400 hover:text-slate-200">
            {view === "cards" ? "Raw" : "Cards"}
          </button>
          <button onClick={load} disabled={loading}
            className="btn bg-sky-500/20 text-sky-400 border border-sky-500/30 text-xs py-1.5">
            {loading ? "…" : "Refresh"}
          </button>
        </div>
      </div>

      {loading && (
        <div className="card flex flex-col items-center gap-3 py-10">
          <div className="w-10 h-10 rounded-full border-4 border-border border-t-sky-400 animate-spin" />
          <p className="text-slate-400 text-sm">Generating Street Pulse…</p>
        </div>
      )}

      {/* Count summary bar */}
      {report && !loading && (
        <div className="flex gap-2 flex-wrap">
          {Object.entries(BUCKET_CONFIG).map(([key, cfg]) => (
            report.counts[key] > 0 && (
              <span key={key} className={clsx("badge border", cfg.badge)}>
                {cfg.icon} {cfg.label} {report.counts[key]}
              </span>
            )
          ))}
        </div>
      )}

      {/* Cards view */}
      {report && !loading && view === "cards" && (
        <div className="space-y-3">
          {["breakout", "momentum", "base", "weak"].map((key) => (
            <BucketCard
              key={key}
              bucketKey={key}
              stocks={report.buckets[key]}
              onSelect={onSelectStock}
            />
          ))}
          {Object.values(report.buckets).every(b => !b?.length) && (
            <div className="card text-center text-slate-500 py-8">
              No high-quality setups found in this scan. Market may be choppy.
            </div>
          )}
        </div>
      )}

      {/* Markdown / raw view */}
      {report && !loading && view === "markdown" && (
        <div className="card font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed overflow-x-auto">
          {report.markdown}
        </div>
      )}
    </div>
  );
}
