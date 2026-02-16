import { useState } from 'react'
import SearchForm from './components/SearchForm'
import FilmList from './components/FilmList'
import type { ShowingsResponse } from './types'

function App() {
  const [showings, setShowings] = useState<ShowingsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = async (searchParams: {
    date: string
    timeFrom: string
    timeTo: string
  }) => {
    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams({
        date: searchParams.date,
        time_from: searchParams.timeFrom,
        time_to: searchParams.timeTo,
      })

      const response = await fetch(
        `http://localhost:8000/api/showings?${params.toString()}`
      )

      if (!response.ok) {
        throw new Error('Failed to fetch showings')
      }

      const data = await response.json()
      setShowings(data)
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
              Found {showings.total_films} films with {showings.total_showings} showings
            </div>
            <FilmList films={showings.films} />
          </div>
        )}

        {!loading && !showings && !error && (
          <div className="mt-8 text-center text-gray-600">
            <p>Enter a date and time to search for films</p>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
