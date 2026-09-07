import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { apiFetch, ApiError, AUTH_EXPIRED_EVENT } from './client'
import { clearToken, setToken } from './tokenStorage'

const mockFetch = vi.fn()
global.fetch = mockFetch

function mockResponse(body: unknown, init: { status?: number; ok?: boolean } = {}) {
  const status = init.status ?? 200
  return {
    ok: init.ok ?? (status >= 200 && status < 300),
    status,
    json: async () => body,
  }
}

beforeEach(() => {
  clearToken()
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('apiFetch', () => {
  it('attaches the Authorization header when a token is stored', async () => {
    setToken('my-token')
    mockFetch.mockResolvedValueOnce(mockResponse({ ok: true }))

    await apiFetch('/api/whatever')

    const [, options] = mockFetch.mock.calls[0]
    expect(options.headers['Authorization']).toBe('Bearer my-token')
  })

  it('omits the Authorization header when auth: false', async () => {
    setToken('my-token')
    mockFetch.mockResolvedValueOnce(mockResponse({ ok: true }))

    await apiFetch('/api/whatever', { auth: false })

    const [, options] = mockFetch.mock.calls[0]
    expect(options.headers['Authorization']).toBeUndefined()
  })

  it('omits the Authorization header when no token is stored', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse({ ok: true }))

    await apiFetch('/api/whatever')

    const [, options] = mockFetch.mock.calls[0]
    expect(options.headers['Authorization']).toBeUndefined()
  })

  it('stringifies the body and sets Content-Type when a body is given', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse({ ok: true }))

    await apiFetch('/api/whatever', { method: 'POST', body: { a: 1 } })

    const [, options] = mockFetch.mock.calls[0]
    expect(options.body).toBe(JSON.stringify({ a: 1 }))
    expect(options.headers['Content-Type']).toBe('application/json')
  })

  it('throws ApiError with the parsed detail message on a non-2xx response', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse({ detail: 'Invalid username or password' }, { status: 401 }))

    await expect(apiFetch('/api/whatever')).rejects.toMatchObject({
      message: 'Invalid username or password',
      status: 401,
    })
  })

  it('dispatches the auth-expired event on a 401 response', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse({ detail: 'Not authenticated' }, { status: 401 }))
    const handler = vi.fn()
    window.addEventListener(AUTH_EXPIRED_EVENT, handler)

    await expect(apiFetch('/api/whatever')).rejects.toBeInstanceOf(ApiError)
    expect(handler).toHaveBeenCalled()

    window.removeEventListener(AUTH_EXPIRED_EVENT, handler)
  })

  it('returns undefined for a 204 No Content response', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, status: 204, json: async () => { throw new Error('no body') } })

    const result = await apiFetch('/api/whatever')
    expect(result).toBeUndefined()
  })
})
