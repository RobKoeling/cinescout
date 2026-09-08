import { getToken } from './tokenStorage'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Dispatched whenever an authenticated request comes back 401, so AuthContext
// can clear its state without every call site needing to know about auth.
export const AUTH_EXPIRED_EVENT = 'cinescout:auth-expired'

export class ApiError extends Error {
  status: number
  body?: unknown

  constructor(message: string, status: number, body?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

interface ApiFetchOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  /** Attach the stored Authorization header. Defaults to true. */
  auth?: boolean
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { body, auth = true, headers, ...rest } = options

  const finalHeaders: Record<string, string> = {
    ...(headers as Record<string, string> | undefined),
  }
  if (body !== undefined) {
    finalHeaders['Content-Type'] = 'application/json'
  }
  if (auth) {
    const token = getToken()
    if (token) {
      finalHeaders['Authorization'] = `Bearer ${token}`
    }
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (response.status === 401) {
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`
    let parsedBody: unknown
    try {
      parsedBody = await response.json()
      if (
        parsedBody &&
        typeof parsedBody === 'object' &&
        'detail' in parsedBody &&
        typeof (parsedBody as { detail?: unknown }).detail === 'string'
      ) {
        message = (parsedBody as { detail: string }).detail
      }
    } catch {
      // Response body wasn't JSON — keep the default message.
    }
    throw new ApiError(message, response.status, parsedBody)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}
