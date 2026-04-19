import React from "react";
import clsx from "clsx";

const RISK_CONFIG = {
  LOW:    { color: "text-buy  bg-buy/10  border-buy/20",  dot: "bg-buy",  label: "Low Risk"    },
  MEDIUM: { color: "text-hold bg-hold/10 border-hold/20", dot: "bg-hold", label: "Medium Risk"  },
  HIGH:   { color: "text-sell bg-sell/10 border-sell/20", dot: "bg-sell", label: "High Risk"    },
};

export default function RiskBadge({ risk }) {
  const cfg = RISK_CONFIG[risk] || RISK_CONFIG.MEDIUM;
  return (
    <span className={clsx("badge border", cfg.color)}>
      <span className={clsx("w-2 h-2 rounded-full animate-pulse", cfg.dot)} />
      {cfg.label}
    </span>
  );
}
