import { useEffect, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface RTLinkProps {
  title: string
  year?: number | null
}

export default function RTLink({ title, year }: RTLinkProps) {
  // null = still checking, true = valid, false = 404
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams({ title })
    if (year) params.set('year', String(year))
    fetch(`${API_URL}/api/films/rt-check?${params}`)
      .then(r => r.json())
      .then((data: { valid: boolean; url: string }) => {
        if (data.valid) setUrl(data.url)
      })
      .catch(() => {/* leave url null — don't show broken links on fetch error */})
  }, [title, year])

  if (!url) return null

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={e => e.stopPropagation()}
      className="ml-2 text-xs font-medium text-red-600 hover:text-red-800 opacity-70 hover:opacity-100 transition-opacity align-middle"
      title="Rotten Tomatoes"
    >
      🍅
    </a>
  )
}
