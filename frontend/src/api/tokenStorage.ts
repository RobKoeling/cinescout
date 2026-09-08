// Shared localStorage helper for the auth token, used by both the API client
// (to attach the Authorization header) and AuthContext (to hydrate on load),
// without either module needing to import the other.

export const TOKEN_STORAGE_KEY = 'cinescout_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY)
}
