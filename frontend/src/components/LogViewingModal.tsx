import { useEffect, useState } from 'react'
import StarRating from './StarRating'
import { createWatchLogFromShowing } from '../api/watchLogs'
import type { Cinema, Film, ShowingTime } from '../types'

interface LogViewingModalProps {
  film: Film
  cinema: Cinema
  showing: ShowingTime
  onClose: () => void
  onLogged?: () => void
}

function LogViewingModal({ film, cinema, showing, onClose, onLogged }: LogViewingModalProps) {
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

  const formatTime = (isoString: string) =>
    new Date(isoString).toLocaleString('en-GB', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Europe/London',
    })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await createWatchLogFromShowing({
        showing_id: showing.id,
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
          <div>
            <h2 className="text-xl font-bold text-gray-900">
              {film.title}
              {film.year && <span className="text-gray-500 font-normal ml-1.5">({film.year})</span>}
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {cinema.name} — {formatTime(showing.start_time)}
            </p>
          </div>
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
          <form id="log-viewing-form" onSubmit={handleSubmit} className="overflow-y-auto p-5 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Rating</label>
              <StarRating value={rating} onChange={setRating} />
            </div>
            <div>
              <label htmlFor="comment" className="block text-sm font-medium text-gray-700">
                Comment
              </label>
              <textarea
                id="comment"
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
              form="log-viewing-form"
              disabled={submitting}
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

export default LogViewingModal
