import { useEffect, useRef, useState } from 'react'
import { Signal } from '../api/client'

export default function SignalStream() {
  const [signals, setSignals] = useState<Signal[]>([])
  const ws = useRef<EventSource | null>(null)

  useEffect(() => {
    const es = new EventSource('/api/v1/stream/signals')
    ws.current = es
    es.onmessage = (event) => {
      try {
        const signal: Signal = JSON.parse(event.data)
        setSignals((prev) => [signal, ...prev].slice(0, 20))
      } catch {
        // ignore malformed
      }
    }
    return () => es.close()
  }, [])

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 h-96 overflow-hidden flex flex-col">
      <h2 className="text-sm font-semibold text-slate-300 mb-3">Live Signal Stream</h2>
      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {signals.length === 0 && (
          <p className="text-slate-500 text-sm">Waiting for signals...</p>
        )}
        {signals.map((s) => (
          <div
            key={s.signal_id}
            className="flex items-center justify-between bg-slate-850 border border-slate-800 rounded p-2 text-sm"
          >
            <div>
              <span className="font-bold text-emerald-400">{s.ticker}</span>
              <span className="ml-2 text-slate-400">{s.signal_type}</span>
            </div>
            <div className="text-right">
              <div className={`font-mono ${s.direction === 'long' ? 'text-green-400' : 'text-red-400'}`}>
                {s.direction.toUpperCase()} {s.score.toFixed(2)}
              </div>
              <div className="text-xs text-slate-500">ML {(s.ml_score * 100).toFixed(0)}%</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
