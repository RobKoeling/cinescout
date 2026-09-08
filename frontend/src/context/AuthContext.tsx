import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import * as authApi from '../api/auth'
import { AUTH_EXPIRED_EVENT } from '../api/client'
import { clearToken, getToken, setToken } from '../api/tokenStorage'
import type { User } from '../types'
import { AuthContext } from './authContextInstance'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const token = getToken()
    if (!token) {
      setIsLoading(false)
      return
    }
    authApi
      .fetchMe()
      .then(setUser)
      .catch(() => {
        clearToken()
        setUser(null)
      })
      .finally(() => setIsLoading(false))
  }, [])

  useEffect(() => {
    const onAuthExpired = () => {
      clearToken()
      setUser(null)
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, onAuthExpired)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onAuthExpired)
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    setError(null)
    try {
      const response = await authApi.login(username, password)
      setToken(response.access_token)
      setUser(response.user)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
      throw err
    }
  }, [])

  const register = useCallback(async (username: string, password: string) => {
    setError(null)
    try {
      const response = await authApi.register(username, password)
      setToken(response.access_token)
      setUser(response.user)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
      throw err
    }
  }, [])

  const logout = useCallback(() => {
    clearToken()
    setUser(null)
  }, [])

  const updateUser = useCallback((updated: User) => {
    setUser(updated)
  }, [])

  return (
    <AuthContext.Provider value={{ user, isLoading, error, login, register, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  )
}
