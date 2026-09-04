import { motion } from 'framer-motion'
import {
  AlertTriangle,
  BadgeDollarSign,
  GraduationCap,
  Receipt,
  TrendingUp,
  Users,
  Wallet,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import client from '../api/client'
import { ErrorBanner, KpiCard, Spinner, StatusBadge } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const money = (v) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(Number(v || 0))

export default function Dashboard() {
  const { user } = useAuth()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [data, setData] = useState({
    students: { total: 0 },
    finance: null,
    payments: [],
    revenue: [],
  })

  useEffect(() => {
    let active = true
    Promise.all([
      client.get('/students', { params: { page: 1, page_size: 1 } }),
      client.get('/finance/summary'),
      client.get('/finance/payments', { params: { limit: 6 } }),
      client.get('/finance/revenue/monthly'),
    ])
      .then(([students, finance, payments, revenue]) => {
        if (!active) return
        setData({
          students: students.data,
          finance: finance.data,
          payments: payments.data,
          revenue: revenue.data,
        })
      })
      .catch((err) => active && setError(err.message))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [])

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-brand-600">
        <Spinner className="h-8 w-8" />
      </div>
    )
  }

  const f = data.finance
  const maxRevenue = Math.max(
    1,
    ...data.revenue.flatMap((r) => [Number(r.billed), Number(r.collected)]),
  )

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-extrabold tracking-tight text-slate-900">
          Welcome back, {user?.full_name?.split(' ')[0] ?? 'there'} 👋
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Here's what's happening across your school today.
        </p>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* KPI cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          icon={Users}
          label="Enrolled Students"
          value={data.students.total}
          sub="Active directory records"
          accent="brand"
          delay={0}
        />
        <KpiCard
          icon={BadgeDollarSign}
          label="Total Billed"
          value={money(f?.total_billed)}
          sub={`${f?.invoices_total ?? 0} invoices issued`}
          accent="violet"
          delay={0.06}
        />
        <KpiCard
          icon={Wallet}
          label="Collected"
          value={money(f?.total_collected)}
          sub={`${f?.collection_rate ?? 0}% collection rate`}
          accent="emerald"
          delay={0.12}
        />
        <KpiCard
          icon={AlertTriangle}
          label="Outstanding"
          value={money(f?.total_outstanding)}
          sub={`${money(f?.total_overdue)} overdue`}
          accent="rose"
          delay={0.18}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        {/* Revenue chart */}
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.4 }}
          className="glass-panel p-6 lg:col-span-3"
        >
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h3 className="flex items-center gap-2 text-base font-bold text-slate-900">
                <TrendingUp className="h-4 w-4 text-brand-600" />
                Revenue — last 6 months
              </h3>
              <p className="text-xs text-slate-500">Billed vs collected</p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-brand-500" /> Billed
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" /> Collected
              </span>
            </div>
          </div>

          <div className="flex h-52 items-end gap-3 sm:gap-5">
            {data.revenue.map((row, i) => (
              <div key={row.month} className="flex flex-1 flex-col items-center gap-2">
                <div className="flex h-44 w-full items-end justify-center gap-1.5">
                  <motion.div
                    initial={{ height: 0 }}
                    animate={{ height: `${(Number(row.billed) / maxRevenue) * 100}%` }}
                    transition={{ delay: 0.25 + i * 0.06, duration: 0.5, ease: 'easeOut' }}
                    className="w-1/2 rounded-t-md bg-gradient-to-t from-brand-600 to-brand-400"
                    title={`Billed: ${money(row.billed)}`}
                  />
                  <motion.div
                    initial={{ height: 0 }}
                    animate={{ height: `${(Number(row.collected) / maxRevenue) * 100}%` }}
                    transition={{ delay: 0.3 + i * 0.06, duration: 0.5, ease: 'easeOut' }}
                    className="w-1/2 rounded-t-md bg-gradient-to-t from-emerald-600 to-emerald-400"
                    title={`Collected: ${money(row.collected)}`}
                  />
                </div>
                <span className="text-[10px] font-medium uppercase text-slate-400">
                  {row.month.slice(5)}
                </span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Recent payments */}
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.26, duration: 0.4 }}
          className="glass-panel p-6 lg:col-span-2"
        >
          <h3 className="mb-4 flex items-center gap-2 text-base font-bold text-slate-900">
            <Receipt className="h-4 w-4 text-emerald-600" />
            Recent payments
          </h3>
          {data.payments.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-400">
              No payments recorded yet.
            </p>
          ) : (
            <ul className="space-y-3">
              {data.payments.map((p, i) => (
                <motion.li
                  key={p.id}
                  initial={{ opacity: 0, x: 14 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.3 + i * 0.05 }}
                  className="flex items-center gap-3 rounded-xl bg-white/60 p-3"
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-100 text-emerald-600">
                    <GraduationCap className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-slate-800">
                      {p.receipt_no}
                    </p>
                    <p className="text-xs text-slate-500">
                      {new Date(p.paid_at).toLocaleDateString()} · {p.method.replace('_', ' ')}
                    </p>
                  </div>
                  <span className="text-sm font-bold text-emerald-600">
                    {money(p.amount)}
                  </span>
                </motion.li>
              ))}
            </ul>
          )}
        </motion.div>
      </div>

      {/* Quick status strip */}
      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.32, duration: 0.4 }}
        className="glass-panel flex flex-wrap items-center gap-x-8 gap-y-3 p-5"
      >
        <span className="text-sm font-semibold text-slate-700">System status:</span>
        <StatusBadge status="active" />
        <span className="text-xs text-slate-500">
          Signed in as <strong className="text-slate-700">{user?.email}</strong> · role{' '}
          <strong className="capitalize text-slate-700">{user?.role}</strong>
        </span>
      </motion.div>
    </div>
  )
}
