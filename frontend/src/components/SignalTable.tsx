import { useQuery } from '@tanstack/react-query'
import { Signal, fetchSignals } from '../api/client'

interface Props {
  onSelectTicker: (ticker: string) => void
  onSelectSignal: (signalId: string) => void
}

export default function SignalTable({ onSelectTicker, onSelectSignal }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ['signals'],
    queryFn: () => fetchSignals(200),
  })

  if (isLoading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 h-96 animate-pulse">
        <h2 className="text-sm font-semibold text-slate-300 mb-3">Recent Signals</h2>
      </div>
    )
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 overflow-hidden">
      <h2 className="text-sm font-semibold text-slate-300 mb-3">Recent Signals</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="text-xs text-slate-400 uppercase bg-slate-850">
            <tr>
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2">Ticker</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Direction</th>
              <th className="px-3 py-2">Score</th>
              <th className="px-3 py-2">ML</th>
            </tr>
          </thead>
          <tbody>
            {data?.map((s: Signal) => (
              <tr
                key={s.signal_id}
                className="border-b border-slate-800 hover:bg-slate-850 cursor-pointer"
                onClick={() => {
                  onSelectTicker(s.ticker)
                  onSelectSignal(s.signal_id)
                }}
              >
                <td className="px-3 py-2 text-slate-400">
                  {new Date(s.timestamp).toLocaleString()}
                </td>
                <td className="px-3 py-2 font-bold text-emerald-400">{s.ticker}</td>
                <td className="px-3 py-2">{s.signal_type}</td>
                <td className={`px-3 py-2 ${s.direction === 'long' ? 'text-green-400' : 'text-red-400'}`}>
                  {s.direction}
                </td>
                <td className="px-3 py-2 font-mono">{s.score.toFixed(3)}</td>
                <td className="px-3 py-2 font-mono">{(s.ml_score * 100).toFixed(0)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
