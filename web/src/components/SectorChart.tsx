import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { Stock } from '../types'

interface Props {
  stocks: Stock[]
}

const COLORS = [
  '#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6',
  '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1',
  '#14b8a6', '#e11d48', '#a855f7',
]

export function SectorChart({ stocks }: Props) {
  const data = useMemo(() => {
    const grouped: Record<string, { scores: number[]; count: number }> = {}
    for (const s of stocks) {
      if (!s.sector || s.total_score === null) continue
      if (!grouped[s.sector]) grouped[s.sector] = { scores: [], count: 0 }
      grouped[s.sector].scores.push(s.total_score)
      grouped[s.sector].count++
    }
    return Object.entries(grouped)
      .map(([sector, { scores, count }]) => ({
        sector: sector.replace('Communication Services', 'Comm. Svcs')
          .replace('Consumer Cyclical', 'Consumer Cyc.')
          .replace('Consumer Defensive', 'Consumer Def.')
          .replace('Financial Services', 'Financial Svcs')
          .replace('Information Technology', 'Info. Tech')
          .replace('Basic Materials', 'Materials'),
        avg: scores.reduce((a, b) => a + b, 0) / scores.length,
        count,
      }))
      .sort((a, b) => b.avg - a.avg)
  }, [stocks])

  if (data.length === 0) return null

  return (
    <div className="mb-6 p-4 bg-zinc-900/50 border border-zinc-800 rounded-lg">
      <h3 className="text-sm font-medium text-zinc-400 mb-3">セクター別平均スコア</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} layout="vertical" margin={{ left: 90, right: 30, top: 0, bottom: 0 }}>
          <XAxis type="number" domain={[0, 80]} tick={{ fill: '#71717a', fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="sector" tick={{ fill: '#a1a1aa', fontSize: 11 }} axisLine={false} tickLine={false} width={85} />
          <Tooltip
            contentStyle={{ background: '#27272a', border: '1px solid #3f3f46', borderRadius: 6, fontSize: 13 }}
            labelStyle={{ color: '#e4e4e7' }}
            formatter={(value, _name, item) => [
              `${Number(value).toFixed(1)}  (${(item as any).payload.count} stocks)`,
              '平均スコア',
            ]}
          />
          <Bar dataKey="avg" radius={[0, 3, 3, 0]} barSize={14}>
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} fillOpacity={0.8} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
