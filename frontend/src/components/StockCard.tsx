import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { createPaperOrder, fetchStockRecommendation, StockRecommendation } from '../api/client'

interface Props {
  ticker: string
  onBuy?: () => void
}

export default function StockCard({ ticker, onBuy }: Props) {
  const [qty, setQty] = useState(1)
  const { data, isLoading, error } = useQuery<StockRecommendation, Error>({
    queryKey: ['recommendation', ticker],
    queryFn: () => fetchStockRecommendation(ticker),
  })

  const buyMutation = useMutation({
    mutationFn: () =>
      createPaperOrder({
        ticker,
        qty,
        side: 'buy',
        price: data?.price ?? undefined,
        order_type: 'market',
      }),
    onSuccess: () => {
      if (onBuy) onBuy()
    },
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

  const priceColor = data.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
        <div>
          <div className="flex items-center gap-3">
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

      <p className="text-slate-300 text-sm mb-4 leading-relaxed">{data.summary}</p>

      {data.signals.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-5">
          {data.signals.map((signal) => (
            <div key={signal.label} className="bg-slate-950 border border-slate-800 rounded-lg p-3">
              <div className="text-xs text-slate-500 mb-1">{signal.label}</div>
              <div className="text-sm font-medium text-slate-200">{signal.value}</div>
              <div className="text-xs text-slate-500 mt-1">{signal.detail}</div>
            </div>
          ))}
        </div>
      )}

      {data.price !== null && (
        <div className="flex items-center gap-3">
          <label className="text-sm text-slate-400">Shares</label>
          <input
            type="number"
            min="1"
            step="1"
            value={qty}
            onChange={(e) => setQty(Math.max(1, parseInt(e.target.value, 10) || 0))}
            className="w-20 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-500"
          />
          <button
            onClick={() => buyMutation.mutate()}
            disabled={buyMutation.isPending}
            className="bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white font-medium px-5 py-2 rounded-lg text-sm transition-colors"
          >
            {buyMutation.isPending ? 'Buying...' : 'Buy (paper)'}
          </button>
          {buyMutation.isSuccess && <span className="text-emerald-400 text-sm">Added to portfolio</span>}
          {buyMutation.isError && <span className="text-red-400 text-sm">Buy failed</span>}
        </div>
      )}
    </div>
  )
}
