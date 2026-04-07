import { useEffect, useState } from 'react'
import type { RankingData } from './types'
import { RankingTable } from './components/RankingTable'
import { Filters } from './components/Filters'
import { ICChart } from './components/ICChart'
import { LiquidityRegimeChart } from './components/LiquidityRegimeChart'
import './index.css'

function fmtNum(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return '-'
  return value.toFixed(digits)
}

function regimeTone(regime?: string | null): string {
  switch (regime) {
    case 'tightening':
      return 'border-amber-500/40 bg-amber-950/20 text-amber-200'
    case 'easing':
      return 'border-emerald-500/40 bg-emerald-950/20 text-emerald-200'
    default:
      return 'border-zinc-700 bg-zinc-900/80 text-zinc-200'
  }
}

function App() {
  const [data, setData] = useState<RankingData | null>(null)
  const [sectorFilter, setSectorFilter] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [hideValueTraps, setHideValueTraps] = useState(false)
  const [minScore, setMinScore] = useState(0)
  const [portfolioOnly, setPortfolioOnly] = useState(false)

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}ranking.json`)
      .then(res => res.json())
      .then(setData)
  }, [])

  if (!data) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-zinc-400 text-lg">Loading...</div>
      </div>
    )
  }

  const sectors = [...new Set(data.stocks.map(s => s.sector).filter(Boolean))].sort()

  const filtered = data.stocks.filter(s => {
    if (portfolioOnly && !s.is_portfolio) return false
    if (sectorFilter && s.sector !== sectorFilter) return false
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      if (!s.ticker.toLowerCase().includes(q) && !s.name?.toLowerCase().includes(q)) return false
    }
    if (hideValueTraps && s.is_value_trap) return false
    if (minScore > 0 && (s.total_score === null || s.total_score < minScore)) return false
    return true
  })

  return (
    <div className="min-h-screen bg-zinc-950">
      <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[1600px] mx-auto px-6 py-4">
          <div className="flex items-baseline gap-4">
            <h1 className="text-xl font-bold text-zinc-100 tracking-tight">Alpha Seeker</h1>
            <span className="text-sm text-zinc-500">
              S&P500 Ranking / {filtered.length} stocks / 最終更新: {data.date}
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-6 py-4">
        {data.liquidity_regime && (
          <section className={`mb-4 rounded-xl border px-4 py-3 ${regimeTone(data.liquidity_regime.liquidity_regime)}`}>
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-zinc-400">Fed Liquidity Regime</div>
                <div className="mt-1 text-sm font-medium">
                  {data.liquidity_regime.liquidity_regime_summary ?? 'liquidity regime summary unavailable'}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-zinc-400 md:text-right">
                <div>IORB {fmtNum(data.liquidity_regime.iorb, 2)}% ({data.liquidity_regime.iorb_as_of ?? '-'})</div>
                <div>Fed liabilities {fmtNum(data.liquidity_regime.fed_liabilities_bn, 0)}B</div>
                <div>LP base {fmtNum(data.liquidity_regime.liquidity_premium_change_base_bp, 2)}bp</div>
                <div>LP range {fmtNum(data.liquidity_regime.liquidity_premium_change_low_bp, 2)} / {fmtNum(data.liquidity_regime.liquidity_premium_change_high_bp, 2)}bp</div>
              </div>
            </div>
          </section>
        )}
        <Filters
          sectors={sectors}
          sectorFilter={sectorFilter}
          setSectorFilter={setSectorFilter}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          hideValueTraps={hideValueTraps}
          setHideValueTraps={setHideValueTraps}
          minScore={minScore}
          setMinScore={setMinScore}
          portfolioOnly={portfolioOnly}
          setPortfolioOnly={setPortfolioOnly}
          hasPortfolio={data.stocks.some(s => s.is_portfolio)}
        />
        <ICChart />
        <LiquidityRegimeChart />
        <RankingTable stocks={filtered} />
      </main>
    </div>
  )
}

export default App
