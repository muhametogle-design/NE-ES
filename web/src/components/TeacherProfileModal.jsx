import React from 'react';
import { Button } from './ui/Button';
import { Badge } from './ui/Badge';
import { X, Mail, Phone, Award, BookOpen, ShieldCheck } from 'lucide-react';

export function TeacherProfileModal({ isOpen, onClose, teacher }) {
  if (!isOpen || !teacher) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full overflow-hidden border border-slate-200">
        <div className="px-6 py-4 bg-slate-900 text-white flex items-center justify-between">
          <div>
            <h3 className="font-bold text-lg">Teacher Profile</h3>
            <p className="text-xs text-slate-300">National Staff Identifier: {teacher.staff_identifier || 'N/A'}</p>
          </div>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <div className="flex items-center gap-4 border-b border-slate-100 pb-4">
            <div className="h-16 w-16 bg-emerald-100 text-emerald-800 rounded-full flex items-center justify-center font-bold text-2xl border-2 border-emerald-300">
              {teacher.first_name?.[0]}{teacher.last_name?.[0]}
            </div>
            <div>
              <h4 className="text-xl font-bold text-slate-900">
                {teacher.first_name} {teacher.last_name}
              </h4>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{teacher.designation || 'Faculty Member'}</p>
              <div className="flex gap-2 mt-2">
                {teacher.is_department_head && <Badge variant="purple">Department Head</Badge>}
                <Badge variant={teacher.is_active ? 'success' : 'danger'}>
                  {teacher.is_active ? 'Active Staff' : 'Inactive'}
                </Badge>
              </div>
            </div>
          </div>

          <div className="space-y-3 text-sm">
            <div className="flex items-center gap-3 text-slate-700">
              <Mail className="h-4 w-4 text-slate-400" />
              <span>{teacher.email}</span>
            </div>

            {teacher.phone && (
              <div className="flex items-center gap-3 text-slate-700">
                <Phone className="h-4 w-4 text-slate-400" />
                <span>{teacher.phone}</span>
              </div>
            )}

            <div className="flex items-start gap-3 text-slate-700">
              <Award className="h-4 w-4 text-slate-400 mt-0.5" />
              <div>
                <span className="font-semibold text-xs uppercase text-slate-500 block">Qualifications</span>
                <span>{teacher.qualifications || 'Standard Education Certification'}</span>
              </div>
            </div>

            {teacher.bio && (
              <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs text-slate-600 mt-2">
                <span className="font-semibold text-slate-700 block mb-1">Bio / Profile Note</span>
                {teacher.bio}
              </div>
            )}
          </div>

          <div className="flex justify-end pt-3 border-t border-slate-100">
            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
