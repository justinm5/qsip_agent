import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1'

const TOKEN = localStorage.getItem('qsip_token') || ''

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {},
})

export interface Signal {
  signal_id: string
  timestamp: string
  ticker: string
  signal_type: string
  direction: string
  score: number
  ml_score: number
  features?: Record<string, number>
  metadata?: Record<string, any>
}

export interface BacktestSummary {
  ticker: string
  total_signals: number
  win_rate: number
  avg_return: number
  avg_excess: number
  max_drawdown: number
}

export interface MarketDataPoint {
  time: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface SignalExplanation {
  signal_id: string
  summary: string
  top_features: { feature: string; impact: number }[]
  shap_values: Record<string, number>
}

export interface PortfolioSnapshot {
  strategy: string
  nav: number
  total_value: number
  sharpe: number
  sortino: number
  max_drawdown: number
  alpha: number
  beta: number
}

export const fetchSignals = (limit = 100): Promise<Signal[]> =>
  api.get(`/signals?limit=${limit}`).then((r) => r.data)

export const fetchSignalsByTicker = (ticker: string, limit = 100): Promise<Signal[]> =>
  api.get(`/signals/${ticker}?limit=${limit}`).then((r) => r.data)

export const fetchSignalExplanation = (signalId: string): Promise<SignalExplanation> =>
  api.get(`/signals/${signalId}/explain`).then((r) => r.data)

export const fetchBacktest = (ticker: string): Promise<BacktestSummary> =>
  api.get(`/backtest/${ticker}`).then((r) => r.data)

export const fetchMarketData = (ticker: string, limit = 252): Promise<MarketDataPoint[]> =>
  api.get(`/market/${ticker}?limit=${limit}`).then((r) => r.data)

export const fetchPortfolio = (strategy: string): Promise<PortfolioSnapshot> =>
  api.get(`/portfolio/${strategy}`).then((r) => r.data)

export interface Recommendation {
  signal_id: string
  timestamp: string
  ticker: string
  signal_type: string
  direction: string
  score: number
  ml_score: number
  confidence: number
  summary: string
  top_features: { feature: string; impact: number }[]
}

export const fetchTopRecommendations = (limit = 10): Promise<Recommendation[]> =>
  api.get(`/top-recommendations?limit=${limit}`).then((r) => r.data)

export interface PaperAccount {
  strategy: string
  cash: number
  equity: number
  buying_power: number
}

export interface PaperPosition {
  ticker: string
  qty: number
  avg_entry_price: number
  market_price: number
  market_value: number
  unrealized_pnl: number
  realized_pnl: number
  side: string
}

export interface PaperTrade {
  trade_id: string
  ticker: string
  side: string
  qty: number
  price: number
  total_value: number
  executed_at: string
}

export const fetchPaperAccount = (): Promise<PaperAccount> => api.get('/paper/account').then((r) => r.data)
export const fetchPaperPositions = (): Promise<PaperPosition[]> => api.get('/paper/positions').then((r) => r.data)
export const fetchPaperTrades = (): Promise<PaperTrade[]> => api.get('/paper/trades').then((r) => r.data)

export const login = (username: string, password: string): Promise<{ token: string }> =>
  api.post('/auth/login', { username, password }).then((r) => r.data)
