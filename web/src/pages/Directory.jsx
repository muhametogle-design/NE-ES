import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Input } from '../components/ui/Input';
import { addToast } from '../features/ui/uiSlice';
import { Building2, Users, ArrowRight, Settings, Phone, MapPin } from 'lucide-react';

export function Directory() {
  const navigate = useNavigate();
  const dispatch = useDispatch();

  const [schools, setSchools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedSchool, setSelectedSchool] = useState(null);
  const [nextRollValue, setNextRollValue] = useState('');
  const [updatingSeq, setUpdatingSeq] = useState(false);

  const loadSchools = async () => {
    try {
      setLoading(true);
      const data = await api.getStateSchools();
      setSchools(data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSchools();
  }, []);

  const openSequenceManager = async (school) => {
    setSelectedSchool(school);
    try {
      const seq = await api.getRollSequence(school.id);
      setNextRollValue(String(seq.next_value));
    } catch (e) {
      console.error(e);
    }
  };

  const handleUpdateSequence = async (e) => {
    e.preventDefault();
    if (!selectedSchool || !nextRollValue) return;
    try {
      setUpdatingSeq(true);
      await api.updateRollSequence(selectedSchool.id, {
        next_value: parseInt(nextRollValue),
      });
      dispatch(addToast({ type: 'success', message: `Roll sequence updated for ${selectedSchool.school_code}` }));
      setSelectedSchool(null);
      loadSchools();
    } catch (err) {
      dispatch(addToast({ type: 'error', message: err.message }));
    } finally {
      setUpdatingSeq(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Regional Private Institutions Directory</h2>
          <p className="text-xs text-slate-500">Official registry of licensed private schools under state oversight</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {schools.map((s) => (
          <Card key={s.id} className="flex flex-col justify-between hover:border-slate-400 transition-all">
            <div className="space-y-3">
              <div className="flex justify-between items-start">
                <div className="h-12 w-12 bg-slate-900 text-white rounded-xl flex items-center justify-center font-bold text-lg">
                  {s.school_code}
                </div>
                <Badge variant="success">{s.accreditation_status || 'Active'}</Badge>
              </div>

              <div>
                <h3 className="font-bold text-slate-900 text-base">{s.school_name}</h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">License: {s.state_license_number}</p>
              </div>

              <div className="space-y-1.5 text-xs text-slate-600 pt-2 border-t border-slate-100">
                <p>Proprietor: <span className="font-semibold text-slate-800">{s.proprietor_name}</span></p>
                <p className="flex items-center gap-1.5"><Phone className="h-3.5 w-3.5 text-slate-400" /> {s.contact_phone}</p>
                <p className="flex items-center gap-1.5"><MapPin className="h-3.5 w-3.5 text-slate-400" /> {s.physical_address}</p>
              </div>

              <div className="flex gap-4 pt-2 text-xs font-semibold">
                <div className="bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200">
                  <span className="text-slate-500 block text-[10px] uppercase">Students</span>
                  <span className="text-slate-900 font-bold">{s.student_count || 0}</span>
                </div>
                <div className="bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200">
                  <span className="text-slate-500 block text-[10px] uppercase">Teachers</span>
                  <span className="text-slate-900 font-bold">{s.teacher_count || 0}</span>
                </div>
              </div>
            </div>

            <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-between">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => openSequenceManager(s)}
                className="text-xs flex items-center gap-1"
              >
                <Settings className="h-3.5 w-3.5" /> Roll Sequence
              </Button>

              <Button
                size="sm"
                variant="outline"
                onClick={() => navigate(`/state/institutions/${s.id}`)}
                className="text-xs flex items-center gap-1"
              >
                Inspect <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </Card>
        ))}
      </div>

      {/* Roll Sequence Config Modal */}
      {selectedSchool && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full overflow-hidden border border-slate-200">
            <div className="px-6 py-4 bg-slate-900 text-white flex justify-between items-center">
              <div>
                <h4 className="font-bold text-sm">Roll Sequence Counter: {selectedSchool.school_name}</h4>
                <p className="text-[11px] text-slate-400 font-mono">School Code: {selectedSchool.school_code}</p>
              </div>
              <button type="button" onClick={() => setSelectedSchool(null)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleUpdateSequence} className="p-6 space-y-4">
              <Input
                label="Next Roll Sequence Number"
                type="number"
                value={nextRollValue}
                onChange={(e) => setNextRollValue(e.target.value)}
                required
              />
              <p className="text-xs text-amber-700 bg-amber-50 p-3 rounded-lg border border-amber-200 font-medium">
                ⚠️ Sequence numbers can only advance forward. Decrementing or reusing issued roll numbers is prohibited by state policy.
              </p>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <Button variant="outline" onClick={() => setSelectedSchool(null)}>Cancel</Button>
                <Button type="submit" loading={updatingSeq}>Update Sequence</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
