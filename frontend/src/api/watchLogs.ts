import { apiFetch } from './client'
import type {
  CreateManualWatchLogRequest,
  CreateWatchLogFromShowingRequest,
  WatchLogEntry,
} from '../types'

export async function createWatchLogFromShowing(
  payload: CreateWatchLogFromShowingRequest
): Promise<WatchLogEntry> {
  return apiFetch<WatchLogEntry>('/api/watch-logs', { method: 'POST', body: payload })
}

export async function createManualWatchLog(
  payload: CreateManualWatchLogRequest
): Promise<WatchLogEntry> {
  return apiFetch<WatchLogEntry>('/api/watch-logs', { method: 'POST', body: payload })
}

export async function listWatchLogs(): Promise<WatchLogEntry[]> {
  return apiFetch<WatchLogEntry[]>('/api/watch-logs')
}

export async function deleteWatchLog(id: number): Promise<void> {
  await apiFetch<void>(`/api/watch-logs/${id}`, { method: 'DELETE' })
}
