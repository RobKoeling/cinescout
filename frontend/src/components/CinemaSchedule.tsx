import type { FilmWithCinemas } from '../types'

interface CinemaScheduleProps {
  films: FilmWithCinemas[]
  onDirectorClick: (director: string, filmId: string) => void
}

const LONDON_TZ = 'Europe/London'

function formatTime(isoString: string): string {
  return new Date(isoString).toLocaleTimeString('en-GB', {
    hour: '2-digit', minute: '2-digit', timeZone: LONDON_TZ,
  })
}

export default function CinemaSchedule({ films, onDirectorClick }: CinemaScheduleProps) {
  if (films.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600">No films found for this cinema and date</p>
      </div>
    )
  }

  // Collect all showings across all cinema entries, tagged with their film.
  // In cinema mode each FilmWithCinemas has exactly one cinema entry.
  const rows = films
    .map(({ film, cinemas }) => {
      const times = cinemas.flatMap(c => c.times)
      times.sort((a, b) => a.start_time.localeCompare(b.start_time))
      return { film, times }
    })
    .filter(r => r.times.length > 0)
    .sort((a, b) => a.times[0].start_time.localeCompare(b.times[0].start_time))

  return (
    <div className="bg-white shadow-sm rounded-lg border border-gray-200 divide-y divide-gray-100">
      {rows.map(({ film, times }) => (
        <div key={film.id} className="flex items-baseline gap-4 px-6 py-3">
          {/* Film info */}
          <div className="w-64 flex-shrink-0">
            <span className="font-medium text-gray-900">{film.title}</span>
            {film.year && (
              <span className="ml-1.5 text-gray-400 text-sm">({film.year})</span>
            )}
            {film.directors && film.directors.length > 0 && (
              <div className="text-xs text-gray-500 mt-0.5">
                {film.directors.map((dir, i) => (
                  <span key={dir}>
                    <button
                      onClick={() => onDirectorClick(dir, film.id)}
                      className="hover:text-blue-600 hover:underline transition-colors"
                    >
                      {dir}
                    </button>
                    {i < film.directors!.length - 1 && ', '}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Show times */}
          <div className="flex flex-wrap gap-1.5">
            {times.map(showing => (
              <span key={showing.id} className="inline-flex items-center gap-1">
                {showing.booking_url ? (
                  <a
                    href={showing.booking_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="bg-blue-50 border border-blue-200 text-blue-700 hover:bg-blue-100 rounded px-2 py-0.5 text-sm font-medium transition-colors"
                  >
                    {formatTime(showing.start_time)}
                  </a>
                ) : (
                  <span className="bg-gray-100 border border-gray-200 text-gray-700 rounded px-2 py-0.5 text-sm font-medium">
                    {formatTime(showing.start_time)}
                  </span>
                )}
                {showing.format_tags && (
                  <span className="text-xs text-gray-400">[{showing.format_tags}]</span>
                )}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
