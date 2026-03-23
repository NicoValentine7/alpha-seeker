import { useState, useEffect } from 'react'
import { Plus, X, Briefcase } from 'lucide-react'
import type { Stock } from '../types'
import { ScoreBar } from './ScoreBar'

interface Props {
  stocks: Stock[]
}

const STORAGE_KEY = 'alpha-seeker-portfolio'

function loadPortfolio(): string[] {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? JSON.parse(saved) : []
  } catch {
    return []
  }
}

function savePortfolio(tickers: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tickers))
}

export function Portfolio({ stocks }: Props) {
  const [tickers, setTickers] = useState<string[]>(loadPortfolio)
  const [input, setInput] = useState('')
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    savePortfolio(tickers)
  }, [tickers])

  const addTicker = () => {
    const t = input.trim().toUpperCase()
    if (t && !tickers.includes(t)) {
      setTickers([...tickers, t])
      setInput('')
    }
  }

  const removeTicker = (t: string) => {
    setTickers(tickers.filter(x => x !== t))
  }

  const matched = tickers.map(t => {
    const stock = stocks.find(s => s.ticker === t)
    return { ticker: t, stock }
  })

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border border-zinc-700 rounded text-sm text-zinc-300 hover:border-blue-500 transition-colors"
      >
        <Briefcase className="w-4 h-4" />
        Portfolio {tickers.length > 0 && `(${tickers.length})`}
      </button>
    )
  }

  return (
    <div className="mb-4 p-4 bg-zinc-900/50 border border-zinc-800 rounded-lg">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-zinc-300 flex items-center gap-2">
          <Briefcase className="w-4 h-4" />
          My Portfolio
        </h3>
        <button onClick={() => setIsOpen(false)} className="text-zinc-500 hover:text-zinc-300">&times;</button>
      </div>

      {/* Add ticker */}
      <div className="flex gap-2 mb-3">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && addTicker()}
          placeholder="AAPL, MSFT..."
          className="flex-1 px-3 py-1.5 bg-zinc-800 border border-zinc-700 rounded text-sm text-zinc-200
                     placeholder:text-zinc-500 focus:outline-none focus:border-blue-500"
        />
        <button
          onClick={addTicker}
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded text-sm text-white flex items-center gap-1"
        >
          <Plus className="w-3.5 h-3.5" /> Add
        </button>
      </div>

      {/* Portfolio list */}
      {matched.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="text-left text-xs text-zinc-500 py-1 px-2">Ticker</th>
                <th className="text-left text-xs text-zinc-500 py-1 px-2">Name</th>
                <th className="text-left text-xs text-zinc-500 py-1 px-2">Total</th>
                <th className="text-left text-xs text-zinc-500 py-1 px-2">Value</th>
                <th className="text-left text-xs text-zinc-500 py-1 px-2">Growth</th>
                <th className="text-left text-xs text-zinc-500 py-1 px-2">Quality</th>
                <th className="text-left text-xs text-zinc-500 py-1 px-2">Mom.</th>
                <th className="text-left text-xs text-zinc-500 py-1 px-2">F</th>
                <th className="text-left text-xs text-zinc-500 py-1 px-2">Price</th>
                <th className="text-left text-xs text-zinc-500 py-1 px-2">Upside</th>
                <th className="py-1 px-2"></th>
              </tr>
            </thead>
            <tbody>
              {matched.map(({ ticker, stock }) => (
                <tr key={ticker} className="border-b border-zinc-800/30 hover:bg-zinc-800/30">
                  <td className="py-1.5 px-2 font-semibold text-zinc-100">{ticker}</td>
                  {stock ? (
                    <>
                      <td className="py-1.5 px-2 text-zinc-400 max-w-[140px] truncate">{stock.name}</td>
                      <td className="py-1.5 px-2"><ScoreBar value={stock.total_score} /></td>
                      <td className="py-1.5 px-2"><ScoreBar value={stock.valuation_score} /></td>
                      <td className="py-1.5 px-2"><ScoreBar value={stock.growth_score} /></td>
                      <td className="py-1.5 px-2"><ScoreBar value={stock.quality_score} /></td>
                      <td className="py-1.5 px-2"><ScoreBar value={stock.earnings_momentum_score} /></td>
                      <td className="py-1.5 px-2">
                        {stock.piotroski_fscore !== null ? (
                          <span className={`text-xs font-medium ${
                            stock.piotroski_fscore >= 7 ? 'text-emerald-400' :
                            stock.piotroski_fscore >= 4 ? 'text-zinc-300' : 'text-red-400'
                          }`}>{stock.piotroski_fscore}</span>
                        ) : <span className="text-zinc-600">-</span>}
                      </td>
                      <td className="py-1.5 px-2 text-xs tabular-nums text-zinc-300">
                        {stock.current_price ? `$${stock.current_price.toFixed(0)}` : '-'}
                      </td>
                      <td className="py-1.5 px-2 text-xs tabular-nums">
                        {stock.upside_potential !== null ? (
                          <span className={stock.upside_potential > 0.1 ? 'text-emerald-400' : stock.upside_potential < -0.05 ? 'text-red-400' : 'text-zinc-300'}>
                            {(stock.upside_potential * 100).toFixed(0)}%
                          </span>
                        ) : '-'}
                      </td>
                    </>
                  ) : (
                    <td colSpan={9} className="py-1.5 px-2 text-zinc-600 italic">Not in ranking data</td>
                  )}
                  <td className="py-1.5 px-2">
                    <button onClick={() => removeTicker(ticker)} className="text-zinc-600 hover:text-red-400">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-xs text-zinc-500">保有銘柄のティッカーを入力してください</p>
      )}
    </div>
  )
}
