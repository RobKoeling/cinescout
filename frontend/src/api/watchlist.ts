import { apiFetch } from './client'
import type { LetterboxdWatchlistImportResult, UpcomingWatchlistShowing, WatchlistItem } from '../types'

export async function importWatchlist(): Promise<LetterboxdWatchlistImportResult> {
  return apiFetch<LetterboxdWatchlistImportResult>('/api/watchlist/import', { method: 'POST' })
}

export async function listWatchlist(): Promise<WatchlistItem[]> {
  return apiFetch<WatchlistItem[]>('/api/watchlist')
}

export async function listUpcomingWatchlistShowings(): Promise<UpcomingWatchlistShowing[]> {
  return apiFetch<UpcomingWatchlistShowing[]>('/api/watchlist/upcoming')
}
