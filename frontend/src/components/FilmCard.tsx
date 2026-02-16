import { useState } from 'react'
import type { FilmWithCinemas } from '../types'

interface FilmCardProps {
  filmWithCinemas: FilmWithCinemas
}

function FilmCard({ filmWithCinemas }: FilmCardProps) {
  const [expanded, setExpanded] = useState(false)
  const { film, cinemas } = filmWithCinemas

  const formatTime = (isoString: string) => {
    const date = new Date(isoString)
    return date.toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Europe/London',
    })
  }

  const formatPrice = (price: number | null) => {
    if (price === null) return null
    return `£${price.toFixed(2)}`
  }

  return (
    <div className="bg-white shadow-sm rounded-lg overflow-hidden border border-gray-200">
      {/* Film Header - Always Visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left py-3 px-6 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center">
          <h2 className="w-1/2 text-xl font-semibold text-gray-900 pr-4">
            {film.title}
            {film.year && (
              <span className="text-gray-500 font-normal ml-2">({film.year})</span>
            )}
          </h2>

          <span className="flex-1 text-sm text-gray-500">
            {film.showing_count} showing{film.showing_count !== 1 ? 's' : ''} at{' '}
            {cinemas.length} cinema{cinemas.length !== 1 ? 's' : ''}
          </span>

          <svg
            className={`h-6 w-6 text-gray-400 ml-4 flex-shrink-0 transition-transform ${
              expanded ? 'rotate-180' : ''
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>

        {(film.directors?.length || film.countries?.length || film.runtime) && (
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-600">
            {film.directors && film.directors.length > 0 && (
              <span>Dir: {film.directors.join(', ')}</span>
            )}
            {film.countries && film.countries.length > 0 && (
              <span>{film.countries.join(', ')}</span>
            )}
            {film.runtime && <span>{film.runtime} min</span>}
          </div>
        )}
      </button>

      {/* Expanded Content - Cinemas and Showtimes */}
      {expanded && (
        <div className="border-t border-gray-200 bg-gray-50 p-6">
          {film.overview && (
            <p className="text-sm text-gray-700 mb-6">{film.overview}</p>
          )}

          <div className="space-y-3">
            {cinemas.map((cinemaWithShowings) => (
              <div
                key={cinemaWithShowings.cinema.id}
                className="grid items-center gap-x-4"
                style={{ gridTemplateColumns: '40% 1fr auto' }}
              >
                {/* Cinema name — indented 5cm from the left */}
                <div className="pl-[3cm]">
                  <span className="font-medium text-gray-900">
                    {cinemaWithShowings.cinema.name}
                  </span>
                </div>

                {/* Showing times — start at the 40% mark */}
                <div className="flex flex-wrap gap-2">
                  {cinemaWithShowings.times.map((showing) => (
                    <div
                      key={showing.id}
                      className="bg-white border border-gray-200 rounded-md px-3 py-2"
                    >
                      {showing.booking_url ? (
                        <a
                          href={showing.booking_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 font-medium"
                        >
                          {formatTime(showing.start_time)}
                        </a>
                      ) : (
                        <span className="font-medium text-gray-900">
                          {formatTime(showing.start_time)}
                        </span>
                      )}

                      {showing.screen_name && (
                        <span className="ml-2 text-xs text-gray-500">
                          {showing.screen_name}
                        </span>
                      )}

                      {showing.format_tags && (
                        <span className="ml-2 text-xs text-gray-500">
                          [{showing.format_tags}]
                        </span>
                      )}

                      {showing.price !== null && (
                        <span className="ml-2 text-xs text-gray-500">
                          {formatPrice(showing.price)}
                        </span>
                      )}
                    </div>
                  ))}
                </div>

                {/* Address — far right */}
                <div className="text-sm text-gray-500 text-right whitespace-nowrap">
                  {cinemaWithShowings.cinema.address}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default FilmCard
