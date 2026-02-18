import { useState } from 'react'
import SearchForm from './components/SearchForm'
import type { SearchParams } from './components/SearchForm'
import FilmList from './components/FilmList'
import CinemaSchedule from './components/CinemaSchedule'
import CinemaModal from './components/CinemaModal'
import DirectorModal from './components/DirectorModal'
import type { Cinema, FilmWithCinemas, ShowingTime, FilmWithShowingCount, ShowingsResponse } from './types'

// ── helpers ──────────────────────────────────────────────────────────────────

function addDays(dateStr: string, n: number): string {
  const d = new Date(`${dateStr}T00:00:00`)
  d.setDate(d.getDate() + n)
  return d.toISOString().split('T')[0]
}

async function fetchAllDay(date: string): Promise<FilmWithCinemas[]> {
  const p = new URLSearchParams({ date, time_from: '00:00', time_to: '23:59' })
  const res = await fetch(`http://localhost:8000/api/showings?${p}`)
  if (!res.ok) throw new Error('Failed to fetch showings')
  const data: ShowingsResponse = await res.json()
  return data.films
}

function mergeFilmsFromDays(dayFilms: FilmWithCinemas[][]): FilmWithCinemas[] {
  const filmMap = new Map<string, {
    film: FilmWithShowingCount
    cinemaMap: Map<string, { cinema: Cinema; times: ShowingTime[] }>
  }>()

  for (const dayList of dayFilms) {
    for (const { film, cinemas } of dayList) {
      if (!filmMap.has(film.id)) {
        filmMap.set(film.id, { film: { ...film }, cinemaMap: new Map() })
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

  return Array.from(filmMap.values()).map(({ film, cinemaMap }) => {
    const cinemas = Array.from(cinemaMap.values())
    return { film: { ...film, showing_count: cinemas.reduce((s, c) => s + c.times.length, 0) }, cinemas }
  })
}

async function fetchForPeriod(date: string, period: 'today' | 'week'): Promise<FilmWithCinemas[]> {
  if (period === 'today') return fetchAllDay(date)
  const dates = Array.from({ length: 7 }, (_, i) => addDays(date, i))
  const results = await Promise.all(dates.map(fetchAllDay))
  return mergeFilmsFromDays(results)
}

function applyFormatFilter(films: FilmWithCinemas[], format: string | null): FilmWithCinemas[] {
  if (!format) return films
  return films
    .map(f => ({
      ...f,
      cinemas: f.cinemas
        .map(c => ({ ...c, times: c.times.filter(t => t.format_tags === format) }))
        .filter(c => c.times.length > 0),
    }))
    .filter(f => f.cinemas.length > 0)
}

function applyFilter(films: FilmWithCinemas[], params: SearchParams): FilmWithCinemas[] {
  if (params.mode === 'film' && params.filmTitle) {
    const q = params.filmTitle.toLowerCase()
    return films.filter(f => f.film.title.toLowerCase().includes(q))
  }
  if (params.mode === 'cinema' && params.cinemaId) {
    return films
      .map(f => ({ ...f, cinemas: f.cinemas.filter(c => c.cinema.id === params.cinemaId) }))
      .filter(f => f.cinemas.length > 0)
  }
  if (params.mode === 'format') {
    return applyFormatFilter(films, params.format)
  }
  return films
}

// ── component ─────────────────────────────────────────────────────────────────

function App() {
  const [showings, setShowings]       = useState<ShowingsResponse | null>(null)
  const [filteredFilms, setFilteredFilms] = useState<FilmWithCinemas[]>([])
  const [activeMode, setActiveMode]   = useState<SearchParams['mode']>('time')

  // Format-mode live filtering state
  const [rawFormatFilms, setRawFormatFilms] = useState<FilmWithCinemas[]>([])
  const [formatDate, setFormatDate]         = useState<string>('')
  const [formatPeriod, setFormatPeriod]     = useState<'today' | 'week'>('today')

  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)
  const [selectedCinema, setSelectedCinema] = useState<Cinema | null>(null)
  const [selectedDirector, setSelectedDirector] = useState<{ name: string; filmId: string } | null>(null)

  const handleSearch = async (params: SearchParams) => {
    setLoading(true)
    setError(null)

    try {
      const timeFrom = params.mode === 'time' ? params.timeFrom : '00:00'
      const timeTo   = params.mode === 'time' ? params.timeTo   : '23:59'

      const apiParams = new URLSearchParams({ date: params.date, time_from: timeFrom, time_to: timeTo })
      const response = await fetch(`http://localhost:8000/api/showings?${apiParams}`)
      if (!response.ok) throw new Error('Failed to fetch showings')

      const data: ShowingsResponse = await response.json()
      setShowings(data)

      if (params.mode === 'format') {
        setRawFormatFilms(data.films)
        setFormatDate(params.date)
        setFormatPeriod('today')
      }

      setFilteredFilms(applyFilter(data.films, params))
      setActiveMode(params.mode)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleLiveFormatChange = async (format: string | null, period: 'today' | 'week') => {
    if (!formatDate) return  // no initial search done yet

    let films = rawFormatFilms
    if (period !== formatPeriod) {
      setLoading(true)
      setFormatPeriod(period)
      try {
        films = await fetchForPeriod(formatDate, period)
        setRawFormatFilms(films)
      } catch {
        setLoading(false)
        return
      }
      setLoading(false)
    }

    setFilteredFilms(applyFormatFilter(films, format))
    setActiveMode('format')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">CineScout</h1>
            <p className="mt-1 text-sm text-gray-600">
              Find films showing in London cinemas
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <SearchForm
          onSearch={handleSearch}
          onLiveFormatChange={handleLiveFormatChange}
          loading={loading}
        />

        {error && (
          <div className="mt-4 bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {loading && (
          <div className="mt-8 text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
            <p className="mt-2 text-sm text-gray-600">Searching for films...</p>
          </div>
        )}

        {!loading && showings && (
          <div className="mt-8">
            <div className="mb-4 text-sm text-gray-600">
              Found {filteredFilms.length} film{filteredFilms.length !== 1 ? 's' : ''}
            </div>
            {activeMode === 'cinema' ? (
              <CinemaSchedule
                films={filteredFilms}
                onDirectorClick={(name, filmId) => setSelectedDirector({ name, filmId })}
              />
            ) : (
              <FilmList
                films={filteredFilms}
                onCinemaClick={setSelectedCinema}
                onDirectorClick={(name, filmId) => setSelectedDirector({ name, filmId })}
              />
            )}
          </div>
        )}

        {!loading && !showings && !error && (
          <div className="mt-8 text-center text-gray-600">
            <p>Enter a date and time to search for films</p>
          </div>
        )}
      </main>

      {selectedDirector && showings && (
        <DirectorModal
          director={selectedDirector.name}
          city={showings.query.city}
          excludeFilmId={selectedDirector.filmId}
          onClose={() => setSelectedDirector(null)}
        />
      )}
      {selectedCinema && showings && (
        <CinemaModal
          cinema={selectedCinema}
          date={showings.query.date}
          allFilms={showings.films}
          onClose={() => setSelectedCinema(null)}
        />
      )}
    </div>
  )
}

export default App
