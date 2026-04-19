import React, { useState } from "react";
import clsx from "clsx";
import { useAnalysis } from "./hooks/useAnalysis";

import StockSelector    from "./components/StockSelector";
import ActionButton     from "./components/ActionButton";
import ConfidenceMeter  from "./components/ConfidenceMeter";
import RiskBadge        from "./components/RiskBadge";
import PriceChart       from "./components/PriceChart";
import SignalBreakdown  from "./components/SignalBreakdown";
import NewsPanel        from "./components/NewsPanel";
import RiskPanel        from "./components/RiskPanel";
import AdvancedPanel    from "./components/AdvancedPanel";
import PortfolioPanel   from "./components/PortfolioPanel";
import JarvisScan       from "./components/JarvisScan";
import DailyReport      from "./components/DailyReport";
import InvestPanel      from "./components/InvestPanel";
import Scorecard        from "./components/Scorecard";
import Loader           from "./components/Loader";
import { fmtINR }       from "./utils/format";

const NAV = [
  { id: "single",    label: "Single",    icon: "◎" },
  { id: "jarvis",    label: "JARVIS",    icon: "⚡" },
  { id: "report",    label: "Pulse",     icon: "📰" },
  { id: "invest",    label: "Invest",    icon: "🤖" },
  { id: "portfolio", label: "Portfolio", icon: "◈" },
];

export default function App() {
  const [symbol,    setSymbol]    = useState("RELIANCE.NS");
  const [advanced,  setAdvanced]  = useState(false);
  const [detail,    setDetail]    = useState(false);
  const [nav,       setNav]       = useState("single");
  const [scorecard, setScorecard] = useState(false);

  const { decision, analysis, chart, loading, error, reload } = useAnalysis(symbol);

  const action     = decision?.decision?.action     || "HOLD";
  const confidence = decision?.decision?.confidence || 0;
  const riskLevel  = decision?.decision?.risk_level || "MEDIUM";
  const price      = decision?.price                || 0;
  const stopLoss   = decision?.stop_loss;

  const handleJarvisSelect = (sym) => {
    setSymbol(sym);
    setNav("single");
    setDetail(true);
  };

  return (
    <div className="min-h-screen bg-surface flex flex-col">
      {/* ── Top bar ─────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 bg-surface/80 backdrop-blur border-b border-border">
        <div className="max-w-lg mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-sky-500 flex items-center justify-center">
              <span className="text-xs font-black text-white">SQ</span>
            </div>
            <span className="font-bold text-slate-100 text-base tracking-tight">SimpleQuant</span>
            {nav === "jarvis" && (
              <span className="text-xs font-semibold text-sky-400 bg-sky-500/10 border border-sky-500/20 rounded-full px-2 py-0.5">
                JARVIS
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {nav === "single" && (
              <button
                onClick={() => setAdvanced(!advanced)}
                className={clsx(
                  "text-xs px-3 py-1.5 rounded-lg font-medium transition-all",
                  advanced
                    ? "bg-sky-500/20 text-sky-400 border border-sky-500/30"
                    : "bg-panel text-slate-400 border border-border hover:text-slate-200"
                )}
              >
                {advanced ? "Simple" : "Advanced"}
              </button>
            )}
            <button
              onClick={reload}
              className="w-8 h-8 bg-panel border border-border rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-200 transition-colors"
            >
              <svg className={clsx("w-4 h-4", loading && "animate-spin")} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* ── Main ─────────────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-lg mx-auto w-full px-4 py-5 space-y-4">

        {/* ── JARVIS tab ──────────────────────────────────────────────────── */}
        {nav === "jarvis" && (
          <JarvisScan onSelectStock={handleJarvisSelect} />
        )}

        {/* ── Daily Report tab ─────────────────────────────────────────────── */}
        {nav === "report" && (
          <DailyReport onSelectStock={(sym) => { setSymbol(sym); setNav("single"); setDetail(true); }} />
        )}

        {/* ── Invest tab ───────────────────────────────────────────────────── */}
        {nav === "invest" && (
          <InvestPanel onSelectStock={(sym) => { setSymbol(sym); setNav("single"); setDetail(true); }} />
        )}

        {/* ── Portfolio tab ────────────────────────────────────────────────── */}
        {nav === "portfolio" && (
          <PortfolioPanel symbol={symbol} decision={decision} standalone />
        )}

        {/* ── Single stock tab ──────────────────────────────────────────────── */}
        {nav === "single" && (
          <>
            <StockSelector value={symbol} onChange={(s) => { setSymbol(s); setDetail(false); }} />

            {error && (
              <div className="card border-sell/30 text-sell text-sm">⚠ {error}</div>
            )}

            {loading && <Loader label="Running quant analysis…" />}

            {!loading && decision && (
              <>
                {/* Price header */}
                <div className="flex items-end justify-between">
                  <div>
                    <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">
                      {symbol.split(".")[0]}
                      {decision.data_source === "kite_live" && (
                        <span className="ml-2 text-buy font-semibold">● LIVE</span>
                      )}
                    </p>
                    <p className="text-3xl font-black text-slate-100">{fmtINR(price)}</p>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <RiskBadge risk={riskLevel} />
                    <button
                      onClick={() => setScorecard(true)}
                      className="text-xs px-3 py-1.5 rounded-lg bg-sky-500/10 border border-sky-500/20 text-sky-400 hover:bg-sky-500/20 transition-all font-semibold"
                    >
                      📊 Scorecard
                    </button>
                  </div>
                </div>

                {/* BIG BUTTON */}
                <div className="flex flex-col items-center gap-5 py-2">
                  <ActionButton
                    action={action}
                    confidence={Math.round(confidence)}
                    onClick={() => setDetail(!detail)}
                  />
                  <ConfidenceMeter action={action} confidence={confidence} />
                </div>

                {/* Stop loss */}
                {stopLoss && (
                  <div className="flex items-center gap-3 bg-sell/5 border border-sell/20 rounded-xl px-4 py-3">
                    <div className="w-1.5 h-8 bg-sell rounded-full" />
                    <div>
                      <p className="text-xs text-slate-400">Stop Loss Level</p>
                      <p className="text-lg font-bold text-sell">{fmtINR(stopLoss)}</p>
                    </div>
                  </div>
                )}

                {/* Detail screen */}
                {detail && (
                  <div className="space-y-4 animate-slide-up">
                    <PriceChart chart={chart} stopLoss={stopLoss} analysis={analysis} />
                    <SignalBreakdown
                      breakdown={decision?.decision?.signal_breakdown}
                      agreePct={decision?.decision?.signals_agree}
                    />
                    <NewsPanel news={analysis?.news} />
                    <RiskPanel risk={analysis?.risk} />
                  </div>
                )}

                {/* Advanced panel */}
                {advanced && <AdvancedPanel analysis={analysis} symbol={symbol} />}

                {!detail && !advanced && (
                  <button onClick={() => setDetail(true)}
                    className="w-full text-center text-sm text-slate-500 hover:text-slate-300 transition-colors py-2">
                    Tap the button for details ↓
                  </button>
                )}
              </>
            )}
          </>
        )}
      </main>

      {/* ── Bottom nav ────────────────────────────────────────────────────── */}
      <nav className="sticky bottom-0 z-40 bg-surface/90 backdrop-blur border-t border-border">
        <div className="max-w-lg mx-auto px-4 py-2 flex gap-1">
          {NAV.map((item) => (
            <button
              key={item.id}
              onClick={() => setNav(item.id)}
              className={clsx(
                "flex-1 flex flex-col items-center gap-0.5 py-2 rounded-xl transition-all text-xs font-semibold",
                nav === item.id
                  ? "bg-panel text-slate-100"
                  : "text-slate-500 hover:text-slate-300"
              )}
            >
              <span className="text-base leading-none">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      </nav>

      {/* ── Scorecard modal ───────────────────────────────────────────────── */}
      {scorecard && (
        <Scorecard symbol={symbol} onClose={() => setScorecard(false)} />
      )}
    </div>
  );
}
