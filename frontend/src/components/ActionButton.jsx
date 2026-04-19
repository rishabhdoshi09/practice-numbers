import React from "react";
import clsx from "clsx";

const CONFIG = {
  BUY: {
    label: "BUY",
    emoji: "↑",
    base:  "bg-buy hover:bg-buy/90 text-white",
    glow:  "animate-glow-buy shadow-[0_0_30px_rgba(34,197,94,0.5)]",
    ring:  "focus:ring-buy",
  },
  SELL: {
    label: "SELL",
    emoji: "↓",
    base:  "bg-sell hover:bg-sell/90 text-white",
    glow:  "animate-glow-sell shadow-[0_0_30px_rgba(239,68,68,0.5)]",
    ring:  "focus:ring-sell",
  },
  HOLD: {
    label: "WAIT",
    emoji: "—",
    base:  "bg-hold hover:bg-hold/90 text-white",
    glow:  "",
    ring:  "focus:ring-hold",
  },
};

export default function ActionButton({ action, confidence, onClick }) {
  const cfg = CONFIG[action] || CONFIG.HOLD;

  return (
    <button
      onClick={onClick}
      className={clsx(
        "relative flex flex-col items-center justify-center",
        "w-56 h-56 rounded-full text-center cursor-pointer",
        "transition-all duration-300 focus:outline-none focus:ring-4 focus:ring-offset-4 focus:ring-offset-surface",
        "active:scale-95 select-none",
        cfg.base, cfg.glow, cfg.ring,
      )}
      aria-label={`${cfg.label} — ${confidence}% confidence`}
    >
      <span className="text-5xl font-black tracking-tight leading-none">{cfg.label}</span>
      <span className="text-2xl mt-1 opacity-80">{cfg.emoji}</span>
      <span className="text-sm mt-3 font-semibold opacity-90">{confidence}% confident</span>
    </button>
  );
}
