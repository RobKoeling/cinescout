import { useEffect, useState } from 'react'
import type { Cinema, FilmWithCinemas } from '../types'

interface CinemaModalProps {
  cinema: Cinema
  date: string
  city: string
  allFilms: FilmWithCinemas[]
  onClose: () => void
}

function CinemaModal({ cinema, date, city, allFilms, onClose }: CinemaModalProps) {
  const [showFullDay, setShowFullDay] = useState(false)
  const [fullDayFilms, setFullDayFilms] = useState<FilmWithCinemas[] | null>(null)
  const [fullDayLoading, setFullDayLoading] = useState(false)

  // Close on Escape key
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const formatTime = (isoString: string) =>
    new Date(isoString).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Europe/London',
    })

  const formatPrice = (price: number | null) => {
    if (price === null) return null
    return `£${price.toFixed(2)}`
  }

  const extractCinemaFilms = (films: FilmWithCinemas[]) =>
    films
      .flatMap(({ film, cinemas }) => {
        const match = cinemas.find((c) => c.cinema.id === cinema.id)
        return match ? [{ film, times: match.times }] : []
      })
      .sort((a, b) => a.times[0].start_time.localeCompare(b.times[0].start_time))

  const handleShowFullDay = async () => {
    if (fullDayFilms) {
      setShowFullDay(true)
      return
    }
    setFullDayLoading(true)
    try {
      const params = new URLSearchParams({ date, city, time_from: '00:00', time_to: '23:59' })
      const res = await fetch(`http://localhost:8000/api/showings?${params}`)
      if (!res.ok) throw new Error('Failed to fetch')
      const data = await res.json()
      setFullDayFilms(data.films)
      setShowFullDay(true)
    } finally {
      setFullDayLoading(false)
    }
  }

  const displayedFilms = showFullDay && fullDayFilms
    ? extractCinemaFilms(fullDayFilms)
    : extractCinemaFilms(allFilms)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" />

      {/* Modal */}
      <div
        className="relative bg-white rounded-xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-gray-200">
          <div>
            <h2 className="text-xl font-bold text-gray-900">{cinema.name}</h2>
            {cinema.address && (
              <p className="text-sm text-gray-500 mt-0.5">{cinema.address}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="ml-4 text-gray-400 hover:text-gray-600 transition-colors"
            aria-label="Close"
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Film list */}
        <div className="overflow-y-auto p-5 space-y-4">
          {displayedFilms.length === 0 ? (
            <p className="text-gray-500 text-sm">No films found.</p>
          ) : (
            displayedFilms.map(({ film, times }) => (
              <div key={film.id} className="flex items-start gap-4">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 truncate">
                    {film.title}
                    {film.year && (
                      <span className="text-gray-500 font-normal ml-1.5">({film.year})</span>
                    )}
                  </p>
                  {film.directors && film.directors.length > 0 && (
                    <p className="text-xs text-gray-500 mt-0.5">
                      Dir: {film.directors.join(', ')}
                    </p>
                  )}
                </div>
                <div className="flex flex-wrap gap-1.5 justify-end flex-shrink-0">
                  {times.map((showing) => {
                    const price = showing.estimated_price ?? showing.price
                    const timeText = formatTime(showing.start_time)
                    const priceText = formatPrice(price)
                    const displayText = priceText ? `${timeText} • ${priceText}` : timeText

                    return showing.booking_url ? (
                      <a
                        key={showing.id}
                        href={showing.booking_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="bg-blue-50 border border-blue-200 text-blue-700 hover:bg-blue-100 rounded px-2 py-1 text-sm font-medium transition-colors"
                      >
                        {displayText}
                      </a>
                    ) : (
                      <span
                        key={showing.id}
                        className="bg-gray-100 border border-gray-200 text-gray-700 rounded px-2 py-1 text-sm font-medium"
                      >
                        {displayText}
                      </span>
                    )
                  })}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        {!showFullDay && (
          <div className="border-t border-gray-200 px-5 py-3 flex justify-end">
            <button
              onClick={handleShowFullDay}
              disabled={fullDayLoading}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium disabled:opacity-50 transition-colors"
            >
              {fullDayLoading ? 'Loading…' : 'Show all films today'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default CinemaModal
