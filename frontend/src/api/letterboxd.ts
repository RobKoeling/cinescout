import { apiFetch } from './client'
import type { LetterboxdImportResult, User } from '../types'

export async function linkLetterboxdUsername(username: string): Promise<User> {
  return apiFetch<User>('/api/letterboxd/link', {
    method: 'POST',
    body: { letterboxd_username: username },
  })
}

export async function unlinkLetterboxdUsername(): Promise<User> {
  return apiFetch<User>('/api/letterboxd/link', { method: 'DELETE' })
}

export async function importLetterboxdDiary(): Promise<LetterboxdImportResult> {
  return apiFetch<LetterboxdImportResult>('/api/letterboxd/import', { method: 'POST' })
}
