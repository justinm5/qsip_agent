import { useQuery } from '@tanstack/react-query'
import { fetchPortfolio } from '../api/client'

export default function PortfolioPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ['portfolio', 'equal_weight_top20'],
    queryFn: () => fetchPortfolio('equal_weight_top20'),
  })

  if (isLoading) return <div className="text-slate-400 text-sm">Loading portfolio...</div>

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 h-96 overflow-y-auto">
      <h2 className="text-sm font-semibold text-slate-300 mb-3">Portfolio Simulation</h2>
      {data ? (
        <div className="grid grid-cols-2 gap-3">
          <Metric label="NAV" value={`$${(data.nav / 1e6).toFixed(2)}M`} />
          <Metric label="Sharpe" value={data.sharpe?.toFixed(2)} />
          <Metric label="Sortino" value={data.sortino?.toFixed(2)} />
          <Metric label="Max DD" value={`${(data.max_drawdown * 100).toFixed(1)}%`} />
          <Metric label="Alpha" value={data.alpha?.toFixed(3)} />
          <Metric label="Beta" value={data.beta?.toFixed(3)} />
        </div>
      ) : (
        <p className="text-slate-500 text-sm">No portfolio snapshot available.</p>
      )}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string | number | undefined }) {
  return (
    <div className="bg-slate-850 border border-slate-800 rounded p-3">
      <div className="text-xs text-slate-500 mb-1">{label}</div>
      <div className="text-lg font-mono font-semibold text-emerald-400">{value ?? '-'}</div>
    </div>
  )
}
