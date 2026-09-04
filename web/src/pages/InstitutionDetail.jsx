import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { TeacherProfileModal } from '../components/TeacherProfileModal';
import { ArrowLeft, Building2, Users, BookOpen, UserCheck, ShieldCheck } from 'lucide-react';

export function InstitutionDetail() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [school, setSchool] = useState(null);
  const [classes, setClasses] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [loading, setLoading] = useState(true);

  const [selectedTeacher, setSelectedTeacher] = useState(null);

  useEffect(() => {
    loadDetails();
  }, [id]);

  const loadDetails = async () => {
    try {
      setLoading(true);
      const [sData, cData, tData] = await Promise.all([
        api.getStateSchool(id),
        api.getStateClasses(id),
        api.getStateTeachers(id),
      ]);
      setSchool(sData);
      setClasses(cData || []);
      setTeachers(tData || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="p-8 text-center text-xs text-slate-400">Loading institution details...</div>;

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate('/state/directory')} className="flex items-center gap-1.5 text-xs">
        <ArrowLeft className="h-4 w-4" /> Back to Directory
      </Button>

      {/* School Header */}
      <Card>
        <div className="flex items-start gap-4">
          <div className="h-16 w-16 bg-slate-900 text-white rounded-2xl flex items-center justify-center font-black text-2xl">
            {school?.school_code}
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h2 className="text-2xl font-black text-slate-900">{school?.school_name}</h2>
              <Badge variant="success">{school?.accreditation_status || 'Accredited'}</Badge>
            </div>
            <p className="text-xs text-slate-500 font-mono">License: {school?.state_license_number} • Proprietor: {school?.proprietor_name}</p>
            <p className="text-xs text-slate-600">{school?.physical_address}</p>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Classes Breakdown */}
        <Card title="Enrolled Class Streams" subtitle={`${classes.length} Academic Streams Configured`}>
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {classes.map((c) => (
              <div key={c.id} className="p-3 rounded-lg border border-slate-200 bg-slate-50 flex items-center justify-between text-xs">
                <div>
                  <span className="font-bold text-slate-800 text-sm">Grade {c.class_level} ({c.stream})</span>
                  <span className="text-slate-500 block text-[11px]">Primary / Secondary Curriculum</span>
                </div>
                <Badge variant="info">{c.student_count || 0} Students</Badge>
              </div>
            ))}
          </div>
        </Card>

        {/* Teachers List */}
        <Card title="Accredited Teaching Faculty" subtitle={`${teachers.length} Verified Instructors`}>
          <div className="divide-y divide-slate-100 max-h-[400px] overflow-y-auto">
            {teachers.map((t) => (
              <div key={t.id} className="py-3 flex items-center justify-between text-xs">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-slate-900">{t.first_name} {t.last_name}</span>
                    {t.is_department_head && <Badge variant="purple" size="sm">Dept Head</Badge>}
                  </div>
                  <span className="text-[11px] font-mono text-slate-500">{t.staff_identifier}</span>
                </div>
                <Button size="sm" variant="outline" onClick={() => setSelectedTeacher(t)}>
                  View Profile
                </Button>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <TeacherProfileModal
        isOpen={!!selectedTeacher}
        onClose={() => setSelectedTeacher(null)}
        teacher={selectedTeacher}
      />
    </div>
  );
}
