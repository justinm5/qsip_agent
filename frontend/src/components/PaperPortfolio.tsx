import { useQuery } from '@tanstack/react-query'
import { fetchPaperAccount, fetchPaperPositions, fetchPaperTrades } from '../api/client'

export default function PaperPortfolio() {
  const { data: account, isLoading: accountLoading } = useQuery({
    queryKey: ['paper-account'],
    queryFn: fetchPaperAccount,
  })
  const { data: positions, isLoading: positionsLoading } = useQuery({
    queryKey: ['paper-positions'],
    queryFn: fetchPaperPositions,
  })
  const { data: trades, isLoading: tradesLoading } = useQuery({
    queryKey: ['paper-trades'],
    queryFn: fetchPaperTrades,
  })

  if (accountLoading || positionsLoading || tradesLoading) {
    return <div className="text-slate-400 text-sm">Loading paper portfolio...</div>
  }

  const totalPnl = positions?.reduce((sum, p) => sum + (p.unrealized_pnl || 0) + (p.realized_pnl || 0), 0) || 0

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 h-96 overflow-y-auto">
      <h2 className="text-sm font-semibold text-slate-300 mb-3">Live Paper Portfolio</h2>
      {account ? (
        <div className="grid grid-cols-3 gap-3 mb-4">
          <Metric label="Equity" value={`$${(account.equity || 0).toLocaleString()}`} />
          <Metric label="Cash" value={`$${(account.cash || 0).toLocaleString()}`} />
          <Metric label="Buying Power" value={`$${(account.buying_power || 0).toLocaleString()}`} />
          <Metric label="Total PnL" value={`$${totalPnl.toLocaleString()}`} />
          <Metric label="Open Positions" value={positions?.length ?? 0} />
          <Metric label="Recent Trades" value={trades?.length ?? 0} />
        </div>
      ) : (
        <p className="text-slate-500 text-sm mb-4">Paper account not initialized.</p>
      )}

      <h3 className="text-xs font-semibold text-slate-500 mb-2">Open Positions</h3>
      <div className="space-y-1 mb-4">
        {positions?.length ? (
          positions.map((p) => (
            <div key={p.ticker} className="flex justify-between text-sm">
              <span className="font-bold text-slate-300">{p.ticker}</span>
              <span className={`font-mono ${p.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {p.qty.toFixed(2)} @ ${p.market_price?.toFixed(2)} | ${p.unrealized_pnl?.toFixed(0)}
              </span>
            </div>
          ))
        ) : (
          <p className="text-slate-600 text-xs">No open positions.</p>
        )}
      </div>

      <h3 className="text-xs font-semibold text-slate-500 mb-2">Recent Trades</h3>
      <div className="space-y-1">
        {trades?.slice(0, 5).map((t) => (
          <div key={t.trade_id} className="flex justify-between text-xs">
            <span className="text-slate-300">{t.ticker} <span className={t.side === 'buy' ? 'text-green-400' : 'text-red-400'}>{t.side}</span></span>
            <span className="text-slate-500">{t.qty} @ ${t.price?.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string | number | undefined }) {
  return (
    <div className="bg-slate-850 border border-slate-800 rounded p-2">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-sm font-mono font-semibold text-emerald-400">{value ?? '-'}</div>
    </div>
  )
}
