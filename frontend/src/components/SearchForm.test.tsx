import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import SearchForm from './SearchForm'

// Mock fetch globally
const mockFetch = vi.fn()
global.fetch = mockFetch

beforeEach(() => {
  // Default: cinemas endpoint returns empty list
  mockFetch.mockResolvedValue({
    ok: true,
    json: async () => [],
  } as Response)
})

afterEach(() => {
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe('SearchForm rendering', () => {
  it('renders the date input', () => {
    render(<SearchForm city="london" onSearch={vi.fn()} loading={false} />)
    expect(screen.getByLabelText('Date')).toBeInTheDocument()
  })

  it('renders time inputs in default time mode', () => {
    render(<SearchForm city="london" onSearch={vi.fn()} loading={false} />)
    expect(screen.getByLabelText('From')).toBeInTheDocument()
    expect(screen.getByLabelText('To')).toBeInTheDocument()
  })

  it('renders the Search Films button', () => {
    render(<SearchForm city="london" onSearch={vi.fn()} loading={false} />)
    expect(screen.getByRole('button', { name: 'Search Films' })).toBeInTheDocument()
  })

  it('shows "Searching..." when loading', () => {
    render(<SearchForm city="london" onSearch={vi.fn()} loading={true} />)
    expect(screen.getByRole('button', { name: 'Searching...' })).toBeDisabled()
  })

  it('renders mode buttons: Time, Film, Cinema, Format', () => {
    render(<SearchForm city="london" onSearch={vi.fn()} loading={false} />)
    expect(screen.getByRole('button', { name: 'Time' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Film' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cinema' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Format' })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Mode switching
// ---------------------------------------------------------------------------

describe('mode switching', () => {
  it('switches to Film mode and shows film title input', () => {
    render(<SearchForm city="london" onSearch={vi.fn()} loading={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'Film' }))
    expect(screen.getByLabelText('Film title')).toBeInTheDocument()
    expect(screen.queryByLabelText('From')).not.toBeInTheDocument()
  })

  it('switches to Cinema mode and shows cinema input', () => {
    render(<SearchForm city="london" onSearch={vi.fn()} loading={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'Cinema' }))
    expect(screen.getByLabelText('Cinema')).toBeInTheDocument()
    expect(screen.queryByLabelText('From')).not.toBeInTheDocument()
  })

  it('switches to Format mode and shows format select', () => {
    render(<SearchForm city="london" onSearch={vi.fn()} loading={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'Format' }))
    expect(screen.getByLabelText('Format')).toBeInTheDocument()
    expect(screen.queryByLabelText('From')).not.toBeInTheDocument()
  })

  it('can switch back to Time mode', () => {
    render(<SearchForm city="london" onSearch={vi.fn()} loading={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'Film' }))
    fireEvent.click(screen.getByRole('button', { name: 'Time' }))
    expect(screen.getByLabelText('From')).toBeInTheDocument()
    expect(screen.queryByLabelText('Film title')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Form submission
// ---------------------------------------------------------------------------

describe('form submission', () => {
  it('calls onSearch with date, timeFrom, timeTo in time mode', () => {
    const onSearch = vi.fn()
    render(<SearchForm city="london" onSearch={onSearch} loading={false} />)

    fireEvent.change(screen.getByLabelText('From'), { target: { value: '18:00' } })
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '21:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search Films' }))

    expect(onSearch).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: 'time',
        timeFrom: '18:00',
        timeTo: '21:00',
        filmTitle: null,
        cinemaId: null,
        format: null,
      })
    )
  })

  it('calls onSearch with filmTitle in film mode when free text entered', () => {
    const onSearch = vi.fn()
    render(<SearchForm city="london" onSearch={onSearch} loading={false} />)

    fireEvent.click(screen.getByRole('button', { name: 'Film' }))
    fireEvent.change(screen.getByLabelText('Film title'), { target: { value: 'Nosferatu' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search Films' }))

    expect(onSearch).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: 'film',
        filmTitle: 'Nosferatu',
        cinemaId: null,
        format: null,
      })
    )
  })

  it('passes null filmTitle in time mode even if film input was typed earlier', () => {
    const onSearch = vi.fn()
    render(<SearchForm city="london" onSearch={onSearch} loading={false} />)

    // Switch to film, type something, switch back to time
    fireEvent.click(screen.getByRole('button', { name: 'Film' }))
    fireEvent.change(screen.getByLabelText('Film title'), { target: { value: 'Nosferatu' } })
    fireEvent.click(screen.getByRole('button', { name: 'Time' }))
    fireEvent.click(screen.getByRole('button', { name: 'Search Films' }))

    expect(onSearch).toHaveBeenCalledWith(
      expect.objectContaining({ mode: 'time', filmTitle: null })
    )
  })

  it('passes null format in time mode', () => {
    const onSearch = vi.fn()
    render(<SearchForm city="london" onSearch={onSearch} loading={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'Search Films' }))
    expect(onSearch).toHaveBeenCalledWith(expect.objectContaining({ format: null }))
  })

  it('passes selected format in format mode', () => {
    const onSearch = vi.fn()
    render(<SearchForm city="london" onSearch={onSearch} loading={false} />)

    fireEvent.click(screen.getByRole('button', { name: 'Format' }))
    fireEvent.change(screen.getByLabelText('Format'), { target: { value: '35mm' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search Films' }))

    expect(onSearch).toHaveBeenCalledWith(
      expect.objectContaining({ mode: 'format', format: '35mm' })
    )
  })
})

// ---------------------------------------------------------------------------
// Cinema filtering
// ---------------------------------------------------------------------------

describe('cinema filtering', () => {
  it('fetches cinemas for the given city on mount', async () => {
    render(<SearchForm city="brighton" onSearch={vi.fn()} loading={false} />)
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('city=brighton')
      )
    })
  })

  it('filters cinemas by typed text', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => [
        { id: 'bfi', name: 'BFI Southbank', city: 'london', address: '', postcode: '', latitude: null, longitude: null, website: null, has_online_booking: true, supports_availability_check: false },
        { id: 'curzon', name: 'Curzon Soho', city: 'london', address: '', postcode: '', latitude: null, longitude: null, website: null, has_online_booking: true, supports_availability_check: false },
      ],
    } as Response)

    render(<SearchForm city="london" onSearch={vi.fn()} loading={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'Cinema' }))

    await waitFor(() => expect(mockFetch).toHaveBeenCalled())

    const input = screen.getByLabelText('Cinema')
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: 'BFI' } })

    await waitFor(() => {
      expect(screen.getByText('BFI Southbank')).toBeInTheDocument()
      expect(screen.queryByText('Curzon Soho')).not.toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Format mode — live change callback
// ---------------------------------------------------------------------------

describe('format live change', () => {
  it('calls onLiveFormatChange when format select changes', () => {
    const onLiveFormatChange = vi.fn()
    render(
      <SearchForm city="london" onSearch={vi.fn()} onLiveFormatChange={onLiveFormatChange} loading={false} />
    )
    fireEvent.click(screen.getByRole('button', { name: 'Format' }))
    fireEvent.change(screen.getByLabelText('Format'), { target: { value: '35mm' } })
    expect(onLiveFormatChange).toHaveBeenCalledWith('35mm', 'today')
  })

  it('calls onLiveFormatChange when period button is clicked', () => {
    const onLiveFormatChange = vi.fn()
    render(
      <SearchForm city="london" onSearch={vi.fn()} onLiveFormatChange={onLiveFormatChange} loading={false} />
    )
    fireEvent.click(screen.getByRole('button', { name: 'Format' }))
    fireEvent.click(screen.getByRole('button', { name: 'This week' }))
    expect(onLiveFormatChange).toHaveBeenCalledWith(null, 'week')
  })
})
