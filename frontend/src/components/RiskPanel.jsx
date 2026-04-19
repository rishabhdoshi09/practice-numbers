import React from "react";
import { fmtINR, fmtPct } from "../utils/format";

function Metric({ label, value, sub, highlight }) {
  return (
    <div className="bg-surface rounded-xl p-3">
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className={`text-base font-bold ${highlight || "text-slate-100"}`}>{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
    </div>
  );
}

export default function RiskPanel({ risk }) {
  if (!risk) return null;
  const { position_sizing, stop_loss, drawdown, var: varData, portfolio_value } = risk;

  return (
    <div className="card animate-slide-up">
      <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">Risk Metrics</h2>

      {drawdown?.halt_trading && (
        <div className="bg-sell/10 border border-sell/30 rounded-xl p-3 mb-4 text-sm text-sell font-semibold">
          ⚠ Max drawdown limit reached — trading halted
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 mb-4">
        <Metric
          label="Recommended Position"
          value={fmtINR(position_sizing?.recommended_inr)}
          sub={`${position_sizing?.recommended_pct}% of portfolio (Half-Kelly)`}
        />
        <Metric
          label="Stop Loss"
          value={`₹${stop_loss?.price}`}
          sub={`${stop_loss?.distance_pct}% below entry · ${stop_loss?.multiplier}×ATR`}
          highlight="text-sell"
        />
        <Metric
          label="VaR 95% (1-day)"
          value={fmtPct(varData?.var_95_pct)}
          sub={fmtINR(varData?.var_95_inr) + " at risk"}
          highlight="text-hold"
        />
        <Metric
          label="VaR 99% (1-day)"
          value={fmtPct(varData?.var_99_pct)}
          sub={fmtINR(varData?.var_99_inr) + " at risk"}
          highlight="text-sell"
        />
      </div>

      {/* Drawdown gauge */}
      <div>
        <div className="flex justify-between text-xs text-slate-400 mb-1.5">
          <span>Drawdown</span>
          <span>{drawdown?.current_pct}% / {drawdown?.halt_threshold_pct}% limit</span>
        </div>
        <div className="h-2 bg-surface rounded-full overflow-hidden">
          <div
            className="h-full bg-sell rounded-full transition-all duration-700"
            style={{ width: `${Math.min(100, (drawdown?.current_pct / drawdown?.halt_threshold_pct) * 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
}
