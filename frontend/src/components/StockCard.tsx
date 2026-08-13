import { useQuery } from '@tanstack/react-query'
import { fetchStockRecommendation, StockRecommendation } from '../api/client'
import { useWatchlist } from '../hooks/useWatchlist'

interface Props {
  ticker: string
}

export default function StockCard({ ticker }: Props) {
  const { add, isSaved } = useWatchlist()
  const saved = isSaved(ticker)
  const { data, isLoading, error } = useQuery<StockRecommendation, Error>({
    queryKey: ['recommendation', ticker],
    queryFn: () => fetchStockRecommendation(ticker),
  })

  if (isLoading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 animate-pulse h-48">
        <div className="h-6 bg-slate-800 rounded w-1/3 mb-4"></div>
        <div className="h-4 bg-slate-800 rounded w-1/2"></div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="bg-slate-900 border border-red-900/50 rounded-xl p-5">
        <p className="text-red-400 text-sm">Could not load {ticker}. Please try again.</p>
      </div>
    )
  }

  const recColor =
    data.recommendation === 'Strong Buy' || data.recommendation === 'Buy'
      ? 'bg-emerald-900/40 text-emerald-400 border-emerald-800'
      : data.recommendation === 'Strong Sell' || data.recommendation === 'Sell'
      ? 'bg-red-900/40 text-red-400 border-red-800'
      : 'bg-amber-900/40 text-amber-400 border-amber-800'

  const convictionColor =
    data.conviction === 'High'
      ? 'text-emerald-400'
      : data.conviction === 'Medium'
      ? 'text-amber-400'
      : 'text-slate-400'

  const priceColor = data.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h3 className="text-2xl font-bold text-white">{data.ticker}</h3>
            <span className={`text-sm px-3 py-1 rounded-full border ${recColor}`}>{data.recommendation}</span>
          </div>
          <p className="text-slate-400 text-sm">{data.name}</p>
        </div>
        {data.price !== null && (
          <div className="text-right">
            <div className="text-2xl font-mono font-semibold">${data.price.toFixed(2)}</div>
            <div className={`text-sm font-mono ${priceColor}`}>
              {data.change_pct >= 0 ? '+' : ''}{data.change_pct.toFixed(2)}%
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-4 mb-4">
        <div className="bg-slate-950 border border-slate-800 rounded-lg px-4 py-2">
          <span className="text-xs text-slate-500">Research score</span>
          <div className="text-lg font-mono font-semibold text-emerald-400">{data.research_score}/100</div>
        </div>
        <div className="bg-slate-950 border border-slate-800 rounded-lg px-4 py-2">
          <span className="text-xs text-slate-500">Conviction</span>
          <div className={`text-lg font-semibold ${convictionColor}`}>{data.conviction}</div>
        </div>
        {data.analyst_count > 0 && (
          <div className="bg-slate-950 border border-slate-800 rounded-lg px-4 py-2">
            <span className="text-xs text-slate-500">Analyst rating</span>
            <div className="text-sm font-semibold text-slate-200">
              {data.analyst_rating} <span className="text-slate-500">({data.analyst_count})</span>
            </div>
          </div>
        )}
      </div>

      <p className="text-slate-300 text-sm mb-5 leading-relaxed">{data.summary}</p>

      {data.recommendation !== 'No data' && (
        <button
          onClick={() => add(ticker)}
          disabled={saved}
          className={`mb-5 text-sm font-medium px-4 py-2 rounded-lg transition-colors ${
            saved
              ? 'bg-slate-800 text-slate-500 cursor-default'
              : 'bg-emerald-600 hover:bg-emerald-500 text-white'
          }`}
        >
          {saved ? 'Saved to watchlist' : 'Save to watchlist'}
        </button>
      )}

      {data.factors.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {data.factors.map((factor) => (
            <FactorCard key={factor.label} factor={factor} />
          ))}
        </div>
      )}
    </div>
  )
}

function FactorCard({ factor }: { factor: StockRecommendation['factors'][number] }) {
  const borderColor =
    factor.sentiment === 'positive'
      ? 'border-emerald-800'
      : factor.sentiment === 'negative'
      ? 'border-red-800'
      : 'border-slate-800'
  const valueColor =
    factor.sentiment === 'positive'
      ? 'text-emerald-400'
      : factor.sentiment === 'negative'
      ? 'text-red-400'
      : 'text-slate-300'

  return (
    <div className={`bg-slate-950 border ${borderColor} rounded-lg p-3`}>
      <div className="text-xs text-slate-500 mb-1">{factor.label}</div>
      <div className={`text-sm font-medium ${valueColor}`}>{factor.value}</div>
      <div className="text-xs text-slate-500 mt-1">{factor.detail}</div>
    </div>
  )
}
