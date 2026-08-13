import { useQuery } from '@tanstack/react-query'
import { fetchTrendingStocks, StockRecommendation } from '../api/client'
import TrendingCard from './TrendingCard'

interface Props {
  onSelect: (ticker: string) => void
}

export default function TrendingList({ onSelect }: Props) {
  const { data, isLoading, error } = useQuery<StockRecommendation[], Error>({
    queryKey: ['trending'],
    queryFn: () => fetchTrendingStocks(12),
    staleTime: 5 * 60 * 1000,
  })

  if (isLoading) {
    return (
      <div>
        <h2 className="text-lg font-semibold text-slate-200 mb-3">Top opportunities right now</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="bg-slate-900 border border-slate-800 rounded-xl p-4 h-40 animate-pulse"></div>
          ))}
        </div>
      </div>
    )
  }

  if (error || !data || data.length === 0) {
    return (
      <div>
        <h2 className="text-lg font-semibold text-slate-200 mb-3">Top opportunities right now</h2>
        <p className="text-slate-500 text-sm">
          {error ? 'Could not load trending stocks. Please try again later.' : 'No trending data available right now.'}
        </p>
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-200 mb-3">Top opportunities right now</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {data.map((stock) => (
          <TrendingCard key={stock.ticker} stock={stock} onSelect={onSelect} />
        ))}
      </div>
    </div>
  )
}
