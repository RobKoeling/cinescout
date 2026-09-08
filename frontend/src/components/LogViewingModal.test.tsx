import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import LogViewingModal from './LogViewingModal'
import type { Cinema, Film, ShowingTime } from '../types'

const mockFetch = vi.fn()
global.fetch = mockFetch

afterEach(() => {
  vi.clearAllMocks()
})

const FILM: Film = {
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
}

const CINEMA: Cinema = {
  id: 'bfi-southbank',
  name: 'BFI Southbank',
  city: 'london',
  address: 'Belvedere Road',
  postcode: 'SE1 8XT',
  latitude: 51.5065,
  longitude: -0.115,
  website: 'https://bfi.org.uk',
  has_online_booking: true,
  supports_availability_check: false,
}

const SHOWING: ShowingTime = {
  id: 42,
  start_time: '2026-02-20T18:30:00Z',
  screen_name: null,
  format_tags: null,
  booking_url: null,
  price: null,
  raw_title: null,
}

function mockResponse(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

describe('LogViewingModal', () => {
  it('displays the film title, year, and cinema/time context', () => {
    render(<LogViewingModal film={FILM} cinema={CINEMA} showing={SHOWING} onClose={vi.fn()} />)
    expect(screen.getByText('Nosferatu')).toBeInTheDocument()
    expect(screen.getByText('(2024)')).toBeInTheDocument()
    expect(screen.getByText(/BFI Southbank/)).toBeInTheDocument()
  })

  it('clicking a star sets the rating', () => {
    render(<LogViewingModal film={FILM} cinema={CINEMA} showing={SHOWING} onClose={vi.fn()} />)
    fireEvent.click(screen.getByLabelText('Rate 4 stars'))
    // No direct visible assertion needed beyond it not throwing; verified via submit payload below.
  })

  it('submits showing_id, rating, and comment', async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse({
        id: 1, film_id: FILM.id, showing_id: SHOWING.id, watched_date: '2026-02-20',
        rating: 4, comment: 'Great!', created_at: '2026-02-20T20:00:00Z',
      })
    )
    render(<LogViewingModal film={FILM} cinema={CINEMA} showing={SHOWING} onClose={vi.fn()} />)

    fireEvent.click(screen.getByLabelText('Rate 4 stars'))
    fireEvent.change(screen.getByLabelText('Comment'), { target: { value: 'Great!' } })
    fireEvent.click(screen.getByRole('button', { name: 'Log as watched' }))

    await waitFor(() => expect(mockFetch).toHaveBeenCalled())
    const [, options] = mockFetch.mock.calls[0]
    const body = JSON.parse(options.body)
    expect(body).toEqual({ showing_id: 42, rating: 4, comment: 'Great!' })
  })

  it('shows a success message after submitting', async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse({
        id: 1, film_id: FILM.id, showing_id: SHOWING.id, watched_date: '2026-02-20',
        rating: null, comment: null, created_at: '2026-02-20T20:00:00Z',
      })
    )
    render(<LogViewingModal film={FILM} cinema={CINEMA} showing={SHOWING} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Log as watched' }))
    expect(await screen.findByText('Logged as watched.')).toBeInTheDocument()
  })

  it('shows an error message on failure', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse({ detail: 'This showing is already logged as watched' }, 409))
    render(<LogViewingModal film={FILM} cinema={CINEMA} showing={SHOWING} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Log as watched' }))
    expect(await screen.findByText('This showing is already logged as watched')).toBeInTheDocument()
  })

  it('closes on Escape key', () => {
    const onClose = vi.fn()
    render(<LogViewingModal film={FILM} cinema={CINEMA} showing={SHOWING} onClose={onClose} />)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })
})
