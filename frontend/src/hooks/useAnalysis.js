import { useState, useEffect, useCallback } from "react";
import { fetchDecision, fetchAnalysis, fetchChart } from "../utils/api";

export function useAnalysis(symbol) {
  const [decision,  setDecision]  = useState(null);
  const [analysis,  setAnalysis]  = useState(null);
  const [chart,     setChart]     = useState(null);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState(null);

  const load = useCallback(async () => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    try {
      const [decRes, anaRes, chartRes] = await Promise.all([
        fetchDecision(symbol),
        fetchAnalysis(symbol),
        fetchChart(symbol, 60),
      ]);
      setDecision(decRes.data);
      setAnalysis(anaRes.data);
      setChart(chartRes.data);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Analysis failed");
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => { load(); }, [load]);

  return { decision, analysis, chart, loading, error, reload: load };
}
