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
import Loader           from "./components/Loader";
import { fmtINR }       from "./utils/format";

export default function App() {
  const [symbol,   setSymbol]   = useState("RELIANCE.NS");
  const [advanced, setAdvanced] = useState(false);
  const [screen,   setScreen]   = useState("home"); // "home" | "detail"

  const { decision, analysis, chart, loading, error, reload } = useAnalysis(symbol);

  const action     = decision?.decision?.action      || "HOLD";
  const confidence = decision?.decision?.confidence  || 0;
  const riskLevel  = decision?.decision?.risk_level  || "MEDIUM";
  const price      = decision?.price                 || 0;
  const stopLoss   = decision?.stop_loss;

  return (
    <div className="min-h-screen bg-surface flex flex-col">
      {/* ── Top bar ─────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 bg-surface/80 backdrop-blur border-b border-border">
        <div className="max-w-lg mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-sky-500 flex items-center justify-center">
              <span className="text-xs font-black text-white">SQ</span>
            </div>
            <span className="font-bold text-slate-100 text-base tracking-tight">SimpleQuant</span>
          </div>
          <div className="flex items-center gap-2">
            {/* Advanced toggle */}
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
            {/* Refresh */}
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

      {/* ── Main content ─────────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-lg mx-auto w-full px-4 py-6 space-y-5">

        {/* Stock selector */}
        <StockSelector value={symbol} onChange={(s) => { setSymbol(s); setScreen("home"); }} />

        {/* Error state */}
        {error && (
          <div className="card border-sell/30 text-sell text-sm">
            ⚠ {error}
          </div>
        )}

        {/* Loading state */}
        {loading && <Loader label="Running quant analysis…" />}

        {/* ── HOME SCREEN ───────────────────────────────────────────────────── */}
        {!loading && decision && (
          <>
            {/* Price header */}
            <div className="flex items-end justify-between">
              <div>
                <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">
                  {symbol.split(".")[0]}
                </p>
                <p className="text-3xl font-black text-slate-100">
                  {fmtINR(price)}
                </p>
              </div>
              <RiskBadge risk={riskLevel} />
            </div>

            {/* ── THE BIG BUTTON ────────────────────────────────────────────── */}
            <div className="flex flex-col items-center gap-6 py-4">
              <ActionButton
                action={action}
                confidence={Math.round(confidence)}
                onClick={() => setScreen(screen === "detail" ? "home" : "detail")}
              />
              <ConfidenceMeter action={action} confidence={confidence} />
            </div>

            {/* Stop loss callout */}
            {stopLoss && (
              <div className="flex items-center gap-3 bg-sell/5 border border-sell/20 rounded-xl px-4 py-3">
                <div className="w-1.5 h-8 bg-sell rounded-full" />
                <div>
                  <p className="text-xs text-slate-400">Stop Loss Level</p>
                  <p className="text-lg font-bold text-sell">{fmtINR(stopLoss)}</p>
                </div>
              </div>
            )}

            {/* Tap-to-expand detail screen */}
            {screen === "detail" && (
              <div className="space-y-4 animate-slide-up">
                <PriceChart chart={chart} stopLoss={stopLoss} analysis={analysis} />
                <SignalBreakdown
                  breakdown={decision?.decision?.signal_breakdown}
                  agreePct={decision?.decision?.signals_agree}
                />
                <NewsPanel news={analysis?.news} />
                <RiskPanel risk={analysis?.risk} />
                <PortfolioPanel symbol={symbol} decision={decision} />
              </div>
            )}

            {/* Advanced quant panel */}
            {advanced && (
              <AdvancedPanel analysis={analysis} symbol={symbol} />
            )}

            {/* "Tap to see detail" prompt */}
            {screen === "home" && !advanced && (
              <button
                onClick={() => setScreen("detail")}
                className="w-full text-center text-sm text-slate-500 hover:text-slate-300 transition-colors py-2"
              >
                Tap the button for details ↓
              </button>
            )}
          </>
        )}
      </main>

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      <footer className="border-t border-border py-4">
        <p className="text-center text-xs text-slate-600">
          SimpleQuant · Paper trading only · Not financial advice
        </p>
      </footer>
    </div>
  );
}
