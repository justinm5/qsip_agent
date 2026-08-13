import { useQuery } from '@tanstack/react-query'
import { fetchTopRecommendations } from '../api/client'

export default function TopRecommendations() {
  const { data, isLoading } = useQuery({
    queryKey: ['top-recommendations'],
    queryFn: () => fetchTopRecommendations(10),
  })

  if (isLoading) return <div className="text-slate-400 text-sm">Loading rankings...</div>

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 h-96 overflow-y-auto">
      <h2 className="text-sm font-semibold text-slate-300 mb-3">Top Recommendations</h2>
      {data?.length ? (
        <div className="space-y-3">
          {data.map((rec, idx) => (
            <div
              key={rec.signal_id}
              className="bg-slate-850 border border-slate-800 rounded p-3 hover:border-emerald-500 transition-colors"
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">#{idx + 1}</span>
                  <span className="font-bold text-emerald-400">{rec.ticker}</span>
                  <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300">{rec.signal_type}</span>
                </div>
                <span className="font-mono text-sm text-emerald-400">
                  {(rec.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <p className="text-xs text-slate-400 mb-2">{rec.summary}</p>
              <div className="flex flex-wrap gap-2">
                {rec.top_features?.slice(0, 3).map((f) => (
                  <span
                    key={f.feature}
                    className={`text-xs px-2 py-0.5 rounded ${
                      f.impact > 0 ? 'bg-green-900/40 text-green-400' : 'bg-red-900/40 text-red-400'
                    }`}
                  >
                    {f.impact > 0 ? '+' : ''}{f.impact.toFixed(3)} {f.feature.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-slate-500 text-sm">No recommendations available.</p>
      )}
    </div>
  )
}
