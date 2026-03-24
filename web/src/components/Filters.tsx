import { Search, Briefcase } from 'lucide-react'

const SECTOR_LABELS: Record<string, string> = {
  'Basic Materials': '素材',
  'Communication Services': '通信',
  'Consumer Cyclical': '一般消費財',
  'Consumer Defensive': '生活必需品',
  'Consumer Discretionary': '一般消費財',
  'Consumer Staples': '生活必需品',
  'Energy': 'エネルギー',
  'Financial Services': '金融',
  'Financials': '金融',
  'Health Care': 'ヘルスケア',
  'Healthcare': 'ヘルスケア',
  'Industrials': '資本財',
  'Information Technology': '情報技術',
  'Real Estate': '不動産',
  'Technology': 'テクノロジー',
  'Utilities': '公益事業',
}

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
  portfolioOnly: boolean
  setPortfolioOnly: (v: boolean) => void
  portfolioTickers: string[]
}

export function Filters({
  sectors, sectorFilter, setSectorFilter,
  searchQuery, setSearchQuery,
  hideValueTraps, setHideValueTraps,
  minScore, setMinScore,
  portfolioOnly, setPortfolioOnly, portfolioTickers,
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
        {sectors.map(s => (
          <option key={s} value={s}>{SECTOR_LABELS[s] || s}</option>
        ))}
      </select>

      {/* Min Score Slider */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-zinc-400 whitespace-nowrap">最低スコア</label>
        <input
          type="range"
          min={0}
          max={80}
          step={5}
          value={minScore}
          onChange={e => setMinScore(Number(e.target.value))}
          className="w-24 accent-blue-500"
        />
        <span className="text-xs text-zinc-300 tabular-nums w-6">{minScore}</span>
      </div>

      {/* Portfolio Only */}
      {portfolioTickers.length > 0 && (
        <label className="flex items-center gap-1.5 text-sm text-zinc-400 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={portfolioOnly}
            onChange={e => setPortfolioOnly(e.target.checked)}
            className="accent-blue-500"
          />
          <Briefcase className="w-3.5 h-3.5" />
          保有銘柄のみ
        </label>
      )}

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
