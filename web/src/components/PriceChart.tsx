import { useMemo } from 'react'
import { AreaChart, Area, ResponsiveContainer, Tooltip, YAxis, XAxis } from 'recharts'

interface Props {
  sparkline: number[] | null
  sparkline_dates?: string[] | null
  ticker: string
  currentPrice: number | null
}

export function PriceChart({ sparkline, sparkline_dates, ticker, currentPrice }: Props) {
  if (!sparkline || sparkline.length < 3) return null

  const data = useMemo(() =>
    sparkline.map((price, i) => ({
      date: sparkline_dates?.[i]
        ? new Date(sparkline_dates[i]).toLocaleDateString('ja-JP', { month: 'short', day: 'numeric' })
        : `W${i}`,
      price,
    })),
    [sparkline, sparkline_dates]
  )

  const first = sparkline[0]
  const last = currentPrice ?? sparkline[sparkline.length - 1]
  const change = ((last - first) / first) * 100
  const isUp = change >= 0
  const color = isUp ? '#10b981' : '#ef4444'
  const min = Math.min(...sparkline) * 0.97
  const max = Math.max(...sparkline) * 1.03

  return (
    <div className="mt-4">
      <div className="flex items-baseline gap-3 mb-2">
        <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wide">株価推移（1年）</h4>
        <span className="text-sm font-semibold text-zinc-100 tabular-nums">${last.toFixed(2)}</span>
        <span className={`text-xs tabular-nums ${isUp ? 'text-emerald-400' : 'text-red-400'}`}>
          {change >= 0 ? '+' : ''}{change.toFixed(1)}%
        </span>
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
          <defs>
            <linearGradient id={`grad-${ticker}`} x1="0" y1="0" x2="0" y2="1">
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
            fill={`url(#grad-${ticker})`}
            dot={false}
            activeDot={{ r: 3, fill: color }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
