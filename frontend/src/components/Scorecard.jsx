import React, { useState, useEffect, useCallback, useRef } from "react";
import clsx from "clsx";
import {
  LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

const API = process.env.REACT_APP_API_URL || "http://localhost:8000";

// ── Helpers ────────────────────────────────────────────────────────────────────
const fmtNum  = (v, d=2)  => v != null ? Number(v).toLocaleString("en-IN", { maximumFractionDigits: d }) : "—";
const fmtPct  = (v)       => v != null ? `${v > 0 ? "+" : ""}${Number(v).toFixed(1)}%` : "—";
const fmtCr   = (v) => {
  if (v == null) return "—";
  const a = Math.abs(v), s = v < 0 ? "-" : "";
  if (a >= 1e9)  return `${s}₹${(a / 1e9).toFixed(1)}B`;
  if (a >= 1e7)  return `${s}₹${(a / 1e7).toFixed(1)}Cr`;
  return `${s}₹${(a / 1e5).toFixed(1)}L`;
};
const riskColor = (c) => ({
  green: { text: "text-buy",  bg: "bg-buy/10",  border: "border-buy/30"  },
  amber: { text: "text-hold", bg: "bg-hold/10", border: "border-hold/30" },
  red:   { text: "text-sell", bg: "bg-sell/10", border: "border-sell/30" },
}[c] || { text: "text-slate-400", bg: "bg-panel", border: "border-border" });

// ── SVG Risk Gauge ─────────────────────────────────────────────────────────────
function RiskGauge({ score, label, color }) {
  const r      = 70;
  const cx     = 90;
  const cy     = 90;
  const start  = Math.PI;
  const end    = 0;
  const angle  = start + (score / 100) * Math.PI;
  const nx     = cx + r * Math.cos(angle);
  const ny     = cy + r * Math.sin(angle);

  const arcColor = color === "green" ? "#22c55e" : color === "amber" ? "#f59e0b" : "#ef4444";
  const trackArc = `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`;
  const fillArc  = `M ${cx - r} ${cy} A ${r} ${r} 0 ${score > 50 ? 1 : 0} 1 ${nx} ${ny}`;

  return (
    <div className="flex flex-col items-center">
      <svg width={180} height={110} viewBox="0 0 180 110">
        {/* Track */}
        <path d={trackArc} fill="none" stroke="#1e293b" strokeWidth={14} strokeLinecap="round" />
        {/* Fill */}
        <path d={fillArc} fill="none" stroke={arcColor} strokeWidth={14} strokeLinecap="round"
              style={{ transition: "stroke-dasharray 1s ease" }} />
        {/* Needle */}
        <line
          x1={cx} y1={cy}
          x2={nx} y2={ny}
          stroke={arcColor} strokeWidth={3} strokeLinecap="round"
          style={{ transition: "all 1s ease" }}
        />
        <circle cx={cx} cy={cy} r={5} fill={arcColor} />
        {/* Score */}
        <text x={cx} y={cy - 10} textAnchor="middle" fill="white"
              fontSize={28} fontWeight="900" fontFamily="JetBrains Mono, monospace">
          {score}
        </text>
        <text x={cx} y={cy + 8} textAnchor="middle" fill="#64748b" fontSize={9}>
          / 100
        </text>
        {/* Labels */}
        <text x={cx - r - 4} y={cy + 18} fill="#64748b" fontSize={8}>0</text>
        <text x={cx + r - 2} y={cy + 18} fill="#64748b" fontSize={8}>100</text>
      </svg>
      <span className={clsx("text-sm font-black tracking-widest mt-1", riskColor(color).text)}>
        {label}
      </span>
    </div>
  );
}

// ── KPI Strip ──────────────────────────────────────────────────────────────────
function KpiStrip({ metrics }) {
  const items = [
    { label: "P/E",          value: metrics?.pe_ratio    != null ? `${metrics.pe_ratio}×`    : "—" },
    { label: "EV/EBITDA",    value: metrics?.ev_ebitda   != null ? `${metrics.ev_ebitda}×`   : "—" },
    { label: "ROE",          value: metrics?.roe         != null ? `${metrics.roe}%`          : "—" },
    { label: "D/E",          value: metrics?.debt_equity != null ? `${metrics.debt_equity}×` : "—" },
    { label: "Rev Growth",   value: fmtPct(metrics?.revenue_growth) },
    { label: "Profit Growth",value: fmtPct(metrics?.profit_growth)  },
    { label: "FCF",          value: fmtCr(metrics?.fcf)             },
    { label: "Div Yield",    value: metrics?.dividend_yield != null ? `${metrics.dividend_yield}%` : "—" },
  ];
  return (
    <div className="grid grid-cols-4 gap-1.5">
      {items.map((k) => (
        <div key={k.label} className="bg-surface rounded-xl px-2 py-2 text-center">
          <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-0.5">{k.label}</p>
          <p className="text-sm font-black text-slate-100 font-mono">{k.value}</p>
        </div>
      ))}
    </div>
  );
}

// ── Score Breakdown ────────────────────────────────────────────────────────────
function ScoreBreakdown({ scoring }) {
  if (!scoring) return null;
  const dims = [
    { key: "valuation",       label: "Valuation",       weight: "35%", data: scoring.valuation       },
    { key: "financial_health",label: "Financial Health", weight: "35%", data: scoring.financial_health },
    { key: "growth",          label: "Growth",           weight: "30%", data: scoring.growth           },
  ];
  return (
    <div className="card space-y-3">
      <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Score Breakdown</p>
      {dims.map(({ key, label, weight, data }) => {
        if (!data) return null;
        const pct   = data.pct || 0;
        const color = pct < 35 ? "#22c55e" : pct < 65 ? "#f59e0b" : "#ef4444";
        return (
          <div key={key}>
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs font-semibold text-slate-200">{label}
                <span className="text-slate-500 ml-1 text-[10px]">({weight})</span>
              </span>
              <span className="font-mono text-xs font-bold" style={{ color }}>
                {data.score} / {data.max}
              </span>
            </div>
            <div className="h-2 bg-surface rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all duration-1000"
                   style={{ width: `${pct}%`, background: color }} />
            </div>
            <p className="text-[10px] text-slate-500 mt-0.5">{data.summary}</p>
          </div>
        );
      })}
    </div>
  );
}

// ── Six Metric Cards ───────────────────────────────────────────────────────────
function MetricCard({ title, value, sub, status }) {
  const s = { good: "border-buy/20 bg-buy/5",
              warn: "border-hold/20 bg-hold/5",
              bad:  "border-sell/20 bg-sell/5" }[status] || "border-border bg-panel";
  const tc = { good: "text-buy", warn: "text-hold", bad: "text-sell" }[status] || "text-slate-200";
  return (
    <div className={clsx("rounded-xl border p-3 space-y-1", s)}>
      <p className="text-[10px] text-slate-400 uppercase tracking-wide">{title}</p>
      <p className={clsx("text-lg font-black font-mono", tc)}>{value}</p>
      {sub && <p className="text-[10px] text-slate-500 leading-snug">{sub}</p>}
    </div>
  );
}

function CardGrid({ metrics, scoring }) {
  if (!metrics) return null;
  const pe  = metrics.pe_ratio;
  const ev  = metrics.ev_ebitda;
  const de  = metrics.debt_equity;
  const rg  = metrics.revenue_growth;
  const pg  = metrics.profit_growth;
  const fcf = metrics.fcf;

  return (
    <div className="grid grid-cols-2 gap-2">
      <MetricCard title="P/E Ratio" value={pe != null ? `${pe}×` : "—"}
        sub={scoring?.valuation?.label}
        status={pe == null ? "warn" : pe < 20 ? "good" : pe < 40 ? "warn" : "bad"} />
      <MetricCard title="EV / EBITDA" value={ev != null ? `${ev}×` : "—"}
        sub="Enterprise value multiple"
        status={ev == null ? "warn" : ev < 12 ? "good" : ev < 20 ? "warn" : "bad"} />
      <MetricCard title="Debt / Equity" value={de != null ? `${de}×` : "—"}
        sub={scoring?.financial_health?.debt_label}
        status={de == null ? "warn" : de < 0.4 ? "good" : de < 1.0 ? "warn" : "bad"} />
      <MetricCard title="Free Cash Flow" value={fmtCr(fcf)}
        sub={scoring?.financial_health?.fcf_label}
        status={fcf == null ? "warn" : fcf > 0 ? "good" : "bad"} />
      <MetricCard title="Revenue Growth" value={fmtPct(rg)}
        sub="Year-over-year"
        status={rg == null ? "warn" : rg > 10 ? "good" : rg > 3 ? "warn" : "bad"} />
      <MetricCard title="Profit Growth" value={fmtPct(pg)}
        sub="Net income YoY"
        status={pg == null ? "warn" : pg > 12 ? "good" : pg > 0 ? "warn" : "bad"} />
    </div>
  );
}

// ── Price Chart ────────────────────────────────────────────────────────────────
function PriceHistoryChart({ history, company }) {
  if (!history?.dates?.length) return null;
  const data = history.dates.map((d, i) => ({ date: d.slice(5), close: history.close[i] }));
  const min  = Math.min(...history.close) * 0.98;
  const max  = Math.max(...history.close) * 1.02;

  return (
    <div className="card space-y-2">
      <div className="flex justify-between items-center">
        <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">12-Month Price</p>
        <div className="text-xs text-slate-500 font-mono">
          <span className="text-sell mr-2">52W L: ₹{fmtNum(history.low_52w)}</span>
          <span className="text-buy">52W H: ₹{fmtNum(history.high_52w)}</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="date" tick={{ fontSize: 8, fill: "#475569" }} tickLine={false}
                 interval={Math.floor(data.length / 6)} />
          <YAxis domain={[min, max]} tick={{ fontSize: 8, fill: "#475569" }}
                 width={55} tickFormatter={(v) => `₹${fmtNum(v, 0)}`} tickLine={false} axisLine={false} />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 10 }}
            formatter={(v) => [`₹${fmtNum(v)}`, "Close"]}
          />
          <Line type="monotone" dataKey="close" stroke="#38bdf8" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Quarterly Table ────────────────────────────────────────────────────────────
function QuarterlyTable({ quarters }) {
  if (!quarters?.length) return (
    <div className="card">
      <p className="text-xs text-slate-500 text-center py-4">Quarterly data unavailable</p>
    </div>
  );
  return (
    <div className="card space-y-2">
      <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Quarterly Financials</p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-border">
              <th className="text-left py-1.5 pr-2">Quarter</th>
              <th className="text-right py-1 px-1">Revenue</th>
              <th className="text-right py-1 px-1">Net Profit</th>
              <th className="text-right py-1 px-1">Gross Margin</th>
              <th className="text-right py-1 pl-1">Net Margin</th>
            </tr>
          </thead>
          <tbody>
            {quarters.map((q, i) => (
              <tr key={i} className="border-b border-border/40 last:border-0">
                <td className="py-1.5 pr-2 text-slate-300 font-semibold">{q.quarter?.slice(0, 7)}</td>
                <td className="py-1.5 px-1 text-right font-mono text-slate-200">{fmtCr(q.revenue)}</td>
                <td className={clsx("py-1.5 px-1 text-right font-mono font-semibold",
                  q.net_profit > 0 ? "text-buy" : "text-sell")}>{fmtCr(q.net_profit)}</td>
                <td className="py-1.5 px-1 text-right text-slate-300 font-mono">
                  {q.gross_margin != null ? `${q.gross_margin}%` : "—"}
                </td>
                <td className={clsx("py-1.5 pl-1 text-right font-mono font-semibold",
                  q.net_margin > 10 ? "text-buy" : q.net_margin > 0 ? "text-hold" : "text-sell")}>
                  {q.net_margin != null ? `${q.net_margin}%` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Catalysts vs Risks ────────────────────────────────────────────────────────
function CatalystsRisks({ catalysts, risks }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="card space-y-2">
        <p className="text-xs text-buy font-semibold uppercase tracking-wide">🚀 Catalysts</p>
        {catalysts?.length ? catalysts.map((c, i) => (
          <div key={i} className="flex gap-2 text-xs text-slate-300 leading-snug">
            <span className="text-buy shrink-0">+</span>{c}
          </div>
        )) : <p className="text-xs text-slate-500">No major catalysts identified</p>}
      </div>
      <div className="card space-y-2">
        <p className="text-xs text-sell font-semibold uppercase tracking-wide">⚠ Risks</p>
        {risks?.length ? risks.map((r, i) => (
          <div key={i} className="flex gap-2 text-xs text-slate-300 leading-snug">
            <span className="text-sell shrink-0">−</span>{r}
          </div>
        )) : <p className="text-xs text-slate-500">No major risks identified</p>}
      </div>
    </div>
  );
}

// ── News Panel ─────────────────────────────────────────────────────────────────
function NewsList({ news }) {
  if (!news?.length) return null;
  return (
    <div className="card space-y-2">
      <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Latest News</p>
      {news.slice(0, 4).map((n, i) => (
        <div key={i} className="border-b border-border/40 pb-2 last:border-0 last:pb-0">
          <p className="text-xs text-slate-200 leading-snug">{n.headline}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">{n.source}</p>
        </div>
      ))}
    </div>
  );
}

// ── Final Verdict ──────────────────────────────────────────────────────────────
function FinalVerdict({ verdict, scoring }) {
  if (!verdict) return null;
  const c = riskColor(verdict.color);
  const ratingBg = {
    "STRONG BUY":  "bg-buy text-white",
    "BUY":         "bg-buy/20 text-buy border border-buy/40",
    "NEUTRAL":     "bg-hold/20 text-hold border border-hold/40",
    "SELL":        "bg-sell/20 text-sell border border-sell/40",
    "STRONG SELL": "bg-sell text-white",
  }[verdict.rating] || "bg-panel text-slate-300 border border-border";

  return (
    <div className="card space-y-3">
      <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Final Verdict</p>
      <div className="flex items-center justify-between">
        <span className={clsx("text-xl font-black px-5 py-2 rounded-xl tracking-wide", ratingBg)}>
          {verdict.rating}
        </span>
        <div className="text-right">
          <p className={clsx("text-2xl font-black font-mono", c.text)}>{scoring?.total}</p>
          <p className="text-[10px] text-slate-500">Risk Score / 100</p>
        </div>
      </div>
      <p className="text-xs text-slate-300 leading-relaxed">{verdict.reason}</p>
    </div>
  );
}

// ── Copy to HTML button ────────────────────────────────────────────────────────
function CopyHtmlButton({ data }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    if (!data) return;
    const html = generateHtmlExport(data);
    navigator.clipboard.writeText(html).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [data]);

  return (
    <button onClick={handleCopy}
      className="btn bg-panel border border-border text-slate-400 hover:text-slate-200 text-xs py-2">
      {copied ? "✓ Copied!" : "⬇ Copy as HTML"}
    </button>
  );
}

function generateHtmlExport(data) {
  const { company, metrics, scoring, verdict } = data;
  const c  = company   || {};
  const m  = metrics   || {};
  const sc = scoring   || {};
  const v  = verdict   || {};

  const arcColor = sc.color === "green" ? "#22c55e" : sc.color === "amber" ? "#f59e0b" : "#ef4444";
  const ratingColor = ["STRONG BUY","BUY"].includes(v.rating) ? "#22c55e"
                    : v.rating === "NEUTRAL" ? "#f59e0b" : "#ef4444";

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${c.symbol} — Risk Scorecard</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;900&family=DM+Sans:wght@400;500;700&display=swap');
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#08090d;color:#e2e8f0;font-family:'DM Sans',sans-serif;padding:24px;min-height:100vh}
  .header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px;padding:20px;background:#0f172a;border:1px solid #1e293b;border-radius:16px}
  .company-name{font-size:22px;font-weight:900;color:#f1f5f9;margin-bottom:4px}
  .ticker{font-family:'JetBrains Mono',monospace;font-size:13px;color:#64748b;background:#1e293b;padding:3px 10px;border-radius:20px}
  .price{font-family:'JetBrains Mono',monospace;font-size:28px;font-weight:900;color:#f1f5f9}
  .chg{font-size:13px;font-weight:700;margin-left:8px;color:${(c.chg_pct||0) >= 0 ? '#22c55e' : '#ef4444'}}
  .gauge-section{text-align:center;padding:20px;background:#0f172a;border:1px solid #1e293b;border-radius:16px;margin-bottom:16px}
  .risk-label{font-size:14px;font-weight:900;letter-spacing:2px;color:${arcColor};margin-top:8px}
  .kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px}
  .kpi{background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:12px;text-align:center}
  .kpi-label{font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}
  .kpi-value{font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:900;color:#f1f5f9}
  .card{background:#0f172a;border:1px solid #1e293b;border-radius:16px;padding:16px;margin-bottom:16px}
  .section-title{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1.5px;font-weight:700;margin-bottom:12px}
  .bar-row{margin-bottom:10px}
  .bar-label{display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px}
  .bar-track{height:6px;background:#1e293b;border-radius:3px;overflow:hidden}
  .bar-fill{height:100%;border-radius:3px}
  .card-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:16px}
  .metric-card{border-radius:12px;padding:12px;border:1px solid}
  .metric-label{font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}
  .metric-value{font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:900}
  .metric-sub{font-size:10px;margin-top:3px;color:#64748b}
  .verdict-box{display:flex;justify-content:space-between;align-items:center;padding:16px;background:#0f172a;border:2px solid ${ratingColor}33;border-radius:16px;margin-top:16px}
  .rating{font-size:18px;font-weight:900;color:${ratingColor};letter-spacing:1px}
  .score-big{font-family:'JetBrains Mono',monospace;font-size:36px;font-weight:900;color:${arcColor}}
  table{width:100%;border-collapse:collapse;font-size:12px}
  th{color:#64748b;text-align:right;padding:6px 8px;border-bottom:1px solid #1e293b;font-weight:600;font-size:10px}
  th:first-child{text-align:left}
  td{padding:8px;border-bottom:1px solid #0f172a33;font-family:'JetBrains Mono',monospace}
  td:first-child{font-family:'DM Sans',sans-serif;color:#cbd5e1}
  .two-col{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  .tag-buy{color:#22c55e} .tag-sell{color:#ef4444}
  .footer{text-align:center;color:#334155;font-size:10px;margin-top:20px}
</style>
</head>
<body>
<div class="header">
  <div>
    <div class="company-name">${c.name || c.symbol}</div>
    <span class="ticker">${c.symbol}</span>
    <div style="margin-top:6px;font-size:11px;color:#64748b">${c.sector || ''} · ${c.industry || ''}</div>
  </div>
  <div style="text-align:right">
    <div class="price">₹${(c.price||0).toLocaleString('en-IN',{maximumFractionDigits:2})}</div>
    <span class="chg">${(c.chg_pct||0) > 0 ? '▲' : '▼'} ${Math.abs(c.chg_pct||0).toFixed(2)}%</span>
    <div style="font-size:11px;color:#64748b;margin-top:4px">
      MCap: ₹${((c.market_cap||0)/1e9).toFixed(1)}B · ${new Date().toLocaleDateString('en-IN')}
    </div>
  </div>
</div>

<div class="gauge-section">
  <div class="section-title" style="margin-bottom:4px">RISK SCORE</div>
  <svg width="200" height="120" viewBox="0 0 200 120" style="display:block;margin:0 auto">
    <path d="M 30 100 A 70 70 0 0 1 170 100" fill="none" stroke="#1e293b" stroke-width="14" stroke-linecap="round"/>
    <path d="M 30 100 A 70 70 0 ${sc.total > 50 ? 1 : 0} 1 ${100 + 70 * Math.cos(Math.PI - (sc.total/100)*Math.PI)} ${100 + 70 * Math.sin(Math.PI - (sc.total/100)*Math.PI)}" fill="none" stroke="${arcColor}" stroke-width="14" stroke-linecap="round"/>
    <text x="100" y="88" text-anchor="middle" fill="white" font-size="36" font-weight="900" font-family="JetBrains Mono,monospace">${sc.total||0}</text>
    <text x="100" y="104" text-anchor="middle" fill="#64748b" font-size="11">/ 100</text>
  </svg>
  <div class="risk-label">${sc.label || ''}</div>
</div>

<div class="kpi-grid">
  ${[
    {l:'P/E', v: m.pe_ratio != null ? m.pe_ratio+'×' : '—'},
    {l:'EV/EBITDA', v: m.ev_ebitda != null ? m.ev_ebitda+'×' : '—'},
    {l:'ROE', v: m.roe != null ? m.roe+'%' : '—'},
    {l:'D/E', v: m.debt_equity != null ? m.debt_equity+'×' : '—'},
    {l:'Rev Growth', v: m.revenue_growth != null ? (m.revenue_growth>0?'+':'')+m.revenue_growth+'%' : '—'},
    {l:'Profit Growth', v: m.profit_growth != null ? (m.profit_growth>0?'+':'')+m.profit_growth+'%' : '—'},
    {l:'FCF', v: m.fcf != null ? (Math.abs(m.fcf)>1e7?(m.fcf<0?'-':'')+'₹'+(Math.abs(m.fcf)/1e7).toFixed(1)+'Cr':'₹'+(m.fcf/1e5).toFixed(0)+'L') : '—'},
    {l:'Div Yield', v: m.dividend_yield != null ? m.dividend_yield+'%' : '—'},
  ].map(k=>`<div class="kpi"><div class="kpi-label">${k.l}</div><div class="kpi-value">${k.v}</div></div>`).join('')}
</div>

<div class="card">
  <div class="section-title">Score Breakdown</div>
  ${[
    {l:'Valuation (35%)', s: sc.valuation?.score||0, m:35, col: (sc.valuation?.pct||0)<35?'#22c55e':(sc.valuation?.pct||0)<65?'#f59e0b':'#ef4444'},
    {l:'Financial Health (35%)', s: sc.financial_health?.score||0, m:35, col: (sc.financial_health?.pct||0)<35?'#22c55e':(sc.financial_health?.pct||0)<65?'#f59e0b':'#ef4444'},
    {l:'Growth (30%)', s: sc.growth?.score||0, m:30, col: (sc.growth?.pct||0)<35?'#22c55e':(sc.growth?.pct||0)<65?'#f59e0b':'#ef4444'},
  ].map(d=>`<div class="bar-row">
    <div class="bar-label"><span style="font-size:12px;color:#cbd5e1">${d.l}</span><span style="font-family:JetBrains Mono,monospace;color:${d.col}">${d.s} / ${d.m}</span></div>
    <div class="bar-track"><div class="bar-fill" style="width:${d.s/d.m*100}%;background:${d.col}"></div></div>
  </div>`).join('')}
</div>

<div class="two-col" style="margin-bottom:16px">
  <div class="card" style="margin-bottom:0">
    <div class="section-title" style="color:#22c55e">🚀 Catalysts</div>
    ${(data.catalysts||[]).map(c=>`<div style="font-size:11px;color:#94a3b8;margin-bottom:6px;line-height:1.5"><span class="tag-buy">+</span> ${c}</div>`).join('')}
  </div>
  <div class="card" style="margin-bottom:0">
    <div class="section-title" style="color:#ef4444">⚠ Risks</div>
    ${(data.risks||[]).map(r=>`<div style="font-size:11px;color:#94a3b8;margin-bottom:6px;line-height:1.5"><span class="tag-sell">−</span> ${r}</div>`).join('')}
  </div>
</div>

${(data.quarterly||[]).length > 0 ? `
<div class="card">
  <div class="section-title">Quarterly Financials</div>
  <table>
    <thead><tr><th>Quarter</th><th>Revenue</th><th>Net Profit</th><th>Net Margin</th></tr></thead>
    <tbody>
    ${(data.quarterly||[]).map(q=>`
      <tr>
        <td>${(q.quarter||'').slice(0,7)}</td>
        <td style="text-align:right">${q.revenue != null ? (Math.abs(q.revenue)>1e7?(q.revenue<0?'-':'')+'₹'+(Math.abs(q.revenue)/1e7).toFixed(1)+'Cr':'₹'+(q.revenue/1e5).toFixed(0)+'L') : '—'}</td>
        <td style="text-align:right;color:${(q.net_profit||0)>0?'#22c55e':'#ef4444'}">${q.net_profit != null ? (Math.abs(q.net_profit)>1e7?(q.net_profit<0?'-':'')+'₹'+(Math.abs(q.net_profit)/1e7).toFixed(1)+'Cr':'₹'+(q.net_profit/1e5).toFixed(0)+'L') : '—'}</td>
        <td style="text-align:right;color:${(q.net_margin||0)>10?'#22c55e':(q.net_margin||0)>0?'#f59e0b':'#ef4444'}">${q.net_margin != null ? q.net_margin+'%' : '—'}</td>
      </tr>`).join('')}
    </tbody>
  </table>
</div>` : ''}

<div class="verdict-box">
  <div>
    <div class="section-title" style="margin-bottom:6px">FINAL VERDICT</div>
    <div class="rating">${v.rating || '—'}</div>
    <div style="font-size:12px;color:#94a3b8;margin-top:6px;max-width:280px">${v.reason || ''}</div>
  </div>
  <div style="text-align:right">
    <div class="score-big">${sc.total||0}</div>
    <div style="font-size:10px;color:#64748b">RISK / 100</div>
  </div>
</div>

<div class="footer">Generated by SimpleQuant · ${new Date().toLocaleString('en-IN')} · For research purposes only. Not financial advice.</div>
</body>
</html>`;
}

// ══════════════════════════════════════════════════════════════════════════════
// Main Component
// ══════════════════════════════════════════════════════════════════════════════
export default function Scorecard({ symbol, onClose }) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const [page,    setPage]    = useState(1);

  const load = useCallback(async (sym) => {
    if (!sym) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/invest/scorecard/${encodeURIComponent(sym)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(`Failed to load scorecard: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (symbol) load(symbol); }, [symbol, load]);

  const c  = data?.company;
  const sc = data?.scoring;
  const rc = riskColor(sc?.color);

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#08090d] border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-sky-500 flex items-center justify-center">
            <span className="text-[9px] font-black text-white">SC</span>
          </div>
          <div>
            <span className="text-sm font-black text-slate-100">{c?.name || symbol}</span>
            <span className="ml-2 text-xs text-slate-500 font-mono">{c?.symbol || symbol}</span>
          </div>
          {sc && (
            <span className={clsx("text-xs font-bold px-2 py-0.5 rounded-full border", rc.text, rc.bg, rc.border)}>
              {sc.total} — {sc.label}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {data && <CopyHtmlButton data={data} />}
          <button onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg bg-panel border border-border text-slate-400 hover:text-slate-100 text-lg">
            ×
          </button>
        </div>
      </div>

      {/* Page tabs */}
      <div className="flex gap-1 px-4 pt-2 bg-[#08090d] shrink-0">
        {[{ n: 1, l: "📊 Snapshot" }, { n: 2, l: "📋 Analysis" }].map(t => (
          <button key={t.n} onClick={() => setPage(t.n)}
            className={clsx("text-xs px-4 py-1.5 rounded-lg font-semibold transition-all",
              page === t.n ? "bg-panel text-slate-100 border border-border" : "text-slate-500 hover:text-slate-300")}>
            {t.l}
          </button>
        ))}
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 bg-[#08090d]">

        {loading && (
          <div className="flex flex-col items-center gap-3 py-16">
            <div className="w-12 h-12 rounded-full border-4 border-border border-t-sky-400 animate-spin" />
            <p className="text-slate-400 text-sm">Fetching live financial data…</p>
          </div>
        )}

        {error && (
          <div className="card border-sell/30 text-sell text-sm">{error}</div>
        )}

        {data && !loading && page === 1 && (
          <>
            {/* Header */}
            <div className="card flex items-center justify-between">
              <div>
                <p className="text-xl font-black text-slate-100">{c?.name}</p>
                <p className="text-xs text-slate-500">{c?.sector} · {c?.industry}</p>
              </div>
              <div className="text-right">
                <p className="text-2xl font-black font-mono text-slate-100">
                  ₹{fmtNum(c?.price)}
                </p>
                <p className={clsx("text-sm font-bold", (c?.chg_pct||0) >= 0 ? "text-buy" : "text-sell")}>
                  {(c?.chg_pct||0) >= 0 ? "▲" : "▼"} {Math.abs(c?.chg_pct||0).toFixed(2)}%
                </p>
                <p className="text-[10px] text-slate-500">
                  MCap: ₹{((c?.market_cap||0)/1e9).toFixed(1)}B
                </p>
              </div>
            </div>

            {/* Gauge */}
            {sc && <div className="card flex flex-col items-center py-4">
              <RiskGauge score={sc.total} label={sc.label} color={sc.color} />
            </div>}

            <KpiStrip metrics={data.metrics} />
            <PriceHistoryChart history={data.price_history} company={c} />
            <ScoreBreakdown scoring={sc} />
            <CardGrid metrics={data.metrics} scoring={sc} />
            <FinalVerdict verdict={data.verdict} scoring={sc} />
          </>
        )}

        {data && !loading && page === 2 && (
          <>
            <QuarterlyTable quarters={data.quarterly} />
            <NewsList news={data.news} />
            <CatalystsRisks catalysts={data.catalysts} risks={data.risks} />
            <FinalVerdict verdict={data.verdict} scoring={sc} />
          </>
        )}
      </div>
    </div>
  );
}
