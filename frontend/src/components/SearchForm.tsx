import { useState, FormEvent } from 'react'

interface SearchFormProps {
  onSearch: (params: {
    date: string
    timeFrom: string
    timeTo: string
  }) => void
  loading: boolean
}

function SearchForm({ onSearch, loading }: SearchFormProps) {
  // Default to today's date
  const today = new Date().toISOString().split('T')[0]

  const [date, setDate] = useState(today)
  const [timeFrom, setTimeFrom] = useState('18:00')
  const [timeTo, setTimeTo] = useState('21:00')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    onSearch({ date, timeFrom, timeTo })
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white shadow-sm rounded-lg p-6">
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
        <div>
          <label htmlFor="date" className="block text-sm font-medium text-gray-700">
            Date
          </label>
          <input
            type="date"
            id="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            required
          />
        </div>

        <div>
          <label htmlFor="timeFrom" className="block text-sm font-medium text-gray-700">
            From
          </label>
          <input
            type="time"
            id="timeFrom"
            value={timeFrom}
            onChange={(e) => setTimeFrom(e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            required
          />
        </div>

        <div>
          <label htmlFor="timeTo" className="block text-sm font-medium text-gray-700">
            To
          </label>
          <input
            type="time"
            id="timeTo"
            value={timeTo}
            onChange={(e) => setTimeTo(e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            required
          />
        </div>
      </div>

      <div className="mt-6">
        <button
          type="submit"
          disabled={loading}
          className="w-full sm:w-auto px-6 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Searching...' : 'Search Films'}
        </button>
      </div>
    </form>
  )
}

export default SearchForm
