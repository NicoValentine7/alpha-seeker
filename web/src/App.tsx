import { useEffect, useState } from 'react'
import type { RankingData } from './types'
import { RankingTable } from './components/RankingTable'
import { Filters } from './components/Filters'
import { SectorChart } from './components/SectorChart'
import { Portfolio } from './components/Portfolio'
import './index.css'

function App() {
  const [data, setData] = useState<RankingData | null>(null)
  const [sectorFilter, setSectorFilter] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [hideValueTraps, setHideValueTraps] = useState(false)
  const [minScore, setMinScore] = useState(0)

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
              S&P500 Ranking / {data.date} / {filtered.length} stocks
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-6 py-4">
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
        />
        <Portfolio stocks={data.stocks} />
        <SectorChart stocks={filtered} />
        <RankingTable stocks={filtered} />
      </main>
    </div>
  )
}

export default App
