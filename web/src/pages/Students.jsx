import { motion } from 'framer-motion'
import {
  ChevronLeft,
  ChevronRight,
  GraduationCap,
  Loader2,
  Pencil,
  Plus,
  Search,
  Trash2,
  Users,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import client from '../api/client'
import {
  EmptyState,
  ErrorBanner,
  Modal,
  Spinner,
  StatusBadge,
} from '../components/ui.jsx'

const EMPTY_FORM = {
  admission_no: '',
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  gender: '',
  grade: '',
  guardian_name: '',
  guardian_phone: '',
  address: '',
  status: 'active',
}

export default function Students() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [students, setStudents] = useState([])
  const [meta, setMeta] = useState({ total: 0, page: 1, pages: 1 })

  const [search, setSearch] = useState('')
  const [grade, setGrade] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [grades, setGrades] = useState([])
  const [page, setPage] = useState(1)

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null) // Student object or null
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState(null)

  const PAGE_SIZE = 8

  const fetchStudents = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { page, page_size: PAGE_SIZE }
      if (search.trim()) params.search = search.trim()
      if (grade) params.grade = grade
      if (statusFilter) params.status = statusFilter
      const { data } = await client.get('/students', { params })
      setStudents(data.items)
      setMeta({ total: data.total, page: data.page, pages: data.pages })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [page, search, grade, statusFilter])

  useEffect(() => {
    fetchStudents()
  }, [fetchStudents])

  useEffect(() => {
    client
      .get('/students/grades')
      .then(({ data }) => setGrades(data))
      .catch(() => {})
  }, [])

  // Debounce search input.
  const [searchInput, setSearchInput] = useState('')
  useEffect(() => {
    const t = setTimeout(() => {
      setSearch(searchInput)
      setPage(1)
    }, 350)
    return () => clearTimeout(t)
  }, [searchInput])

  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY_FORM)
    setFormError(null)
    setModalOpen(true)
  }

  const openEdit = (student) => {
    setEditing(student)
    setForm({
      ...EMPTY_FORM,
      ...student,
      email: student.email ?? '',
      phone: student.phone ?? '',
      gender: student.gender ?? '',
      guardian_name: student.guardian_name ?? '',
      guardian_phone: student.guardian_phone ?? '',
      address: student.address ?? '',
      date_of_birth: student.date_of_birth ?? '',
    })
    setFormError(null)
    setModalOpen(true)
  }

  const handleChange = (field) => (e) =>
    setForm((f) => ({ ...f, [field]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setFormError(null)

    // Strip blank optional fields so Pydantic doesn't choke on empty emails.
    const payload = Object.fromEntries(
      Object.entries(form).filter(([, v]) => v !== '' && v !== null),
    )

    try {
      if (editing) {
        await client.patch(`/students/${editing.id}`, payload)
      } else {
        await client.post('/students', payload)
      }
      setModalOpen(false)
      fetchStudents()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (student) => {
    if (!window.confirm(`Delete student "${student.full_name}" (${student.admission_no})?`))
      return
    try {
      await client.delete(`/students/${student.id}`)
      fetchStudents()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-extrabold tracking-tight text-slate-900">
            Student Directory
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            {meta.total} student{meta.total === 1 ? '' : 's'} on record
          </p>
        </div>
        <motion.button
          whileHover={{ scale: 1.03, y: -2 }}
          whileTap={{ scale: 0.97 }}
          onClick={openCreate}
          className="btn-primary"
        >
          <Plus className="h-4 w-4" />
          New Student
        </motion.button>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Filter bar */}
      <div className="glass-panel flex flex-wrap items-center gap-3 p-4">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search name, email or admission no…"
            className="glass-input pl-10"
          />
        </div>
        <select
          value={grade}
          onChange={(e) => {
            setGrade(e.target.value)
            setPage(1)
          }}
          className="glass-input w-auto min-w-[140px]"
        >
          <option value="">All grades</option>
          {grades.map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value)
            setPage(1)
          }}
          className="glass-input w-auto min-w-[140px]"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="graduated">Graduated</option>
          <option value="suspended">Suspended</option>
        </select>
      </div>

      {/* Table */}
      <div className="glass-panel overflow-hidden">
        {loading ? (
          <div className="flex h-64 items-center justify-center text-brand-600">
            <Spinner className="h-7 w-7" />
          </div>
        ) : students.length === 0 ? (
          <EmptyState
            icon={Users}
            title="No students found"
            hint="Try adjusting filters or register a new student."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-left text-sm">
              <thead>
                <tr className="border-b border-white/70 bg-white/50 text-xs uppercase tracking-wider text-slate-500">
                  <th className="px-5 py-3.5 font-semibold">Student</th>
                  <th className="px-5 py-3.5 font-semibold">Admission No.</th>
                  <th className="px-5 py-3.5 font-semibold">Grade</th>
                  <th className="px-5 py-3.5 font-semibold">Guardian</th>
                  <th className="px-5 py-3.5 font-semibold">Status</th>
                  <th className="px-5 py-3.5 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {students.map((s, i) => (
                  <motion.tr
                    key={s.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.03 }}
                    className="border-b border-white/50 transition-colors last:border-0 hover:bg-white/60"
                  >
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-100 text-sm font-bold text-brand-700">
                          {s.first_name.charAt(0)}
                          {s.last_name.charAt(0)}
                        </div>
                        <div className="leading-tight">
                          <p className="font-semibold text-slate-800">
                            {s.first_name} {s.last_name}
                          </p>
                          <p className="text-xs text-slate-500">{s.email || '—'}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 font-mono text-xs text-slate-600">
                      {s.admission_no}
                    </td>
                    <td className="px-5 py-3.5 text-slate-700">{s.grade}</td>
                    <td className="px-5 py-3.5 text-slate-600">
                      {s.guardian_name ? (
                        <span>
                          {s.guardian_name}
                          {s.guardian_phone && (
                            <span className="block text-xs text-slate-400">
                              {s.guardian_phone}
                            </span>
                          )}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={s.status} />
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center justify-end gap-1.5">
                        <motion.button
                          whileHover={{ scale: 1.1 }}
                          whileTap={{ scale: 0.92 }}
                          onClick={() => openEdit(s)}
                          className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-brand-50 hover:text-brand-600"
                          aria-label="Edit"
                        >
                          <Pencil className="h-4 w-4" />
                        </motion.button>
                        <motion.button
                          whileHover={{ scale: 1.1 }}
                          whileTap={{ scale: 0.92 }}
                          onClick={() => handleDelete(s)}
                          className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-rose-50 hover:text-rose-600"
                          aria-label="Delete"
                        >
                          <Trash2 className="h-4 w-4" />
                        </motion.button>
                      </div>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
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

      {/* Create / Edit modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? 'Edit Student' : 'Register New Student'}
        wide
      >
        <ErrorBanner message={formError} onDismiss={() => setFormError(null)} />
        <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field
            label="Admission No. *"
            value={form.admission_no}
            onChange={handleChange('admission_no')}
            placeholder="NE-2026-007"
            disabled={!!editing}
            required
          />
          <Field label="Grade / Class *" value={form.grade} onChange={handleChange('grade')} placeholder="Grade 7" required />
          <Field label="First name *" value={form.first_name} onChange={handleChange('first_name')} required />
          <Field label="Last name *" value={form.last_name} onChange={handleChange('last_name')} required />
          <Field label="Email" type="email" value={form.email} onChange={handleChange('email')} placeholder="student@school.edu" />
          <Field label="Phone" value={form.phone} onChange={handleChange('phone')} />
          <div>
            <label className="glass-label">Gender</label>
            <select className="glass-input" value={form.gender} onChange={handleChange('gender')}>
              <option value="">—</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label className="glass-label">Status</label>
            <select className="glass-input" value={form.status} onChange={handleChange('status')}>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="graduated">Graduated</option>
              <option value="suspended">Suspended</option>
            </select>
          </div>
          <Field label="Guardian name" value={form.guardian_name} onChange={handleChange('guardian_name')} />
          <Field label="Guardian phone" value={form.guardian_phone} onChange={handleChange('guardian_phone')} />
          <div className="sm:col-span-2">
            <label className="glass-label">Address</label>
            <textarea
              rows={2}
              className="glass-input resize-none"
              value={form.address}
              onChange={handleChange('address')}
            />
          </div>

          <div className="flex justify-end gap-3 sm:col-span-2">
            <button type="button" onClick={() => setModalOpen(false)} className="btn-ghost">
              Cancel
            </button>
            <motion.button
              type="submit"
              disabled={saving}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="btn-primary"
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  {editing ? (
                    <Pencil className="h-4 w-4" />
                  ) : (
                    <GraduationCap className="h-4 w-4" />
                  )}
                  {editing ? 'Save changes' : 'Register student'}
                </>
              )}
            </motion.button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

function Field({ label, ...props }) {
  return (
    <div>
      <label className="glass-label">{label}</label>
      <input className="glass-input" {...props} />
    </div>
  )
}
