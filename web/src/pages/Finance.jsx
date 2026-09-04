import { motion } from 'framer-motion'
import {
  AlertTriangle,
  BadgeDollarSign,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  FileText,
  Loader2,
  Plus,
  Receipt,
  Search,
  Wallet,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import client from '../api/client'
import {
  EmptyState,
  ErrorBanner,
  KpiCard,
  Modal,
  Spinner,
  StatusBadge,
} from '../components/ui.jsx'

const money = (v) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(Number(v || 0))

const FEE_TYPES = ['tuition', 'registration', 'examination', 'transport', 'meals', 'library', 'other']
const PAYMENT_METHODS = ['cash', 'bank_transfer', 'card', 'mobile_money', 'cheque']

export default function Finance() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [summary, setSummary] = useState(null)
  const [invoices, setInvoices] = useState([])
  const [meta, setMeta] = useState({ total: 0, page: 1, pages: 1 })
  const [students, setStudents] = useState([])

  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')

  const [invoiceModal, setInvoiceModal] = useState(false)
  const [paymentModal, setPaymentModal] = useState(null) // invoice being paid
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState(null)

  const [invoiceForm, setInvoiceForm] = useState({
    student_id: '',
    fee_type: 'tuition',
    amount: '',
    description: '',
    term: '',
    due_date: '',
  })
  const [paymentForm, setPaymentForm] = useState({
    amount: '',
    method: 'cash',
    reference: '',
    note: '',
  })

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { page, page_size: 8 }
      if (statusFilter) params.status = statusFilter
      if (search.trim()) params.search = search.trim()
      const [sumRes, invRes] = await Promise.all([
        client.get('/finance/summary'),
        client.get('/finance/invoices', { params }),
      ])
      setSummary(sumRes.data)
      setInvoices(invRes.data.items)
      setMeta({ total: invRes.data.total, page: invRes.data.page, pages: invRes.data.pages })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [page, statusFilter, search])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  useEffect(() => {
    client
      .get('/students', { params: { page: 1, page_size: 100 } })
      .then(({ data }) => setStudents(data.items))
      .catch(() => {})
  }, [])

  useEffect(() => {
    const t = setTimeout(() => {
      setSearch(searchInput)
      setPage(1)
    }, 350)
    return () => clearTimeout(t)
  }, [searchInput])

  const openInvoiceModal = () => {
    setInvoiceForm({ student_id: '', fee_type: 'tuition', amount: '', description: '', term: '', due_date: '' })
    setFormError(null)
    setInvoiceModal(true)
  }

  const openPaymentModal = (invoice) => {
    setPaymentForm({
      amount: String(invoice.balance),
      method: 'cash',
      reference: '',
      note: '',
    })
    setFormError(null)
    setPaymentModal(invoice)
  }

  const createInvoice = async (e) => {
    e.preventDefault()
    setSaving(true)
    setFormError(null)
    try {
      await client.post('/finance/invoices', {
        ...invoiceForm,
        student_id: Number(invoiceForm.student_id),
        amount: invoiceForm.amount,
        due_date: invoiceForm.due_date || null,
      })
      setInvoiceModal(false)
      fetchData()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const recordPayment = async (e) => {
    e.preventDefault()
    setSaving(true)
    setFormError(null)
    try {
      await client.post('/finance/payments', {
        invoice_id: paymentModal.id,
        amount: paymentForm.amount,
        method: paymentForm.method,
        reference: paymentForm.reference || null,
        note: paymentForm.note || null,
      })
      setPaymentModal(null)
      fetchData()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-extrabold tracking-tight text-slate-900">
            Finance &amp; Billing
          </h2>
          <p className="mt-1 text-sm text-slate-500">Invoices, payments and fee collection</p>
        </div>
        <motion.button
          whileHover={{ scale: 1.03, y: -2 }}
          whileTap={{ scale: 0.97 }}
          onClick={openInvoiceModal}
          className="btn-primary"
        >
          <Plus className="h-4 w-4" />
          New Invoice
        </motion.button>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard icon={BadgeDollarSign} label="Total Billed" value={money(summary?.total_billed)} sub={`${summary?.invoices_total ?? 0} invoices`} accent="violet" delay={0} />
        <KpiCard icon={Wallet} label="Collected" value={money(summary?.total_collected)} sub={`${summary?.collection_rate ?? 0}% rate`} accent="emerald" delay={0.06} />
        <KpiCard icon={CreditCard} label="Outstanding" value={money(summary?.total_outstanding)} sub="Pending balances" accent="amber" delay={0.12} />
        <KpiCard icon={AlertTriangle} label="Overdue" value={money(summary?.total_overdue)} sub={`${summary?.payments_total ?? 0} payments logged`} accent="rose" delay={0.18} />
      </div>

      {/* Filters */}
      <div className="glass-panel flex flex-wrap items-center gap-3 p-4">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search invoice no. or student…"
            className="glass-input pl-10"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value)
            setPage(1)
          }}
          className="glass-input w-auto min-w-[150px]"
        >
          <option value="">All statuses</option>
          <option value="issued">Issued</option>
          <option value="partial">Partially paid</option>
          <option value="paid">Paid</option>
          <option value="overdue">Overdue</option>
          <option value="draft">Draft</option>
          <option value="void">Void</option>
        </select>
      </div>

      {/* Ledger table */}
      <div className="glass-panel overflow-hidden">
        {loading ? (
          <div className="flex h-64 items-center justify-center text-brand-600">
            <Spinner className="h-7 w-7" />
          </div>
        ) : invoices.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="No invoices found"
            hint="Create your first invoice to start billing."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead>
                <tr className="border-b border-white/70 bg-white/50 text-xs uppercase tracking-wider text-slate-500">
                  <th className="px-5 py-3.5 font-semibold">Invoice</th>
                  <th className="px-5 py-3.5 font-semibold">Student</th>
                  <th className="px-5 py-3.5 font-semibold">Fee</th>
                  <th className="px-5 py-3.5 text-right font-semibold">Amount</th>
                  <th className="px-5 py-3.5 text-right font-semibold">Balance</th>
                  <th className="px-5 py-3.5 font-semibold">Status</th>
                  <th className="px-5 py-3.5 text-right font-semibold">Action</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv, i) => (
                  <motion.tr
                    key={inv.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.03 }}
                    className="border-b border-white/50 transition-colors last:border-0 hover:bg-white/60"
                  >
                    <td className="px-5 py-3.5">
                      <p className="font-mono text-xs font-semibold text-slate-800">{inv.invoice_no}</p>
                      <p className="text-xs text-slate-400">
                        {new Date(inv.issue_date).toLocaleDateString()}
                        {inv.term ? ` · ${inv.term}` : ''}
                      </p>
                    </td>
                    <td className="px-5 py-3.5">
                      <p className="font-semibold text-slate-800">{inv.student_name ?? '—'}</p>
                      <p className="text-xs text-slate-500">
                        {inv.student_admission_no} · {inv.grade}
                      </p>
                    </td>
                    <td className="px-5 py-3.5 capitalize text-slate-600">{inv.fee_type.replace('_', ' ')}</td>
                    <td className="px-5 py-3.5 text-right font-semibold text-slate-800">
                      {money(inv.amount)}
                    </td>
                    <td className="px-5 py-3.5 text-right font-bold text-slate-900">
                      {money(inv.balance)}
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={inv.status} />
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      {Number(inv.balance) > 0 && inv.status !== 'void' ? (
                        <motion.button
                          whileHover={{ scale: 1.04, y: -1 }}
                          whileTap={{ scale: 0.96 }}
                          onClick={() => openPaymentModal(inv)}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500/90 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-emerald-600"
                        >
                          <Receipt className="h-3.5 w-3.5" />
                          Record payment
                        </motion.button>
                      ) : (
                        <span className="text-xs text-slate-400">Settled</span>
                      )}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {meta.pages > 1 && (
          <div className="flex items-center justify-between border-t border-white/60 bg-white/40 px-5 py-3">
            <p className="text-xs text-slate-500">
              Page {meta.page} of {meta.pages}
            </p>
            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="btn-ghost px-3 py-2 disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                disabled={page >= meta.pages}
                onClick={() => setPage((p) => Math.min(meta.pages, p + 1))}
                className="btn-ghost px-3 py-2 disabled:opacity-40"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* New invoice modal */}
      <Modal open={invoiceModal} onClose={() => setInvoiceModal(false)} title="Create Invoice">
        <ErrorBanner message={formError} onDismiss={() => setFormError(null)} />
        <form onSubmit={createInvoice} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="glass-label">Student *</label>
            <select
              required
              className="glass-input"
              value={invoiceForm.student_id}
              onChange={(e) => setInvoiceForm((f) => ({ ...f, student_id: e.target.value }))}
            >
              <option value="">Select a student…</option>
              {students.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.first_name} {s.last_name} — {s.admission_no} ({s.grade})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="glass-label">Fee type *</label>
            <select
              className="glass-input"
              value={invoiceForm.fee_type}
              onChange={(e) => setInvoiceForm((f) => ({ ...f, fee_type: e.target.value }))}
            >
              {FEE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replace('_', ' ')}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="glass-label">Amount *</label>
            <input
              required
              type="number"
              min="0.01"
              step="0.01"
              className="glass-input"
              placeholder="0.00"
              value={invoiceForm.amount}
              onChange={(e) => setInvoiceForm((f) => ({ ...f, amount: e.target.value }))}
            />
          </div>
          <div>
            <label className="glass-label">Term</label>
            <input
              className="glass-input"
              placeholder="Term 1"
              value={invoiceForm.term}
              onChange={(e) => setInvoiceForm((f) => ({ ...f, term: e.target.value }))}
            />
          </div>
          <div>
            <label className="glass-label">Due date</label>
            <input
              type="date"
              className="glass-input"
              value={invoiceForm.due_date}
              onChange={(e) => setInvoiceForm((f) => ({ ...f, due_date: e.target.value }))}
            />
          </div>
          <div className="sm:col-span-2">
            <label className="glass-label">Description</label>
            <textarea
              rows={2}
              className="glass-input resize-none"
              value={invoiceForm.description}
              onChange={(e) => setInvoiceForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>
          <div className="flex justify-end gap-3 sm:col-span-2">
            <button type="button" onClick={() => setInvoiceModal(false)} className="btn-ghost">
              Cancel
            </button>
            <motion.button
              type="submit"
              disabled={saving}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="btn-primary"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
              Issue invoice
            </motion.button>
          </div>
        </form>
      </Modal>

      {/* Record payment modal */}
      <Modal
        open={!!paymentModal}
        onClose={() => setPaymentModal(null)}
        title={`Record Payment — ${paymentModal?.invoice_no ?? ''}`}
      >
        <ErrorBanner message={formError} onDismiss={() => setFormError(null)} />
        {paymentModal && (
          <div className="mb-5 rounded-xl bg-white/70 p-4 text-sm">
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Student</span>
              <span className="font-semibold text-slate-800">{paymentModal.student_name}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Invoice total</span>
              <span className="font-semibold text-slate-800">{money(paymentModal.amount)}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Outstanding balance</span>
              <span className="font-bold text-rose-600">{money(paymentModal.balance)}</span>
            </div>
          </div>
        )}
        <form onSubmit={recordPayment} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="glass-label">Amount *</label>
            <input
              required
              type="number"
              min="0.01"
              step="0.01"
              max={paymentModal?.balance}
              className="glass-input"
              value={paymentForm.amount}
              onChange={(e) => setPaymentForm((f) => ({ ...f, amount: e.target.value }))}
            />
          </div>
          <div>
            <label className="glass-label">Method *</label>
            <select
              className="glass-input"
              value={paymentForm.method}
              onChange={(e) => setPaymentForm((f) => ({ ...f, method: e.target.value }))}
            >
              {PAYMENT_METHODS.map((m) => (
                <option key={m} value={m}>
                  {m.replace('_', ' ')}
                </option>
              ))}
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className="glass-label">Transaction reference</label>
            <input
              className="glass-input"
              placeholder="e.g. MM-20260904-1938"
              value={paymentForm.reference}
              onChange={(e) => setPaymentForm((f) => ({ ...f, reference: e.target.value }))}
            />
          </div>
          <div className="sm:col-span-2">
            <label className="glass-label">Note</label>
            <input
              className="glass-input"
              value={paymentForm.note}
              onChange={(e) => setPaymentForm((f) => ({ ...f, note: e.target.value }))}
            />
          </div>
          <div className="flex justify-end gap-3 sm:col-span-2">
            <button type="button" onClick={() => setPaymentModal(null)} className="btn-ghost">
              Cancel
            </button>
            <motion.button
              type="submit"
              disabled={saving}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="btn-primary"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Receipt className="h-4 w-4" />}
              Confirm payment
            </motion.button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
