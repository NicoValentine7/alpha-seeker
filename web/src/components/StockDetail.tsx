import type { Stock } from '../types'

function fmt(v: number | null, suffix = '', mul = 1): string {
  if (v === null || v === undefined) return '-'
  const val = v * mul
  return val >= 0 ? `+${val.toFixed(1)}${suffix}` : `${val.toFixed(1)}${suffix}`
}

function fmtRatio(v: number | null): string {
  if (v === null || v === undefined) return '-'
  return v.toFixed(2)
}

function fmtMcap(v: number | null): string {
  if (v === null || v === undefined) return '-'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9) return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

interface Props {
  stock: Stock
  onClose: () => void
}

export function StockDetail({ stock: s, onClose }: Props) {
  return (
    <tr>
      <td colSpan={99} className="p-0">
        <div className="bg-zinc-900/80 border-y border-zinc-700 px-6 py-5">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="text-lg font-semibold text-zinc-100">{s.ticker} - {s.name}</h3>
              <p className="text-sm text-zinc-400">{s.sector} / {fmtMcap(s.market_cap)}</p>
            </div>
            <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300 text-xl leading-none">&times;</button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-sm">
            {/* Valuation */}
            <div>
              <h4 className="text-xs font-medium text-blue-400 uppercase tracking-wide mb-2">Valuation</h4>
              <dl className="space-y-1">
                <Row label="PER" value={fmtRatio(s.pe_ratio)} />
                <Row label="Forward PE" value={fmtRatio(s.forward_pe)} />
                <Row label="PBR" value={fmtRatio(s.pb_ratio)} />
                <Row label="EV/EBITDA" value={fmtRatio(s.ev_ebitda)} />
                <Row label="PSR" value={fmtRatio(s.ps_ratio)} />
                <Row label="FCF Yield" value={fmt(s.fcf_yield, '%', 100)} />
                <Row label="PEG" value={fmtRatio(s.peg_ratio)} />
              </dl>
            </div>

            {/* Growth */}
            <div>
              <h4 className="text-xs font-medium text-emerald-400 uppercase tracking-wide mb-2">Growth</h4>
              <dl className="space-y-1">
                <Row label="Revenue" value={fmt(s.revenue_growth_calc, '%', 100)} />
                <Row label="Op. Income" value={fmt(s.operating_income_growth, '%', 100)} />
                <Row label="EPS" value={fmt(s.eps_growth, '%', 100)} />
                <Row label="Fwd EPS" value={fmt(s.forward_eps_growth, '%', 100)} />
                <Row label="Rev. Accel" value={fmt(s.revenue_acceleration, '%', 100)} />
              </dl>
            </div>

            {/* Quality */}
            <div>
              <h4 className="text-xs font-medium text-amber-400 uppercase tracking-wide mb-2">Quality</h4>
              <dl className="space-y-1">
                <Row label="ROE" value={fmt(s.roe, '%', 100)} />
                <Row label="Gross Margin" value={fmt(s.gross_margin, '%', 100)} />
                <Row label="D/E" value={fmtRatio(s.debt_to_equity)} />
                <Row label="FCF Margin" value={fmt(s.fcf_margin, '%', 100)} />
                <Row label="F-Score" value={s.piotroski_fscore !== null ? `${s.piotroski_fscore}/9` : '-'} />
              </dl>
            </div>

            {/* Analyst & Earnings */}
            <div>
              <h4 className="text-xs font-medium text-purple-400 uppercase tracking-wide mb-2">Analyst & Earnings</h4>
              <dl className="space-y-1">
                <Row label="Price" value={s.current_price ? `$${s.current_price.toFixed(2)}` : '-'} />
                <Row label="Target" value={s.target_mean_price ? `$${s.target_mean_price.toFixed(0)}` : '-'} />
                <Row label="Upside" value={fmt(s.upside_potential, '%', 100)} />
                <Row label="Rating" value={s.recommendation_mean ? `${s.recommendation_mean.toFixed(1)}/5` : '-'} />
                <Row label="Analysts" value={s.num_analysts ? `${s.num_analysts}` : '-'} />
                <Row label="Surprise" value={fmt(s.avg_surprise_pct, '%')} />
                <Row label="EPS Rev 90d" value={fmt(s.eps_revision_90d, '%', 100)} />
                <Row label="Beat" value={
                  s.earnings_beat_count !== null && s.earnings_beat_total !== null
                    ? `${s.earnings_beat_count}/${s.earnings_beat_total}`
                    : '-'
                } />
              </dl>
            </div>
          </div>

          {/* F-Score Details */}
          {s.piotroski_details && (
            <div className="mt-4 px-3 py-2 bg-zinc-800/50 border border-zinc-700/50 rounded text-sm">
              <span className="text-zinc-400">F-Score {s.piotroski_fscore}/9: </span>
              <span className="text-zinc-300">{s.piotroski_details}</span>
            </div>
          )}

          {s.is_value_trap && (
            <div className="mt-2 px-3 py-2 bg-red-950/50 border border-red-800/50 rounded text-sm text-red-300">
              Value Trap: {s.value_trap_reason}
            </div>
          )}

          {/* Earnings Surprises */}
          {s.earnings_surprises && s.earnings_surprises.length > 0 && (
            <div className="mt-4">
              <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wide mb-2">決算サプライズ</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {s.earnings_surprises.map((e, i) => (
                  <div key={i} className="px-2 py-1.5 bg-zinc-800/50 rounded text-xs">
                    <div className="text-zinc-500">{e.date}</div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">予想: {e.eps_estimate != null ? `$${e.eps_estimate.toFixed(2)}` : '-'}</span>
                      <span className="text-zinc-200">実績: {e.eps_actual != null ? `$${e.eps_actual.toFixed(2)}` : '-'}</span>
                    </div>
                    {e.surprise_pct != null && (
                      <div className={`font-medium ${e.surprise_pct > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {e.surprise_pct > 0 ? '+' : ''}{e.surprise_pct.toFixed(1)}%
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Analyst Actions */}
          {s.analyst_actions && s.analyst_actions.length > 0 && (
            <div className="mt-4">
              <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wide mb-2">アナリストアクション</h4>
              <div className="space-y-1">
                {s.analyst_actions.slice(0, 5).map((a, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className="text-zinc-500 w-20 shrink-0">{a.date}</span>
                    <span className="text-zinc-300">{a.firm}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                      a.action === 'up' ? 'bg-emerald-900/50 text-emerald-300' :
                      a.action === 'down' ? 'bg-red-900/50 text-red-300' :
                      'bg-zinc-800 text-zinc-400'
                    }`}>
                      {a.action === 'up' ? 'UP' : a.action === 'down' ? 'DOWN' : a.action.toUpperCase()}
                    </span>
                    <span className="text-zinc-400">{a.from_grade} → {a.to_grade}</span>
                    {a.target_price && (
                      <span className="text-zinc-500">TP: ${a.target_price.toFixed(0)}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* News */}
          {s.news && s.news.length > 0 && (
            <div className="mt-4">
              <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wide mb-2">ニュース</h4>
              <div className="space-y-1.5">
                {s.news.slice(0, 5).map((n, i) => (
                  <div key={i} className="text-xs">
                    <div className="flex items-baseline gap-2">
                      <span className="text-zinc-500 shrink-0">{n.date}</span>
                      {n.url ? (
                        <a href={n.url} target="_blank" rel="noopener noreferrer"
                           className="text-blue-400 hover:text-blue-300 hover:underline line-clamp-1">
                          {n.title}
                        </a>
                      ) : (
                        <span className="text-zinc-300 line-clamp-1">{n.title}</span>
                      )}
                    </div>
                    {n.publisher && <span className="text-zinc-600 ml-[4.5rem]">{n.publisher}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Next Earnings */}
          {s.next_earnings_date && (
            <div className="mt-3 text-xs text-zinc-500">
              次回決算日: <span className="text-zinc-300">{s.next_earnings_date}</span>
            </div>
          )}
        </div>
      </td>
    </tr>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-zinc-500">{label}</dt>
      <dd className="text-zinc-200 tabular-nums">{value}</dd>
    </div>
  )
}
