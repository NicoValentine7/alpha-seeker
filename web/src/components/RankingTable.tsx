import { useState, useMemo } from 'react'
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
    title: 'Total Score (0-100)',
    body: '4 categories weighted average. Valuation 25%, Growth 30%, Quality 20%, Earnings Momentum 25%.',
  },
  valuation: {
    title: 'Valuation Score (0-100)',
    body: 'PER(20%), PBR(15%), EV/EBITDA(20%), PSR(15%), FCF Yield(30%). Lower = cheaper within sector.',
  },
  growth: {
    title: 'Growth Score (0-100)',
    body: 'Revenue Growth(30%), Op. Income Growth(25%), EPS Growth(30%), PEG(15%). Higher = faster growing.',
  },
  quality: {
    title: 'Quality Score (0-100)',
    body: 'ROE(30%), Gross Margin(20%), D/E(25%), FCF Margin(25%). Higher = stronger fundamentals.',
  },
  momentum: {
    title: 'Earnings Momentum (0-100)',
    body: 'Surprise Rate(25%), EPS Revision 90d(25%), Revenue Acceleration(20%), Forward EPS Growth(30%).',
  },
  fscore: {
    title: 'Piotroski F-Score (0-9)',
    body: '9 binary financial checks. Profitability(4), Leverage(3), Efficiency(2). Score <= 2 = value trap warning.',
  },
}

function SortIcon({ sorted }: { sorted: false | 'asc' | 'desc' }) {
  if (sorted === 'asc') return <ChevronUp className="w-3.5 h-3.5" />
  if (sorted === 'desc') return <ChevronDown className="w-3.5 h-3.5" />
  return <ChevronsUpDown className="w-3.5 h-3.5 text-zinc-600" />
}

function HeaderCell({ label, tooltipKey, column }: { label: string; tooltipKey?: string; column: any }) {
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
      header: ({ column }) => <HeaderCell label="Ticker" column={column} />,
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
              <Tooltip content={<span className="text-red-300">Value Trap: {s.value_trap_reason}</span>}>
                <AlertTriangle className="w-3.5 h-3.5 text-red-500" />
              </Tooltip>
            )}
          </div>
        )
      },
    },
    {
      accessorKey: 'name',
      header: ({ column }) => <HeaderCell label="Name" column={column} />,
      size: 180,
      cell: ({ getValue }) => (
        <span className="text-sm text-zinc-400 truncate block max-w-[180px]">{getValue() as string}</span>
      ),
    },
    {
      accessorKey: 'sector',
      header: ({ column }) => <HeaderCell label="Sector" column={column} />,
      size: 140,
      cell: ({ getValue }) => (
        <span className="text-xs text-zinc-500 truncate block max-w-[140px]">{getValue() as string}</span>
      ),
    },
    {
      accessorKey: 'total_score',
      header: ({ column }) => <HeaderCell label="Total" tooltipKey="total" column={column} />,
      size: 110,
      cell: ({ getValue }) => <ScoreBar value={getValue() as number | null} />,
      sortDescFirst: true,
    },
    {
      accessorKey: 'valuation_score',
      header: ({ column }) => <HeaderCell label="Value" tooltipKey="valuation" column={column} />,
      size: 110,
      cell: ({ getValue }) => <ScoreBar value={getValue() as number | null} />,
      sortDescFirst: true,
    },
    {
      accessorKey: 'growth_score',
      header: ({ column }) => <HeaderCell label="Growth" tooltipKey="growth" column={column} />,
      size: 110,
      cell: ({ getValue }) => <ScoreBar value={getValue() as number | null} />,
      sortDescFirst: true,
    },
    {
      accessorKey: 'quality_score',
      header: ({ column }) => <HeaderCell label="Quality" tooltipKey="quality" column={column} />,
      size: 110,
      cell: ({ getValue }) => <ScoreBar value={getValue() as number | null} />,
      sortDescFirst: true,
    },
    {
      accessorKey: 'earnings_momentum_score',
      header: ({ column }) => <HeaderCell label="Momentum" tooltipKey="momentum" column={column} />,
      size: 110,
      cell: ({ getValue }) => <ScoreBar value={getValue() as number | null} />,
      sortDescFirst: true,
    },
    {
      accessorKey: 'piotroski_fscore',
      header: ({ column }) => <HeaderCell label="F" tooltipKey="fscore" column={column} />,
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
      header: ({ column }) => <HeaderCell label="Price" column={column} />,
      size: 80,
      cell: ({ getValue }) => {
        const v = getValue() as number | null
        return <span className="text-xs tabular-nums text-zinc-300">{v ? `$${v.toFixed(0)}` : '-'}</span>
      },
      sortDescFirst: true,
    },
    {
      accessorKey: 'upside_potential',
      header: ({ column }) => <HeaderCell label="Upside" column={column} />,
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
              <>
                <tr
                  key={row.id}
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
              </>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
