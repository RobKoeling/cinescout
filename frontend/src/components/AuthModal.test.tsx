import { screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import AuthModal from './AuthModal'
import { renderWithAuth } from '../test/authTestUtils'

afterEach(() => {
  vi.clearAllMocks()
})

// The mode-toggle tab and the footer submit button share the same label
// text ("Log in" / "Sign up"), so tests target the submit button by its
// `type="submit"` attribute rather than by accessible name.
function getSubmitButton(container: HTMLElement): HTMLButtonElement {
  const button = container.querySelector('button[type="submit"]')
  if (!button) throw new Error('submit button not found')
  return button as HTMLButtonElement
}

describe('AuthModal', () => {
  it('renders login mode by default with no confirm-password field', () => {
    const { container } = renderWithAuth(<AuthModal mode="login" onClose={vi.fn()} />)

    expect(getSubmitButton(container)).toHaveTextContent('Log in')
    expect(screen.queryByLabelText('Confirm password')).not.toBeInTheDocument()
  })

  it('toggling to signup shows the confirm-password field', () => {
    const { container } = renderWithAuth(<AuthModal mode="login" onClose={vi.fn()} />)

    // At this point only the header tab says "Sign up" (footer still says "Log in").
    fireEvent.click(screen.getByText('Sign up'))
    expect(screen.getByLabelText('Confirm password')).toBeInTheDocument()
    expect(getSubmitButton(container)).toHaveTextContent('Sign up')
  })

  it('submitting login calls useAuth().login with entered values', async () => {
    const { container, authValue } = renderWithAuth(<AuthModal mode="login" onClose={vi.fn()} />)

    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'alice' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } })
    fireEvent.click(getSubmitButton(container))

    await waitFor(() => {
      expect(authValue.login).toHaveBeenCalledWith('alice', 'password123')
    })
  })

  it('submitting signup with mismatched passwords shows an error and does not call register', async () => {
    const { container, authValue } = renderWithAuth(<AuthModal mode="signup" onClose={vi.fn()} />)

    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'alice' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } })
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'different' } })
    fireEvent.click(getSubmitButton(container))

    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument()
    expect(authValue.register).not.toHaveBeenCalled()
  })

  it('shows the error message when login rejects', async () => {
    const onClose = vi.fn()
    const { container, authValue } = renderWithAuth(<AuthModal mode="login" onClose={onClose} />)
    ;(authValue.login as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error('Invalid username or password')
    )

    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'alice' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong-pass' } })
    fireEvent.click(getSubmitButton(container))

    expect(await screen.findByText('Invalid username or password')).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('calls onClose after a successful login', async () => {
    const onClose = vi.fn()
    const { container } = renderWithAuth(<AuthModal mode="login" onClose={onClose} />)

    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'alice' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } })
    fireEvent.click(getSubmitButton(container))

    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('closes on Escape key', () => {
    const onClose = vi.fn()
    renderWithAuth(<AuthModal mode="login" onClose={onClose} />)

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })
})
