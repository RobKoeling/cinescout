import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import CinemaModal from './CinemaModal'
import type { Cinema, FilmWithCinemas } from '../types'

// Mock fetch globally
const mockFetch = vi.fn()
global.fetch = mockFetch

afterEach(() => {
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeCinema(id = 'bfi-southbank', name = 'BFI Southbank'): Cinema {
  return {
    id,
    name,
    city: 'london',
    address: 'Belvedere Road',
    postcode: 'SE1 8XT',
    latitude: 51.5065,
    longitude: -0.115,
    website: 'https://bfi.org.uk',
    has_online_booking: true,
    supports_availability_check: false,
  }
}

function makeFilmWithCinemas(cinemaId = 'bfi-southbank'): FilmWithCinemas {
  return {
    film: {
      id: 'nosferatu-2024',
      title: 'Nosferatu',
      year: 2024,
      directors: ['Robert Eggers'],
      countries: null,
      cast: null,
      runtime: 132,
      overview: null,
      poster_path: null,
      tmdb_id: 12345,
      showing_count: 1,
    },
    cinemas: [
      {
        cinema: makeCinema(cinemaId),
        times: [
          {
            id: 1,
            start_time: '2026-02-20T19:30:00Z',
            screen_name: null,
            format_tags: null,
            booking_url: 'https://bfi.org.uk/book/1',
            price: null,
            raw_title: null,
          },
        ],
      },
    ],
  }
}

function renderModal(overrides: {
  cinema?: Cinema
  date?: string
  city?: string
  allFilms?: FilmWithCinemas[]
  onClose?: () => void
} = {}) {
  const cinema = overrides.cinema ?? makeCinema()
  return render(
    <CinemaModal
      cinema={cinema}
      date={overrides.date ?? '2026-02-20'}
      city={overrides.city ?? 'london'}
      allFilms={overrides.allFilms ?? [makeFilmWithCinemas()]}
      onClose={overrides.onClose ?? vi.fn()}
    />
  )
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe('CinemaModal rendering', () => {
  it('displays the cinema name in the header', () => {
    renderModal()
    expect(screen.getByRole('heading', { name: 'BFI Southbank' })).toBeInTheDocument()
  })

  it('displays the cinema address', () => {
    renderModal()
    expect(screen.getByText('Belvedere Road')).toBeInTheDocument()
  })

  it('shows films that belong to this cinema', () => {
    renderModal()
    expect(screen.getByText('Nosferatu')).toBeInTheDocument()
  })

  it('does not show films from other cinemas', () => {
    const otherFilm = makeFilmWithCinemas('curzon-soho')
    otherFilm.film.title = 'Other Film'
    renderModal({ allFilms: [otherFilm] })
    expect(screen.queryByText('Other Film')).not.toBeInTheDocument()
    expect(screen.getByText('No films found.')).toBeInTheDocument()
  })

  it('shows "No films found." when allFilms is empty', () => {
    renderModal({ allFilms: [] })
    expect(screen.getByText('No films found.')).toBeInTheDocument()
  })

  it('shows a booking link when booking_url is set', () => {
    renderModal()
    expect(screen.getByRole('link')).toHaveAttribute('href', 'https://bfi.org.uk/book/1')
  })

  it('shows a plain time span when no booking_url', () => {
    const data = makeFilmWithCinemas()
    data.cinemas[0].times[0].booking_url = null
    renderModal({ allFilms: [data] })
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('shows director line when directors are present', () => {
    renderModal()
    expect(screen.getByText(/Dir:.*Robert Eggers/)).toBeInTheDocument()
  })

  it('shows "Show all films today" button initially', () => {
    renderModal()
    expect(screen.getByRole('button', { name: 'Show all films today' })).toBeInTheDocument()
  })

  it('sorts films by their earliest showing time', () => {
    const filmA = makeFilmWithCinemas()
    filmA.film.id = 'film-a'
    filmA.film.title = 'Film A'
    filmA.cinemas[0].times[0].start_time = '2026-02-20T21:00:00Z'

    const filmB = makeFilmWithCinemas()
    filmB.film.id = 'film-b'
    filmB.film.title = 'Film B'
    filmB.cinemas[0].times[0].start_time = '2026-02-20T14:00:00Z'

    renderModal({ allFilms: [filmA, filmB] })

    const titles = screen.getAllByText(/Film [AB]/)
    expect(titles[0]).toHaveTextContent('Film B')
    expect(titles[1]).toHaveTextContent('Film A')
  })
})

// ---------------------------------------------------------------------------
// Close behaviour
// ---------------------------------------------------------------------------

describe('CinemaModal close', () => {
  it('calls onClose when the close button is clicked', () => {
    const onClose = vi.fn()
    renderModal({ onClose })
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(onClose).toHaveBeenCalled()
  })

  it('calls onClose when the backdrop is clicked', () => {
    const onClose = vi.fn()
    const { container } = renderModal({ onClose })
    // The outermost div is the backdrop container
    fireEvent.click(container.firstChild as Element)
    expect(onClose).toHaveBeenCalled()
  })

  it('calls onClose when Escape is pressed', () => {
    const onClose = vi.fn()
    renderModal({ onClose })
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })

  it('does not call onClose when other keys are pressed', () => {
    const onClose = vi.fn()
    renderModal({ onClose })
    fireEvent.keyDown(window, { key: 'Enter' })
    expect(onClose).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// "Show all films today" button
// ---------------------------------------------------------------------------

describe('"Show all films today"', () => {
  it('fetches full-day showings with correct city parameter', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ films: [] }),
    } as Response)

    renderModal({ city: 'brighton', date: '2026-02-20' })
    fireEvent.click(screen.getByRole('button', { name: 'Show all films today' }))

    await waitFor(() => expect(mockFetch).toHaveBeenCalled())

    const url = mockFetch.mock.calls[0][0] as string
    expect(url).toContain('city=brighton')
    expect(url).toContain('date=2026-02-20')
    expect(url).toContain('time_from=00%3A00')
    expect(url).toContain('time_to=23%3A59')
  })

  it('hides the button after successful fetch', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ films: [] }),
    } as Response)

    renderModal()
    fireEvent.click(screen.getByRole('button', { name: 'Show all films today' }))

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Show all films today' })).not.toBeInTheDocument()
    })
  })

  it('shows "Loading…" while fetching', async () => {
    let resolve!: (v: unknown) => void
    mockFetch.mockReturnValue(new Promise(r => { resolve = r }))

    renderModal()
    fireEvent.click(screen.getByRole('button', { name: 'Show all films today' }))

    expect(screen.getByRole('button', { name: 'Loading…' })).toBeInTheDocument()

    // Clean up the pending promise
    resolve({ ok: true, json: async () => ({ films: [] }) })
  })

  it('displays full-day results filtered to this cinema', async () => {
    const fullDayFilm = makeFilmWithCinemas()
    fullDayFilm.film.id = 'full-day-film'
    fullDayFilm.film.title = 'Full Day Film'

    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ films: [fullDayFilm] }),
    } as Response)

    renderModal({ allFilms: [] })
    fireEvent.click(screen.getByRole('button', { name: 'Show all films today' }))

    await waitFor(() => {
      expect(screen.getByText('Full Day Film')).toBeInTheDocument()
    })
  })
})
