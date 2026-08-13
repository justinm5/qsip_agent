import { useQuery } from '@tanstack/react-query'
import { fetchSignalExplanation } from '../api/client'

interface Props {
  signalId: string
}

export default function SignalExplain({ signalId }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ['explain', signalId],
    queryFn: () => fetchSignalExplanation(signalId),
    enabled: !!signalId,
  })

  if (isLoading) return <div className="text-slate-400 text-sm">Loading explanation...</div>
  if (!data) return null

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-slate-300 mb-2">Signal Explainability</h3>
      <p className="text-emerald-400 text-sm mb-3">{data.summary}</p>
      <div className="space-y-2">
        {data.top_features?.map((f: { feature: string; impact: number }) => (
          <div key={f.feature} className="flex items-center justify-between text-sm">
            <span className="text-slate-400">{f.feature.replace(/_/g, ' ')}</span>
            <span className={`font-mono ${f.impact > 0 ? 'text-green-400' : 'text-red-400'}`}>
              {f.impact > 0 ? '+' : ''}{f.impact.toFixed(3)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
