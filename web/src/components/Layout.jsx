import { useState } from 'react'
import {
  BarChart3,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Menu,
  Wallet,
  X,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/students', label: 'Students', icon: GraduationCap },
  { to: '/finance', label: 'Finance', icon: Wallet },
]

function Brand() {
  return (
    <div className="flex items-center gap-3 px-2">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-600 to-brand-400 text-white shadow-lg shadow-brand-500/30">
        <GraduationCap className="h-6 w-6" />
      </div>
      <div className="leading-tight">
        <p className="text-base font-extrabold tracking-tight text-slate-900">
          NE-EMIS
        </p>
        <p className="text-[11px] font-medium text-slate-500">
          Education Management
        </p>
      </div>
    </div>
  )
}

function SidebarContent({ onNavigate }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex h-full flex-col">
      <div className="py-6">
        <Brand />
      </div>

      <nav className="flex-1 space-y-1.5 px-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            className={({ isActive }) =>
              [
                'group flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-all duration-200',
                isActive
                  ? 'bg-gradient-to-r from-brand-600 to-brand-500 text-white shadow-md shadow-brand-500/30'
                  : 'text-slate-600 hover:bg-white/80 hover:text-brand-700',
              ].join(' ')
            }
          >
            <Icon className="h-[18px] w-[18px] transition-transform duration-200 group-hover:scale-110" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/60 p-4">
        <div className="mb-3 flex items-center gap-3 rounded-xl bg-white/60 p-3 backdrop-blur-sm">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-sm font-bold text-brand-700">
            {user?.full_name?.charAt(0)?.toUpperCase() ?? 'U'}
          </div>
          <div className="min-w-0 flex-1 leading-tight">
            <p className="truncate text-sm font-semibold text-slate-800">
              {user?.full_name ?? 'User'}
            </p>
            <p className="truncate text-xs text-slate-500">{user?.email}</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-rose-200 bg-rose-50/70 px-3 py-2.5 text-sm font-medium text-rose-600 transition-all duration-200 hover:bg-rose-100"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
        <p className="mt-3 flex items-center justify-center gap-1.5 text-[11px] text-slate-400">
          <BarChart3 className="h-3 w-3" /> NE-EMIS v1.0
        </p>
      </div>
    </div>
  )
}

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="min-h-screen lg:pl-72">
      {/* Desktop sidebar — fixed glass panel */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 border-r border-white/60 bg-white/70 backdrop-blur-xl lg:block">
        <SidebarContent />
      </aside>

      {/* Mobile sidebar */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
              className="fixed inset-0 z-40 bg-slate-900/30 backdrop-blur-sm lg:hidden"
            />
            <motion.aside
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', damping: 28, stiffness: 260 }}
              className="fixed inset-y-0 left-0 z-50 w-72 border-r border-white/60 bg-white/90 backdrop-blur-xl lg:hidden"
            >
              <button
                onClick={() => setMobileOpen(false)}
                className="absolute right-3 top-5 rounded-lg p-1.5 text-slate-500 hover:bg-slate-100"
                aria-label="Close menu"
              >
                <X className="h-5 w-5" />
              </button>
              <SidebarContent onNavigate={() => setMobileOpen(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Main column */}
      <div className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-white/60 bg-white/70 px-4 py-3 backdrop-blur-md lg:px-8">
          <button
            onClick={() => setMobileOpen(true)}
            className="rounded-lg p-2 text-slate-600 hover:bg-white/80 lg:hidden"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex-1">
            <h1 className="text-lg font-bold tracking-tight text-slate-900">
              School Operations Console
            </h1>
            <p className="hidden text-xs text-slate-500 sm:block">
              Students, billing and performance at a glance
            </p>
          </div>
        </header>

        <main className="flex-1 px-4 py-6 lg:px-8 lg:py-8">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: 'easeOut' }}
          >
            <Outlet />
          </motion.div>
        </main>
      </div>
    </div>
  )
}
