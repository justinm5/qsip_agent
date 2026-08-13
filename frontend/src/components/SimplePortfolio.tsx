import { useQuery } from '@tanstack/react-query'
import { fetchPaperAccount, fetchPaperPositions, fetchPaperTrades, PaperAccount, PaperPosition, PaperTrade } from '../api/client'

export default function SimplePortfolio() {
  const { data: account, isLoading: accountLoading } = useQuery<PaperAccount, Error>({
    queryKey: ['paper-account'],
    queryFn: fetchPaperAccount,
  })
  const { data: positions, isLoading: positionsLoading } = useQuery<PaperPosition[], Error>({
    queryKey: ['paper-positions'],
    queryFn: fetchPaperPositions,
  })
  const { data: trades, isLoading: tradesLoading } = useQuery<PaperTrade[], Error>({
    queryKey: ['paper-trades'],
    queryFn: fetchPaperTrades,
  })

  if (accountLoading || positionsLoading || tradesLoading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 animate-pulse h-32">
        <div className="h-6 bg-slate-800 rounded w-1/4 mb-3"></div>
        <div className="h-4 bg-slate-800 rounded w-1/2"></div>
      </div>
    )
  }

  const cash = account?.cash ?? 100_000
  const equity = account?.equity ?? cash
  const openPositions = positions ?? []
  const recentTrades = trades ?? []
  const totalPnl = openPositions.reduce((sum, p) => sum + (p.unrealized_pnl || 0) + (p.realized_pnl || 0), 0)

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <h2 className="text-lg font-semibold text-slate-200 mb-4">Your paper portfolio</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Metric label="Cash" value={`$${cash.toLocaleString()}`} />
        <Metric label="Total value" value={`$${equity.toLocaleString()}`} />
        <Metric label="Open positions" value={openPositions.length} />
        <Metric label="Unrealized P&L" value={`$${totalPnl.toLocaleString()}`} color={totalPnl >= 0 ? 'text-emerald-400' : 'text-red-400'} />
      </div>

      {openPositions.length === 0 ? (
        <p className="text-slate-400 text-sm mb-4">You do not own any stocks yet. Search a ticker above and click Buy to start building your portfolio.</p>
      ) : (
        <div className="mb-6">
          <h3 className="text-sm font-medium text-slate-300 mb-2">Open positions</h3>
          <div className="space-y-2">
            {openPositions.map((p) => (
              <div key={p.ticker} className="flex justify-between items-center bg-slate-950 border border-slate-800 rounded-lg p-3">
                <div>
                  <span className="font-bold text-white">{p.ticker}</span>
                  <span className="text-slate-400 text-sm ml-2">{p.qty.toFixed(2)} shares</span>
                </div>
                <div className={`font-mono text-sm ${(p.unrealized_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  ${(p.unrealized_pnl || 0).toFixed(0)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {recentTrades.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-slate-300 mb-2">Recent trades</h3>
          <div className="space-y-2">
            {recentTrades.slice(0, 5).map((t) => (
              <div key={t.trade_id} className="flex justify-between text-sm text-slate-300">
                <span>
                  {t.ticker}{' '}
                  <span className={t.side === 'buy' ? 'text-emerald-400' : 'text-red-400'}>{t.side}</span>
                </span>
                <span className="text-slate-500">
                  {t.qty} @ ${t.price?.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function Metric({ label, value, color = 'text-white' }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="bg-slate-950 border border-slate-800 rounded-lg p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`text-sm font-mono font-semibold ${color}`}>{value}</div>
    </div>
  )
}
