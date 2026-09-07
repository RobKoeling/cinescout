import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import ProfilePage from './ProfilePage'
import type { WatchLogEntry } from '../types'

const mockFetch = vi.fn()
global.fetch = mockFetch

afterEach(() => {
  vi.clearAllMocks()
})

function mockResponse(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

function makeEntry(overrides: Partial<WatchLogEntry> = {}): WatchLogEntry {
  return {
    id: 1,
    film_id: 'nosferatu-2024',
    showing_id: 42,
    watched_date: '2026-02-20',
    rating: 4.5,
    comment: 'Great atmosphere',
    created_at: '2026-02-20T20:00:00Z',
    film: {
      id: 'nosferatu-2024',
      title: 'Nosferatu',
      year: 2024,
      directors: null,
      countries: null,
      cast: null,
      runtime: 132,
      overview: null,
      poster_path: null,
      tmdb_id: 12345,
    },
    cinema: {
      id: 'bfi-southbank',
      name: 'BFI Southbank',
      city: 'london',
      address: 'Belvedere Road',
      postcode: 'SE1 8XT',
      latitude: null,
      longitude: null,
      website: null,
      has_online_booking: true,
      supports_availability_check: false,
    },
    ...overrides,
  }
}

describe('ProfilePage', () => {
  it('fetches and renders entries on mount', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse([makeEntry()]))
    render(<ProfilePage onBack={vi.fn()} />)

    expect(await screen.findByText('Nosferatu')).toBeInTheDocument()
    expect(screen.getByText(/BFI Southbank/)).toBeInTheDocument()
    expect(screen.getByText('Great atmosphere')).toBeInTheDocument()
  })

  it('shows an empty state when there are no entries', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse([]))
    render(<ProfilePage onBack={vi.fn()} />)

    expect(await screen.findByText(/haven't logged any films yet/)).toBeInTheDocument()
  })

  it('shows an error message when the fetch fails', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse({ detail: 'Not authenticated' }, 401))
    render(<ProfilePage onBack={vi.fn()} />)

    expect(await screen.findByText('Not authenticated')).toBeInTheDocument()
  })

  it('removes an entry after a successful delete', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse([makeEntry()]))
    render(<ProfilePage onBack={vi.fn()} />)
    await screen.findByText('Nosferatu')

    mockFetch.mockResolvedValueOnce({ ok: true, status: 204, json: async () => undefined })
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))

    await waitFor(() => expect(screen.queryByText('Nosferatu')).not.toBeInTheDocument())
  })

  it('calls onBack when Back to search is clicked', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse([]))
    const onBack = vi.fn()
    render(<ProfilePage onBack={onBack} />)
    await screen.findByText(/haven't logged any films yet/)

    fireEvent.click(screen.getByRole('button', { name: /Back to search/ }))
    expect(onBack).toHaveBeenCalled()
  })

  it('opens ManualLogModal when + Log a film is clicked', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse([]))
    render(<ProfilePage onBack={vi.fn()} />)
    await screen.findByText(/haven't logged any films yet/)

    fireEvent.click(screen.getByRole('button', { name: '+ Log a film' }))
    expect(screen.getByText('Log a film', { selector: 'h2' })).toBeInTheDocument()
  })
})
