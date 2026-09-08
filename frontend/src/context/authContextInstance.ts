import { createContext } from 'react'
import type { User } from '../types'

export interface AuthContextValue {
  user: User | null
  isLoading: boolean
  error: string | null
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string) => Promise<void>
  logout: () => void
  /** Patch the current user in place — used after an API call (e.g. linking
   * Letterboxd) returns an updated user object, without a full re-login. */
  updateUser: (user: User) => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)
