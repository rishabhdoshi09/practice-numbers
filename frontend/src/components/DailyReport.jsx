import React, { useState, useEffect, useCallback } from "react";
import clsx from "clsx";
import {
  LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

const API = process.env.REACT_APP_API_URL || "http://localhost:8000";

// ── Helpers ────────────────────────────────────────────────────────────────────
const pctColor  = (v) => v >= 0 ? "text-buy" : "text-sell";
const pctArrow  = (v) => v >= 0 ? "▲" : "▼";
const fmtPct    = (v) => `${v >= 0 ? "+" : ""}${Number(v).toFixed(2)}%`;
const fmtPrice  = (v) => v?.toLocaleString("en-IN", { maximumFractionDigits: 2 }) || "—";

// ── Section header ─────────────────────────────────────────────────────────────
function SectionHeader({ icon, title, subtitle }) {
  return (
    <div className="flex items-center gap-3 mb-3">
      <span className="text-2xl">{icon}</span>
      <div>
        <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">{title}</h3>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      </div>
    </div>
  );
}

// ── Executive Summary ─────────────────────────────────────────────────────────
function ExecutiveSummary({ data }) {
  if (!data) return null;
  const sentColor = {
    "STRONGLY BULLISH": "text-buy",  "BULLISH": "text-buy",
    "NEUTRAL":          "text-hold", "BEARISH": "text-sell",
    "STRONGLY BEARISH": "text-sell",
  }[data.sentiment] || "text-slate-400";

  return (
    <div className="card space-y-4">
      <SectionHeader icon="📋" title="Executive Summary" />
      <p className="text-sm text-slate-200 leading-relaxed font-medium">{data.headline}</p>

      <div className="grid grid-cols-2 gap-2">
        {/* Nifty */}
        <div className="bg-surface rounded-xl p-3">
          <p className="text-xs text-slate-400 mb-1">Nifty 50</p>
          <p className="text-lg font-black text-slate-100">{fmtPrice(data.nifty?.close)}</p>
          <p className={clsx("text-xs font-semibold", pctColor(data.nifty?.chg_pct))}>
            {pctArrow(data.nifty?.chg_pct)} {fmtPct(data.nifty?.chg_pct)}
          </p>
        </div>
        {/* VIX */}
        <div className="bg-surface rounded-xl p-3">
          <p className="text-xs text-slate-400 mb-1">VIX</p>
          <p className="text-lg font-black text-slate-100">{data.vix?.value}</p>
          <p className="text-xs text-slate-400 capitalize">{data.vix?.level}</p>
        </div>
        {/* Leading sector */}
        <div className="bg-surface rounded-xl p-3">
          <p className="text-xs text-slate-400 mb-1">Leading Sector</p>
          <p className="text-sm font-bold text-slate-100">{data.leading_sector?.name}</p>
          <p className={clsx("text-xs font-semibold", pctColor(data.leading_sector?.chg_pct))}>
            {fmtPct(data.leading_sector?.chg_pct)}
          </p>
        </div>
        {/* Breadth */}
        <div className="bg-surface rounded-xl p-3">
          <p className="text-xs text-slate-400 mb-1">Market Breadth</p>
          <p className={clsx("text-sm font-bold capitalize", pctColor(data.market_breadth?.buy_count - data.market_breadth?.sell_count))}>
            {data.market_breadth?.label}
          </p>
          <p className="text-xs text-slate-500">
            {data.market_breadth?.buy_count}↑ / {data.market_breadth?.sell_count}↓
          </p>
        </div>
      </div>

      <div className={clsx("text-center py-2 rounded-xl text-sm font-black tracking-widest", sentColor)}>
        {data.sentiment}
      </div>
    </div>
  );
}

// ── Index Tables ──────────────────────────────────────────────────────────────
function IndexTable({ title, rows }) {
  return (
    <div>
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">{title}</p>
      <div className="space-y-1">
        {rows?.map((r) => (
          <div key={r.name} className="flex items-center justify-between text-sm bg-surface rounded-lg px-3 py-2">
            <span className="text-slate-300">{r.flag} {r.name}</span>
            <span className="font-mono text-slate-100">{fmtPrice(r.close)}</span>
            <span className={clsx("font-semibold font-mono text-xs", pctColor(r.chg_pct))}>
              {pctArrow(r.chg_pct)} {fmtPct(r.chg_pct)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Global Cues ───────────────────────────────────────────────────────────────
function GlobalCues({ data }) {
  if (!data) return null;
  const regionOrder = ["India", "North America", "Europe", "Asia", "South America"];
  return (
    <div className="card space-y-4">
      <SectionHeader icon="🌍" title="Global Cues" subtitle="Indices by region + commodities" />
      {regionOrder.map((region) => data.regions?.[region] && (
        <IndexTable key={region} title={region} rows={data.regions[region]} />
      ))}
      <div className="mt-2">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Commodities</p>
        <div className="grid grid-cols-2 gap-2">
          {data.commodities?.map((c) => (
            <div key={c.name} className="bg-surface rounded-lg px-3 py-2 flex justify-between items-center">
              <div>
                <p className="text-xs text-slate-300 font-medium">{c.name}</p>
                <p className="text-xs text-slate-500">{c.unit}</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-bold text-slate-100">{c.close}</p>
                <p className={clsx("text-xs font-semibold", pctColor(c.chg_pct))}>
                  {pctArrow(c.chg_pct)} {fmtPct(c.chg_pct)}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Stock Card ────────────────────────────────────────────────────────────────
function SpotlightCard({ stock, color, onSelect }) {
  return (
    <button onClick={() => onSelect?.(stock.symbol)}
      className="w-full text-left bg-surface rounded-xl p-3 hover:bg-white/5 transition-colors">
      <div className="flex justify-between items-start mb-1">
        <div>
          <p className="text-sm font-bold text-slate-100">{stock.name}</p>
          <p className="text-xs text-slate-500">{stock.sector} · {stock.symbol.replace(".NS","")}</p>
        </div>
        <span className={clsx("badge border text-xs", color)}>
          {stock.action}
        </span>
      </div>
      <p className="text-xs text-slate-400 leading-relaxed">{stock.narrative}</p>
      <div className="flex justify-between mt-2 text-xs text-slate-500">
        <span>₹{fmtPrice(stock.price)}</span>
        <span className="text-sell">Stop ₹{fmtPrice(stock.stop_loss)}</span>
        <span>{stock.confidence?.toFixed(0)}% conf</span>
      </div>
    </button>
  );
}

// ── Stock Spotlights ──────────────────────────────────────────────────────────
function StockSpotlights({ data, onSelect }) {
  const [tab, setTab] = useState("buzzing");
  if (!data) return null;
  const tabs = [
    { key: "buzzing", label: "🚀 Buzzing", color: "bg-buy/10 border-buy/30 text-buy" },
    { key: "gaining", label: "💪 Gaining",  color: "bg-sky-500/10 border-sky-500/30 text-sky-400" },
    { key: "losing",  label: "⚠️ Losing",   color: "bg-sell/10 border-sell/30 text-sell" },
  ];
  const current = data[tab] || [];

  return (
    <div className="card space-y-3">
      <SectionHeader icon="🔦" title="Stock Spotlights" subtitle="Deep dives by category" />
      <div className="flex gap-1 bg-surface rounded-xl p-1">
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={clsx("flex-1 text-xs py-1.5 rounded-lg font-semibold transition-all",
              tab === t.key ? "bg-panel text-slate-100 shadow" : "text-slate-500 hover:text-slate-300")}>
            {t.label} ({data[t.key]?.length || 0})
          </button>
        ))}
      </div>
      <div className="space-y-2">
        {current.length === 0 && <p className="text-slate-500 text-sm text-center py-4">No stocks in this category.</p>}
        {current.map((s) => (
          <SpotlightCard key={s.symbol} stock={s}
            color={tabs.find(t => t.key === tab)?.color}
            onSelect={onSelect} />
        ))}
      </div>
    </div>
  );
}

// ── EMA Analysis ─────────────────────────────────────────────────────────────
function EMAAnalysis({ data }) {
  if (!data?.nifty50) return null;
  const { close, ema_values, structure, above_emas, chart_data } = data.nifty50;

  const chartData = chart_data?.dates?.map((d, i) => ({
    date:   d.slice(5),
    close:  chart_data.close?.[i],
    ema10:  chart_data.ema10?.[i],
    ema20:  chart_data.ema20?.[i],
    ema50:  chart_data.ema50?.[i],
    ema200: chart_data.ema200?.[i],
    volume: chart_data.volume?.[i],
  })) || [];

  return (
    <div className="card space-y-3">
      <SectionHeader icon="📈" title="Technical Index Analysis" subtitle="Nifty 50 EMA Structure" />
      <p className="text-sm text-slate-300">{structure}</p>

      <div className="grid grid-cols-4 gap-1">
        {Object.entries(ema_values || {}).map(([key, val]) => {
          const above = close >= val;
          return (
            <div key={key} className={clsx("rounded-lg p-2 text-center border",
              above ? "bg-buy/5 border-buy/20" : "bg-sell/5 border-sell/20")}>
              <p className="text-xs text-slate-400 uppercase">{key}</p>
              <p className="text-xs font-bold text-slate-200">{fmtPrice(val)}</p>
              <p className={clsx("text-xs font-semibold", above ? "text-buy" : "text-sell")}>
                {above ? "Above" : "Below"}
              </p>
            </div>
          );
        })}
      </div>

      {chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={chartData.slice(-40)}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#64748b" }} tickLine={false} />
            <YAxis tick={{ fontSize: 9, fill: "#64748b" }} width={52} tickLine={false} axisLine={false} domain={["auto","auto"]} />
            <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 10 }} />
            <Line type="monotone" dataKey="close"  stroke="#38bdf8" strokeWidth={2}   dot={false} name="Close" />
            <Line type="monotone" dataKey="ema10"  stroke="#22c55e" strokeWidth={1}   dot={false} name="EMA10" strokeDasharray="3 2" />
            <Line type="monotone" dataKey="ema20"  stroke="#f59e0b" strokeWidth={1}   dot={false} name="EMA20" strokeDasharray="3 2" />
            <Line type="monotone" dataKey="ema50"  stroke="#a78bfa" strokeWidth={1.5} dot={false} name="EMA50" />
            <Line type="monotone" dataKey="ema200" stroke="#ef4444" strokeWidth={1.5} dot={false} name="EMA200" />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

// ── Sector Heatmap ────────────────────────────────────────────────────────────
function SectorHeatmap({ data }) {
  if (!data) return null;
  const { sectors, stock_cells } = data;

  const heatColor = (score) => {
    if (score > 0.3)  return "bg-buy  text-white";
    if (score > 0.1)  return "bg-buy/50 text-white";
    if (score > -0.1) return "bg-hold/30 text-slate-300";
    if (score > -0.3) return "bg-sell/50 text-white";
    return "bg-sell text-white";
  };

  return (
    <div className="card space-y-4">
      <SectionHeader icon="🟦" title="Performance Heatmap" subtitle="Sector + Nifty 50 stocks" />

      {/* Sector bar */}
      <div>
        <p className="text-xs text-slate-400 mb-2 uppercase tracking-wider">Sectors</p>
        <div className="space-y-1">
          {sectors?.slice(0, 8).map((s) => (
            <div key={s.name} className="flex items-center gap-2">
              <span className="text-xs text-slate-400 w-24 shrink-0">{s.name}</span>
              <div className="flex-1 h-4 bg-surface rounded overflow-hidden">
                <div
                  className={clsx("h-full rounded transition-all duration-700",
                    s.chg_pct >= 0 ? "bg-buy" : "bg-sell")}
                  style={{ width: `${Math.min(100, Math.abs(s.chg_pct) * 20)}%` }}
                />
              </div>
              <span className={clsx("text-xs font-mono font-semibold w-14 text-right", pctColor(s.chg_pct))}>
                {fmtPct(s.chg_pct)}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Stock tile heatmap */}
      <div>
        <p className="text-xs text-slate-400 mb-2 uppercase tracking-wider">Nifty 50 Stocks</p>
        <div className="grid grid-cols-5 gap-1">
          {stock_cells?.slice(0, 50).map((s) => (
            <div key={s.symbol}
              className={clsx("rounded p-1 text-center text-xs font-bold transition-colors", heatColor(s.score))}>
              <p className="text-[9px] leading-tight">{s.symbol}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── News ─────────────────────────────────────────────────────────────────────
function NewsSection({ items }) {
  if (!items?.length) return null;
  const sentColor = { positive: "text-buy", negative: "text-sell", neutral: "text-slate-400" };
  return (
    <div className="card space-y-3">
      <SectionHeader icon="📰" title="Corporate News & Updates" />
      <div className="space-y-2">
        {items.map((n, i) => (
          <div key={i} className="flex gap-3 items-start border-b border-border/50 pb-2 last:border-0 last:pb-0">
            <span className={clsx("text-sm font-bold shrink-0 mt-0.5", sentColor[n.sentiment])}>
              {n.icon}
            </span>
            <div>
              <p className="text-xs text-slate-200 leading-snug">{n.headline}</p>
              <p className="text-xs text-slate-500 mt-0.5">{n.name} · {n.sector}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Tomorrow Breakouts ────────────────────────────────────────────────────────
function TomorrowBreakouts({ stocks, onSelect }) {
  if (!stocks?.length) return null;
  return (
    <div className="card space-y-3">
      <SectionHeader icon="🎯" title="Breakout Stocks for Tomorrow" subtitle="Watch these setups at open" />
      <div className="space-y-2">
        {stocks.map((s) => (
          <button key={s.symbol} onClick={() => onSelect?.(s.symbol)}
            className="w-full text-left bg-surface rounded-xl p-3 hover:bg-white/5 transition-colors">
            <div className="flex justify-between items-center mb-1">
              <p className="text-sm font-bold text-slate-100">{s.name}</p>
              <span className="badge bg-sky-500/10 border border-sky-500/30 text-sky-400 text-xs">
                {s.setup_quality?.toFixed(0)}% setup
              </span>
            </div>
            <p className="text-xs text-slate-400 mb-1">{s.setup_type}</p>
            <div className="flex gap-3 text-xs">
              <span className="text-hold">{s.trigger}</span>
              <span className="text-buy">{s.target}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Main Report Component ─────────────────────────────────────────────────────
export default function DailyReport({ onSelectStock }) {
  const [report,  setReport]  = useState(null);
  const [loading, setLoading] = useState(false);
  const [section, setSection] = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res  = await fetch(`${API}/report/daily`);
      const data = await res.json();
      setReport(data);
    } catch (e) {
      console.error("Report load failed:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const NAV_ITEMS = [
    { id: "all",       label: "All" },
    { id: "summary",   label: "Summary" },
    { id: "global",    label: "Global" },
    { id: "stocks",    label: "Stocks" },
    { id: "technical", label: "Charts" },
    { id: "tomorrow",  label: "Tomorrow" },
  ];

  const show = (id) => section === "all" || section === id;

  return (
    <div className="space-y-4 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-100">📰 Daily Street Pulse</h2>
          {report?.meta && (
            <p className="text-xs text-slate-500">{report.meta.date} · {report.meta.time} · {report.meta.scanned} stocks</p>
          )}
        </div>
        <button onClick={load} disabled={loading}
          className="btn bg-sky-500/20 text-sky-400 border border-sky-500/30 text-xs py-1.5">
          {loading ? "…" : "Refresh"}
        </button>
      </div>

      {/* Section nav */}
      <div className="flex gap-1 overflow-x-auto pb-1 no-scrollbar">
        {NAV_ITEMS.map((n) => (
          <button key={n.id} onClick={() => setSection(n.id)}
            className={clsx("text-xs px-3 py-1.5 rounded-lg font-medium whitespace-nowrap transition-all shrink-0",
              section === n.id
                ? "bg-panel text-slate-100 border border-border"
                : "text-slate-500 hover:text-slate-300")}>
            {n.label}
          </button>
        ))}
      </div>

      {loading && (
        <div className="card flex flex-col items-center gap-3 py-10">
          <div className="w-10 h-10 rounded-full border-4 border-border border-t-sky-400 animate-spin" />
          <p className="text-slate-400 text-sm">Generating Daily Street Pulse…</p>
          <p className="text-slate-500 text-xs">Fetching global indices · Scanning Nifty 50 · Building report</p>
        </div>
      )}

      {report && !loading && (
        <>
          {show("summary")   && <ExecutiveSummary  data={report.executive_summary} />}
          {show("global")    && <GlobalCues         data={report.global_cues} />}
          {show("stocks")    && <StockSpotlights    data={report.stock_spotlights} onSelect={onSelectStock} />}
          {show("technical") && <EMAAnalysis        data={report.ema_analysis} />}
          {show("technical") && <SectorHeatmap      data={report.heatmap} />}
          {show("stocks")    && <NewsSection         items={report.news} />}
          {show("tomorrow")  && <TomorrowBreakouts   stocks={report.tomorrow_breakouts} onSelect={onSelectStock} />}
        </>
      )}
    </div>
  );
}
