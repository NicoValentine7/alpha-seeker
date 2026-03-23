import { useState, useMemo, Fragment } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  type ColumnDef,
  flexRender,
} from '@tanstack/react-table'
import { ChevronUp, ChevronDown, ChevronsUpDown, AlertTriangle } from 'lucide-react'
import type { Stock } from '../types'
import { ScoreBar } from './ScoreBar'
import { StockDetail } from './StockDetail'
import { Tooltip } from './Tooltip'

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
}

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

export function RankingTable({ stocks }: { stocks: Stock[] }) {
  const [sorting, setSorting] = useState<SortingState>([{ id: 'total_score', desc: true }])
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null)

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
      accessorKey: 'ticker',
      header: ({ column }) => <HeaderCell label="銘柄" column={column} />,
      size: 70,
      cell: ({ row }) => {
        const s = row.original
        return (
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setExpandedTicker(expandedTicker === s.ticker ? null : s.ticker)}
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
      accessorKey: 'name',
      header: ({ column }) => <HeaderCell label="企業名" column={column} />,
      size: 180,
      cell: ({ getValue }) => (
        <span className="text-sm text-zinc-400 truncate block max-w-[180px]">{getValue() as string}</span>
      ),
    },
    {
      accessorKey: 'sector',
      header: ({ column }) => <HeaderCell label="セクター" column={column} />,
      size: 140,
      cell: ({ getValue }) => (
        <span className="text-xs text-zinc-500 truncate block max-w-[140px]">{getValue() as string}</span>
      ),
    },
    {
      accessorKey: 'total_score',
      header: ({ column }) => <HeaderCell label="総合" tooltipKey="total" column={column} />,
      size: 110,
      cell: ({ getValue }) => <ScoreBar value={getValue() as number | null} />,
      sortDescFirst: true,
    },
    {
      accessorKey: 'valuation_score',
      header: ({ column }) => <HeaderCell label="割安度" tooltipKey="valuation" column={column} />,
      size: 110,
      cell: ({ getValue }) => <ScoreBar value={getValue() as number | null} />,
      sortDescFirst: true,
    },
    {
      accessorKey: 'growth_score',
      header: ({ column }) => <HeaderCell label="成長力" tooltipKey="growth" column={column} />,
      size: 110,
      cell: ({ getValue }) => <ScoreBar value={getValue() as number | null} />,
      sortDescFirst: true,
    },
    {
      accessorKey: 'quality_score',
      header: ({ column }) => <HeaderCell label="質" tooltipKey="quality" column={column} />,
      size: 110,
      cell: ({ getValue }) => <ScoreBar value={getValue() as number | null} />,
      sortDescFirst: true,
    },
    {
      accessorKey: 'earnings_momentum_score',
      header: ({ column }) => <HeaderCell label="決算勢い" tooltipKey="momentum" column={column} />,
      size: 110,
      cell: ({ getValue }) => <ScoreBar value={getValue() as number | null} />,
      sortDescFirst: true,
    },
    {
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
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
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
  )
}
