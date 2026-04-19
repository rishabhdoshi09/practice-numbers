import React from "react";
import clsx from "clsx";

export default function ConfidenceMeter({ confidence, action }) {
  const color = { BUY: "#22c55e", SELL: "#ef4444", HOLD: "#f59e0b" }[action] || "#94a3b8";
  const segments = 20;
  const filled   = Math.round((confidence / 100) * segments);

  return (
    <div className="flex flex-col items-center gap-2">
      <p className="text-xs text-slate-400 font-medium uppercase tracking-widest">Confidence</p>

      {/* Arc gauge using SVG */}
      <svg width="160" height="90" viewBox="0 0 160 90">
        <defs>
          <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"   stopColor="#ef4444" />
            <stop offset="50%"  stopColor="#f59e0b" />
            <stop offset="100%" stopColor="#22c55e" />
          </linearGradient>
        </defs>
        {/* Track */}
        <path
          d="M 10 80 A 70 70 0 0 1 150 80"
          fill="none" stroke="#334155" strokeWidth="12" strokeLinecap="round"
        />
        {/* Fill — dash trick to animate fill */}
        <path
          d="M 10 80 A 70 70 0 0 1 150 80"
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray="220"
          strokeDashoffset={220 - (confidence / 100) * 220}
          style={{ transition: "stroke-dashoffset 0.8s ease-out" }}
        />
        {/* Value label */}
        <text x="80" y="78" textAnchor="middle" fontSize="26" fontWeight="800"
              fill="white" fontFamily="Inter, sans-serif">
          {Math.round(confidence)}
        </text>
        <text x="80" y="92" textAnchor="middle" fontSize="11"
              fill="#94a3b8" fontFamily="Inter, sans-serif">
          out of 100
        </text>
      </svg>

      {/* Segment bar */}
      <div className="flex gap-1">
        {Array.from({ length: segments }).map((_, i) => (
          <div
            key={i}
            className={clsx("h-1.5 w-3 rounded-full transition-all duration-300")}
            style={{ backgroundColor: i < filled ? color : "#334155" }}
          />
        ))}
      </div>
    </div>
  );
}
