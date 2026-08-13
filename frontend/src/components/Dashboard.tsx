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
        <header className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
              <span className="text-emerald-400 font-bold text-lg">Q</span>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-emerald-400 tracking-tight">QSIP</h1>
              <p className="text-slate-400 text-xs">Research-backed stock picks for everyday investors</p>
            </div>
          </div>
        </header>

        <section className="mb-8">
          <div className="bg-gradient-to-r from-emerald-900/30 to-slate-900 border border-emerald-800/40 rounded-2xl p-6 mb-6">
            <h2 className="text-xl font-semibold text-slate-100 mb-2">Find a safer stock commitment</h2>
            <p className="text-slate-400 text-sm max-w-2xl mb-4">
              Search any ticker to see a simple recommendation built from analysts, momentum, news, insiders, earnings, options, ML, and cross-checked against quant research.
            </p>
            <StockSearch onSelect={setSelectedTicker} />
          </div>
        </section>

        <Watchlist onSelect={setSelectedTicker} />

        {selectedTicker && (
          <section className="mb-8">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              <h2 className="text-lg font-semibold text-slate-200">Search result</h2>
            </div>
            <StockCard ticker={selectedTicker} />
          </section>
        )}

        <section className="mb-8">
          <TrendingList onSelect={setSelectedTicker} />
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-2xl p-6 mb-8">
          <h2 className="text-lg font-semibold text-slate-200 mb-4">How this works</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
              <div className="text-emerald-400 font-bold mb-2">1</div>
              <h3 className="text-sm font-medium text-slate-200 mb-1">Many sources</h3>
              <p className="text-slate-500 text-xs">We read analysts, momentum, news, insiders, earnings, options, and ML signals.</p>
            </div>
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
              <div className="text-emerald-400 font-bold mb-2">2</div>
              <h3 className="text-sm font-medium text-slate-200 mb-1">Cross-check</h3>
              <p className="text-slate-500 text-xs">Optionally blend in external quant research like QuantSignals for a second opinion.</p>
            </div>
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
              <div className="text-emerald-400 font-bold mb-2">3</div>
              <h3 className="text-sm font-medium text-slate-200 mb-1">Clear score</h3>
              <p className="text-slate-500 text-xs">Each stock gets a 0-100 research score, a recommendation label, and a conviction level.</p>
            </div>
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
              <div className="text-emerald-400 font-bold mb-2">4</div>
              <h3 className="text-sm font-medium text-slate-200 mb-1">Save & track</h3>
              <p className="text-slate-500 text-xs">Save picks to your local watchlist and revisit them whenever you return.</p>
            </div>
          </div>
        </section>

        <footer className="text-center text-slate-600 text-xs py-6">
          QSIP is for research, not financial advice. Always do your own due diligence before investing.
        </footer>
      </div>
    </div>
  )
}
