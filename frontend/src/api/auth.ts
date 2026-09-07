import { apiFetch } from './client'
import type { AuthResponse, User } from '../types'

export async function register(username: string, password: string): Promise<AuthResponse> {
  return apiFetch<AuthResponse>('/api/auth/register', {
    method: 'POST',
    body: { username, password },
    auth: false,
  })
}

export async function login(username: string, password: string): Promise<AuthResponse> {
  return apiFetch<AuthResponse>('/api/auth/login', {
    method: 'POST',
    body: { username, password },
    auth: false,
  })
}

export async function fetchMe(): Promise<User> {
  return apiFetch<User>('/api/auth/me')
}
