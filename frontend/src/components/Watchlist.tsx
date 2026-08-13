import { useQueries } from '@tanstack/react-query'
import { fetchStockRecommendation, StockRecommendation } from '../api/client'
import TrendingCard from './TrendingCard'
import { useWatchlist } from '../hooks/useWatchlist'

interface Props {
  onSelect?: (ticker: string) => void
}

export default function Watchlist({ onSelect }: Props) {
  const { tickers, remove } = useWatchlist()

  const queries = useQueries({
    queries: tickers.map((ticker) => ({
      queryKey: ['recommendation', ticker],
      queryFn: () => fetchStockRecommendation(ticker),
      staleTime: 5 * 60 * 1000,
    })),
  })

  if (tickers.length === 0) {
    return null
  }

  const stocks: StockRecommendation[] = []
  queries.forEach((q) => {
    if (q.data) {
      stocks.push(q.data)
    }
  })

  return (
    <section className="mb-8">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-slate-200">Your watchlist</h2>
        <span className="text-xs text-slate-500">Saved on this device</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {stocks.map((stock) => (
          <div key={stock.ticker} className="relative group">
            <TrendingCard stock={stock} onSelect={() => onSelect?.(stock.ticker)} />
            <button
              onClick={() => remove(stock.ticker)}
              className="absolute top-2 right-2 bg-slate-800 hover:bg-red-900/60 text-slate-400 hover:text-red-400 text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
            >
              Remove
            </button>
          </div>
        ))}
      </div>
    </section>
  )
}
