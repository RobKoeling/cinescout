import { useState, FormEvent, useEffect, useRef } from 'react'
import type { Cinema } from '../types'

export type SearchMode = 'time' | 'film' | 'cinema' | 'format'

export interface SearchParams {
  date: string
  mode: SearchMode
  timeFrom: string
  timeTo: string
  filmTitle: string | null
  cinemaId: string | null
  format: string | null
}

interface SearchFormProps {
  city: string
  onSearch: (params: SearchParams) => void
  onLiveFormatChange?: (format: string | null, period: 'today' | 'week') => void
  loading: boolean
}

const MODE_LABELS: { mode: SearchMode; label: string }[] = [
  { mode: 'time',   label: 'Time' },
  { mode: 'film',   label: 'Film' },
  { mode: 'cinema', label: 'Cinema' },
  { mode: 'format', label: 'Format' },
]

const FORMAT_OPTIONS = ['16mm', '35mm', '70mm']

function SearchForm({ city, onSearch, onLiveFormatChange, loading }: SearchFormProps) {
  const today = new Date().toISOString().split('T')[0]

  const [date, setDate]       = useState(today)
  const [timeFrom, setTimeFrom] = useState('18:00')
  const [timeTo, setTimeTo]   = useState('21:00')
  const [mode, setMode]       = useState<SearchMode>('time')

  // Film autocomplete
  const [filmInput, setFilmInput]         = useState('')
  const [filmSuggestions, setFilmSuggestions] = useState<{ id: string; title: string; year: number | null }[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [selectedFilmTitle, setSelectedFilmTitle] = useState<string | null>(null)
  const filmDebounce = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Cinema
  const [cinemas, setCinemas]     = useState<Cinema[]>([])
  const [cinemaInput, setCinemaInput] = useState('')
  const [selectedCinemaId, setSelectedCinemaId] = useState<string | null>(null)
  const [showCinemaList, setShowCinemaList] = useState(false)

  // Format
  const [format, setFormat] = useState<string>('')
  const [period, setPeriod] = useState<'today' | 'week'>('today')

  // Fetch cinemas when city changes
  useEffect(() => {
    setCinemas([])
    setCinemaInput('')
    setSelectedCinemaId(null)
    fetch(`http://localhost:8000/api/cinemas?city=${city}`)
      .then(r => r.json())
      .then((data: Cinema[]) => setCinemas(data))
      .catch(() => {})
  }, [city])

  // Film autocomplete: fetch suggestions on input change
  useEffect(() => {
    if (filmDebounce.current) clearTimeout(filmDebounce.current)
    setSelectedFilmTitle(null)
    if (filmInput.length < 2) {
      setFilmSuggestions([])
      setShowSuggestions(false)
      return
    }
    filmDebounce.current = setTimeout(async () => {
      try {
        const params = new URLSearchParams({ q: filmInput, city })
        const res = await fetch(`http://localhost:8000/api/films/search?${params}`)
        const data = await res.json()
        setFilmSuggestions(data)
        setShowSuggestions(data.length > 0)
      } catch {
        setFilmSuggestions([])
      }
    }, 250)
  }, [filmInput])

  const filteredCinemas = cinemas.filter(c =>
    c.name.toLowerCase().includes(cinemaInput.toLowerCase())
  )

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    onSearch({
      date,
      mode,
      timeFrom,
      timeTo,
      filmTitle: mode === 'film' ? (selectedFilmTitle ?? (filmInput || null)) : null,
      cinemaId: mode === 'cinema' ? selectedCinemaId : null,
      format: mode === 'format' ? (format || null) : null,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white shadow-sm rounded-lg p-6">
      <div className="flex flex-wrap items-end gap-4">
        {/* Date — always visible */}
        <div className="flex-none">
          <label htmlFor="date" className="block text-sm font-medium text-gray-700">Date</label>
          <input
            type="date"
            id="date"
            value={date}
            onChange={e => setDate(e.target.value)}
            className="mt-1 block rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            required
          />
        </div>

        {/* Mode-specific inputs */}
        <div className="flex-1 min-w-0">
          {mode === 'time' && (
            <div className="flex gap-4">
              <div>
                <label htmlFor="timeFrom" className="block text-sm font-medium text-gray-700">From</label>
                <input
                  type="time"
                  id="timeFrom"
                  value={timeFrom}
                  onChange={e => setTimeFrom(e.target.value)}
                  className="mt-1 block rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                  required
                />
              </div>
              <div>
                <label htmlFor="timeTo" className="block text-sm font-medium text-gray-700">To</label>
                <input
                  type="time"
                  id="timeTo"
                  value={timeTo}
                  onChange={e => setTimeTo(e.target.value)}
                  className="mt-1 block rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                  required
                />
              </div>
            </div>
          )}

          {mode === 'film' && (
            <div className="relative">
              <label htmlFor="filmInput" className="block text-sm font-medium text-gray-700">Film title</label>
              <input
                type="text"
                id="filmInput"
                value={filmInput}
                onChange={e => setFilmInput(e.target.value)}
                onFocus={() => filmSuggestions.length > 0 && setShowSuggestions(true)}
                onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
                placeholder="Type a film title…"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                autoComplete="off"
              />
              {showSuggestions && (
                <ul className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-md shadow-lg max-h-60 overflow-auto text-sm">
                  {filmSuggestions.map(s => (
                    <li
                      key={s.id}
                      className="px-3 py-2 cursor-pointer hover:bg-blue-50"
                      onMouseDown={() => {
                        setFilmInput(s.title)
                        setSelectedFilmTitle(s.title)
                        setShowSuggestions(false)
                      }}
                    >
                      {s.title}
                      {s.year && <span className="ml-1 text-gray-400">({s.year})</span>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {mode === 'cinema' && (
            <div className="relative">
              <label htmlFor="cinemaInput" className="block text-sm font-medium text-gray-700">Cinema</label>
              <input
                type="text"
                id="cinemaInput"
                value={cinemaInput}
                onChange={e => {
                  setCinemaInput(e.target.value)
                  setSelectedCinemaId(null)
                  setShowCinemaList(true)
                }}
                onFocus={() => setShowCinemaList(true)}
                onBlur={() => setTimeout(() => setShowCinemaList(false), 150)}
                placeholder="Type or select a cinema…"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                autoComplete="off"
              />
              {showCinemaList && filteredCinemas.length > 0 && (
                <ul className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-md shadow-lg max-h-60 overflow-auto text-sm">
                  {filteredCinemas.map(c => (
                    <li
                      key={c.id}
                      className="px-3 py-2 cursor-pointer hover:bg-blue-50"
                      onMouseDown={() => {
                        setCinemaInput(c.name)
                        setSelectedCinemaId(c.id)
                        setShowCinemaList(false)
                      }}
                    >
                      {c.name}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {mode === 'format' && (
            <div>
              <label htmlFor="format" className="block text-sm font-medium text-gray-700">Format</label>
              <div className="mt-1 flex items-center gap-3">
                <select
                  id="format"
                  value={format}
                  onChange={e => {
                    setFormat(e.target.value)
                    onLiveFormatChange?.(e.target.value || null, period)
                  }}
                  className="block rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                >
                  <option value="">Any format</option>
                  {FORMAT_OPTIONS.map(f => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
                <div className="flex gap-1">
                  {(['today', 'week'] as const).map(p => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => {
                        setPeriod(p)
                        onLiveFormatChange?.(format || null, p)
                      }}
                      className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                        period === p
                          ? 'bg-gray-900 text-white border-gray-900'
                          : 'text-gray-500 border-gray-300 hover:border-gray-500 hover:text-gray-700'
                      }`}
                    >
                      {p === 'today' ? 'Today' : 'This week'}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Mode selector — far right */}
        <div className="flex-none flex flex-col gap-1 self-end pb-0.5">
          <span className="text-xs font-medium text-gray-500 mb-0.5">Search by</span>
          <div className="flex gap-1">
            {MODE_LABELS.map(({ mode: m, label }) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                  mode === m
                    ? 'bg-gray-900 text-white border-gray-900'
                    : 'text-gray-500 border-gray-300 hover:border-gray-500 hover:text-gray-700'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-5">
        <button
          type="submit"
          disabled={loading}
          className="px-6 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Searching...' : 'Search Films'}
        </button>
      </div>
    </form>
  )
}

export default SearchForm
