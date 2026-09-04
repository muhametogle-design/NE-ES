import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import client, { TOKEN_KEY, USER_KEY } from '../api/client'

const AuthContext = createContext(null)

/**
 * Authentication state provider.
 *
 * Exposes:
 *   user        — cached user profile (or null)
 *   token       — JWT string (or null)
 *   isAuthenticated
 *   login(email, password)  -> user
 *   logout()
 *   refreshMe()             -> re-fetches /auth/me
 */
export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem(USER_KEY)
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  })

  const login = useCallback(async (email, password) => {
    // OAuth2 password flow expects form-encoded data.
    const form = new URLSearchParams()
    form.append('username', email)
    form.append('password', password)

    const { data } = await client.post('/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })

    localStorage.setItem(TOKEN_KEY, data.access_token)
    localStorage.setItem(USER_KEY, JSON.stringify(data.user))
    setToken(data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUser(null)
  }, [])

  const refreshMe = useCallback(async () => {
    const { data } = await client.get('/auth/me')
    localStorage.setItem(USER_KEY, JSON.stringify(data))
    setUser(data)
    return data
  }, [])

  const value = useMemo(
    () => ({
      user,
      token,
      isAuthenticated: Boolean(token),
      login,
      logout,
      refreshMe,
    }),
    [user, token, login, logout, refreshMe],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used inside <AuthProvider>')
  }
  return ctx
}

export default AuthContext
