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

interface LiquidityRegimeRecord {
  snapshot_date: string
  regime: string
  iorb: number
  fed_liabilities_bn: number
  liquidity_premium_change_base_bp: number
}

function tone(regime: string): string {
  switch (regime) {
    case 'tightening':
      return 'text-amber-300'
    case 'easing':
      return 'text-emerald-300'
    default:
      return 'text-zinc-300'
  }
}

export function LiquidityRegimeChart() {
  const [history, setHistory] = useState<LiquidityRegimeRecord[]>([])
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}history/liquidity_regime_history.json`)
      .then((res) => (res.ok ? res.json() : []))
      .then(setHistory)
      .catch(() => setHistory([]))
  }, [])

  if (history.length === 0) return null

  const latest = history[history.length - 1]
  const counts = history.reduce(
    (acc, record) => {
      acc[record.regime] = (acc[record.regime] ?? 0) + 1
      return acc
    },
    {} as Record<string, number>
  )

  return (
    <div className="mb-4">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-sm text-zinc-400 hover:text-zinc-200 transition-colors"
      >
        <span className={`transform transition-transform ${isOpen ? 'rotate-90' : ''}`}>
          &#9654;
        </span>
        Liquidity Regime History ({history.length} records)
      </button>

      {isOpen && (
        <div className="mt-3 space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div className="bg-zinc-900 rounded-lg p-3 border border-zinc-800">
              <div className="text-xs text-zinc-500">Latest Regime</div>
              <div className={`text-lg font-semibold capitalize ${tone(latest.regime)}`}>{latest.regime}</div>
              <div className="text-xs text-zinc-500">{latest.snapshot_date}</div>
            </div>
            <div className="bg-zinc-900 rounded-lg p-3 border border-zinc-800">
              <div className="text-xs text-zinc-500">LP Base</div>
              <div className={`text-lg font-mono font-bold ${latest.liquidity_premium_change_base_bp > 0 ? 'text-amber-300' : 'text-emerald-300'}`}>
                {latest.liquidity_premium_change_base_bp > 0 ? '+' : ''}
                {latest.liquidity_premium_change_base_bp.toFixed(2)}bp
              </div>
              <div className="text-xs text-zinc-500">tight {counts.tightening ?? 0} / neutral {counts.neutral ?? 0} / easing {counts.easing ?? 0}</div>
            </div>
            <div className="bg-zinc-900 rounded-lg p-3 border border-zinc-800">
              <div className="text-xs text-zinc-500">IORB</div>
              <div className="text-lg font-mono font-bold text-cyan-300">{latest.iorb.toFixed(2)}%</div>
              <div className="text-xs text-zinc-500">policy floor proxy</div>
            </div>
            <div className="bg-zinc-900 rounded-lg p-3 border border-zinc-800">
              <div className="text-xs text-zinc-500">Fed Liabilities</div>
              <div className="text-lg font-mono font-bold text-violet-300">{(latest.fed_liabilities_bn / 1000).toFixed(2)}T</div>
              <div className="text-xs text-zinc-500">reserves + ON RRP</div>
            </div>
          </div>

          <div className="bg-zinc-900 rounded-lg p-4 border border-zinc-800">
            <div className="text-xs text-zinc-500 mb-2">Liquidity Premium / IORB Timeline</div>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={history}>
                <XAxis
                  dataKey="snapshot_date"
                  tick={{ fill: '#71717a', fontSize: 11 }}
                  tickFormatter={(v: string) => v.slice(5)}
                />
                <YAxis
                  yAxisId="left"
                  tick={{ fill: '#71717a', fontSize: 11 }}
                  tickFormatter={(v: number) => `${v.toFixed(1)}bp`}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fill: '#71717a', fontSize: 11 }}
                  tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#18181b',
                    border: '1px solid #27272a',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  formatter={(value, name) => {
                    if (name === 'liquidity_premium_change_base_bp' && typeof value === 'number') {
                      return [`${value.toFixed(2)}bp`, 'LP Base']
                    }
                    if (name === 'iorb' && typeof value === 'number') {
                      return [`${value.toFixed(2)}%`, 'IORB']
                    }
                    return [String(value), String(name)]
                  }}
                  labelFormatter={(value) => `Date: ${value}`}
                />
                <ReferenceLine yAxisId="left" y={0} stroke="#3f3f46" strokeDasharray="3 3" />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="liquidity_premium_change_base_bp"
                  name="LP Base"
                  stroke="#f59e0b"
                  strokeWidth={2.5}
                  dot={{ r: 3 }}
                  connectNulls
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="iorb"
                  name="IORB"
                  stroke="#22d3ee"
                  strokeWidth={1.75}
                  dot={{ r: 2.5 }}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
