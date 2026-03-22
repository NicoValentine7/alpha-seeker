interface ScoreBarProps {
  value: number | null
  max?: number
}

function scoreColor(v: number): string {
  if (v >= 70) return 'bg-emerald-500'
  if (v >= 50) return 'bg-blue-500'
  if (v >= 30) return 'bg-amber-500'
  return 'bg-red-500'
}

export function ScoreBar({ value, max = 100 }: ScoreBarProps) {
  if (value === null || value === undefined) {
    return <span className="text-zinc-600 text-xs">-</span>
  }
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <div className="flex items-center gap-1.5 min-w-[80px]">
      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${scoreColor(value)}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-zinc-300 w-8 text-right">{value.toFixed(0)}</span>
    </div>
  )
}
