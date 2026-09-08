import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import ManualLogModal from './ManualLogModal'

const mockFetch = vi.fn()
global.fetch = mockFetch

afterEach(() => {
  vi.clearAllMocks()
})

function mockResponse(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

describe('ManualLogModal', () => {
  it('date input defaults to today', () => {
    const today = new Date().toISOString().split('T')[0]
    render(<ManualLogModal onClose={vi.fn()} />)
    expect(screen.getByLabelText('Date watched')).toHaveValue(today)
  })

  it('submit is disabled until a film is selected', () => {
    render(<ManualLogModal onClose={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Log as watched' })).toBeDisabled()
  })

  it('debounced search calls /api/films/search without a city param and lists suggestions', async () => {
    vi.useFakeTimers()
    mockFetch.mockResolvedValueOnce(
      mockResponse([{ id: 'nosferatu-2024', title: 'Nosferatu', year: 2024 }])
    )
    render(<ManualLogModal onClose={vi.fn()} />)

    fireEvent.change(screen.getByLabelText('Film'), { target: { value: 'Nosfera' } })
    await vi.advanceTimersByTimeAsync(250)
    vi.useRealTimers()

    expect(mockFetch).toHaveBeenCalled()
    const [url] = mockFetch.mock.calls[0]
    expect(url).toContain('/api/films/search?q=Nosfera')
    expect(url).not.toContain('city')

    expect(screen.getByText('Nosferatu')).toBeInTheDocument()
  })

  it('selecting a suggestion enables submit and calls createManualWatchLog with film_id and date', async () => {
    vi.useFakeTimers()
    mockFetch.mockResolvedValueOnce(
      mockResponse([{ id: 'nosferatu-2024', title: 'Nosferatu', year: 2024 }])
    )
    render(<ManualLogModal onClose={vi.fn()} />)

    fireEvent.change(screen.getByLabelText('Film'), { target: { value: 'Nosfera' } })
    await vi.advanceTimersByTimeAsync(250)
    vi.useRealTimers()

    fireEvent.mouseDown(screen.getByText('Nosferatu'))
    expect(screen.getByRole('button', { name: 'Log as watched' })).toBeEnabled()

    mockFetch.mockResolvedValueOnce(
      mockResponse({
        id: 1, film_id: 'nosferatu-2024', showing_id: null, watched_date: '2026-01-01',
        rating: null, comment: null, created_at: '2026-01-01T00:00:00Z',
      })
    )
    fireEvent.change(screen.getByLabelText('Date watched'), { target: { value: '2026-01-01' } })
    fireEvent.click(screen.getByRole('button', { name: 'Log as watched' }))

    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2))
    const [, options] = mockFetch.mock.calls[1]
    const body = JSON.parse(options.body)
    expect(body).toMatchObject({ film_id: 'nosferatu-2024', watched_date: '2026-01-01' })
  })

  it('closes on Escape key', () => {
    const onClose = vi.fn()
    render(<ManualLogModal onClose={onClose} />)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })
})
