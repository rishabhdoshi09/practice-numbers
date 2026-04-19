import React, { useState, useEffect, useCallback } from "react";
import clsx from "clsx";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell,
} from "recharts";

const API = process.env.REACT_APP_API_URL || "http://localhost:8000";

// ── Helpers ────────────────────────────────────────────────────────────────────
const fmt  = (v, d = 2)  => v != null ? Number(v).toLocaleString("en-IN", { maximumFractionDigits: d }) : "—";
const fmtP = (v)         => v != null ? `${v >= 0 ? "+" : ""}${Number(v).toFixed(2)}%` : "—";

const actionColor = (a) =>
  a === "LONG"  ? { text: "text-buy",  bg: "bg-buy/10",  border: "border-buy/30"  } :
  a === "SHORT" ? { text: "text-sell", bg: "bg-sell/10", border: "border-sell/30" } :
                  { text: "text-slate-400", bg: "bg-panel", border: "border-border" };

const TF_OPTIONS = [
  { label: "5m",  value: "5m"  },
  { label: "15m", value: "15m" },
  { label: "1D",  value: "1d"  },
];

// ── Mini Stat Box ──────────────────────────────────────────────────────────────
function Stat({ label, value, color = "text-slate-100" }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-slate-500 uppercase tracking-wider">{label}</span>
      <span className={clsx("text-sm font-bold font-mono", color)}>{value}</span>
    </div>
  );
}

// ── Signal Card ────────────────────────────────────────────────────────────────
function SignalCard({ sig }) {
  const c = actionColor(sig.action);
  return (
    <div className={clsx("rounded-xl border p-4 space-y-3", c.bg, c.border)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={clsx("text-base font-black", c.text)}>{sig.action}</span>
          <span className="text-xs text-slate-400 bg-panel px-2 py-0.5 rounded-full border border-border">
            {sig.setup}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">Confidence</span>
          <span className={clsx("text-sm font-bold", c.text)}>
            {Math.round((sig.confidence || 0) * 100)}%
          </span>
        </div>
      </div>

      {/* Reason */}
      <p className="text-xs text-slate-400 leading-relaxed">{sig.reason}</p>

      {/* Levels grid */}
      {sig.action !== "HOLD" && (
        <div className="grid grid-cols-4 gap-2">
          <Stat label="Entry"    value={`₹${fmt(sig.entry)}`} />
          <Stat label="Stop"     value={`₹${fmt(sig.stop_loss)}`}  color="text-sell" />
          <Stat label="Target 1" value={`₹${fmt(sig.target_1)}`}   color="text-buy"  />
          <Stat label="R/R"      value={sig.risk_reward != null ? `1:${sig.risk_reward}` : "—"} color="text-sky-400" />
        </div>
      )}

      {/* Context */}
      {sig.context && (
        <div className="flex flex-wrap gap-3 pt-1 border-t border-border/50">
          <span className="text-xs text-slate-500">
            POC ₹{fmt(sig.context.poc)} &nbsp;·&nbsp;
            VAH ₹{fmt(sig.context.vah)} &nbsp;·&nbsp;
            VAL ₹{fmt(sig.context.val)}
          </span>
          <span className={clsx(
            "text-xs font-semibold ml-auto",
            sig.context.trend === "UP" ? "text-buy" : "text-sell"
          )}>
            {sig.context.trend === "UP" ? "▲ UPTREND" : "▼ DOWNTREND"}
          </span>
        </div>
      )}
    </div>
  );
}

// ── Volume Histogram (horizontal) ─────────────────────────────────────────────
function VolumeHistogram({ profile, price }) {
  if (!profile || !profile.bins) return null;

  const { bins, volumes, poc, vah, val, hvn = [], lvn = [] } = profile;
  const maxVol = Math.max(...volumes);

  const data = bins.map((b, i) => ({
    price: b,
    vol:   volumes[i],
    isPoc: Math.abs(b - poc) < (bins[1] - bins[0]) * 0.5,
    isHvn: hvn.some(h => Math.abs(b - h) < (bins[1] - bins[0]) * 1.5),
    isLvn: lvn.some(l => Math.abs(b - l) < (bins[1] - bins[0]) * 1.5),
    isVah: Math.abs(b - vah) < (bins[1] - bins[0]) * 0.5,
    isVal: Math.abs(b - val) < (bins[1] - bins[0]) * 0.5,
  })).reverse(); // highest price at top

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-300">Volume Profile</h3>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span><span className="text-yellow-400">■</span> POC</span>
          <span><span className="text-buy">■</span> HVN</span>
          <span><span className="text-slate-500">■</span> LVN</span>
          <span><span className="text-sky-400 border-b border-dashed border-sky-400">—</span> VAH/VAL</span>
        </div>
      </div>

      <div style={{ height: 320 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: 10, bottom: 0, left: 52 }}
            barSize={3}
          >
            <XAxis type="number" hide domain={[0, maxVol]} />
            <YAxis
              type="number"
              dataKey="price"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(v) => `₹${Math.round(v)}`}
              tick={{ fill: "#94a3b8", fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              width={50}
            />
            <Tooltip
              cursor={false}
              contentStyle={{ background: "#0f1117", border: "1px solid #1e2433", borderRadius: 8, fontSize: 12 }}
              labelFormatter={(v) => `₹${fmt(v)}`}
              formatter={(v) => [`${(v / 1e6).toFixed(2)}M`, "Volume"]}
            />
            {/* VAH line */}
            <ReferenceLine y={vah} stroke="#38bdf8" strokeDasharray="4 3" strokeWidth={1.5}
              label={{ value: "VAH", position: "insideTopRight", fill: "#38bdf8", fontSize: 10 }} />
            {/* VAL line */}
            <ReferenceLine y={val} stroke="#38bdf8" strokeDasharray="4 3" strokeWidth={1.5}
              label={{ value: "VAL", position: "insideBottomRight", fill: "#38bdf8", fontSize: 10 }} />
            {/* POC line */}
            <ReferenceLine y={poc} stroke="#fbbf24" strokeDasharray="0" strokeWidth={1.5}
              label={{ value: "POC", position: "insideTopRight", fill: "#fbbf24", fontSize: 10 }} />
            {/* Current price */}
            {price && (
              <ReferenceLine y={price} stroke="#e2e8f0" strokeDasharray="2 3" strokeWidth={1}
                label={{ value: "NOW", position: "insideTopRight", fill: "#e2e8f0", fontSize: 10 }} />
            )}
            <Bar dataKey="vol" radius={[0, 2, 2, 0]}>
              {data.map((d, i) => (
                <Cell
                  key={i}
                  fill={
                    d.isPoc ? "#fbbf24" :
                    d.isHvn ? "#22c55e" :
                    d.isLvn ? "#475569" :
                    "#334155"
                  }
                  fillOpacity={d.isHvn || d.isPoc ? 0.9 : 0.55}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Key levels strip */}
      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-border">
        <div className="text-center">
          <p className="text-xs text-yellow-400 font-semibold">POC</p>
          <p className="text-sm font-bold font-mono text-slate-100">₹{fmt(poc)}</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-sky-400 font-semibold">VAH</p>
          <p className="text-sm font-bold font-mono text-slate-100">₹{fmt(vah)}</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-sky-400 font-semibold">VAL</p>
          <p className="text-sm font-bold font-mono text-slate-100">₹{fmt(val)}</p>
        </div>
      </div>
    </div>
  );
}

// ── HVN / LVN Level Tags ───────────────────────────────────────────────────────
function LevelTags({ profile }) {
  if (!profile) return null;
  const { hvn = [], lvn = [] } = profile;
  return (
    <div className="card space-y-3">
      <h3 className="text-sm font-semibold text-slate-300">Volume Nodes</h3>
      <div className="space-y-2">
        {hvn.length > 0 && (
          <div>
            <p className="text-xs text-slate-500 mb-1.5">High Volume Nodes (acceptance / support)</p>
            <div className="flex flex-wrap gap-1.5">
              {hvn.map((h, i) => (
                <span key={i} className="text-xs font-mono bg-buy/10 text-buy border border-buy/20 px-2 py-0.5 rounded-md">
                  ₹{fmt(h)}
                </span>
              ))}
            </div>
          </div>
        )}
        {lvn.length > 0 && (
          <div>
            <p className="text-xs text-slate-500 mb-1.5">Low Volume Nodes (breakout / rejection zones)</p>
            <div className="flex flex-wrap gap-1.5">
              {lvn.map((l, i) => (
                <span key={i} className="text-xs font-mono bg-sell/10 text-sell border border-sell/20 px-2 py-0.5 rounded-md">
                  ₹{fmt(l)}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Backtest Metrics ───────────────────────────────────────────────────────────
function BacktestPanel({ bt }) {
  if (!bt) return null;
  if (bt.error) return (
    <div className="card text-xs text-slate-500">Backtest unavailable: {bt.error}</div>
  );
  if (!bt.total_trades) return (
    <div className="card text-xs text-slate-500">Not enough signals to backtest on this timeframe.</div>
  );

  const winRatePct = Math.round((bt.win_rate || 0) * 100);
  const ddColor    = bt.max_drawdown_pct > 15 ? "text-sell" : bt.max_drawdown_pct > 8 ? "text-hold" : "text-buy";
  const wr_color   = winRatePct >= 55 ? "text-buy" : winRatePct >= 45 ? "text-hold" : "text-sell";

  return (
    <div className="card space-y-4">
      <h3 className="text-sm font-semibold text-slate-300">Backtest Results
        <span className="ml-2 text-xs text-slate-500 font-normal">{bt.total_trades} trades</span>
      </h3>

      {/* Metrics grid */}
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Win Rate"    value={`${winRatePct}%`}             color={wr_color} />
        <Stat label="Avg R:R"     value={bt.avg_rr != null ? `1:${bt.avg_rr}` : "—"} color="text-sky-400" />
        <Stat label="Sharpe"      value={bt.sharpe_ratio?.toFixed(2) ?? "—"} color="text-slate-100" />
        <Stat label="Max Drawdown" value={`-${(bt.max_drawdown_pct || 0).toFixed(1)}%`} color={ddColor} />
        <Stat label="Profit Factor" value={bt.profit_factor?.toFixed(2) ?? "—"} color="text-slate-100" />
        <Stat label="Total Return" value={fmtP(bt.total_return_pct)} color={bt.total_return_pct >= 0 ? "text-buy" : "text-sell"} />
      </div>

      {/* Setup breakdown */}
      {bt.setup_breakdown && Object.keys(bt.setup_breakdown).length > 0 && (
        <div className="border-t border-border pt-3 space-y-2">
          <p className="text-xs text-slate-500 uppercase tracking-wider">By Setup</p>
          {Object.entries(bt.setup_breakdown).map(([setup, s]) => (
            <div key={setup} className="flex items-center gap-3">
              <span className="text-xs text-slate-400 flex-1 truncate">{setup}</span>
              <span className="text-xs text-slate-500">{s.trades}T</span>
              <div className="w-16 h-1.5 bg-panel rounded-full overflow-hidden">
                <div
                  className={clsx("h-full rounded-full transition-all", s.win_rate >= 0.5 ? "bg-buy" : "bg-sell")}
                  style={{ width: `${Math.min(s.win_rate * 100, 100)}%` }}
                />
              </div>
              <span className={clsx("text-xs font-mono", s.win_rate >= 0.5 ? "text-buy" : "text-sell")}>
                {Math.round(s.win_rate * 100)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Recent trades */}
      {bt.trades && bt.trades.length > 0 && (
        <div className="border-t border-border pt-3 space-y-2">
          <p className="text-xs text-slate-500 uppercase tracking-wider">Recent Trades</p>
          <div className="space-y-1 max-h-48 overflow-y-auto pr-1">
            {bt.trades.slice(-15).reverse().map((t, i) => (
              <div key={i} className="flex items-center justify-between py-1 px-2 rounded-lg bg-panel/60">
                <div className="flex items-center gap-2 min-w-0">
                  <span className={clsx(
                    "text-xs font-bold w-10 shrink-0",
                    t.action === "LONG" ? "text-buy" : "text-sell"
                  )}>
                    {t.action}
                  </span>
                  <span className="text-xs text-slate-500 truncate">{t.date}</span>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-xs text-slate-400 font-mono">₹{fmt(t.entry)}</span>
                  <span className={clsx(
                    "text-xs font-bold font-mono",
                    t.pnl_pct >= 0 ? "text-buy" : "text-sell"
                  )}>
                    {fmtP(t.pnl_pct)}
                  </span>
                  <span className={clsx(
                    "w-2 h-2 rounded-full shrink-0",
                    t.won ? "bg-buy" : "bg-sell"
                  )} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Modal ─────────────────────────────────────────────────────────────────
export default function VolumeProfileModal({ symbol, price, onClose }) {
  const [tf,      setTf]      = useState("1d");
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API}/vp/${encodeURIComponent(symbol)}?timeframe=${tf}&lookback=60&backtest=true`);
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || `HTTP ${r.status}`);
      }
      setData(await r.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [symbol, tf]);

  useEffect(() => { load(); }, [load]);

  const profile = data?.profile;
  const signals = data?.signals || [];
  const backtest = data?.backtest;
  const topSignal = signals.find(s => s.action !== "HOLD") || signals[0];

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-surface">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-surface/90 backdrop-blur border-b border-border px-4 py-3">
        <div className="max-w-lg mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-sky-500/20 border border-sky-500/30 flex items-center justify-center">
              <span className="text-xs font-black text-sky-400">VP</span>
            </div>
            <div>
              <p className="text-sm font-bold text-slate-100">{symbol.split(".")[0]}</p>
              <p className="text-xs text-slate-500">Volume Profile</p>
            </div>
            {price && (
              <span className="text-xs font-mono text-slate-400 ml-1">₹{fmt(price)}</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* Timeframe selector */}
            <div className="flex gap-1">
              {TF_OPTIONS.map(o => (
                <button
                  key={o.value}
                  onClick={() => setTf(o.value)}
                  className={clsx(
                    "text-xs px-2.5 py-1.5 rounded-lg font-semibold transition-all",
                    tf === o.value
                      ? "bg-sky-500/20 text-sky-400 border border-sky-500/30"
                      : "text-slate-500 hover:text-slate-300 border border-transparent"
                  )}
                >
                  {o.label}
                </button>
              ))}
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg bg-panel border border-border flex items-center justify-center text-slate-400 hover:text-slate-200"
            >
              ✕
            </button>
          </div>
        </div>
      </header>

      {/* Body */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-lg mx-auto px-4 py-4 space-y-4">

          {/* Error */}
          {error && (
            <div className="card border-sell/30 text-sell text-sm">⚠ {error}</div>
          )}

          {/* Loading */}
          {loading && (
            <div className="flex flex-col items-center gap-3 py-16">
              <div className="w-8 h-8 border-2 border-sky-500/30 border-t-sky-500 rounded-full animate-spin" />
              <p className="text-sm text-slate-500">Computing volume profile…</p>
            </div>
          )}

          {!loading && data && (
            <>
              {/* Top signal banner */}
              {topSignal && <SignalCard sig={topSignal} />}

              {/* Additional signals */}
              {signals.filter((s, i) => i > 0 && s.action !== "HOLD").map((s, i) => (
                <SignalCard key={i} sig={s} />
              ))}

              {/* Volume histogram */}
              <VolumeHistogram profile={profile} price={price} />

              {/* HVN / LVN tags */}
              <LevelTags profile={profile} />

              {/* Backtest */}
              <BacktestPanel bt={backtest} />

              {/* Meta */}
              <p className="text-center text-xs text-slate-600 pb-4">
                {data.bars} bars · {data.timeframe} · lookback {data.lookback}
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
