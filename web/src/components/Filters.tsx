import { Search } from 'lucide-react'

interface FiltersProps {
  sectors: string[]
  sectorFilter: string
  setSectorFilter: (v: string) => void
  searchQuery: string
  setSearchQuery: (v: string) => void
  hideValueTraps: boolean
  setHideValueTraps: (v: boolean) => void
  minScore: number
  setMinScore: (v: number) => void
}

export function Filters({
  sectors, sectorFilter, setSectorFilter,
  searchQuery, setSearchQuery,
  hideValueTraps, setHideValueTraps,
  minScore, setMinScore,
}: FiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 mb-4">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
        <input
          type="text"
          placeholder="銘柄名 or ティッカー..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          className="pl-9 pr-3 py-1.5 bg-zinc-900 border border-zinc-700 rounded text-sm text-zinc-200
                     placeholder:text-zinc-500 focus:outline-none focus:border-blue-500 w-52"
        />
      </div>

      {/* Sector */}
      <select
        value={sectorFilter}
        onChange={e => setSectorFilter(e.target.value)}
        className="px-3 py-1.5 bg-zinc-900 border border-zinc-700 rounded text-sm text-zinc-200
                   focus:outline-none focus:border-blue-500"
      >
        <option value="">全セクター</option>
        {sectors.map(s => <option key={s} value={s}>{s}</option>)}
      </select>

      {/* Min Score */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-zinc-400">最低スコア</label>
        <input
          type="number"
          min={0}
          max={100}
          step={5}
          value={minScore}
          onChange={e => setMinScore(Number(e.target.value))}
          className="w-16 px-2 py-1.5 bg-zinc-900 border border-zinc-700 rounded text-sm text-zinc-200
                     focus:outline-none focus:border-blue-500"
        />
      </div>

      {/* Value Trap Toggle */}
      <label className="flex items-center gap-2 text-sm text-zinc-400 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={hideValueTraps}
          onChange={e => setHideValueTraps(e.target.checked)}
          className="accent-blue-500"
        />
        バリュートラップ非表示
      </label>
    </div>
  )
}
