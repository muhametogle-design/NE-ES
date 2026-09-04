import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input, Select } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { StudentModal } from '../components/StudentModal';
import { Search, UserPlus, Trash2, Edit2, CheckCircle2 } from 'lucide-react';

export function Students() {
  const [students, setStudents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedClass, setSelectedClass] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const [modalOpen, setModalOpen] = useState(false);
  const [editingStudent, setEditingStudent] = useState(null);

  const loadStudents = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: String(page),
        per_page: '15',
        ...(search ? { q: search } : {}),
        ...(selectedClass ? { class_id: selectedClass } : {}),
      });
      const data = await api.getStudents(params.toString());
      setStudents(data.items || []);
      setTotalPages(data.pages || 1);
      setTotalCount(data.total || 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const loadClasses = async () => {
    try {
      const cls = await api.getClasses();
      setClasses(cls || []);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadClasses();
  }, []);

  useEffect(() => {
    loadStudents();
  }, [page, search, selectedClass]);

  const handleSaveStudent = async (studentData) => {
    if (editingStudent) {
      await api.updateStudent(editingStudent.roll_number, studentData);
    } else {
      await api.createStudent(studentData);
    }
    loadStudents();
  };

  const handleDeleteStudent = async (rollNumber) => {
    if (window.confirm(`Deactivate student ${rollNumber}?`)) {
      await api.deleteStudent(rollNumber);
      loadStudents();
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Student Registry</h2>
          <p className="text-xs text-slate-500">
            Total active students enrolled: <span className="font-bold text-slate-800">{totalCount}</span>
          </p>
        </div>
        <Button
          onClick={() => {
            setEditingStudent(null);
            setModalOpen(true);
          }}
          className="flex items-center gap-1.5"
        >
          <UserPlus className="h-4 w-4" /> Enroll Student
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="sm:col-span-2 relative">
            <Input
              placeholder="Search by student name or roll number..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <Select
            value={selectedClass}
            onChange={(e) => {
              setSelectedClass(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Class Streams</option>
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                Grade {c.class_level} ({c.stream})
              </option>
            ))}
          </Select>
        </div>
      </Card>

      {/* Table */}
      <Card className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 text-slate-500 font-bold uppercase tracking-wider border-b border-slate-200">
            <tr>
              <th className="px-4 py-3">Roll Number (NE-SID)</th>
              <th className="px-4 py-3">Student Name</th>
              <th className="px-4 py-3">Gender</th>
              <th className="px-4 py-3">Class</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr>
                <td colSpan="6" className="px-4 py-8 text-center text-slate-400">Loading student directory...</td>
              </tr>
            ) : students.length === 0 ? (
              <tr>
                <td colSpan="6" className="px-4 py-8 text-center text-slate-400">No student records found.</td>
              </tr>
            ) : (
              students.map((s) => (
                <tr key={s.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 font-mono font-bold text-slate-900">{s.roll_number}</td>
                  <td className="px-4 py-3 font-semibold text-slate-800">{s.first_name} {s.last_name}</td>
                  <td className="px-4 py-3 text-slate-600">{s.gender}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {classes.find((c) => c.id === s.class_id)
                      ? `Grade ${classes.find((c) => c.id === s.class_id).class_level} (${classes.find((c) => c.id === s.class_id).stream})`
                      : 'Unassigned'}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={s.is_active ? 'success' : 'danger'}>
                      {s.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right space-x-2">
                    <button
                      type="button"
                      onClick={() => {
                        setEditingStudent(s);
                        setModalOpen(true);
                      }}
                      className="p-1 text-slate-400 hover:text-slate-800"
                      title="Edit"
                    >
                      <Edit2 className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteStudent(s.roll_number)}
                      className="p-1 text-slate-400 hover:text-rose-600"
                      title="Deactivate"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100 text-xs">
            <span className="text-slate-500">Page {page} of {totalPages}</span>
            <div className="space-x-1">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                Previous
              </Button>
              <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>

      <StudentModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSave={handleSaveStudent}
        classes={classes}
        initialData={editingStudent}
      />
    </div>
  );
}
