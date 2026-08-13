import { useState } from 'react'
import SimplePortfolio from './SimplePortfolio'
import StockCard from './StockCard'
import StockSearch from './StockSearch'
import TrendingList from './TrendingList'

export default function Dashboard() {
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null)
  const [refreshPortfolio, setRefreshPortfolio] = useState(0)

  const handleBought = () => {
    setRefreshPortfolio((n) => n + 1)
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 lg:p-6">
      <div className="max-w-6xl mx-auto">
        <header className="mb-8 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-emerald-400 tracking-tight">QSIP</h1>
            <p className="text-slate-400 text-sm">Simple, honest stock recommendations and paper trading.</p>
          </div>
        </header>

        <section className="mb-8">
          <StockSearch onSelect={setSelectedTicker} />
        </section>

        {selectedTicker && (
          <section className="mb-8">
            <h2 className="text-lg font-semibold text-slate-200 mb-3">Your search</h2>
            <StockCard ticker={selectedTicker} onBuy={handleBought} />
          </section>
        )}

        <section className="mb-8">
          <TrendingList onSelect={setSelectedTicker} onBuy={handleBought} />
        </section>

        <section>
          <SimplePortfolio key={refreshPortfolio} />
        </section>
      </div>
    </div>
  )
}
