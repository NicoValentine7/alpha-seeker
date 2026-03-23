export interface Stock {
  ticker: string
  name: string
  sector: string
  total_score: number | null
  valuation_score: number | null
  growth_score: number | null
  quality_score: number | null
  earnings_momentum_score: number | null
  piotroski_fscore: number | null
  buy_signal: number | null
  pe_ratio: number | null
  forward_pe: number | null
  pb_ratio: number | null
  ev_ebitda: number | null
  ps_ratio: number | null
  fcf_yield: number | null
  revenue_growth_calc: number | null
  operating_income_growth: number | null
  eps_growth: number | null
  peg_ratio: number | null
  roe: number | null
  gross_margin: number | null
  debt_to_equity: number | null
  fcf_margin: number | null
  avg_surprise_pct: number | null
  eps_revision_90d: number | null
  revenue_acceleration: number | null
  forward_eps_growth: number | null
  current_price: number | null
  target_mean_price: number | null
  upside_potential: number | null
  recommendation_mean: number | null
  num_analysts: number | null
  is_value_trap: boolean
  value_trap_reason: string | null
  market_cap: number | null
  earnings_beat_count: number | null
  earnings_beat_total: number | null
}

export interface RankingData {
  date: string
  count: number
  stocks: Stock[]
}
