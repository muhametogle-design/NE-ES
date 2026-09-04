import React, { useState, useEffect } from 'react';
import { useDispatch } from 'react-redux';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Select, Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { addToast } from '../features/ui/uiSlice';
import { CalendarCheck, Send, Check, X, Clock, AlertCircle } from 'lucide-react';

export function Attendance() {
  const dispatch = useDispatch();

  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [selectedSubject, setSelectedSubject] = useState('');
  const [attDate, setAttDate] = useState(new Date().toISOString().split('T')[0]);

  const [students, setStudents] = useState([]);
  const [attendanceMap, setAttendanceMap] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [submittingDaily, setSubmittingDaily] = useState(false);

  useEffect(() => {
    api.getClasses().then((cls) => {
      setClasses(cls || []);
      if (cls && cls.length > 0) setSelectedClass(cls[0].id);
    });
  }, []);

  useEffect(() => {
    if (selectedClass) {
      api.getSubjects().then((subs) => {
        setSubjects(subs || []);
        if (subs && subs.length > 0) setSelectedSubject(subs[0].id);
      });
    }
  }, [selectedClass]);

  useEffect(() => {
    if (selectedClass && selectedSubject) {
      loadAttendanceRoster();
    }
  }, [selectedClass, selectedSubject, attDate]);

  const loadAttendanceRoster = async () => {
    try {
      setLoading(true);
      const [stuRes, attRes] = await Promise.all([
        api.getStudents(`class_id=${selectedClass}&per_page=100`),
        api.getAttendance(selectedClass, selectedSubject, attDate).catch(() => []),
      ]);

      const stuList = stuRes.items || [];
      setStudents(stuList);

      const existingMap = {};
      attRes.forEach((a) => {
        existingMap[a.student_id] = a.status;
      });

      // Default unmarked to present
      const fullMap = {};
      stuList.forEach((s) => {
        fullMap[s.id] = existingMap[s.id] || 'present';
      });
      setAttendanceMap(fullMap);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = (studentId, status) => {
    setAttendanceMap((prev) => ({ ...prev, [studentId]: status }));
  };

  const handleSaveAttendance = async () => {
    try {
      setSaving(true);
      const records = Object.entries(attendanceMap).map(([studentId, status]) => ({
        student_id: parseInt(studentId),
        status,
      }));
      await api.markAttendance({
        class_id: parseInt(selectedClass),
        subject_id: parseInt(selectedSubject),
        date: attDate,
        records,
      });
      dispatch(addToast({ type: 'success', message: 'Subject attendance saved successfully!' }));
    } catch (err) {
      dispatch(addToast({ type: 'error', message: err.message }));
    } finally {
      setSaving(false);
    }
  };

  const handleSubmitDaily = async () => {
    try {
      setSubmittingDaily(true);
      const res = await api.submitDailyAttendance();
      dispatch(addToast({ type: 'success', message: res.message || 'Daily attendance transmitted to State Ministry!' }));
    } catch (err) {
      dispatch(addToast({ type: 'error', message: err.message }));
    } finally {
      setSubmittingDailyDaily(false);
    }
  };

  const markAll = (status) => {
    const updated = {};
    students.forEach((s) => {
      updated[s.id] = status;
    });
    setAttendanceMap(updated);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Attendance Registry</h2>
          <p className="text-xs text-slate-500">Record classroom roll calls and certify daily submission</p>
        </div>
        <Button
          variant="secondary"
          onClick={handleSubmitDaily}
          loading={submittingDaily}
          className="flex items-center gap-1.5"
        >
          <Send className="h-4 w-4 text-emerald-400" /> Transmit Daily Compliance Report
        </Button>
      </div>

      {/* Selectors */}
      <Card>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Select
            label="Class Stream"
            value={selectedClass}
            onChange={(e) => setSelectedClass(e.target.value)}
          >
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                Grade {c.class_level} ({c.stream})
              </option>
            ))}
          </Select>

          <Select
            label="Subject"
            value={selectedSubject}
            onChange={(e) => setSelectedSubject(e.target.value)}
          >
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code} - {s.name}
              </option>
            ))}
          </Select>

          <Input
            label="Date"
            type="date"
            value={attDate}
            onChange={(e) => setAttDate(e.target.value)}
          />
        </div>
      </Card>

      {/* Roster & Marking */}
      <Card
        title="Student Roster"
        subtitle={`Marking for Class #${selectedClass} • ${students.length} Students`}
        action={
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => markAll('present')}>
              Mark All Present
            </Button>
            <Button size="sm" variant="outline" onClick={() => markAll('absent')}>
              Mark All Absent
            </Button>
          </div>
        }
      >
        {loading ? (
          <div className="py-8 text-center text-xs text-slate-400">Loading student roster...</div>
        ) : students.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-400">No students enrolled in this class stream.</div>
        ) : (
          <div className="divide-y divide-slate-100">
            {students.map((s) => {
              const currentStatus = attendanceMap[s.id] || 'present';
              return (
                <div key={s.id} className="py-3 flex items-center justify-between">
                  <div>
                    <span className="font-mono text-xs font-bold text-slate-900 mr-2">{s.roll_number}</span>
                    <span className="font-semibold text-slate-800 text-sm">{s.first_name} {s.last_name}</span>
                  </div>

                  <div className="flex gap-1.5">
                    {[
                      { key: 'present', label: 'Present', color: 'bg-emerald-600 text-white' },
                      { key: 'absent', label: 'Absent', color: 'bg-rose-600 text-white' },
                      { key: 'late', label: 'Late', color: 'bg-amber-600 text-white' },
                      { key: 'excused', label: 'Excused', color: 'bg-blue-600 text-white' },
                    ].map((opt) => (
                      <button
                        key={opt.key}
                        type="button"
                        onClick={() => handleStatusChange(s.id, opt.key)}
                        className={`px-3 py-1 text-xs font-bold rounded-lg transition-colors ${
                          currentStatus === opt.key
                            ? opt.color
                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}

            <div className="pt-4 flex justify-end">
              <Button onClick={handleSaveAttendance} loading={saving}>
                Save Subject Attendance
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
