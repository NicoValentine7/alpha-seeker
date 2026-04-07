import { useEffect, useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from 'recharts'

interface ICRecord {
  timestamp: string
  score_date: string
  forward_days: number
  n_stocks: number
  category_ic?: Record<string, { ic: number; p_value: number }>
}

const CATEGORY_COLORS: Record<string, string> = {
  total_score: '#a78bfa',
  buy_signal: '#22d3ee',
  overlay_buy_signal: '#f472b6',
  valuation_score: '#34d399',
  growth_score: '#60a5fa',
  quality_score: '#fbbf24',
  earnings_momentum_score: '#f87171',
  price_momentum_score: '#c084fc',
}

const CATEGORY_LABELS: Record<string, string> = {
  total_score: 'Total',
  buy_signal: 'BUY',
  overlay_buy_signal: 'Overlay BUY',
  valuation_score: 'Valuation',
  growth_score: 'Growth',
  quality_score: 'Quality',
  earnings_momentum_score: 'Earnings Mom.',
  price_momentum_score: 'Price Mom.',
}

export function ICChart() {
  const [history, setHistory] = useState<ICRecord[]>([])
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}ic_history.json`)
      .then((res) => (res.ok ? res.json() : []))
      .then(setHistory)
      .catch(() => setHistory([]))
  }, [])

  if (history.length === 0) return null

  const chartData = history.map((rec) => {
    const point: Record<string, string | number | null> = {
      date: rec.score_date,
    }
    if (rec.category_ic) {
      for (const [factor, vals] of Object.entries(rec.category_ic)) {
        point[factor] = vals.ic !== undefined ? Number(vals.ic.toFixed(4)) : null
      }
    }
    return point
  })

  const categories = Object.keys(CATEGORY_COLORS).filter((cat) =>
    chartData.some((d) => d[cat] !== undefined && d[cat] !== null)
  )

  // ICIR calculation
  const icirData = categories
    .map((cat) => {
      const ics = chartData
        .map((d) => d[cat])
        .filter((v): v is number => v !== null && v !== undefined)
      if (ics.length < 2) return null
      const mean = ics.reduce((a, b) => a + b, 0) / ics.length
      const std = Math.sqrt(
        ics.reduce((a, b) => a + (b - mean) ** 2, 0) / (ics.length - 1)
      )
      const icir = std > 0 ? mean / std : 0
      const hitRate = ics.filter((ic) => ic > 0).length / ics.length
      return { factor: cat, meanIC: mean, icir, hitRate, n: ics.length }
    })
    .filter(Boolean)
    .sort((a, b) => (b?.icir ?? 0) - (a?.icir ?? 0))

  return (
    <div className="mb-4">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-sm text-zinc-400 hover:text-zinc-200 transition-colors"
      >
        <span className={`transform transition-transform ${isOpen ? 'rotate-90' : ''}`}>
          &#9654;
        </span>
        IC Analysis ({history.length} records)
      </button>

      {isOpen && (
        <div className="mt-3 space-y-4">
          {/* ICIR Summary */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
            {icirData.map((d) =>
              d ? (
                <div
                  key={d.factor}
                  className="bg-zinc-900 rounded-lg p-3 border border-zinc-800"
                >
                  <div className="text-xs text-zinc-500">
                    {CATEGORY_LABELS[d.factor] ?? d.factor}
                  </div>
                  <div
                    className={`text-lg font-mono font-bold ${
                      d.icir > 0.5
                        ? 'text-emerald-400'
                        : d.icir > 0
                          ? 'text-zinc-300'
                          : 'text-red-400'
                    }`}
                  >
                    {d.icir > 0 ? '+' : ''}
                    {d.icir.toFixed(2)}
                  </div>
                  <div className="text-xs text-zinc-500">
                    IC: {d.meanIC > 0 ? '+' : ''}
                    {d.meanIC.toFixed(3)} / Hit: {(d.hitRate * 100).toFixed(0)}%
                  </div>
                </div>
              ) : null
            )}
          </div>

          {/* IC Timeline Chart */}
          <div className="bg-zinc-900 rounded-lg p-4 border border-zinc-800">
            <div className="text-xs text-zinc-500 mb-2">IC Timeline (Spearman Rank Correlation)</div>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={chartData}>
                <XAxis
                  dataKey="date"
                  tick={{ fill: '#71717a', fontSize: 11 }}
                  tickFormatter={(v: string) => v.slice(5)}
                />
                <YAxis
                  tick={{ fill: '#71717a', fontSize: 11 }}
                  domain={[-0.3, 0.3]}
                  tickFormatter={(v: number) => v.toFixed(1)}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#18181b',
                    border: '1px solid #27272a',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  formatter={(value, name) => [
                    typeof value === 'number' ? value.toFixed(4) : 'N/A',
                    CATEGORY_LABELS[String(name)] ?? String(name),
                  ]}
                />
                <ReferenceLine y={0} stroke="#3f3f46" strokeDasharray="3 3" />
                <ReferenceLine
                  y={0.05}
                  stroke="#22c55e"
                  strokeDasharray="5 5"
                  strokeOpacity={0.3}
                  label={{ value: 'Good IC', fill: '#22c55e', fontSize: 10, position: 'right' }}
                />
                <Legend
                  formatter={(value: string) => CATEGORY_LABELS[value] ?? value}
                  wrapperStyle={{ fontSize: '11px' }}
                />
                {categories.map((cat) => (
                  <Line
                    key={cat}
                    type="monotone"
                    dataKey={cat}
                    stroke={CATEGORY_COLORS[cat]}
                    strokeWidth={cat === 'total_score' ? 2.5 : 1.5}
                    dot={{ r: 3 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="text-xs text-zinc-600">
            ICIR = Mean(IC) / Std(IC). &gt; 0.5 is good. Hit Rate = % of periods with IC &gt; 0.
            IC &gt; 0.05 with p &lt; 0.05 indicates a useful predictive signal.
          </div>
        </div>
      )}
    </div>
  )
}
