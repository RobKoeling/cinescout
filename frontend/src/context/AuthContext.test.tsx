import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { AuthProvider } from './AuthContext'
import { useAuth } from '../hooks/useAuth'
import { AUTH_EXPIRED_EVENT } from '../api/client'
import { TOKEN_STORAGE_KEY } from '../api/tokenStorage'

const mockFetch = vi.fn()
global.fetch = mockFetch

function mockResponse(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

const USER = { id: 1, username: 'alice', letterboxd_username: null, letterboxd_last_synced_at: null }

function Probe() {
  const { user, isLoading, error, login, register, logout } = useAuth()
  return (
    <div>
      <div data-testid="loading">{String(isLoading)}</div>
      <div data-testid="user">{user ? user.username : 'none'}</div>
      <div data-testid="error">{error ?? 'none'}</div>
      <button onClick={() => login('alice', 'password123').catch(() => {})}>do-login</button>
      <button onClick={() => register('alice', 'password123').catch(() => {})}>do-register</button>
      <button onClick={logout}>do-logout</button>
    </div>
  )
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('AuthProvider', () => {
  it('starts logged out with isLoading false when no token is stored', async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )

    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))
    expect(screen.getByTestId('user')).toHaveTextContent('none')
  })

  it('hydrates the user from a stored token via GET /auth/me', async () => {
    localStorage.setItem(TOKEN_STORAGE_KEY, 'stored-token')
    mockFetch.mockResolvedValueOnce(mockResponse(USER))

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )

    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('alice'))
    expect(screen.getByTestId('loading')).toHaveTextContent('false')
  })

  it('clears a stored token when hydration returns 401', async () => {
    localStorage.setItem(TOKEN_STORAGE_KEY, 'stale-token')
    mockFetch.mockResolvedValueOnce(mockResponse({ detail: 'Not authenticated' }, 401))

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )

    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('none'))
    expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull()
  })

  it('login populates user and stores the token', async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse({ access_token: 'new-token', token_type: 'bearer', user: USER })
    )

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))

    fireEvent.click(screen.getByText('do-login'))

    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('alice'))
    expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBe('new-token')
  })

  it('login failure sets error and leaves user logged out', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse({ detail: 'Invalid username or password' }, 401))

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))

    fireEvent.click(screen.getByText('do-login'))

    await waitFor(() =>
      expect(screen.getByTestId('error')).toHaveTextContent('Invalid username or password')
    )
    expect(screen.getByTestId('user')).toHaveTextContent('none')
  })

  it('register populates user and stores the token', async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse({ access_token: 'new-token', token_type: 'bearer', user: USER })
    )

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))

    fireEvent.click(screen.getByText('do-register'))

    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('alice'))
  })

  it('logout clears user and stored token', async () => {
    localStorage.setItem(TOKEN_STORAGE_KEY, 'stored-token')
    mockFetch.mockResolvedValueOnce(mockResponse(USER))

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )
    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('alice'))

    fireEvent.click(screen.getByText('do-logout'))

    expect(screen.getByTestId('user')).toHaveTextContent('none')
    expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull()
  })

  it('clears state when the auth-expired event fires', async () => {
    localStorage.setItem(TOKEN_STORAGE_KEY, 'stored-token')
    mockFetch.mockResolvedValueOnce(mockResponse(USER))

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )
    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('alice'))

    act(() => {
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
    })

    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('none'))
    expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull()
  })
})
