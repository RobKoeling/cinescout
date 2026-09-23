import { useEffect, useState } from 'react'
import { listWatchlist } from '../api/watchlist'
import type { WatchlistItem } from '../types'

interface WatchlistPanelProps {
  reloadToken: number
}

function WatchlistPanel({ reloadToken }: WatchlistPanelProps) {
  const [visible, setVisible] = useState(false)
  const [items, setItems] = useState<WatchlistItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!visible) return
    setLoading(true)
    setError(null)
    listWatchlist()
      .then(setItems)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load your watchlist'))
      .finally(() => setLoading(false))
  }, [visible, reloadToken])

  return (
    <div className="mb-6">
      <button
        onClick={() => setVisible((v) => !v)}
        className="text-sm font-medium text-blue-600 hover:text-blue-800 transition-colors"
      >
        {visible ? 'Hide my watchlist' : 'Show my watchlist'}
      </button>

      {visible && (
        <div className="mt-3">
          {loading && <p className="text-sm text-gray-600">Loading…</p>}
          {error && <p className="text-sm text-red-800">{error}</p>}

          {!loading && !error && items.length === 0 && (
            <p className="text-sm text-gray-600">
              Your watchlist is empty — import it from the Letterboxd panel above.
            </p>
          )}

          {!loading && items.length > 0 && (
            <ul className="bg-white shadow-sm rounded-lg border border-gray-200 divide-y divide-gray-100">
              {items.map((item) => (
                <li key={item.id} className="px-4 py-2.5">
                  <span className="text-gray-900">{item.film.title}</span>
                  {item.film.year && (
                    <span className="text-gray-500 ml-1.5">({item.film.year})</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

export default WatchlistPanel
