import React, { useState } from "react";
import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-panel border border-border rounded-xl p-3 shadow-xl text-xs">
      <p className="text-slate-400 mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {typeof p.value === "number" ? p.value.toFixed(2) : p.value}
        </p>
      ))}
    </div>
  );
};

export default function PriceChart({ chart, stopLoss, analysis }) {
  const [view, setView] = useState("price");

  if (!chart) return (
    <div className="card flex items-center justify-center h-64 text-slate-500">
      Loading chart…
    </div>
  );

  const data = chart.dates.map((d, i) => ({
    date:   d.slice(5),   // "MM-DD"
    close:  chart.close[i],
    volume: chart.volume[i],
    sma20:  analysis?.features?.chart_data?.sma_short?.[i] || null,
    sma50:  analysis?.features?.chart_data?.sma_long?.[i] || null,
    rsi:    analysis?.features?.chart_data?.rsi?.[i] || null,
  }));

  const tabs = [
    { id: "price",  label: "Price" },
    { id: "volume", label: "Volume" },
    { id: "rsi",    label: "RSI" },
  ];

  return (
    <div className="card animate-fade-in">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Price Chart</h2>
        <div className="flex gap-1 bg-surface rounded-lg p-1">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setView(t.id)}
              className={`text-xs px-3 py-1.5 rounded-md font-medium transition-all ${
                view === t.id
                  ? "bg-panel text-slate-100 shadow"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={data} margin={{ left: 0, right: 0, top: 4, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} />
          <YAxis
            domain={["auto", "auto"]}
            tick={{ fontSize: 10, fill: "#64748b" }}
            tickLine={false}
            axisLine={false}
            width={50}
          />
          <Tooltip content={<CustomTooltip />} />

          {view === "price" && (
            <>
              <Line type="monotone" dataKey="close" name="Close" stroke="#38bdf8"
                    dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="sma20" name="SMA20" stroke="#f59e0b"
                    dot={false} strokeWidth={1} strokeDasharray="4 2" />
              <Line type="monotone" dataKey="sma50" name="SMA50" stroke="#a78bfa"
                    dot={false} strokeWidth={1} strokeDasharray="4 2" />
              {stopLoss && (
                <ReferenceLine y={stopLoss} stroke="#ef4444" strokeDasharray="6 3"
                               label={{ value: `Stop ₹${stopLoss}`, fill: "#ef4444", fontSize: 10, position: "insideTopRight" }} />
              )}
            </>
          )}
          {view === "volume" && (
            <Bar dataKey="volume" name="Volume" fill="#38bdf8" opacity={0.6} />
          )}
          {view === "rsi" && (
            <>
              <Line type="monotone" dataKey="rsi" name="RSI" stroke="#a78bfa"
                    dot={false} strokeWidth={2} />
              <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="4 2" label={{ value: "70", fill: "#ef4444", fontSize: 9 }} />
              <ReferenceLine y={30} stroke="#22c55e" strokeDasharray="4 2" label={{ value: "30", fill: "#22c55e", fontSize: 9 }} />
            </>
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
