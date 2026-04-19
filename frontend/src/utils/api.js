import axios from "axios";

const BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL: BASE, timeout: 90_000 });

export const fetchDecision    = (symbol) => api.get(`/decision?symbol=${symbol}`);
export const fetchAnalysis    = (symbol) => api.get(`/analyse?symbol=${symbol}`);
export const fetchChart       = (symbol, days = 60) => api.get(`/chart?symbol=${symbol}&days=${days}`);
export const fetchRisk        = (symbol) => api.get(`/risk?symbol=${symbol}`);
export const fetchSymbols     = () => api.get("/symbols");
export const fetchPortfolio   = () => api.get("/portfolio");
export const fetchTrades      = () => api.get("/trades");
export const fetchMonteCarlo  = (symbol, sims = 1000, horizon = 30) =>
  api.get(`/monte-carlo?symbol=${symbol}&simulations=${sims}&horizon=${horizon}`);
export const fetchOrderBook   = (symbol) => api.get(`/orderbook?symbol=${symbol}`);
export const optimizePortfolio = (symbols) =>
  api.get(`/portfolio/optimize?symbols=${symbols.join(",")}`);
export const placeOrder = (symbol, side, position_inr) =>
  api.post("/order", { symbol, side, position_inr });

export const fetchScorecard     = (symbol) => api.get(`/invest/scorecard/${encodeURIComponent(symbol)}`);
export const fetchVolumeProfile = (symbol, timeframe = "1d", lookback = 60) =>
  api.get(`/vp/${encodeURIComponent(symbol)}?timeframe=${timeframe}&lookback=${lookback}&backtest=true`);
