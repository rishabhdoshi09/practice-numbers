import React, { useState, useCallback } from "react";
import clsx from "clsx";
import { fmtINR } from "../utils/format";

const API = process.env.REACT_APP_API_URL || "http://localhost:8000";

const pctColor = (v) => (v >= 0 ? "text-buy" : "text-sell");
const pctFmt   = (v) => `${v >= 0 ? "+" : ""}${Number(v).toFixed(1)}%`;

// ── Stage header ──────────────────────────────────────────────────────────────
function StageHeader({ num, title, subtitle, done }) {
  return (
    <div className="flex items-center gap-3 mb-3">
      <div className={clsx(
        "w-8 h-8 rounded-full flex items-center justify-center text-xs font-black shrink-0",
        done ? "bg-buy text-white" : "bg-panel border border-border text-slate-400"
      )}>
        {done ? "✓" : num}
      </div>
      <div>
        <p className="text-sm font-bold text-slate-100">{title}</p>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      </div>
    </div>
  );
}

// ── Stage 1: Screening ─────────────────────────────────────────────────────────
function Stage1({ data }) {
  if (!data) return null;
  const { total_scanned, elapsed_sec, summary, top_candidates } = data;
  return (
    <div className="card space-y-3">
      <StageHeader num="1" title="Stage 1 — Screening" subtitle={`${total_scanned} stocks scored in ${elapsed_sec}s`} done />
      <div className="flex gap-2">
        <span className="badge bg-buy/10 border border-buy/30 text-buy">▲ {summary?.buy_count} BUY</span>
        <span className="badge bg-sell/10 border border-sell/30 text-sell">▼ {summary?.sell_count} SELL</span>
        <span className="badge bg-hold/10 border border-hold/30 text-hold">— {summary?.hold_count} WAIT</span>
      </div>
      <p className="text-xs text-slate-400">Top candidates advancing to adversarial research:</p>
      <div className="flex flex-wrap gap-1">
        {top_candidates?.map((s) => (
          <span key={s.symbol} className="text-xs bg-buy/10 border border-buy/20 text-buy rounded-lg px-2 py-1 font-semibold">
            {s.name} {s.confidence?.toFixed(0)}%
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Stage 2: Adversarial ───────────────────────────────────────────────────────
function Stage2({ data }) {
  const [idx, setIdx] = useState(0);
  if (!data?.length) return null;
  const stock = data[idx];

  const verdictStyle = {
    "STRONG BUY":  "text-buy bg-buy/10 border-buy/30",
    "BUY":         "text-buy bg-buy/10 border-buy/30",
    "NEUTRAL":     "text-hold bg-hold/10 border-hold/30",
    "SELL":        "text-sell bg-sell/10 border-sell/30",
    "STRONG SELL": "text-sell bg-sell/10 border-sell/30",
  }[stock.verdict] || "text-slate-400 bg-panel border-border";

  return (
    <div className="card space-y-3">
      <StageHeader num="2" title="Stage 2 — Adversarial Research" subtitle="Bull vs Bear debate — only last 7 days of signals count" done />

      {/* Stock tabs */}
      <div className="flex gap-1 overflow-x-auto pb-1 no-scrollbar">
        {data.map((s, i) => (
          <button key={s.symbol} onClick={() => setIdx(i)}
            className={clsx("text-xs px-3 py-1.5 rounded-lg font-semibold whitespace-nowrap shrink-0 transition-all",
              i === idx ? "bg-panel text-slate-100 border border-border" : "text-slate-500 hover:text-slate-300")}>
            {s.name?.split(" ")[0]}
          </button>
        ))}
      </div>

      {/* Bull/Bear score bar */}
      <div>
        <div className="flex justify-between text-xs mb-1">
          <span className="text-buy font-semibold">🐂 Bull {stock.bull_pct?.toFixed(0)}%</span>
          <span className="text-sell font-semibold">🐻 Bear {stock.bear_pct?.toFixed(0)}%</span>
        </div>
        <div className="h-3 bg-surface rounded-full overflow-hidden flex">
          <div className="bg-buy h-full rounded-l-full transition-all duration-700"
               style={{ width: `${stock.bull_pct}%` }} />
          <div className="bg-sell h-full rounded-r-full transition-all duration-700"
               style={{ width: `${stock.bear_pct}%` }} />
        </div>
      </div>

      {/* Verdict */}
      <div className={clsx("text-center py-1.5 rounded-xl text-sm font-black tracking-widest border", verdictStyle)}>
        VERDICT: {stock.verdict}
      </div>

      {/* Arguments side-by-side */}
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <p className="text-xs text-buy font-semibold mb-1">🐂 Bull Case</p>
          {stock.bull_arguments?.map((a, i) => (
            <div key={i} className="text-xs text-slate-300 bg-buy/5 border border-buy/10 rounded-lg p-2 leading-snug">
              {a.arg}
            </div>
          ))}
        </div>
        <div className="space-y-1">
          <p className="text-xs text-sell font-semibold mb-1">🐻 Bear Case</p>
          {stock.bear_arguments?.map((a, i) => (
            <div key={i} className="text-xs text-slate-300 bg-sell/5 border border-sell/10 rounded-lg p-2 leading-snug">
              {a.arg}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Stage 3: Scenario Modeling ─────────────────────────────────────────────────
function Stage3({ data }) {
  const [idx, setIdx] = useState(0);
  if (!data?.length) return null;
  const sc = data[idx];
  const horizons = sc?.horizons || {};

  return (
    <div className="card space-y-3">
      <StageHeader num="3" title="Stage 3 — Scenario Modeling" subtitle="Bull / Base / Bear price targets" done />

      {/* Stock tabs */}
      <div className="flex gap-1 overflow-x-auto pb-1 no-scrollbar">
        {data.map((s, i) => (
          <button key={s.symbol} onClick={() => setIdx(i)}
            className={clsx("text-xs px-3 py-1.5 rounded-lg font-semibold whitespace-nowrap shrink-0 transition-all",
              i === idx ? "bg-panel text-slate-100 border border-border" : "text-slate-500 hover:text-slate-300")}>
            {s.symbol?.replace(".NS", "")}
          </button>
        ))}
      </div>

      {/* Probability weights */}
      {sc?.probabilities && (
        <div className="flex gap-2 text-xs">
          <span className="bg-buy/10 border border-buy/20 text-buy rounded-lg px-2 py-1">
            🐂 Bull {sc.probabilities.bull}%
          </span>
          <span className="bg-hold/10 border border-hold/20 text-hold rounded-lg px-2 py-1">
            〜 Base {sc.probabilities.base}%
          </span>
          <span className="bg-sell/10 border border-sell/20 text-sell rounded-lg px-2 py-1">
            🐻 Bear {sc.probabilities.bear}%
          </span>
        </div>
      )}

      {/* Price target table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-border">
              <th className="text-left py-1 pr-2">Horizon</th>
              <th className="text-right py-1 px-1 text-buy">Bull</th>
              <th className="text-right py-1 px-1 text-hold">Base</th>
              <th className="text-right py-1 px-1 text-sell">Bear</th>
              <th className="text-right py-1 pl-1 text-sky-400">Wtd</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(horizons).map(([h, v]) => (
              <tr key={h} className="border-b border-border/40 last:border-0">
                <td className="py-1.5 pr-2 font-semibold text-slate-300 uppercase">{h}</td>
                <td className="py-1.5 px-1 text-right">
                  <span className="text-buy font-mono">{fmtINR(v.bull)}</span>
                  <span className={clsx("ml-1", pctColor(v.bull_pct))}>({pctFmt(v.bull_pct)})</span>
                </td>
                <td className="py-1.5 px-1 text-right">
                  <span className="text-slate-200 font-mono">{fmtINR(v.base)}</span>
                  <span className={clsx("ml-1", pctColor(v.base_pct))}>({pctFmt(v.base_pct)})</span>
                </td>
                <td className="py-1.5 px-1 text-right">
                  <span className="text-sell font-mono">{fmtINR(v.bear)}</span>
                  <span className={clsx("ml-1", pctColor(v.bear_pct))}>({pctFmt(v.bear_pct)})</span>
                </td>
                <td className="py-1.5 pl-1 text-right">
                  <span className="text-sky-400 font-mono font-semibold">{fmtINR(v.weighted)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500 text-right">
        Current: {fmtINR(sc.current_price)} · Annual vol: {sc.annual_vol}%
      </p>
    </div>
  );
}

// ── Stage 4: Portfolio Construction ───────────────────────────────────────────
function Stage4({ data, capital }) {
  if (!data) return null;
  if (data.error) return (
    <div className="card">
      <StageHeader num="4" title="Stage 4 — Portfolio Construction" />
      <p className="text-sell text-sm">{data.error}</p>
    </div>
  );

  const { positions, portfolio_stats, sector_allocation, n_positions } = data;

  return (
    <div className="card space-y-3">
      <StageHeader num="4" title="Stage 4 — Portfolio Construction"
        subtitle={`${n_positions} positions · ₹${(capital / 100000).toFixed(1)}L capital · Max-Sharpe Markowitz`} done />

      {/* Portfolio KPIs */}
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: "Exp. Return", value: `${portfolio_stats?.expected_return_pct?.toFixed(1)}%`, color: "text-buy" },
          { label: "Volatility",  value: `${portfolio_stats?.volatility_pct?.toFixed(1)}%`,     color: "text-sell" },
          { label: "Sharpe",      value: portfolio_stats?.sharpe_ratio?.toFixed(2),              color: "text-sky-400" },
        ].map((k) => (
          <div key={k.label} className="bg-surface rounded-xl p-2 text-center">
            <p className="text-xs text-slate-400 mb-0.5">{k.label}</p>
            <p className={clsx("text-base font-black", k.color)}>{k.value}</p>
          </div>
        ))}
      </div>

      {/* Sector allocation */}
      <div>
        <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">Sector Allocation</p>
        <div className="space-y-1">
          {Object.entries(sector_allocation || {}).map(([sec, pct]) => (
            <div key={sec} className="flex items-center gap-2">
              <span className="text-xs text-slate-400 w-20 shrink-0 truncate">{sec}</span>
              <div className="flex-1 h-3 bg-surface rounded overflow-hidden">
                <div className="h-full bg-sky-500/70 rounded transition-all duration-700"
                     style={{ width: `${Math.min(100, pct * (100/35))}%` }} />
              </div>
              <span className="text-xs font-mono text-slate-300 w-10 text-right">{pct?.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* Positions table */}
      <div className="space-y-1.5">
        <p className="text-xs text-slate-400 uppercase tracking-wider">Positions</p>
        {positions?.map((p, i) => (
          <div key={p.symbol} className="flex items-center justify-between bg-surface rounded-xl px-3 py-2">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500 w-4">{i + 1}</span>
              <div>
                <p className="text-xs font-bold text-slate-100">{p.name}</p>
                <p className="text-xs text-slate-500">{p.sector}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm font-black text-sky-400">{p.weight_pct?.toFixed(1)}%</p>
              <p className="text-xs text-slate-500">₹{(p.alloc_inr / 1000).toFixed(0)}K · {p.shares} sh</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Stage 5: Rebalancing ───────────────────────────────────────────────────────
function Stage5({ data }) {
  if (!data) return null;
  const { holds, sells, swaps, new_opportunities, summary } = data;

  return (
    <div className="card space-y-3">
      <StageHeader num="5" title="Stage 5 — Rebalancing" subtitle="Master orchestrator compares portfolio vs latest scan" done />

      {/* Summary badges */}
      <div className="flex gap-2 flex-wrap">
        <span className="badge bg-buy/10 border-buy/30 text-buy">✓ {summary?.hold_count} Hold</span>
        {summary?.sell_count > 0 && (
          <span className="badge bg-sell/10 border-sell/30 text-sell">✕ {summary?.sell_count} Sell</span>
        )}
        {summary?.swap_count > 0 && (
          <span className="badge bg-hold/10 border-hold/30 text-hold">⇄ {summary?.swap_count} Swap</span>
        )}
        {summary?.add_count > 0 && (
          <span className="badge bg-sky-500/10 border-sky-500/30 text-sky-400">+ {summary?.add_count} New</span>
        )}
      </div>

      {/* Sells */}
      {sells?.map((s) => (
        <div key={s.symbol} className="bg-sell/5 border border-sell/20 rounded-xl p-3">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-sm font-bold text-sell">SELL — {s.name}</p>
              <p className="text-xs text-slate-400 mt-0.5">{s.reason}</p>
            </div>
            <span className="badge bg-sell/10 border-sell/30 text-sell text-xs">EXIT</span>
          </div>
        </div>
      ))}

      {/* Swaps */}
      {swaps?.map((sw, i) => (
        <div key={i} className="bg-hold/5 border border-hold/20 rounded-xl p-3 space-y-2">
          <p className="text-xs font-bold text-hold uppercase tracking-wide">⇄ Swap</p>
          <p className="text-xs text-slate-300">{sw.rationale}</p>
          <div className="flex gap-2 text-xs">
            <span className="bg-sell/10 border border-sell/20 text-sell rounded-lg px-2 py-1">
              ✕ Sell {sw.sell?.name}
            </span>
            <span className="bg-buy/10 border border-buy/20 text-buy rounded-lg px-2 py-1">
              ✓ Buy {sw.buy?.name}
            </span>
          </div>
        </div>
      ))}

      {/* New opportunities */}
      {new_opportunities?.length > 0 && (
        <div>
          <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">New Opportunities</p>
          {new_opportunities.map((s) => (
            <div key={s.symbol} className="flex justify-between items-center bg-surface rounded-xl px-3 py-2 mb-1.5">
              <div>
                <p className="text-xs font-bold text-slate-100">{s.name}</p>
                <p className="text-xs text-slate-500">{s.sector} · {s.symbol.replace(".NS","")}</p>
              </div>
              <span className="text-buy font-black text-sm">{s.confidence?.toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}

      {/* Holds summary */}
      {holds?.length > 0 && summary?.sell_count === 0 && summary?.swap_count === 0 && (
        <div className="bg-buy/5 border border-buy/10 rounded-xl p-3 text-center">
          <p className="text-buy text-sm font-semibold">Portfolio is optimal — all {holds.length} positions intact</p>
          <p className="text-xs text-slate-400 mt-1">No rebalancing required at this time</p>
        </div>
      )}
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────
export default function InvestPanel({ onSelectStock }) {
  const [pipeline, setPipeline] = useState(null);
  const [loading,  setLoading]  = useState(false);
  const [capital,  setCapital]  = useState(500000);
  const [error,    setError]    = useState(null);

  const runPipeline = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res  = await fetch(`${API}/invest/pipeline?capital=${capital}`);
      const data = await res.json();
      setPipeline(data);
    } catch (e) {
      setError("Pipeline failed — check server connection");
    } finally {
      setLoading(false);
    }
  }, [capital]);

  const CAPITAL_OPTIONS = [
    { label: "₹1L",  value: 100000  },
    { label: "₹5L",  value: 500000  },
    { label: "₹10L", value: 1000000 },
    { label: "₹25L", value: 2500000 },
  ];

  return (
    <div className="space-y-4 animate-slide-up">
      {/* Header */}
      <div>
        <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
          <span className="text-sky-400">🤖</span> Autonomous Invest
        </h2>
        <p className="text-xs text-slate-500 mt-0.5">
          5-stage pipeline: Screen → Debate → Scenarios → Build → Rebalance
        </p>
      </div>

      {/* Capital selector */}
      <div className="card space-y-2">
        <p className="text-xs text-slate-400 uppercase tracking-wider">Capital to Deploy</p>
        <div className="flex gap-2">
          {CAPITAL_OPTIONS.map((o) => (
            <button key={o.value} onClick={() => setCapital(o.value)}
              className={clsx("flex-1 text-xs py-2 rounded-xl font-semibold transition-all border",
                capital === o.value
                  ? "bg-sky-500/20 text-sky-400 border-sky-500/30"
                  : "bg-surface text-slate-400 border-border hover:text-slate-200")}>
              {o.label}
            </button>
          ))}
        </div>
      </div>

      {/* Run button */}
      <button
        onClick={runPipeline}
        disabled={loading}
        className="w-full btn bg-sky-500 hover:bg-sky-400 text-white font-black text-sm py-4 rounded-2xl transition-all disabled:opacity-50"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Running 5-stage pipeline…
          </span>
        ) : "🤖 Run Investment Pipeline"}
      </button>

      {error && (
        <div className="card border-sell/30 text-sell text-sm">⚠ {error}</div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="card flex flex-col items-center gap-3 py-8 text-center">
          <div className="relative w-12 h-12">
            <div className="absolute inset-0 rounded-full border-4 border-border" />
            <div className="absolute inset-0 rounded-full border-4 border-t-sky-400 animate-spin" />
          </div>
          <p className="text-slate-300 font-medium text-sm">Running autonomous pipeline…</p>
          <div className="space-y-1 text-xs text-slate-500">
            <p>Stage 1: Screening Nifty 50 stocks</p>
            <p>Stage 2: Bull vs Bear adversarial debate</p>
            <p>Stage 3: Building scenario models</p>
            <p>Stage 4: Markowitz portfolio optimisation</p>
            <p>Stage 5: Generating rebalancing plan</p>
          </div>
        </div>
      )}

      {/* Results */}
      {pipeline && !loading && (
        <>
          <Stage1 data={pipeline.stage1_screening} />
          <Stage2 data={pipeline.stage2_adversarial} />
          <Stage3 data={pipeline.stage3_scenarios} />
          <Stage4 data={pipeline.stage4_portfolio} capital={pipeline.capital} />
          <Stage5 data={pipeline.stage5_rebalance} />
        </>
      )}

      {/* Empty state */}
      {!pipeline && !loading && (
        <div className="card flex flex-col items-center gap-4 py-10 text-center">
          <div className="text-5xl">🤖</div>
          <div>
            <p className="text-slate-200 font-bold">AI Portfolio Manager</p>
            <p className="text-slate-500 text-sm mt-1 leading-relaxed">
              Screens all 50 Nifty stocks · runs bull/bear debate ·<br />
              models 4 price horizons · builds optimal portfolio ·<br />
              recommends rebalancing trades
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
