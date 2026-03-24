import { useState, useEffect, useMemo } from 'react'
import { AreaChart, Area, ResponsiveContainer, Tooltip, YAxis, XAxis } from 'recharts'

interface PricePoint {
  date: string
  price: number
}

const PERIODS = [
  { label: '1M', range: '1mo', interval: '1d' },
  { label: '3M', range: '3mo', interval: '1d' },
  { label: '6M', range: '6mo', interval: '1wk' },
  { label: 'YTD', range: 'ytd', interval: '1wk' },
  { label: '1Y', range: '1y', interval: '1wk' },
  { label: '2Y', range: '2y', interval: '1wk' },
  { label: '5Y', range: '5y', interval: '1mo' },
  { label: 'ALL', range: 'max', interval: '1mo' },
] as const

async function fetchPriceHistory(ticker: string, range: string, interval: string): Promise<PricePoint[]> {
  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}?range=${range}&interval=${interval}&includePrePost=false`
    const res = await fetch(url)
    const json = await res.json()
    const result = json.chart?.result?.[0]
    if (!result) return []

    const timestamps: number[] = result.timestamp || []
    const closes: (number | null)[] = result.indicators?.quote?.[0]?.close || []

    return timestamps
      .map((ts, i) => ({
        date: new Date(ts * 1000).toLocaleDateString('ja-JP', { month: 'short', day: 'numeric' }),
        price: closes[i] ?? 0,
      }))
      .filter(p => p.price > 0)
  } catch {
    return []
  }
}

interface Props {
  ticker: string
  currentPrice: number | null
}

export function PriceChart({ ticker, currentPrice }: Props) {
  const [periodIdx, setPeriodIdx] = useState(5) // default 2Y
  const [data, setData] = useState<PricePoint[]>([])
  const [loading, setLoading] = useState(true)

  const period = PERIODS[periodIdx]

  useEffect(() => {
    setLoading(true)
    fetchPriceHistory(ticker, period.range, period.interval).then(d => {
      setData(d)
      setLoading(false)
    })
  }, [ticker, period.range, period.interval])

  const { change, color, min, max } = useMemo(() => {
    if (data.length < 2) return { change: 0, color: '#71717a', min: 0, max: 0 }
    const first = data[0].price
    const last = data[data.length - 1].price
    const ch = ((last - first) / first) * 100
    return {
      change: ch,
      color: ch >= 0 ? '#10b981' : '#ef4444',
      min: Math.min(...data.map(d => d.price)) * 0.98,
      max: Math.max(...data.map(d => d.price)) * 1.02,
    }
  }, [data])

  return (
    <div className="mt-4">
      {/* Header */}
      <div className="flex items-baseline gap-3 mb-2">
        <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wide">株価推移</h4>
        {currentPrice && (
          <span className="text-sm font-semibold text-zinc-100 tabular-nums">${currentPrice.toFixed(2)}</span>
        )}
        {data.length > 0 && (
          <span className={`text-xs tabular-nums ${change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {change >= 0 ? '+' : ''}{change.toFixed(1)}% ({period.label})
          </span>
        )}
      </div>

      {/* Period Tabs */}
      <div className="flex gap-1 mb-2">
        {PERIODS.map((p, i) => (
          <button
            key={p.label}
            onClick={() => setPeriodIdx(i)}
            className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
              i === periodIdx
                ? 'bg-zinc-700 text-zinc-100'
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Chart */}
      {loading ? (
        <div className="h-[140px] flex items-center justify-center text-zinc-600 text-sm">Loading...</div>
      ) : data.length < 2 ? (
        <div className="h-[140px] flex items-center justify-center text-zinc-600 text-sm">データなし</div>
      ) : (
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
            <defs>
              <linearGradient id={`grad-${ticker}-${periodIdx}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.25} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <YAxis domain={[min, max]} hide />
            <XAxis dataKey="date" hide />
            <Tooltip
              contentStyle={{ background: '#27272a', border: '1px solid #3f3f46', borderRadius: 6, fontSize: 12 }}
              labelStyle={{ color: '#a1a1aa', fontSize: 11 }}
              formatter={(value) => [`$${Number(value).toFixed(2)}`, '']}
            />
            <Area
              type="monotone"
              dataKey="price"
              stroke={color}
              strokeWidth={1.5}
              fill={`url(#grad-${ticker}-${periodIdx})`}
              dot={false}
              activeDot={{ r: 3, fill: color }}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
