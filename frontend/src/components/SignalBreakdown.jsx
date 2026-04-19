import React from "react";
import clsx from "clsx";

const SIGNAL_LABELS = {
  trend:       "Trend",
  momentum:    "Momentum",
  arima:       "ARIMA Forecast",
  volatility:  "Volatility",
  gbm:         "GBM Simulation",
  ml:          "Machine Learning",
  sentiment:   "News Sentiment",
  mean_revert: "Mean Reversion",
};

function SignalRow({ name, data }) {
  const val = data.raw_signal;
  const pct = ((val + 1) / 2) * 100;  // map [-1,1] to [0,100]
  const bullish = val >= 0;

  return (
    <div className="flex items-center gap-3 py-2">
      <div className="w-28 shrink-0">
        <p className="text-xs text-slate-300 font-medium leading-tight">{SIGNAL_LABELS[name] || name}</p>
        <p className="text-xs text-slate-500">{data.weight * 100}% weight</p>
      </div>

      <div className="flex-1 relative h-2 bg-surface rounded-full overflow-hidden">
        {/* Centre marker */}
        <div className="absolute inset-y-0 left-1/2 w-px bg-border z-10" />
        {bullish ? (
          <div
            className="absolute inset-y-0 left-1/2 bg-buy rounded-r-full transition-all duration-700"
            style={{ width: `${Math.abs(val) * 50}%` }}
          />
        ) : (
          <div
            className="absolute inset-y-0 right-1/2 bg-sell rounded-l-full transition-all duration-700"
            style={{ width: `${Math.abs(val) * 50}%` }}
          />
        )}
      </div>

      <div className="w-14 text-right shrink-0">
        <span className={clsx("text-xs font-mono font-semibold",
          val > 0.1 ? "text-buy" : val < -0.1 ? "text-sell" : "text-slate-400")}>
          {val > 0 ? "+" : ""}{val.toFixed(3)}
        </span>
      </div>
    </div>
  );
}

export default function SignalBreakdown({ breakdown, agreePct }) {
  if (!breakdown) return null;

  return (
    <div className="card animate-slide-up">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Signal Breakdown</h2>
        <span className="text-xs text-slate-400">
          <span className="text-slate-200 font-semibold">{agreePct}%</span> of signals agree
        </span>
      </div>

      <div className="divide-y divide-border">
        {Object.entries(breakdown).map(([name, data]) => (
          <SignalRow key={name} name={name} data={data} />
        ))}
      </div>
    </div>
  );
}
