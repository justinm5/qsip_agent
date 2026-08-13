import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'qsip_watchlist'

export function useWatchlist() {
  const [tickers, setTickers] = useState<string[]>([])

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw)
        if (Array.isArray(parsed)) {
          setTickers(parsed.map((t) => String(t).toUpperCase()))
        }
      }
    } catch {
      // ignore
    }
  }, [])

  const persist = useCallback((next: string[]) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    setTickers(next)
  }, [])

  const add = useCallback(
    (ticker: string) => {
      const t = ticker.toUpperCase()
      if (!tickers.includes(t)) {
        persist([...tickers, t])
      }
    },
    [tickers, persist]
  )

  const remove = useCallback(
    (ticker: string) => {
      persist(tickers.filter((t) => t !== ticker.toUpperCase()))
    },
    [tickers, persist]
  )

  return { tickers, add, remove, isSaved: (ticker: string) => tickers.includes(ticker.toUpperCase()) }
}
