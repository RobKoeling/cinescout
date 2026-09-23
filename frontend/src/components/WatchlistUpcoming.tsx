import { useEffect, useState } from 'react'
import { listUpcomingWatchlistShowings } from '../api/watchlist'
import type { UpcomingWatchlistShowing } from '../types'

interface WatchlistUpcomingProps {
  reloadToken: number
}

function WatchlistUpcoming({ reloadToken }: WatchlistUpcomingProps) {
  const [showings, setShowings] = useState<UpcomingWatchlistShowing[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    listUpcomingWatchlistShowings()
      .then(setShowings)
      .catch(() => setShowings([]))
      .finally(() => setLoading(false))
  }, [reloadToken])

  const formatDateTime = (isoDateTime: string) =>
    new Date(isoDateTime).toLocaleString('en-GB', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      hour: 'numeric',
      minute: '2-digit',
    })

  if (loading || showings.length === 0) {
    return null
  }

  return (
    <div className="bg-amber-50 shadow-sm rounded-lg border border-amber-200 p-4 mb-6">
      <h3 className="font-medium text-gray-900 mb-3">🎬 On your watchlist, coming up</h3>
      <ul className="space-y-3">
        {showings.map((showing) => (
          <li key={showing.id} className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="font-medium text-gray-900">
                {showing.film.title}
                {showing.film.year && (
                  <span className="text-gray-500 font-normal ml-1.5">({showing.film.year})</span>
                )}
              </p>
              <p className="text-sm text-gray-600 mt-0.5">
                {formatDateTime(showing.start_time)} — {showing.cinema.name}
              </p>
            </div>
            {showing.booking_url && (
              <a
                href={showing.booking_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-blue-600 hover:text-blue-800 transition-colors flex-shrink-0"
              >
                Book
              </a>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default WatchlistUpcoming
