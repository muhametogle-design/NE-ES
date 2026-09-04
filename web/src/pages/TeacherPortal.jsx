import React, { useState, useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Input } from '../components/ui/Input';
import { addToast } from '../features/ui/uiSlice';
import { BookOpen, Calendar, Clock, KeyRound, CheckCircle, Award, UserCheck } from 'lucide-react';

export function TeacherPortal() {
  const dispatch = useDispatch();
  const { user } = useSelector((state) => state.auth);

  const [timetable, setTimetable] = useState([]);
  const [pin, setPin] = useState('');
  const [settingPin, setSettingPin] = useState(false);

  useEffect(() => {
    if (user?.id) {
      api.getTimetable(`teacher_id=${user.id}`)
        .then(setTimetable)
        .catch(console.error);
    }
  }, [user]);

  const handleSetPin = async (e) => {
    e.preventDefault();
    if (pin.length < 4) {
      dispatch(addToast({ type: 'error', message: 'PIN must be at least 4 digits' }));
      return;
    }
    try {
      setSettingPin(true);
      await api.setPin({ pin });
      dispatch(addToast({ type: 'success', message: 'Staff PIN updated successfully!' }));
      setPin('');
    } catch (err) {
      dispatch(addToast({ type: 'error', message: err.message }));
    } finally {
      setSettingPin(false);
    }
  };

  const daysOfWeek = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

  return (
    <div className="space-y-6">
      {/* Teacher Profile & Credentials Header */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="flex items-center gap-4">
          <div className="h-16 w-16 bg-blue-100 text-blue-800 rounded-full flex items-center justify-center font-bold text-2xl border-2 border-blue-300">
            {user?.first_name?.[0]}{user?.last_name?.[0]}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-slate-900">{user?.first_name} {user?.last_name}</h2>
              {user?.is_department_head && <Badge variant="purple">Department Head</Badge>}
            </div>
            <p className="text-xs text-slate-500 font-mono mt-0.5">Staff ID: {user?.staff_identifier}</p>
            <p className="text-xs text-slate-600 font-medium">{user?.designation || 'Faculty Member'}</p>
          </div>
        </div>

        {/* Set PIN Widget */}
        <form onSubmit={handleSetPin} className="flex items-end gap-2 bg-slate-50 p-3 rounded-xl border border-slate-200">
          <Input
            label="Quick Login PIN"
            type="password"
            maxLength={6}
            placeholder="New 4-digit PIN"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            className="w-36"
          />
          <Button type="submit" size="sm" loading={settingPin}>
            Save PIN
          </Button>
        </form>
      </div>

      {/* Weekly Schedule */}
      <Card title="My Teaching Schedule" subtitle="Weekly assigned timetable slots and periods">
        {timetable.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-400">No active teaching assignments scheduled</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {timetable.map((slot) => (
              <div key={slot.id} className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                <div className="flex justify-between items-center">
                  <Badge variant="info">{daysOfWeek[slot.day_of_week] || `Day ${slot.day_of_week}`}</Badge>
                  <span className="text-xs font-bold text-slate-700">Period {slot.period}</span>
                </div>
                <h4 className="font-bold text-slate-900 text-sm">{slot.subject_name}</h4>
                <div className="text-xs text-slate-500 flex justify-between">
                  <span>{slot.class_name}</span>
                  <span>Room: {slot.room || 'Main Hall'}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
