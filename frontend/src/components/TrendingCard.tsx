import { StockRecommendation } from '../api/client'

interface Props {
  stock: StockRecommendation
  onSelect: (ticker: string) => void
}

export default function TrendingCard({ stock, onSelect }: Props) {
  const recColor =
    stock.recommendation === 'Strong Buy' || stock.recommendation === 'Buy'
      ? 'bg-emerald-900/40 text-emerald-400 border-emerald-800'
      : stock.recommendation === 'Strong Sell' || stock.recommendation === 'Sell'
      ? 'bg-red-900/40 text-red-400 border-red-800'
      : 'bg-amber-900/40 text-amber-400 border-amber-800'

  const convictionColor =
    stock.conviction === 'High'
      ? 'text-emerald-400'
      : stock.conviction === 'Medium'
      ? 'text-amber-400'
      : 'text-slate-400'

  const priceColor = stock.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'

  return (
    <button
      onClick={() => onSelect(stock.ticker)}
      className="text-left bg-slate-900 border border-slate-800 rounded-xl p-4 hover:border-emerald-500 transition-colors flex flex-col"
    >
      <div className="flex items-center justify-between mb-2">
        <div>
          <h3 className="text-lg font-bold text-white">{stock.ticker}</h3>
          <p className="text-slate-400 text-xs truncate max-w-[140px]">{stock.name}</p>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full border ${recColor}`}>{stock.recommendation}</span>
      </div>

      {stock.price !== null && (
        <div className="mb-3">
          <div className="text-xl font-mono font-semibold">${stock.price.toFixed(2)}</div>
          <div className={`text-xs font-mono ${priceColor}`}>
            {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct.toFixed(2)}%
          </div>
        </div>
      )}

      <div className="flex items-center gap-3 mb-3">
        <div className="text-xs text-slate-500">
          Score <span className="text-emerald-400 font-mono font-semibold">{stock.research_score}</span>
        </div>
        <div className="text-xs text-slate-500">
          Conviction <span className={`font-semibold ${convictionColor}`}>{stock.conviction}</span>
        </div>
      </div>

      <p className="text-slate-300 text-xs line-clamp-2">{stock.summary}</p>
    </button>
  )
}
