import React, { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";
import { fetchMonteCarlo, optimizePortfolio } from "../utils/api";
import { fmtPct } from "../utils/format";

const PORTFOLIO_SYMBOLS = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"];

function ModelTable({ analysis }) {
  if (!analysis) return null;
  const ml = analysis.features?.model_details?.ml;
  const arima = analysis.features?.model_details?.arima;
  const garch = analysis.features?.model_details?.garch;

  const rows = [
    { name: "ARIMA Forecast (5d)", value: arima?.forecast_return !== undefined ? fmtPct(arima.forecast_return) : "—", model: arima?.model },
    { name: "GARCH Annual Vol",    value: garch?.annual_vol_estimate !== undefined ? fmtPct(garch.annual_vol_estimate * 100) : "—", model: garch?.model },
    { name: "LR Prob Up",          value: ml?.logistic_regression?.probability_up !== undefined ? `${(ml.logistic_regression.probability_up * 100).toFixed(1)}%` : "—", model: `Acc: ${(ml?.logistic_regression?.test_accuracy * 100)?.toFixed(1) || "—"}%` },
    { name: "RF Prob Up",          value: ml?.random_forest?.probability_up !== undefined ? `${(ml.random_forest.probability_up * 100).toFixed(1)}%` : "—", model: `Acc: ${(ml?.random_forest?.test_accuracy * 100)?.toFixed(1) || "—"}%` },
    { name: "Ensemble Prob Up",    value: ml?.ensemble_probability_up !== undefined ? `${(ml.ensemble_probability_up * 100).toFixed(1)}%` : "—", model: "LR + RF" },
  ];

  return (
    <div className="card animate-fade-in">
      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Model Output Table</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-slate-500 border-b border-border">
            <th className="text-left pb-2">Metric</th>
            <th className="text-right pb-2">Value</th>
            <th className="text-right pb-2">Model</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((r) => (
            <tr key={r.name}>
              <td className="py-2 text-slate-300">{r.name}</td>
              <td className="py-2 text-right font-mono font-semibold text-slate-100">{r.value}</td>
              <td className="py-2 text-right text-xs text-slate-500 font-mono">{r.model}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MonteCarloChart({ symbol }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchMonteCarlo(symbol, 500, 30)
      .then((r) => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [symbol]);

  if (loading) return <div className="card h-48 flex items-center justify-center text-slate-500 text-sm">Running Monte Carlo…</div>;
  if (!data) return null;

  const chartData = Array.from({ length: 30 }).map((_, i) => ({
    day: i + 1,
    p5:  data.fan_chart?.["5"]?.[i],
    p25: data.fan_chart?.["25"]?.[i],
    p50: data.fan_chart?.["50"]?.[i],
    p75: data.fan_chart?.["75"]?.[i],
    p95: data.fan_chart?.["95"]?.[i],
  }));

  return (
    <div className="card animate-fade-in">
      <div className="flex justify-between items-start mb-3">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Monte Carlo — 30-Day Fan Chart</h3>
        <div className="text-right">
          <p className="text-xs text-slate-400">P(up): <span className="text-buy font-semibold">{(data.prob_up * 100).toFixed(1)}%</span></p>
          <p className="text-xs text-slate-400">Expected: <span className="text-slate-200 font-semibold">₹{data.expected_price}</span></p>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="day" tick={{ fontSize: 9, fill: "#64748b" }} label={{ value: "Days", position: "insideBottom", offset: -2, fill: "#64748b", fontSize: 9 }} />
          <YAxis tick={{ fontSize: 9, fill: "#64748b" }} width={52} tickLine={false} axisLine={false} />
          <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 12, fontSize: 11 }} />
          <Line type="monotone" dataKey="p95" stroke="#22c55e" dot={false} strokeWidth={1} strokeDasharray="3 2" name="95th %" />
          <Line type="monotone" dataKey="p75" stroke="#86efac" dot={false} strokeWidth={1.5} name="75th %" />
          <Line type="monotone" dataKey="p50" stroke="#38bdf8" dot={false} strokeWidth={2}   name="Median" />
          <Line type="monotone" dataKey="p25" stroke="#fca5a5" dot={false} strokeWidth={1.5} name="25th %" />
          <Line type="monotone" dataKey="p5"  stroke="#ef4444" dot={false} strokeWidth={1} strokeDasharray="3 2" name="5th %" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function PortfolioOptimizer() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const run = () => {
    setLoading(true);
    optimizePortfolio(PORTFOLIO_SYMBOLS)
      .then((r) => setResult(r.data))
      .catch(() => setResult(null))
      .finally(() => setLoading(false));
  };

  return (
    <div className="card animate-fade-in">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Portfolio Optimizer (Markowitz)</h3>
        <button onClick={run} disabled={loading}
          className="btn bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs py-1.5 px-3">
          {loading ? "Running…" : "Optimise"}
        </button>
      </div>
      {result && (
        <div className="grid grid-cols-2 gap-3">
          {["max_sharpe", "min_variance"].map((key) => (
            <div key={key} className="bg-surface rounded-xl p-3">
              <p className="text-xs font-semibold text-slate-400 mb-2">
                {key === "max_sharpe" ? "Max Sharpe" : "Min Variance"}
              </p>
              <p className="text-xs text-slate-300 mb-1">
                Return: <span className="text-buy font-semibold">{fmtPct(result[key].expected_return * 100)}</span>
              </p>
              <p className="text-xs text-slate-300 mb-2">
                Sharpe: <span className="text-slate-100 font-semibold">{result[key].sharpe_ratio.toFixed(2)}</span>
              </p>
              <div className="space-y-1">
                {Object.entries(result[key].weights).map(([sym, w]) => (
                  <div key={sym} className="flex justify-between text-xs">
                    <span className="text-slate-400">{sym.split(".")[0]}</span>
                    <span className="font-mono text-slate-200">{(w * 100).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AdvancedPanel({ analysis, symbol }) {
  return (
    <div className="space-y-4 animate-slide-up">
      <div className="flex items-center gap-2 mb-1">
        <div className="h-px flex-1 bg-border" />
        <span className="text-xs text-slate-500 font-medium uppercase tracking-widest px-2">Advanced Mode</span>
        <div className="h-px flex-1 bg-border" />
      </div>
      <ModelTable analysis={analysis} />
      <MonteCarloChart symbol={symbol} />
      <PortfolioOptimizer />
    </div>
  );
}
