import React from "react";
import clsx from "clsx";

const SENTIMENT_STYLE = {
  positive: "text-buy bg-buy/10 border-buy/20",
  negative: "text-sell bg-sell/10 border-sell/20",
  neutral:  "text-slate-400 bg-slate-700/30 border-slate-600",
};

export default function NewsPanel({ news }) {
  if (!news?.length) return null;

  return (
    <div className="card animate-slide-up">
      <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">News & Sentiment</h2>
      <div className="flex flex-col gap-3">
        {news.slice(0, 3).map((item, i) => (
          <div key={i} className="flex gap-3 items-start">
            <span className={clsx("badge border shrink-0 mt-0.5", SENTIMENT_STYLE[item.sentiment])}>
              {item.sentiment === "positive" ? "▲" : item.sentiment === "negative" ? "▼" : "–"}
            </span>
            <div>
              <p className="text-sm text-slate-200 leading-snug">{item.headline}</p>
              <p className="text-xs text-slate-500 mt-0.5">{item.source} · {new Date(item.timestamp).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
