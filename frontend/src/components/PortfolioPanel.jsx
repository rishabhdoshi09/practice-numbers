import React, { useState, useEffect } from "react";
import { fetchPortfolio, placeOrder } from "../utils/api";
import { fmtINR, fmtPct } from "../utils/format";

export default function PortfolioPanel({ symbol, decision }) {
  const [portfolio, setPortfolio] = useState(null);
  const [placing, setPlacing] = useState(false);
  const [lastFill, setLastFill] = useState(null);

  const load = () => fetchPortfolio().then((r) => setPortfolio(r.data)).catch(() => {});

  useEffect(() => { load(); }, []);

  const handleOrder = async (side) => {
    setPlacing(true);
    try {
      const r = await placeOrder(symbol, side, 50000);
      setLastFill(r.data);
      await load();
    } catch (e) {
      console.error(e);
    } finally {
      setPlacing(false);
    }
  };

  if (!portfolio) return null;
  const pnlColor = portfolio.total_pnl_inr >= 0 ? "text-buy" : "text-sell";

  return (
    <div className="card animate-slide-up">
      <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">Paper Portfolio</h2>

      <div className="grid grid-cols-3 gap-2 mb-4">
        <div className="bg-surface rounded-xl p-3 text-center">
          <p className="text-xs text-slate-400 mb-1">Value</p>
          <p className="text-sm font-bold text-slate-100">{fmtINR(portfolio.portfolio_value)}</p>
        </div>
        <div className="bg-surface rounded-xl p-3 text-center">
          <p className="text-xs text-slate-400 mb-1">P&amp;L</p>
          <p className={`text-sm font-bold ${pnlColor}`}>{fmtINR(portfolio.total_pnl_inr)}</p>
        </div>
        <div className="bg-surface rounded-xl p-3 text-center">
          <p className="text-xs text-slate-400 mb-1">Sharpe</p>
          <p className="text-sm font-bold text-slate-100">
            {portfolio.metrics?.sharpe_ratio ?? "—"}
          </p>
        </div>
      </div>

      {/* Quick order buttons */}
      <div className="flex gap-2">
        <button
          onClick={() => handleOrder("BUY")}
          disabled={placing}
          className="btn flex-1 bg-buy hover:bg-buy/90 text-white focus:ring-buy"
        >
          {placing ? "…" : "Paper BUY ₹50k"}
        </button>
        <button
          onClick={() => handleOrder("SELL")}
          disabled={placing}
          className="btn flex-1 bg-sell hover:bg-sell/90 text-white focus:ring-sell"
        >
          {placing ? "…" : "Paper SELL"}
        </button>
      </div>

      {lastFill && (
        <div className="mt-3 bg-surface rounded-xl p-3 text-xs font-mono text-slate-400">
          Fill #{lastFill.order_id} · {lastFill.side} {lastFill.qty} @ ₹{lastFill.fill_price}
        </div>
      )}

      {portfolio.positions?.length > 0 && (
        <div className="mt-4">
          <p className="text-xs text-slate-400 font-medium mb-2">Open Positions</p>
          <div className="space-y-2">
            {portfolio.positions.map((p) => (
              <div key={p.symbol} className="flex justify-between items-center text-sm">
                <span className="text-slate-300">{p.symbol.split(".")[0]}</span>
                <span className={p.unrealised_pnl_inr >= 0 ? "text-buy" : "text-sell"}>
                  {fmtINR(p.unrealised_pnl_inr)} ({fmtPct(p.unrealised_pnl_pct)})
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
