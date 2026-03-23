import { useState, useMemo, Fragment } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  type ColumnDef,
  type VisibilityState,
  flexRender,
} from '@tanstack/react-table'
import { ChevronUp, ChevronDown, ChevronsUpDown, AlertTriangle, Settings2 } from 'lucide-react'
import type { Stock } from '../types'
import { ScoreBar } from './ScoreBar'
import { StockDetail } from './StockDetail'
import { Tooltip } from './Tooltip'

const STORAGE_KEY_VIS = 'alpha-seeker-col-vis'

const tooltips: Record<string, { title: string; body: string }> = {
  total: {
    title: '総合スコア (0-100)',
    body: '4カテゴリの加重平均。割安度 25%、成長力 30%、質 20%、決算モメンタム 25%。',
  },
  valuation: {
    title: '割安度スコア (0-100)',
    body: 'PER(20%) PBR(15%) EV/EBITDA(20%) PSR(15%) FCF利回り(30%)。セクター内でパーセンタイルランク化。数値が高いほどセクター内で相対的に割安。',
  },
  growth: {
    title: '成長力スコア (0-100)',
    body: '売上成長(30%) 営業利益成長(25%) EPS成長(30%) PEG(15%)。高いほど成長が速い。',
  },
  quality: {
    title: '質スコア (0-100)',
    body: 'ROE(30%) 粗利率(20%) D/E(25%) FCFマージン(25%)。高いほど財務基盤が強い。',
  },
  momentum: {
    title: '決算モメンタム (0-100)',
    body: '決算サプライズ率(25%) EPS予想修正90d(25%) 売上加速度(20%) 来期EPS成長予想(30%)。',
  },
  fscore: {
    title: 'Piotroski F-Score (0-9)',
    body: '9つの財務チェック。収益性(4点) レバレッジ(3点) 効率性(2点)。2以下はバリュートラップ警告。',
  },
  buy_signal: {
    title: '買いシグナル (0-100)',
    body: '総合スコア(40%) + アナリスト上昇余地(25%) + 決算ビート率(15%) + F-Score(10%) + アナリスト評価(10%)。「今買うべきか」の統合指標。',
  },
}

const COLUMN_LABELS: Record<string, string> = {
  rank: '#',
  ticker: '銘柄',
  name: '企業名',
  sector: 'セクター',
  total_score: '総合',
  valuation_score: '割安度',
  growth_score: '成長力',
  quality_score: '質',
  earnings_momentum_score: '決算勢い',
  piotroski_fscore: 'F値',
  buy_signal: '買いシグナル',
  current_price: '株価',
  upside_potential: '上昇余地',
}

const DEFAULT_COLUMN_ORDER = [
  'rank', 'ticker', 'name', 'sector', 'buy_signal', 'total_score', 'valuation_score',
  'growth_score', 'quality_score', 'earnings_momentum_score', 'piotroski_fscore',
  'current_price', 'upside_potential',
]

function SortIcon({ sorted }: { sorted: false | 'asc' | 'desc' }) {
  if (sorted === 'asc') return <ChevronUp className="w-3.5 h-3.5" />
  if (sorted === 'desc') return <ChevronDown className="w-3.5 h-3.5" />
  return <ChevronsUpDown className="w-3.5 h-3.5 text-zinc-600" />
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function HeaderCell({ label, tooltipKey, column }: { label: string; tooltipKey?: string; column: Record<string, any> }) {
  const inner = (
    <button
      onClick={column.getToggleSortingHandler()}
      className="flex items-center gap-1 text-xs font-medium text-zinc-400 hover:text-zinc-200 uppercase tracking-wide select-none"
    >
      {label}
      <SortIcon sorted={column.getIsSorted()} />
    </button>
  )
  if (tooltipKey && tooltips[tooltipKey]) {
    const t = tooltips[tooltipKey]
    return (
      <Tooltip content={
        <div>
          <div className="font-semibold text-zinc-100 mb-1">{t.title}</div>
          <div className="text-zinc-300 text-xs leading-relaxed">{t.body}</div>
        </div>
      }>
        {inner}
      </Tooltip>
    )
  }
  return inner
}

function ColumnSettings({
  allColumns,
  visibility,
  setVisibility,
}: {
  allColumns: { id: string; label: string }[]
  visibility: VisibilityState
  setVisibility: (v: VisibilityState) => void
}) {
  const [open, setOpen] = useState(false)

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-900 border border-zinc-700 rounded text-sm text-zinc-300 hover:border-blue-500 transition-colors"
      >
        <Settings2 className="w-4 h-4" />
        カラム設定
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-50 bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl p-3 min-w-[180px]">
            <div className="text-xs text-zinc-500 mb-2">表示するカラムを選択</div>
            {allColumns.map(col => {
              const isVisible = visibility[col.id] !== false
              const isFixed = col.id === 'rank' || col.id === 'ticker'
              return (
                <label
                  key={col.id}
                  className={`flex items-center gap-2 py-1 text-sm cursor-pointer select-none ${
                    isFixed ? 'text-zinc-600' : 'text-zinc-300 hover:text-zinc-100'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isVisible}
                    disabled={isFixed}
                    onChange={() => {
                      const next = { ...visibility, [col.id]: !isVisible }
                      setVisibility(next)
                      localStorage.setItem(STORAGE_KEY_VIS, JSON.stringify(next))
                    }}
                    className="accent-blue-500"
                  />
                  {col.label}
                </label>
              )
            })}
            <button
              onClick={() => {
                const reset: VisibilityState = {}
                allColumns.forEach(c => { reset[c.id] = true })
                setVisibility(reset)
                localStorage.removeItem(STORAGE_KEY_VIS)
              }}
              className="mt-2 text-xs text-blue-400 hover:text-blue-300"
            >
              全て表示に戻す
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function loadState<T>(key: string, fallback: T): T {
  try {
    const saved = localStorage.getItem(key)
    return saved ? JSON.parse(saved) : fallback
  } catch { return fallback }
}

export function RankingTable({ stocks }: { stocks: Stock[] }) {
  const [sorting, setSorting] = useState<SortingState>([{ id: 'buy_signal', desc: true }])
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null)
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(
    () => loadState(STORAGE_KEY_VIS, {})
  )

  const columns = useMemo<ColumnDef<Stock>[]>(() => [
    {
      id: 'rank',
      header: '#',
      size: 40,
      cell: ({ row }) => (
        <span className="text-xs text-zinc-500 tabular-nums">{row.index + 1}</span>
      ),
      enableSorting: false,
    },
    {
      id: 'ticker',
      accessorKey: 'ticker',
      header: ({ column }) => <HeaderCell label="銘柄" column={column} />,
      size: 70,
      cell: ({ row }) => {
        const s = row.original
        return (
          <div className="flex items-center gap-1.5">
            <button
              onClick={(e) => { e.stopPropagation(); setExpandedTicker(expandedTicker === s.ticker ? null : s.ticker) }}
              className="font-semibold text-sm text-zinc-100 hover:text-blue-400 transition-colors"
            >
              {s.ticker}
            </button>
            {s.is_value_trap && (
              <Tooltip content={<span className="text-red-300">バリュートラップ: {s.value_trap_reason}</span>}>
                <AlertTriangle className="w-3.5 h-3.5 text-red-500" />
              </Tooltip>
            )}
          </div>
        )
      },
    },
    {
      id: 'name',
      accessorKey: 'name',
      header: ({ column }) => <HeaderCell label="企業名" column={column} />,
      size: 180,
      cell: ({ getValue }) => (
        <span className="text-sm text-zinc-400 truncate block max-w-[180px]">{getValue() as string}</span>
      ),
    },
    {
      id: 'sector',
      accessorKey: 'sector',
      header: ({ column }) => <HeaderCell label="セクター" column={column} />,
      size: 140,
      cell: ({ getValue }) => (
        <span className="text-xs text-zinc-500 truncate block max-w-[140px]">{getValue() as string}</span>
      ),
    },
    {
      id: 'buy_signal',
      accessorKey: 'buy_signal',
      header: ({ column }) => <HeaderCell label="買いシグナル" tooltipKey="buy_signal" column={column} />,
      size: 120,
      cell: ({ getValue }) => <ScoreBar value={getValue() as number | null} />,
      sortDescFirst: true,
    },
    {
      id: 'total_score',
      accessorKey: 'total_score',
      header: ({ column }) => <HeaderCell label="総合" tooltipKey="total" column={column} />,
      size: 110,
      cell: ({ getValue }) => <ScoreBar value={getValue() as number | null} />,
      sortDescFirst: true,
    },
    {
      id: 'valuation_score',
      accessorKey: 'valuation_score',
      header: ({ column }) => <HeaderCell label="割安度" tooltipKey="valuation" column={column} />,
      size: 110,
      cell: ({ getValue }) => <ScoreBar value={getValue() as number | null} />,
      sortDescFirst: true,
    },
    {
      id: 'growth_score',
      accessorKey: 'growth_score',
      header: ({ column }) => <HeaderCell label="成長力" tooltipKey="growth" column={column} />,
      size: 110,
      cell: ({ getValue }) => <ScoreBar value={getValue() as number | null} />,
      sortDescFirst: true,
    },
    {
      id: 'quality_score',
      accessorKey: 'quality_score',
      header: ({ column }) => <HeaderCell label="質" tooltipKey="quality" column={column} />,
      size: 110,
      cell: ({ getValue }) => <ScoreBar value={getValue() as number | null} />,
      sortDescFirst: true,
    },
    {
      id: 'earnings_momentum_score',
      accessorKey: 'earnings_momentum_score',
      header: ({ column }) => <HeaderCell label="決算勢い" tooltipKey="momentum" column={column} />,
      size: 110,
      cell: ({ getValue }) => <ScoreBar value={getValue() as number | null} />,
      sortDescFirst: true,
    },
    {
      id: 'piotroski_fscore',
      accessorKey: 'piotroski_fscore',
      header: ({ column }) => <HeaderCell label="F値" tooltipKey="fscore" column={column} />,
      size: 50,
      cell: ({ getValue }) => {
        const v = getValue() as number | null
        if (v === null || v === undefined) return <span className="text-zinc-600 text-xs">-</span>
        const color = v >= 7 ? 'text-emerald-400' : v >= 4 ? 'text-zinc-300' : 'text-red-400'
        return <span className={`text-xs font-medium tabular-nums ${color}`}>{v}</span>
      },
      sortDescFirst: true,
    },
    {
      id: 'current_price',
      accessorKey: 'current_price',
      header: ({ column }) => <HeaderCell label="株価" column={column} />,
      size: 80,
      cell: ({ getValue }) => {
        const v = getValue() as number | null
        return <span className="text-xs tabular-nums text-zinc-300">{v ? `$${v.toFixed(0)}` : '-'}</span>
      },
      sortDescFirst: true,
    },
    {
      id: 'upside_potential',
      accessorKey: 'upside_potential',
      header: ({ column }) => <HeaderCell label="上昇余地" column={column} />,
      size: 70,
      cell: ({ getValue }) => {
        const v = getValue() as number | null
        if (v === null || v === undefined) return <span className="text-zinc-600 text-xs">-</span>
        const color = v > 0.1 ? 'text-emerald-400' : v < -0.05 ? 'text-red-400' : 'text-zinc-300'
        return <span className={`text-xs tabular-nums ${color}`}>{(v * 100).toFixed(0)}%</span>
      },
      sortDescFirst: true,
    },
  ], [expandedTicker])

  const table = useReactTable({
    data: stocks,
    columns,
    state: { sorting, columnOrder: DEFAULT_COLUMN_ORDER, columnVisibility },
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  const allColumnsMeta = DEFAULT_COLUMN_ORDER.map(id => ({
    id,
    label: COLUMN_LABELS[id] || id,
  }))

  return (
    <div>
      <div className="flex justify-end mb-2">
        <ColumnSettings
          allColumns={allColumnsMeta}
          visibility={columnVisibility}
          setVisibility={setColumnVisibility}
        />
      </div>
      <div className="overflow-x-auto rounded-lg border border-zinc-800">
        <table className="w-full">
          <thead>
            {table.getHeaderGroups().map(hg => (
              <tr key={hg.id} className="border-b border-zinc-800 bg-zinc-900/50">
                {hg.headers.map(header => (
                  <th
                    key={header.id}
                    className="px-3 py-2.5 text-left"
                    style={{ width: header.getSize() }}
                  >
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map(row => {
              const s = row.original
              const isExpanded = expandedTicker === s.ticker
              return (
                <Fragment key={row.id}>
                  <tr
                    className={`border-b border-zinc-800/50 hover:bg-zinc-900/50 transition-colors cursor-pointer
                      ${s.is_value_trap ? 'opacity-60' : ''} ${isExpanded ? 'bg-zinc-900/80' : ''}`}
                    onClick={() => setExpandedTicker(isExpanded ? null : s.ticker)}
                  >
                    {row.getVisibleCells().map(cell => (
                      <td key={cell.id} className="px-3 py-2">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                  {isExpanded && (
                    <StockDetail
                      key={`${row.id}-detail`}
                      stock={s}
                      onClose={() => setExpandedTicker(null)}
                    />
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
