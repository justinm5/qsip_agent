import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

interface PerformanceSummary {
  signals_generated: number
  '20d_return_mean': number
  '20d_win_rate': number
  '20d_sharpe': number
  '20d_max_drawdown': number
}

interface ResearchData {
  summary: Record<string, PerformanceSummary>
  ml_spread: {
    top_decile_return_20d: number
    bottom_decile_return_20d: number
    spread: number
  }
}

export default function ResearchResults() {
  const { data, isLoading } = useQuery({
    queryKey: ['research-performance'],
    queryFn: () => api.get<ResearchData>('/research/performance').then((r) => r.data),
  })

  if (isLoading) return <div className="text-slate-400 text-sm">Loading research...</div>

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 h-96 overflow-y-auto">
      <h2 className="text-sm font-semibold text-slate-300 mb-3">Research Results</h2>
      {data ? (
        <div className="space-y-4">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-slate-400 uppercase bg-slate-850">
              <tr>
                <th className="px-2 py-2">Signal</th>
                <th className="px-2 py-2">Signals</th>
                <th className="px-2 py-2">20D Return</th>
                <th className="px-2 py-2">Win Rate</th>
                <th className="px-2 py-2">Sharpe</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.summary).map(([signal, s]) => (
                <tr key={signal} className="border-b border-slate-800">
                  <td className="px-2 py-2">{signal}</td>
                  <td className="px-2 py-2">{s.signals_generated.toLocaleString()}</td>
                  <td className="px-2 py-2 font-mono">{(s['20d_return_mean'] * 100).toFixed(1)}%</td>
                  <td className="px-2 py-2 font-mono">{(s['20d_win_rate'] * 100).toFixed(1)}%</td>
                  <td className="px-2 py-2 font-mono">{s['20d_sharpe'].toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="bg-slate-850 border border-slate-800 rounded p-3">
            <div className="text-xs text-slate-500 mb-1">ML Alpha Decile Spread</div>
            <div className="text-lg font-mono font-semibold text-emerald-400">
              {(data.ml_spread.spread * 100).toFixed(1)}%
            </div>
            <div className="text-xs text-slate-500">
              Top decile { (data.ml_spread.top_decile_return_20d * 100).toFixed(1)}% vs bottom { (data.ml_spread.bottom_decile_return_20d * 100).toFixed(1)}%
            </div>
          </div>
        </div>
      ) : (
        <p className="text-slate-500 text-sm">Research results not available.</p>
      )}
    </div>
  )
}
