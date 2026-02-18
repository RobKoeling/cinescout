import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import FilmCard from './FilmCard'
import type { FilmWithCinemas } from '../types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeFilmWithCinemas(overrides: Partial<FilmWithCinemas> = {}): FilmWithCinemas {
  return {
    film: {
      id: 'nosferatu-2024',
      title: 'Nosferatu',
      year: 2024,
      directors: ['Robert Eggers'],
      countries: ['USA', 'Germany'],
      cast: ['Bill Skarsgård', 'Lily-Rose Depp'],
      runtime: 132,
      overview: 'A gothic horror film.',
      poster_path: '/nosferatu.jpg',
      tmdb_id: 12345,
      showing_count: 2,
    },
    cinemas: [
      {
        cinema: {
          id: 'bfi-southbank',
          name: 'BFI Southbank',
          city: 'london',
          address: 'Belvedere Road, SE1',
          postcode: 'SE1 8XT',
          latitude: 51.5065,
          longitude: -0.115,
          website: 'https://bfi.org.uk',
          has_online_booking: true,
          supports_availability_check: false,
        },
        times: [
          {
            id: 1,
            start_time: '2026-02-20T18:30:00Z',
            screen_name: 'NFT1',
            format_tags: null,
            booking_url: 'https://bfi.org.uk/book/1',
            price: null,
            raw_title: null,
          },
          {
            id: 2,
            start_time: '2026-02-20T21:00:00Z',
            screen_name: null,
            format_tags: null,
            booking_url: null,
            price: null,
            raw_title: null,
          },
        ],
      },
    ],
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// Header — always visible
// ---------------------------------------------------------------------------

describe('FilmCard header', () => {
  it('renders the film title and year', () => {
    render(
      <FilmCard
        filmWithCinemas={makeFilmWithCinemas()}
        allFilms={[]}
        onCinemaClick={vi.fn()}
        onDirectorClick={vi.fn()}
      />
    )
    expect(screen.getByText('Nosferatu')).toBeInTheDocument()
    expect(screen.getByText('(2024)')).toBeInTheDocument()
  })

  it('omits year when null', () => {
    const data = makeFilmWithCinemas()
    data.film.year = null
    render(
      <FilmCard filmWithCinemas={data} allFilms={[]} onCinemaClick={vi.fn()} onDirectorClick={vi.fn()} />
    )
    expect(screen.queryByText(/\(\d{4}\)/)).not.toBeInTheDocument()
  })

  it('shows showing count and cinema count', () => {
    render(
      <FilmCard filmWithCinemas={makeFilmWithCinemas()} allFilms={[]} onCinemaClick={vi.fn()} onDirectorClick={vi.fn()} />
    )
    expect(screen.getByText(/2 showings at 1 cinema/)).toBeInTheDocument()
  })

  it('uses singular "showing" and "cinema" for counts of 1', () => {
    const data = makeFilmWithCinemas()
    data.film.showing_count = 1
    render(
      <FilmCard filmWithCinemas={data} allFilms={[]} onCinemaClick={vi.fn()} onDirectorClick={vi.fn()} />
    )
    expect(screen.getByText(/1 showing at 1 cinema/)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// displayTitle — raw_title override
// ---------------------------------------------------------------------------

describe('displayTitle', () => {
  it('uses film.title when raw_title is null', () => {
    render(
      <FilmCard filmWithCinemas={makeFilmWithCinemas()} allFilms={[]} onCinemaClick={vi.fn()} onDirectorClick={vi.fn()} />
    )
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Nosferatu')
  })

  it('uses film.title when raw_title matches canonical title (case-insensitive)', () => {
    const data = makeFilmWithCinemas()
    data.cinemas[0].times[0].raw_title = 'NOSFERATU'
    render(
      <FilmCard filmWithCinemas={data} allFilms={[]} onCinemaClick={vi.fn()} onDirectorClick={vi.fn()} />
    )
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Nosferatu')
  })

  it('uses raw_title when it differs from canonical title', () => {
    const data = makeFilmWithCinemas()
    data.film.title = 'Certain Women'
    data.cinemas[0].times[0].raw_title = 'Film Club: Certain Women'
    render(
      <FilmCard filmWithCinemas={data} allFilms={[]} onCinemaClick={vi.fn()} onDirectorClick={vi.fn()} />
    )
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Film Club: Certain Women')
  })
})

// ---------------------------------------------------------------------------
// Expand / collapse
// ---------------------------------------------------------------------------

describe('expand / collapse', () => {
  it('hides detailed content by default', () => {
    render(
      <FilmCard filmWithCinemas={makeFilmWithCinemas()} allFilms={[]} onCinemaClick={vi.fn()} onDirectorClick={vi.fn()} />
    )
    expect(screen.queryByText('A gothic horror film.')).not.toBeInTheDocument()
  })

  it('reveals detailed content when header is clicked', () => {
    render(
      <FilmCard filmWithCinemas={makeFilmWithCinemas()} allFilms={[]} onCinemaClick={vi.fn()} onDirectorClick={vi.fn()} />
    )
    fireEvent.click(screen.getByRole('button', { name: /Nosferatu/ }))
    expect(screen.getByText('A gothic horror film.')).toBeInTheDocument()
  })

  it('hides content again when clicked a second time', () => {
    render(
      <FilmCard filmWithCinemas={makeFilmWithCinemas()} allFilms={[]} onCinemaClick={vi.fn()} onDirectorClick={vi.fn()} />
    )
    const btn = screen.getByRole('button', { name: /Nosferatu/ })
    fireEvent.click(btn)
    fireEvent.click(btn)
    expect(screen.queryByText('A gothic horror film.')).not.toBeInTheDocument()
  })

  it('shows directors, countries, and overview when expanded', () => {
    render(
      <FilmCard filmWithCinemas={makeFilmWithCinemas()} allFilms={[]} onCinemaClick={vi.fn()} onDirectorClick={vi.fn()} />
    )
    fireEvent.click(screen.getByRole('button', { name: /Nosferatu/ }))
    expect(screen.getByText('Robert Eggers')).toBeInTheDocument()
    expect(screen.getByText(/USA, Germany/)).toBeInTheDocument()
    expect(screen.getByText('A gothic horror film.')).toBeInTheDocument()
  })

  it('shows cinema name and address when expanded', () => {
    render(
      <FilmCard filmWithCinemas={makeFilmWithCinemas()} allFilms={[]} onCinemaClick={vi.fn()} onDirectorClick={vi.fn()} />
    )
    fireEvent.click(screen.getByRole('button', { name: /Nosferatu/ }))
    expect(screen.getByText('BFI Southbank')).toBeInTheDocument()
    expect(screen.getByText('Belvedere Road, SE1')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Showing times
// ---------------------------------------------------------------------------

describe('showing times', () => {
  it('renders a booking link when booking_url is set', () => {
    render(
      <FilmCard filmWithCinemas={makeFilmWithCinemas()} allFilms={[]} onCinemaClick={vi.fn()} onDirectorClick={vi.fn()} />
    )
    fireEvent.click(screen.getByRole('button', { name: /Nosferatu/ }))
    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('href', 'https://bfi.org.uk/book/1')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('renders a plain span when no booking_url', () => {
    const data = makeFilmWithCinemas()
    // Remove booking URL from both times
    data.cinemas[0].times[0].booking_url = null
    render(
      <FilmCard filmWithCinemas={data} allFilms={[]} onCinemaClick={vi.fn()} onDirectorClick={vi.fn()} />
    )
    fireEvent.click(screen.getByRole('button', { name: /Nosferatu/ }))
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('shows screen name when present', () => {
    render(
      <FilmCard filmWithCinemas={makeFilmWithCinemas()} allFilms={[]} onCinemaClick={vi.fn()} onDirectorClick={vi.fn()} />
    )
    fireEvent.click(screen.getByRole('button', { name: /Nosferatu/ }))
    expect(screen.getByText('NFT1')).toBeInTheDocument()
  })

  it('shows formatted price when present', () => {
    const data = makeFilmWithCinemas()
    data.cinemas[0].times[0].price = 12.5
    render(
      <FilmCard filmWithCinemas={data} allFilms={[]} onCinemaClick={vi.fn()} onDirectorClick={vi.fn()} />
    )
    fireEvent.click(screen.getByRole('button', { name: /Nosferatu/ }))
    expect(screen.getByText('£12.50')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Callbacks
// ---------------------------------------------------------------------------

describe('callbacks', () => {
  it('calls onCinemaClick with the cinema when cinema name is clicked', () => {
    const onCinemaClick = vi.fn()
    render(
      <FilmCard filmWithCinemas={makeFilmWithCinemas()} allFilms={[]} onCinemaClick={onCinemaClick} onDirectorClick={vi.fn()} />
    )
    fireEvent.click(screen.getByRole('button', { name: /Nosferatu/ }))
    fireEvent.click(screen.getByText('BFI Southbank'))
    expect(onCinemaClick).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'bfi-southbank', name: 'BFI Southbank' })
    )
  })

  it('calls onDirectorClick with director name and film id', () => {
    const onDirectorClick = vi.fn()
    render(
      <FilmCard filmWithCinemas={makeFilmWithCinemas()} allFilms={[]} onCinemaClick={vi.fn()} onDirectorClick={onDirectorClick} />
    )
    fireEvent.click(screen.getByRole('button', { name: /Nosferatu/ }))
    fireEvent.click(screen.getByText('Robert Eggers'))
    expect(onDirectorClick).toHaveBeenCalledWith('Robert Eggers', 'nosferatu-2024')
  })
})
