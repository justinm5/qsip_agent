import { useQuery } from '@tanstack/react-query'
import { fetchBacktest } from '../api/client'

interface Props {
  ticker: string
}

export default function BacktestPanel({ ticker }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ['backtest', ticker],
    queryFn: () => fetchBacktest(ticker),
    enabled: !!ticker,
  })

  if (isLoading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 h-96 animate-pulse">
        <h2 className="text-sm font-semibold text-slate-300 mb-3">Backtest: {ticker}</h2>
      </div>
    )
  }

  const stats = [
    { label: 'Total Signals', value: data?.total_signals ?? 0 },
    { label: 'Win Rate', value: `${((data?.win_rate ?? 0) * 100).toFixed(1)}%` },
    { label: 'Avg Return', value: `${((data?.avg_return ?? 0) * 100).toFixed(2)}%` },
    { label: 'Avg Excess', value: `${((data?.avg_excess ?? 0) * 100).toFixed(2)}%` },
    { label: 'Max Drawdown', value: `${((data?.max_drawdown ?? 0) * 100).toFixed(2)}%` },
  ]

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 h-96">
      <h2 className="text-sm font-semibold text-slate-300 mb-3">Backtest: {ticker}</h2>
      <div className="grid grid-cols-2 gap-3">
        {stats.map((s) => (
          <div key={s.label} className="bg-slate-850 border border-slate-800 rounded p-3">
            <div className="text-xs text-slate-500 mb-1">{s.label}</div>
            <div className="text-lg font-mono font-semibold text-emerald-400">{s.value}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
