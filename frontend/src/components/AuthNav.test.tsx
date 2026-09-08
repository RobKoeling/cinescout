import { screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import AuthNav from './AuthNav'
import { renderWithAuth, makeUser } from '../test/authTestUtils'

describe('AuthNav', () => {
  it('shows a Log in button when logged out', () => {
    const onOpenAuth = vi.fn()
    renderWithAuth(<AuthNav onOpenAuth={onOpenAuth} />, { user: null })

    const button = screen.getByRole('button', { name: 'Log in' })
    fireEvent.click(button)
    expect(onOpenAuth).toHaveBeenCalledWith('login')
  })

  it('shows the username and does not render My Diary when onOpenProfile is omitted', () => {
    renderWithAuth(<AuthNav onOpenAuth={vi.fn()} />, { user: makeUser({ username: 'bob' }) })

    expect(screen.getByText('bob')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'My Diary' })).not.toBeInTheDocument()
  })

  it('calls onOpenProfile when My Diary is clicked', () => {
    const onOpenProfile = vi.fn()
    renderWithAuth(<AuthNav onOpenAuth={vi.fn()} onOpenProfile={onOpenProfile} />, {
      user: makeUser(),
    })

    fireEvent.click(screen.getByRole('button', { name: 'My Diary' }))
    expect(onOpenProfile).toHaveBeenCalled()
  })

  it('calls logout when Log out is clicked', () => {
    const { authValue } = renderWithAuth(<AuthNav onOpenAuth={vi.fn()} />, { user: makeUser() })

    fireEvent.click(screen.getByRole('button', { name: 'Log out' }))
    expect(authValue.logout).toHaveBeenCalled()
  })
})
