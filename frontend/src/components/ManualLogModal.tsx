import { useEffect, useRef, useState } from 'react'
import StarRating from './StarRating'
import { createManualWatchLog } from '../api/watchLogs'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface FilmSuggestion {
  id: string
  title: string
  year: number | null
}

interface ManualLogModalProps {
  onClose: () => void
  onLogged?: () => void
}

function ManualLogModal({ onClose, onLogged }: ManualLogModalProps) {
  const today = new Date().toISOString().split('T')[0]

  const [filmInput, setFilmInput] = useState('')
  const [suggestions, setSuggestions] = useState<FilmSuggestion[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [selectedFilm, setSelectedFilm] = useState<FilmSuggestion | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Selecting a suggestion updates filmInput too, which would otherwise
  // re-trigger the search effect below and immediately clear the selection.
  const justSelectedRef = useRef(false)

  const [watchedDate, setWatchedDate] = useState(today)
  const [rating, setRating] = useState<number | null>(null)
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (justSelectedRef.current) {
      justSelectedRef.current = false
      return
    }
    setSelectedFilm(null)
    if (filmInput.length < 2) {
      setSuggestions([])
      setShowSuggestions(false)
      return
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const params = new URLSearchParams({ q: filmInput })
        const res = await fetch(`${API_URL}/api/films/search?${params}`)
        const data = await res.json()
        setSuggestions(data)
        setShowSuggestions(data.length > 0)
      } catch {
        setSuggestions([])
      }
    }, 250)
  }, [filmInput])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedFilm) return
    setError(null)
    setSubmitting(true)
    try {
      await createManualWatchLog({
        film_id: selectedFilm.id,
        watched_date: watchedDate,
        rating,
        comment: comment.trim() || null,
      })
      setSuccess(true)
      onLogged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to log this viewing')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50" />

      <div
        className="relative bg-white rounded-xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between p-5 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">Log a film</h2>
          <button onClick={onClose} className="ml-4 text-gray-400 hover:text-gray-600 transition-colors" aria-label="Close">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {success ? (
          <div className="p-5">
            <p className="text-sm text-green-700">Logged as watched.</p>
          </div>
        ) : (
          <form id="manual-log-form" onSubmit={handleSubmit} className="overflow-y-auto p-5 space-y-4">
            <div className="relative">
              <label htmlFor="manualFilmInput" className="block text-sm font-medium text-gray-700">
                Film
              </label>
              <input
                type="text"
                id="manualFilmInput"
                value={filmInput}
                onChange={(e) => setFilmInput(e.target.value)}
                onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
                placeholder="Type a film title…"
                autoComplete="off"
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {showSuggestions && (
                <ul className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-md shadow-lg max-h-60 overflow-auto text-sm">
                  {suggestions.map((s) => (
                    <li
                      key={s.id}
                      className="px-3 py-2 cursor-pointer hover:bg-blue-50"
                      onMouseDown={() => {
                        justSelectedRef.current = true
                        setFilmInput(s.title)
                        setSelectedFilm(s)
                        setShowSuggestions(false)
                      }}
                    >
                      {s.title}
                      {s.year && <span className="ml-1 text-gray-400">({s.year})</span>}
                    </li>
                  ))}
                </ul>
              )}
              {!selectedFilm && filmInput.length >= 2 && (
                <p className="mt-1 text-xs text-gray-400">Select a film from the list.</p>
              )}
            </div>

            <div>
              <label htmlFor="watchedDate" className="block text-sm font-medium text-gray-700">
                Date watched
              </label>
              <input
                type="date"
                id="watchedDate"
                value={watchedDate}
                onChange={(e) => setWatchedDate(e.target.value)}
                max={today}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Rating</label>
              <StarRating value={rating} onChange={setRating} />
            </div>

            <div>
              <label htmlFor="manualComment" className="block text-sm font-medium text-gray-700">
                Comment
              </label>
              <textarea
                id="manualComment"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={4}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-md p-3">
                <p className="text-sm text-red-800">{error}</p>
              </div>
            )}
          </form>
        )}

        {!success && (
          <div className="border-t border-gray-200 px-5 py-3 flex justify-end">
            <button
              type="submit"
              form="manual-log-form"
              disabled={submitting || !selectedFilm}
              className="px-6 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? 'Saving…' : 'Log as watched'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default ManualLogModal
