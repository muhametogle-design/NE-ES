import axios from 'axios'

/**
 * Centralized Axios instance.
 *
 *  • Base URL is "/api" (same-origin); Vite proxies /api -> FastAPI :8000 in
 *    dev, and in production the reverse container serves both on one origin.
 *  • Every request automatically gets `Authorization: Bearer <token>` when a
 *    token is present in localStorage.
 *  • A response interceptor catches 401s, clears the stale session and
 *    redirects to /login (except for the login call itself).
 */
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export const TOKEN_KEY = 'ne_emis_token'
export const USER_KEY = 'ne_emis_user'

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ---------------------------------------------------------------------------
// Request interceptor — attach Bearer token
// ---------------------------------------------------------------------------
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// ---------------------------------------------------------------------------
// Response interceptor — normalize errors + handle expired sessions
// ---------------------------------------------------------------------------
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const { response, config } = error

    if (response?.status === 401 && !config?.url?.includes('/auth/login')) {
      // Token expired/invalid — drop session and bounce to login.
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      if (!window.location.pathname.startsWith('/login')) {
        window.location.assign('/login?expired=1')
      }
    }

    // Normalize error message for the UI.
    const detail =
      response?.data?.detail ||
      response?.data?.message ||
      error.message ||
      'Network error — please check the API server.'
    return Promise.reject(
      Object.assign(new Error(detail), { status: response?.status, data: response?.data }),
    )
  },
)

export default client
