import React, { useState, useEffect, useRef, useCallback } from "react";
import clsx from "clsx";

const API = process.env.REACT_APP_API_URL || "http://localhost:8000";

// Inline fallback so the selector works even if the API is slow
const FALLBACK = [
  { symbol: "RELIANCE.NS",   name: "Reliance Industries",  sector: "Energy"   },
  { symbol: "TCS.NS",        name: "TCS",                  sector: "IT"       },
  { symbol: "HDFCBANK.NS",   name: "HDFC Bank",            sector: "Banking"  },
  { symbol: "ICICIBANK.NS",  name: "ICICI Bank",           sector: "Banking"  },
  { symbol: "INFY.NS",       name: "Infosys",              sector: "IT"       },
  { symbol: "SBIN.NS",       name: "SBI",                  sector: "Banking"  },
  { symbol: "BHARTIARTL.NS", name: "Bharti Airtel",        sector: "Telecom"  },
  { symbol: "WIPRO.NS",      name: "Wipro",                sector: "IT"       },
  { symbol: "HINDUNILVR.NS", name: "HUL",                  sector: "FMCG"    },
  { symbol: "ITC.NS",        name: "ITC",                  sector: "FMCG"    },
  { symbol: "BAJFINANCE.NS", name: "Bajaj Finance",        sector: "NBFC"    },
  { symbol: "TATAMOTORS.NS", name: "Tata Motors",          sector: "Auto"    },
  { symbol: "AXISBANK.NS",   name: "Axis Bank",            sector: "Banking" },
  { symbol: "KOTAKBANK.NS",  name: "Kotak Bank",           sector: "Banking" },
  { symbol: "LT.NS",         name: "L&T",                  sector: "Infra"   },
  { symbol: "MARUTI.NS",     name: "Maruti Suzuki",        sector: "Auto"    },
  { symbol: "SUNPHARMA.NS",  name: "Sun Pharma",           sector: "Pharma"  },
  { symbol: "ASIANPAINT.NS", name: "Asian Paints",         sector: "Consumer"},
  { symbol: "TITAN.NS",      name: "Titan",                sector: "Consumer"},
  { symbol: "ADANIPORTS.NS", name: "Adani Ports",          sector: "Infra"   },
];

function highlight(text, query) {
  if (!query) return text;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-sky-500/30 text-sky-300 rounded">{text.slice(idx, idx + query.length)}</mark>
      {text.slice(idx + query.length)}
    </>
  );
}

export default function StockSelector({ value, onChange }) {
  const [universe,  setUniverse]  = useState(FALLBACK);
  const [query,     setQuery]     = useState("");
  const [open,      setOpen]      = useState(false);
  const [loading,   setLoading]   = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef  = useRef(null);
  const listRef   = useRef(null);
  const wrapRef   = useRef(null);

  // Fetch full universe once on mount
  useEffect(() => {
    setLoading(true);
    fetch(`${API}/scan/universe`)
      .then(r => r.json())
      .then(d => {
        if (d.symbols && d.symbols.length > 0) {
          // Build display objects from symbol list + sector counts
          // Backend returns {symbols: [...], sectors: {...}}
          // We need to cross-reference with full_universe metadata
          fetch(`${API}/symbols/search?q=&limit=5000`)
            .then(r => r.json())
            .then(sd => {
              if (sd.results && sd.results.length > 0) {
                setUniverse(sd.results);
              }
            })
            .catch(() => {});
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = useCallback(() => {
    const q = query.trim().toLowerCase();
    if (!q) return universe.slice(0, 80);
    return universe.filter(s =>
      s.symbol.toLowerCase().includes(q) ||
      s.name.toLowerCase().includes(q) ||
      (s.sector || "").toLowerCase().includes(q)
    ).slice(0, 60);
  }, [universe, query]);

  const results = filtered();

  // Current display name
  const current = universe.find(s => s.symbol === value);
  const displayName = current
    ? `${current.name} (${current.symbol.split(".")[0]})`
    : value?.split(".")[0] || "Select stock";

  const select = (sym) => {
    onChange(sym);
    setQuery("");
    setOpen(false);
  };

  const handleKey = (e) => {
    if (!open) { if (e.key === "Enter" || e.key === "ArrowDown") setOpen(true); return; }
    if (e.key === "ArrowDown") { e.preventDefault(); setActiveIdx(i => Math.min(i + 1, results.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActiveIdx(i => Math.max(i - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); if (results[activeIdx]) select(results[activeIdx].symbol); }
    else if (e.key === "Escape") { setOpen(false); setQuery(""); }
  };

  // Scroll active item into view
  useEffect(() => {
    if (listRef.current) {
      const el = listRef.current.children[activeIdx];
      if (el) el.scrollIntoView({ block: "nearest" });
    }
  }, [activeIdx]);

  useEffect(() => { setActiveIdx(0); }, [query]);

  return (
    <div ref={wrapRef} className="relative">
      {/* Trigger / search input */}
      <div
        className={clsx(
          "w-full bg-panel border rounded-xl px-4 py-3 flex items-center gap-3 cursor-text transition-all",
          open ? "border-sky-500/50 ring-2 ring-sky-500/20" : "border-border hover:border-slate-500"
        )}
        onClick={() => { setOpen(true); inputRef.current?.focus(); }}
      >
        <svg className="w-4 h-4 text-slate-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"/>
        </svg>

        {open ? (
          <input
            ref={inputRef}
            autoFocus
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Search by name, symbol or sector…"
            className="flex-1 bg-transparent text-slate-100 text-sm outline-none placeholder-slate-500"
          />
        ) : (
          <span className="flex-1 text-slate-100 text-base font-semibold truncate">{displayName}</span>
        )}

        <div className="flex items-center gap-2 shrink-0">
          {loading && (
            <div className="w-3 h-3 border border-sky-500/40 border-t-sky-500 rounded-full animate-spin" />
          )}
          <span className="text-xs text-slate-500 bg-surface px-1.5 py-0.5 rounded font-mono">
            {universe.length.toLocaleString()}
          </span>
          <svg className={clsx("w-4 h-4 text-slate-400 transition-transform", open && "rotate-180")}
            fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-panel border border-border rounded-xl shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="px-3 py-2 border-b border-border flex items-center justify-between">
            <span className="text-xs text-slate-500">
              {query ? `${results.length} results` : `${universe.length.toLocaleString()} stocks — NSE + BSE`}
            </span>
            {!query && (
              <span className="text-xs text-slate-600">Type to search</span>
            )}
          </div>

          {/* Results list */}
          <div ref={listRef} className="max-h-72 overflow-y-auto">
            {results.length === 0 ? (
              <div className="px-4 py-6 text-center text-slate-500 text-sm">
                No results for "{query}"
                <div className="mt-2">
                  <button
                    className="text-xs text-sky-400 underline"
                    onClick={() => { select(query.toUpperCase().includes(".") ? query.toUpperCase() : query.toUpperCase() + ".NS"); }}
                  >
                    Use "{query.toUpperCase()}" as custom symbol
                  </button>
                </div>
              </div>
            ) : (
              results.map((s, i) => (
                <button
                  key={s.symbol}
                  onClick={() => select(s.symbol)}
                  className={clsx(
                    "w-full text-left px-4 py-2.5 flex items-center justify-between gap-3 transition-colors",
                    i === activeIdx ? "bg-sky-500/15" : "hover:bg-surface",
                    s.symbol === value && "bg-sky-500/10"
                  )}
                >
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-100 truncate">
                      {highlight(s.name, query)}
                    </p>
                    <p className="text-xs text-slate-500">
                      {highlight(s.symbol, query)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {s.sector && (
                      <span className="text-xs text-slate-500 bg-surface px-1.5 py-0.5 rounded truncate max-w-[80px]">
                        {s.sector}
                      </span>
                    )}
                    {s.symbol === value && (
                      <span className="text-sky-400 text-xs">✓</span>
                    )}
                  </div>
                </button>
              ))
            )}
          </div>

          {/* Footer hint */}
          <div className="px-3 py-1.5 border-t border-border text-xs text-slate-600 flex gap-3">
            <span>↑↓ navigate</span>
            <span>↵ select</span>
            <span>esc close</span>
          </div>
        </div>
      )}
    </div>
  );
}
