export const fmtINR = (n) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);

export const fmtPct = (n, decimals = 2) => `${n >= 0 ? "+" : ""}${Number(n).toFixed(decimals)}%`;

export const fmtNum = (n, decimals = 2) => Number(n).toFixed(decimals);

export const colorForAction = (action) => ({
  BUY:  "buy",
  SELL: "sell",
  HOLD: "hold",
}[action] || "hold");

export const colorForRisk = (risk) => ({
  LOW:    "text-buy",
  MEDIUM: "text-hold",
  HIGH:   "text-sell",
}[risk] || "text-slate-400");

export const bgForAction = (action) => ({
  BUY:  "bg-buy/10 border-buy/30 text-buy",
  SELL: "bg-sell/10 border-sell/30 text-sell",
  HOLD: "bg-hold/10 border-hold/30 text-hold",
}[action] || "");
