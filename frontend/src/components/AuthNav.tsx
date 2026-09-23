import { useAuth } from '../hooks/useAuth'

interface AuthNavProps {
  onOpenAuth: (mode: 'login' | 'signup') => void
  onOpenProfile?: () => void
}

function AuthNav({ onOpenAuth, onOpenProfile }: AuthNavProps) {
  const { user, logout } = useAuth()

  if (!user) {
    return (
      <button
        onClick={() => onOpenAuth('login')}
        className="text-sm font-medium text-gold-dark hover:text-ink transition-colors"
      >
        Log in
      </button>
    )
  }

  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="text-gray-700">{user.username}</span>
      {onOpenProfile && (
        <button
          onClick={onOpenProfile}
          className="font-medium text-gold-dark hover:text-ink transition-colors"
        >
          My Diary
        </button>
      )}
      <button
        onClick={logout}
        className="font-medium text-gray-500 hover:text-gray-700 transition-colors"
      >
        Log out
      </button>
    </div>
  )
}

export default AuthNav
