import { useState } from 'react'
import StockCard from './StockCard'
import StockSearch from './StockSearch'
import TrendingList from './TrendingList'
import Watchlist from './Watchlist'

export default function Dashboard() {
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null)

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 lg:p-6">
      <div className="max-w-6xl mx-auto">
        <header className="mb-8 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-emerald-400 tracking-tight">QSIP</h1>
            <p className="text-slate-400 text-sm">Research-backed stock picks from many sources, explained simply.</p>
          </div>
        </header>

        <section className="mb-8">
          <StockSearch onSelect={setSelectedTicker} />
        </section>

        <Watchlist onSelect={setSelectedTicker} />

        {selectedTicker && (
          <section className="mb-8">
            <h2 className="text-lg font-semibold text-slate-200 mb-3">Your search</h2>
            <StockCard ticker={selectedTicker} />
          </section>
        )}

        <section className="mb-8">
          <TrendingList onSelect={setSelectedTicker} />
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h2 className="text-lg font-semibold text-slate-200 mb-2">How this works</h2>
          <p className="text-slate-400 text-sm leading-relaxed">
            QSIP reads Wall Street analyst ratings, price momentum, news sentiment, insider activity,
            earnings guidance, options flow, and an internal machine-learning signal. We combine these
            into one clear recommendation and a research score, so you can make safer, more informed
            commitments to stocks and indexes without needing a finance background.
          </p>
        </section>
      </div>
    </div>
  )
}
