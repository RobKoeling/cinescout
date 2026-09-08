import { screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import LetterboxdPanel from './LetterboxdPanel'
import { renderWithAuth, makeUser } from '../test/authTestUtils'

const mockFetch = vi.fn()
global.fetch = mockFetch

afterEach(() => {
  vi.clearAllMocks()
})

function mockResponse(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

describe('LetterboxdPanel', () => {
  it('pre-fills the username input when the user already has one linked', () => {
    const user = makeUser({ letterboxd_username: 'scottn' })
    renderWithAuth(<LetterboxdPanel user={user} />, { user })
    expect(screen.getByLabelText('Username')).toHaveValue('scottn')
  })

  it('Import is disabled until a username is linked', () => {
    const user = makeUser({ letterboxd_username: null })
    renderWithAuth(<LetterboxdPanel user={user} />, { user })
    expect(screen.getByRole('button', { name: 'Import my diary' })).toBeDisabled()
  })

  it('Import is enabled when a username is already linked', () => {
    const user = makeUser({ letterboxd_username: 'scottn' })
    renderWithAuth(<LetterboxdPanel user={user} />, { user })
    expect(screen.getByRole('button', { name: 'Import my diary' })).toBeEnabled()
  })

  it('Save calls linkLetterboxdUsername and updates the auth context user', async () => {
    const user = makeUser({ letterboxd_username: null })
    mockFetch.mockResolvedValueOnce(
      mockResponse({ id: 1, username: 'alice', letterboxd_username: 'scottn', letterboxd_last_synced_at: null })
    )
    const { authValue } = renderWithAuth(<LetterboxdPanel user={user} />, { user })

    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'scottn' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(authValue.updateUser).toHaveBeenCalledWith(
      expect.objectContaining({ letterboxd_username: 'scottn' })
    ))
  })

  it('shows an error when Save fails', async () => {
    const user = makeUser({ letterboxd_username: null })
    mockFetch.mockResolvedValueOnce(mockResponse({ detail: 'Letterboxd profile not found' }, 404))
    renderWithAuth(<LetterboxdPanel user={user} />, { user })

    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'nobody' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Letterboxd profile not found')).toBeInTheDocument()
  })

  it('Import calls importLetterboxdDiary and renders the returned counts', async () => {
    const user = makeUser({ letterboxd_username: 'scottn' })
    mockFetch.mockResolvedValueOnce(
      mockResponse({
        status: 'completed', entries_found: 50, entries_imported: 48,
        entries_skipped_duplicate: 1, entries_unmatched: 1,
      })
    )
    renderWithAuth(<LetterboxdPanel user={user} />, { user })

    fireEvent.click(screen.getByRole('button', { name: 'Import my diary' }))

    expect(await screen.findByText(/Imported 48 of 50 entries/)).toBeInTheDocument()
    expect(screen.getByText(/1 already logged/)).toBeInTheDocument()
    expect(screen.getByText(/1 could not be matched/)).toBeInTheDocument()
  })

  it('shows an error when Import fails', async () => {
    const user = makeUser({ letterboxd_username: 'scottn' })
    mockFetch.mockResolvedValueOnce(mockResponse({ detail: 'Could not fetch Letterboxd diary' }, 502))
    renderWithAuth(<LetterboxdPanel user={user} />, { user })

    fireEvent.click(screen.getByRole('button', { name: 'Import my diary' }))

    expect(await screen.findByText('Could not fetch Letterboxd diary')).toBeInTheDocument()
  })
})
