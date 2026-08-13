import { useState } from 'react'

interface Props {
  onSelect: (ticker: string) => void
}

export default function StockSearch({ onSelect }: Props) {
  const [query, setQuery] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const clean = query.trim().toUpperCase()
    if (clean) {
      onSelect(clean)
    }
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <label htmlFor="stock-search" className="block text-sm font-medium text-slate-300 mb-2">
        Search any stock ticker
      </label>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          id="stock-search"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value.toUpperCase())}
          placeholder="e.g. AAPL, TSLA, NVDA"
          className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-emerald-500 uppercase"
          maxLength={8}
        />
        <button
          type="submit"
          className="bg-emerald-600 hover:bg-emerald-500 text-white font-medium px-6 py-3 rounded-lg text-sm transition-colors"
        >
          Search
        </button>
      </form>
      <p className="text-xs text-slate-500 mt-2">
        We combine Wall Street analyst ratings, price trends, and momentum to give you a clear recommendation.
      </p>
    </div>
  )
}
