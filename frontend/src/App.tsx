import { useState } from 'react'
import SearchForm from './components/SearchForm'
import type { SearchParams } from './components/SearchForm'
import FilmList from './components/FilmList'
import CinemaSchedule from './components/CinemaSchedule'
import CinemaModal from './components/CinemaModal'
import DirectorModal from './components/DirectorModal'
import type { Cinema, FilmWithCinemas, ShowingsResponse } from './types'

function applyFilter(films: FilmWithCinemas[], params: SearchParams): FilmWithCinemas[] {
  if (params.mode === 'film' && params.filmTitle) {
    const q = params.filmTitle.toLowerCase()
    return films.filter(f => f.film.title.toLowerCase().includes(q))
  }

  if (params.mode === 'cinema' && params.cinemaId) {
    return films
      .map(f => ({
        ...f,
        cinemas: f.cinemas.filter(c => c.cinema.id === params.cinemaId),
      }))
      .filter(f => f.cinemas.length > 0)
  }

  if (params.mode === 'format') {
    return films
      .map(f => ({
        ...f,
        cinemas: f.cinemas
          .map(c => ({
            ...c,
            times: c.times.filter(t => !params.format || t.format_tags === params.format),
          }))
          .filter(c => c.times.length > 0),
      }))
      .filter(f => f.cinemas.length > 0)
  }

  return films
}

function App() {
  const [showings, setShowings] = useState<ShowingsResponse | null>(null)
  const [filteredFilms, setFilteredFilms] = useState<FilmWithCinemas[]>([])
  const [activeMode, setActiveMode] = useState<SearchParams['mode']>('time')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedCinema, setSelectedCinema] = useState<Cinema | null>(null)
  const [selectedDirector, setSelectedDirector] = useState<{ name: string; filmId: string } | null>(null)

  const handleSearch = async (params: SearchParams) => {
    setLoading(true)
    setError(null)

    try {
      const timeFrom = params.mode === 'time' ? params.timeFrom : '00:00'
      const timeTo   = params.mode === 'time' ? params.timeTo   : '23:59'

      const apiParams = new URLSearchParams({
        date: params.date,
        time_from: timeFrom,
        time_to: timeTo,
      })

      const response = await fetch(`http://localhost:8000/api/showings?${apiParams}`)
      if (!response.ok) throw new Error('Failed to fetch showings')

      const data: ShowingsResponse = await response.json()
      setShowings(data)
      setFilteredFilms(applyFilter(data.films, params))
      setActiveMode(params.mode)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
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
        <SearchForm onSearch={handleSearch} loading={loading} />

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
