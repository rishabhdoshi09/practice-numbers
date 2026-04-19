import React from "react";

const SYMBOLS = [
  "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
  "HINDUNILVR.NS", "BAJFINANCE.NS", "WIPRO.NS", "SBIN.NS", "TATAMOTORS.NS",
  "ADANIPORTS.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BHARTIARTL.NS", "ITC.NS",
];

const DISPLAY = {
  "RELIANCE.NS":   "Reliance",   "TCS.NS":        "TCS",        "INFY.NS":    "Infosys",
  "HDFCBANK.NS":   "HDFC Bank",  "ICICIBANK.NS":  "ICICI Bank", "HINDUNILVR.NS": "HUL",
  "BAJFINANCE.NS": "Bajaj Fin",  "WIPRO.NS":      "Wipro",      "SBIN.NS":    "SBI",
  "TATAMOTORS.NS": "Tata Motors","ADANIPORTS.NS": "Adani Ports","ASIANPAINT.NS": "Asian Paint",
  "AXISBANK.NS":   "Axis Bank",  "BHARTIARTL.NS": "Airtel",     "ITC.NS":     "ITC",
};

export default function StockSelector({ value, onChange }) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-panel border border-border text-slate-100 text-base font-semibold
                   rounded-xl px-4 py-3 appearance-none cursor-pointer
                   focus:outline-none focus:ring-2 focus:ring-slate-500 transition-all"
      >
        {SYMBOLS.map((sym) => (
          <option key={sym} value={sym}>{DISPLAY[sym] || sym} ({sym.split(".")[0]})</option>
        ))}
      </select>
      <div className="pointer-events-none absolute inset-y-0 right-4 flex items-center">
        <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>
    </div>
  );
}
