import { useEffect, useState } from 'react'
import type { Cinema, Film, ShowingTime } from '../types'

interface DirectorModalProps {
  director: string
  city: string
  excludeFilmId: string
  onClose: () => void
}

interface FilmShowings {
  film: Film
  cinemas: { cinema: Cinema; times: ShowingTime[] }[]
}

type Mode = 'upcoming' | 'future' | 'past'

const LONDON_TZ = 'Europe/London'

function todayInLondon(): string {
  return new Date().toLocaleDateString('sv', { timeZone: LONDON_TZ })
}

function addDays(isoDate: string, n: number): string {
  const d = new Date(`${isoDate}T00:00:00`)
  d.setDate(d.getDate() + n)
  return d.toLocaleDateString('sv', { timeZone: LONDON_TZ })
}

function formatTime(isoString: string): string {
  return new Date(isoString).toLocaleTimeString('en-GB', {
    hour: '2-digit', minute: '2-digit', timeZone: LONDON_TZ,
  })
}

async function fetchDay(date: string, city: string): Promise<{ films: { film: Film; cinemas: { cinema: Cinema; times: ShowingTime[] }[] }[] }> {
  const params = new URLSearchParams({ date, city, time_from: '00:00', time_to: '23:59' })
  const res = await fetch(`http://localhost:8000/api/showings?${params}`)
  if (!res.ok) throw new Error('Failed to fetch')
  return res.json()
}

function datesForMode(mode: Mode): string[] {
  const today = todayInLondon()
  if (mode === 'upcoming') return Array.from({ length: 7 },  (_, i) => addDays(today, i))
  if (mode === 'future')   return Array.from({ length: 14 }, (_, i) => addDays(today, i))
  // past: last 90 days (yesterday back to 90 days ago)
  return Array.from({ length: 90 }, (_, i) => addDays(today, -(i + 1))).reverse()
}

const MODE_LABEL: Record<Mode, string> = {
  upcoming: 'Next 7 days',
  future:   'All future screenings',
  past:     'Past screenings',
}

export default function DirectorModal({ director, city, excludeFilmId, onClose }: DirectorModalProps) {
  const [films, setFilms] = useState<FilmShowings[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState<Mode>('upcoming')

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setFilms(null)

    const dates = datesForMode(mode)

    Promise.all(dates.map(d => fetchDay(d, city)))
      .then(responses => {
        if (cancelled) return

        // Aggregate: film id → { film, cinema id → { cinema, times[] } }
        const filmMap = new Map<string, { film: Film; cinemaMap: Map<string, { cinema: Cinema; times: ShowingTime[] }> }>()

        for (const response of responses) {
          for (const { film, cinemas } of response.films) {
            if (!film.directors?.includes(director)) continue
            if (film.id === excludeFilmId) continue

            if (!filmMap.has(film.id)) {
              filmMap.set(film.id, { film, cinemaMap: new Map() })
            }
            const entry = filmMap.get(film.id)!

            for (const { cinema, times } of cinemas) {
              if (!entry.cinemaMap.has(cinema.id)) {
                entry.cinemaMap.set(cinema.id, { cinema, times: [] })
              }
              entry.cinemaMap.get(cinema.id)!.times.push(...times)
            }
          }
        }

        // For past mode sort most-recent-first; otherwise chronological
        const timeCmp = mode === 'past'
          ? (a: ShowingTime, b: ShowingTime) => b.start_time.localeCompare(a.start_time)
          : (a: ShowingTime, b: ShowingTime) => a.start_time.localeCompare(b.start_time)

        const result: FilmShowings[] = Array.from(filmMap.values())
          .map(({ film, cinemaMap }) => ({
            film,
            cinemas: Array.from(cinemaMap.values())
              .map(({ cinema, times }) => ({
                cinema,
                times: times.sort(timeCmp),
              }))
              .sort((a, b) => timeCmp(a.times[0], b.times[0])),
          }))
          .sort((a, b) => a.film.title.localeCompare(b.film.title))

        setFilms(result)
        setLoading(false)
      })
      .catch(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [director, city, mode])

  // Group a flat list of times by date label
  const groupByDate = (times: ShowingTime[]): { label: string; times: ShowingTime[] }[] => {
    const map = new Map<string, ShowingTime[]>()
    for (const t of times) {
      const label = new Date(t.start_time).toLocaleDateString('en-GB', {
        weekday: 'short', day: 'numeric', month: 'short', timeZone: LONDON_TZ,
      })
      if (!map.has(label)) map.set(label, [])
      map.get(label)!.push(t)
    }
    return Array.from(map.entries()).map(([label, times]) => ({ label, times }))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50" />
      <div
        className="relative bg-white rounded-xl shadow-2xl w-full max-w-xl max-h-[80vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-gray-200">
          <div>
            <h2 className="text-xl font-bold text-gray-900">{director}</h2>
            <div className="flex gap-2 mt-2">
              {(['upcoming', 'future', 'past'] as Mode[]).map(m => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                    mode === m
                      ? 'bg-gray-900 text-white border-gray-900'
                      : 'text-gray-500 border-gray-300 hover:border-gray-500 hover:text-gray-700'
                  }`}
                >
                  {MODE_LABEL[m]}
                </button>
              ))}
            </div>
          </div>
          <button onClick={onClose} className="ml-4 text-gray-400 hover:text-gray-600 transition-colors" aria-label="Close">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto p-5">
          {loading && <p className="text-sm text-gray-500">Loading…</p>}

          {!loading && films?.length === 0 && (
            <p className="text-sm text-gray-500">
              No {mode === 'past' ? 'past' : 'upcoming'} screenings found for {director}.
            </p>
          )}

          {!loading && films && films.length > 0 && (
            <div className="space-y-6">
              {films.map(({ film, cinemas }) => (
                <div key={film.id}>
                  <p className="font-semibold text-gray-900">
                    {film.title}
                    {film.year && <span className="text-gray-500 font-normal ml-1.5">({film.year})</span>}
                  </p>
                  <div className="mt-2 space-y-2">
                    {cinemas.map(({ cinema, times }) => (
                      <div key={cinema.id}>
                        <p className="text-sm font-medium text-gray-700">{cinema.name}</p>
                        <div className="mt-1 space-y-1">
                          {groupByDate(times).map(({ label, times: dayTimes }) => (
                            <div key={label} className="flex items-start gap-2 text-sm">
                              <span className="text-gray-500 w-28 flex-shrink-0">{label}</span>
                              <div className="flex flex-wrap gap-1.5">
                                {dayTimes.map(showing =>
                                  showing.booking_url ? (
                                    <a key={showing.id} href={showing.booking_url} target="_blank" rel="noopener noreferrer"
                                      className="bg-blue-50 border border-blue-200 text-blue-700 hover:bg-blue-100 rounded px-2 py-0.5 font-medium transition-colors">
                                      {formatTime(showing.start_time)}
                                    </a>
                                  ) : (
                                    <span key={showing.id} className="bg-gray-100 border border-gray-200 text-gray-700 rounded px-2 py-0.5 font-medium">
                                      {formatTime(showing.start_time)}
                                    </span>
                                  )
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
