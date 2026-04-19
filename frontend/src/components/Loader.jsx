import React from "react";

export default function Loader({ label = "Analysing…" }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16">
      <div className="relative w-16 h-16">
        <div className="absolute inset-0 rounded-full border-4 border-border" />
        <div className="absolute inset-0 rounded-full border-4 border-t-sky-400 animate-spin" />
      </div>
      <p className="text-sm text-slate-400 font-medium">{label}</p>
    </div>
  );
}
