import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { vi } from 'vitest'
import { AuthContext } from '../context/authContextInstance'
import type { AuthContextValue } from '../context/authContextInstance'
import type { User } from '../types'

interface RenderWithAuthOptions {
  user?: User | null
  isLoading?: boolean
  error?: string | null
}

/**
 * Render a component wrapped in a test-only AuthContext.Provider, so tests
 * don't need to exercise a real GET /api/auth/me call on mount.
 */
export function renderWithAuth(ui: ReactElement, options: RenderWithAuthOptions = {}) {
  const value: AuthContextValue = {
    user: options.user ?? null,
    isLoading: options.isLoading ?? false,
    error: options.error ?? null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    updateUser: vi.fn(),
  }

  const result = render(<AuthContext.Provider value={value}>{ui}</AuthContext.Provider>)
  return { ...result, authValue: value }
}

export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 1,
    username: 'alice',
    letterboxd_username: null,
    letterboxd_last_synced_at: null,
    ...overrides,
  }
}
