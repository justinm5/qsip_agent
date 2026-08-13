import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { createPaperOrder, StockRecommendation } from '../api/client'

interface Props {
  stock: StockRecommendation
  onSelect: (ticker: string) => void
  onBuy?: () => void
}

export default function TrendingCard({ stock, onSelect, onBuy }: Props) {
  const [qty, setQty] = useState(1)

  const buyMutation = useMutation({
    mutationFn: () =>
      createPaperOrder({
        ticker: stock.ticker,
        qty,
        side: 'buy',
        price: stock.price ?? undefined,
        order_type: 'market',
      }),
    onSuccess: () => {
      if (onBuy) onBuy()
    },
  })

  const recColor =
    stock.recommendation === 'Strong Buy' || stock.recommendation === 'Buy'
      ? 'bg-emerald-900/40 text-emerald-400 border-emerald-800'
      : stock.recommendation === 'Strong Sell' || stock.recommendation === 'Sell'
      ? 'bg-red-900/40 text-red-400 border-red-800'
      : 'bg-amber-900/40 text-amber-400 border-amber-800'

  const priceColor = stock.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col">
      <button
        onClick={() => onSelect(stock.ticker)}
        className="text-left flex-1"
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
        <p className="text-slate-300 text-xs line-clamp-2 mb-2">{stock.summary}</p>
      </button>

      {stock.price !== null && (
        <div className="flex items-center gap-2 mt-auto pt-3 border-t border-slate-800">
          <input
            type="number"
            min="1"
            step="1"
            value={qty}
            onChange={(e) => setQty(Math.max(1, parseInt(e.target.value, 10) || 0))}
            className="w-14 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs focus:outline-none focus:border-emerald-500"
          />
          <button
            onClick={() => buyMutation.mutate()}
            disabled={buyMutation.isPending}
            className="bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white text-xs font-medium px-3 py-1.5 rounded transition-colors"
          >
            Buy
          </button>
          {buyMutation.isSuccess && <span className="text-emerald-400 text-xs">Added</span>}
        </div>
      )}
    </div>
  )
}
