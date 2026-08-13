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
    <form onSubmit={handleSubmit} className="flex gap-2 max-w-xl">
      <input
        id="stock-search"
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value.toUpperCase())}
        placeholder="e.g. AAPL, TSLA, NVDA, SPY"
        className="flex-1 bg-slate-950/70 border border-slate-700 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-emerald-500 uppercase"
        maxLength={8}
      />
      <button
        type="submit"
        className="bg-emerald-600 hover:bg-emerald-500 text-white font-medium px-6 py-3 rounded-lg text-sm transition-colors"
      >
        Search
      </button>
    </form>
  )
}
