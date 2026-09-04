import React, { useState, useEffect } from 'react';
import { useDispatch } from 'react-redux';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Select, Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { addToast } from '../features/ui/uiSlice';
import { RefreshCw, UserX, CheckCircle, Shield, AlertTriangle } from 'lucide-react';

export function Substitutions() {
  const dispatch = useDispatch();

  const [teachers, setTeachers] = useState([]);
  const [absences, setAbsences] = useState([]);
  const [substitutions, setSubstitutions] = useState([]);
  const [timetable, setTimetable] = useState([]);

  const [selectedTeacher, setSelectedTeacher] = useState('');
  const [absenceDate, setAbsenceDate] = useState(new Date().toISOString().split('T')[0]);
  const [absenceReason, setAbsenceReason] = useState('Medical / Sick Leave');

  const [selectedSlot, setSelectedSlot] = useState(null);
  const [selectedAbsence, setSelectedAbsence] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [loadingCandidates, setLoadingCandidates] = useState(false);

  const loadData = async () => {
    try {
      const [tList, absList, subList, ttList] = await Promise.all([
        api.getTeachers(),
        api.getAbsences(),
        api.getSubstitutions(),
        api.getTimetable(),
      ]);
      setTeachers(tList || []);
      setAbsences(absList || []);
      setSubstitutions(subList || []);
      setTimetable(ttList || []);
      if (tList && tList.length > 0) setSelectedTeacher(tList[0].id);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleReportAbsence = async (e) => {
    e.preventDefault();
    try {
      await api.reportAbsence({
        teacher_id: parseInt(selectedTeacher),
        date: absenceDate,
        reason: absenceReason,
      });
      dispatch(addToast({ type: 'success', message: 'Teacher absence recorded.' }));
      loadData();
    } catch (err) {
      dispatch(addToast({ type: 'error', message: err.message }));
    }
  };

  const handleFindCandidates = async (absence, slot) => {
    setSelectedAbsence(absence);
    setSelectedSlot(slot);
    try {
      setLoadingCandidates(true);
      const res = await api.getSubstitutionCandidates(slot.id, absence.date);
      setCandidates(res || []);
    } catch (err) {
      dispatch(addToast({ type: 'error', message: err.message }));
    } finally {
      setLoadingCandidates(false);
    }
  };

  const handleAssignSubstitute = async (substituteTeacherId) => {
    try {
      await api.assignSubstitution({
        absence_id: selectedAbsence.id,
        substitute_teacher_id: substituteTeacherId,
        timetable_slot_id: selectedSlot.id,
      });
      dispatch(addToast({ type: 'success', message: 'Substitute teacher assigned successfully!' }));
      setSelectedSlot(null);
      setSelectedAbsence(null);
      loadData();
    } catch (err) {
      dispatch(addToast({ type: 'error', message: err.message }));
    }
  };

  const handleConfirm = async (subId) => {
    try {
      await api.confirmSubstitution(subId);
      dispatch(addToast({ type: 'success', message: 'Substitution confirmed!' }));
      loadData();
    } catch (err) {
      dispatch(addToast({ type: 'error', message: err.message }));
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Faculty Absence & Substitution Engine</h2>
        <p className="text-xs text-slate-500">Automated candidate ranking based on timetable availability & department specialization</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Report Absence Form */}
        <Card title="Report Teacher Absence" subtitle="Log faculty sick leave or absence">
          <form onSubmit={handleReportAbsence} className="space-y-4">
            <Select
              label="Absent Teacher"
              value={selectedTeacher}
              onChange={(e) => setSelectedTeacher(e.target.value)}
            >
              {teachers.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.first_name} {t.last_name} ({t.designation || 'Teacher'})
                </option>
              ))}
            </Select>

            <Input
              label="Date of Absence"
              type="date"
              value={absenceDate}
              onChange={(e) => setAbsenceDate(e.target.value)}
            />

            <Input
              label="Reason"
              value={absenceReason}
              onChange={(e) => setAbsenceReason(e.target.value)}
            />

            <Button type="submit" className="w-full">
              Record Absence
            </Button>
          </form>
        </Card>

        {/* Active Absences & Slot Coverage */}
        <div className="lg:col-span-2">
          <Card title="Recorded Absences & Needs Coverage" subtitle="Pending substitutions">
            {absences.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-400">No active faculty absences reported</div>
            ) : (
              <div className="space-y-4">
                {absences.map((a) => {
                  const teacherSlots = timetable.filter((t) => t.teacher_id === a.teacher_id);
                  return (
                    <div key={a.id} className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-3">
                      <div className="flex justify-between items-start">
                        <div>
                          <h4 className="font-bold text-slate-900 text-sm">{a.teacher_name}</h4>
                          <p className="text-xs text-slate-500">{a.date} • {a.reason}</p>
                        </div>
                        <Badge variant={a.status === 'covered' ? 'success' : 'warning'}>
                          {a.status}
                        </Badge>
                      </div>

                      <div className="space-y-2">
                        <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                          Timetable Slots Needing Cover ({teacherSlots.length})
                        </p>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {teacherSlots.map((slot) => (
                            <div key={slot.id} className="p-2.5 bg-white rounded-lg border border-slate-200 flex items-center justify-between text-xs">
                              <div>
                                <span className="font-bold text-slate-800 block">Period {slot.period}: {slot.subject_name}</span>
                                <span className="text-slate-500">{slot.class_name}</span>
                              </div>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleFindCandidates(a, slot)}
                              >
                                Find Substitute
                              </Button>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* Candidate Ranking Modal / Section */}
      {selectedSlot && (
        <Card
          title={`Candidate Match Ranking for Period ${selectedSlot.period}: ${selectedSlot.subject_name}`}
          subtitle={`Auto-ranked by availability, subject department alignment, and current workload`}
        >
          {loadingCandidates ? (
            <div className="py-8 text-center text-xs text-slate-400">Evaluating faculty schedule availability...</div>
          ) : candidates.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-400">No available faculty members found</div>
          ) : (
            <div className="divide-y divide-slate-100">
              {candidates.map((c) => (
                <div key={c.teacher_id} className="py-3 flex items-center justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-800 text-sm">{c.teacher_name}</span>
                      <Badge variant={c.is_free ? 'success' : 'danger'}>
                        {c.is_free ? 'Free Period' : 'Busy'}
                      </Badge>
                      {c.is_same_department && <Badge variant="purple">Same Department</Badge>}
                    </div>
                    <p className="text-xs text-slate-500">
                      Match Score: <span className="font-bold text-emerald-700">{c.match_score} pts</span> • Weekly Load: {c.current_load} courses
                    </p>
                  </div>

                  <Button
                    size="sm"
                    disabled={!c.is_free}
                    onClick={() => handleAssignSubstitute(c.teacher_id)}
                  >
                    Assign Cover
                  </Button>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Active Assignments */}
      <Card title="Active Substitution Assignments" subtitle="Confirmed coverage for upcoming sessions">
        {substitutions.length === 0 ? (
          <div className="py-6 text-center text-xs text-slate-400">No active substitution records</div>
        ) : (
          <div className="divide-y divide-slate-100 text-xs">
            {substitutions.map((sub) => (
              <div key={sub.id} className="py-3 flex items-center justify-between">
                <div>
                  <span className="font-bold text-slate-900 block">
                    {sub.substitute_name} covering Period {sub.slot_details?.period} ({sub.slot_details?.subject})
                  </span>
                  <span className="text-slate-500">{sub.slot_details?.class} • Room {sub.slot_details?.room || 'Hall'}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={sub.confirmed ? 'success' : 'warning'}>
                    {sub.confirmed ? 'Confirmed' : 'Pending Confirmation'}
                  </Badge>
                  {!sub.confirmed && (
                    <Button size="sm" variant="outline" onClick={() => handleConfirm(sub.id)}>
                      Confirm
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
