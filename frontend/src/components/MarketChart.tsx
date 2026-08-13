import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { ComposedChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip, Bar } from 'recharts'
import { fetchMarketData } from '../api/client'

interface Props {
  ticker: string
}

export default function MarketChart({ ticker }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ['market', ticker],
    queryFn: () => fetchMarketData(ticker),
    enabled: !!ticker,
  })

  const chartData = useMemo(() => {
    if (!data) return []
    return data.map((d) => ({
      date: new Date(d.time).toLocaleDateString(),
      close: d.close,
      volume: d.volume / 1e6,
    }))
  }, [data])

  if (isLoading) return <ChartSkeleton title={`Market Data: ${ticker}`} />

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 h-96">
      <h2 className="text-sm font-semibold text-slate-300 mb-3">Market Data: {ticker}</h2>
      <ResponsiveContainer width="100%" height="85%">
        <ComposedChart data={chartData}>
          <XAxis dataKey="date" tick={{ fontSize: 10 }} minTickGap={30} />
          <YAxis yAxisId="price" tick={{ fontSize: 10 }} domain={['auto', 'auto']} />
          <YAxis yAxisId="vol" orientation="right" tick={{ fontSize: 10 }} />
          <Tooltip
            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }}
            itemStyle={{ color: '#e2e8f0' }}
          />
          <Bar yAxisId="vol" dataKey="volume" fill="#334155" opacity={0.5} />
          <Line yAxisId="price" type="monotone" dataKey="close" stroke="#10b981" strokeWidth={2} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

function ChartSkeleton({ title }: { title: string }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 h-96 animate-pulse">
      <h2 className="text-sm font-semibold text-slate-300 mb-3">{title}</h2>
      <div className="h-[85%] bg-slate-850 rounded" />
    </div>
  )
}
