import { useEffect, useState } from 'react'
import LetterboxdPanel from './LetterboxdPanel'
import ManualLogModal from './ManualLogModal'
import StarRating from './StarRating'
import { deleteWatchLog, listWatchLogs } from '../api/watchLogs'
import { useAuth } from '../hooks/useAuth'
import type { WatchLogEntry } from '../types'

interface ProfilePageProps {
  onBack: () => void
}

function ProfilePage({ onBack }: ProfilePageProps) {
  // ProfilePage is only ever rendered while logged in (App.tsx bounces back
  // to search otherwise), so `user` is always non-null here.
  const { user } = useAuth()
  const [entries, setEntries] = useState<WatchLogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showManualLogModal, setShowManualLogModal] = useState(false)

  const loadEntries = () => {
    setLoading(true)
    setError(null)
    listWatchLogs()
      .then(setEntries)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load your diary'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadEntries()
  }, [])

  const formatDate = (isoDate: string) =>
    new Date(`${isoDate}T00:00:00`).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    })

  const handleDelete = async (id: number) => {
    const previous = entries
    setEntries(entries.filter((e) => e.id !== id))
    try {
      await deleteWatchLog(id)
    } catch {
      setEntries(previous)
    }
  }

  return (
    <div>
      <button
        onClick={onBack}
        className="text-sm font-medium text-blue-600 hover:text-blue-800 transition-colors mb-6"
      >
        ← Back to search
      </button>

      {user && <LetterboxdPanel user={user} />}

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold text-gray-900">My Diary</h2>
        <button
          onClick={() => setShowManualLogModal(true)}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
        >
          + Log a film
        </button>
      </div>

      {loading && <p className="text-sm text-gray-600">Loading…</p>}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {!loading && !error && entries.length === 0 && (
        <p className="text-sm text-gray-600">
          You haven't logged any films yet. Log a showing from search, or add one manually.
        </p>
      )}

      {!loading && entries.length > 0 && (
        <ul className="space-y-3">
          {entries.map((entry) => (
            <li
              key={entry.id}
              className="bg-white shadow-sm rounded-lg border border-gray-200 p-4 flex items-start justify-between gap-4"
            >
              <div className="min-w-0">
                <p className="font-medium text-gray-900">
                  {entry.film.title}
                  {entry.film.year && (
                    <span className="text-gray-500 font-normal ml-1.5">({entry.film.year})</span>
                  )}
                </p>
                <p className="text-sm text-gray-500 mt-0.5">
                  {formatDate(entry.watched_date)}
                  {entry.cinema && ` — ${entry.cinema.name}`}
                </p>
                {entry.rating !== null && (
                  <div className="mt-1">
                    <StarRating value={entry.rating} readOnly />
                  </div>
                )}
                {entry.comment && <p className="text-sm text-gray-700 mt-1">{entry.comment}</p>}
              </div>
              <button
                onClick={() => handleDelete(entry.id)}
                className="text-sm text-gray-400 hover:text-red-600 transition-colors flex-shrink-0"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}

      {showManualLogModal && (
        <ManualLogModal
          onClose={() => setShowManualLogModal(false)}
          onLogged={loadEntries}
        />
      )}
    </div>
  )
}

export default ProfilePage
