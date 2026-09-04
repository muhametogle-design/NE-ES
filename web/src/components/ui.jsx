import { motion, AnimatePresence } from 'framer-motion'
import { AlertCircle, X } from 'lucide-react'
import { useEffect } from 'react'

/** Reusable animated KPI / stat card with glassmorphism styling. */
export function KpiCard({ icon: Icon, label, value, sub, accent = 'brand', delay = 0 }) {
  const accents = {
    brand: 'from-brand-600 to-brand-400 shadow-brand-500/30',
    emerald: 'from-emerald-600 to-emerald-400 shadow-emerald-500/30',
    amber: 'from-amber-500 to-amber-400 shadow-amber-500/30',
    rose: 'from-rose-600 to-rose-400 shadow-rose-500/30',
    violet: 'from-violet-600 to-violet-400 shadow-violet-500/30',
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: 'easeOut' }}
      whileHover={{ scale: 1.02, y: -4 }}
      whileTap={{ scale: 0.985 }}
      className="glass-panel glass-panel-hover cursor-default p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            {label}
          </p>
          <p className="mt-2 truncate text-2xl font-extrabold tracking-tight text-slate-900">
            {value}
          </p>
          {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
        </div>
        <div
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-lg ${accents[accent]}`}
        >
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </motion.div>
  )
}

/** Modal shell with backdrop blur, spring entrance and ESC-to-close. */
export function Modal({ open, onClose, title, children, wide = false }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    if (open) window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, y: 40, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 30, scale: 0.98 }}
            transition={{ type: 'spring', damping: 26, stiffness: 300 }}
            className={`glass-panel relative z-10 max-h-[92vh] w-full overflow-y-auto rounded-b-none rounded-t-3xl p-6 sm:rounded-2xl ${
              wide ? 'sm:max-w-2xl' : 'sm:max-w-lg'
            }`}
          >
            <div className="mb-5 flex items-center justify-between gap-4">
              <h3 className="text-lg font-bold tracking-tight text-slate-900">{title}</h3>
              <button
                onClick={onClose}
                className="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}

/** Inline error banner. */
export function ErrorBanner({ message, onDismiss }) {
  if (!message) return null
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-4 flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50/90 px-4 py-3 text-sm text-rose-700"
    >
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <span className="flex-1">{message}</span>
      {onDismiss && (
        <button onClick={onDismiss} className="text-rose-500 hover:text-rose-700">
          <X className="h-4 w-4" />
        </button>
      )}
    </motion.div>
  )
}

/** Small loading spinner. */
export function Spinner({ className = 'h-5 w-5' }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none">
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-90"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}

/** Status pill mapping canonical statuses to badge colors. */
export function StatusBadge({ status }) {
  const map = {
    active: 'badge-green',
    paid: 'badge-green',
    inactive: 'badge-slate',
    void: 'badge-slate',
    draft: 'badge-slate',
    graduated: 'badge-blue',
    issued: 'badge-blue',
    partial: 'badge-amber',
    suspended: 'badge-amber',
    overdue: 'badge-red',
  }
  const cls = map[status] || 'badge-slate'
  return <span className={cls}>{status?.replace('_', ' ')}</span>
}

/** Empty state placeholder for tables/lists. */
export function EmptyState({ icon: Icon, title, hint }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
        <Icon className="h-7 w-7" />
      </div>
      <p className="text-sm font-semibold text-slate-700">{title}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  )
}
