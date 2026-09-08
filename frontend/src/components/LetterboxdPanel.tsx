import { useState } from 'react'
import { importLetterboxdDiary, linkLetterboxdUsername } from '../api/letterboxd'
import { useAuth } from '../hooks/useAuth'
import type { LetterboxdImportResult, User } from '../types'

interface LetterboxdPanelProps {
  user: User
}

function LetterboxdPanel({ user }: LetterboxdPanelProps) {
  const { updateUser } = useAuth()
  const [username, setUsername] = useState(user.letterboxd_username ?? '')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const [importResult, setImportResult] = useState<LetterboxdImportResult | null>(null)

  const handleSave = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const updated = await linkLetterboxdUsername(username.trim())
      updateUser(updated)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to link Letterboxd account')
    } finally {
      setSaving(false)
    }
  }

  const handleImport = async () => {
    setImporting(true)
    setImportError(null)
    setImportResult(null)
    try {
      const result = await importLetterboxdDiary()
      setImportResult(result)
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Failed to import Letterboxd diary')
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="bg-white shadow-sm rounded-lg border border-gray-200 p-4 mb-6">
      <h3 className="font-medium text-gray-900 mb-3">Letterboxd</h3>

      <div className="flex items-end gap-2">
        <div className="flex-1">
          <label htmlFor="letterboxdUsername" className="block text-sm font-medium text-gray-700">
            Username
          </label>
          <input
            type="text"
            id="letterboxdUsername"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="your-letterboxd-username"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <button
          onClick={handleSave}
          disabled={saving || !username.trim()}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
      {saveError && <p className="mt-2 text-sm text-red-800">{saveError}</p>}

      <div className="mt-4">
        <button
          onClick={handleImport}
          disabled={!user.letterboxd_username || importing}
          className="text-sm font-medium text-blue-600 hover:text-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {importing ? 'Importing…' : 'Import my diary'}
        </button>
        {importError && <p className="mt-2 text-sm text-red-800">{importError}</p>}
        {importResult && (
          <p className="mt-2 text-sm text-green-700">
            Imported {importResult.entries_imported} of {importResult.entries_found} entries
            {importResult.entries_skipped_duplicate > 0 &&
              ` (${importResult.entries_skipped_duplicate} already logged)`}
            {importResult.entries_unmatched > 0 &&
              ` (${importResult.entries_unmatched} could not be matched)`}
            .
          </p>
        )}
      </div>
    </div>
  )
}

export default LetterboxdPanel
