import React, { useState } from 'react';
import { Button } from './ui/Button';
import { Input, Select } from './ui/Input';
import { X } from 'lucide-react';

export function StudentModal({ isOpen, onClose, onSave, classes = [], initialData = null }) {
  const [formData, setFormData] = useState({
    first_name: initialData?.first_name || '',
    last_name: initialData?.last_name || '',
    gender: initialData?.gender || 'Male',
    date_of_birth: initialData?.date_of_birth || '',
    class_id: initialData?.class_id || (classes[0]?.id || ''),
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.first_name || !formData.last_name) {
      setError('First and last name are required');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      await onSave({
        ...formData,
        class_id: formData.class_id ? parseInt(formData.class_id) : null,
        date_of_birth: formData.date_of_birth || null,
      });
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to save student');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full overflow-hidden border border-slate-200">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="font-bold text-slate-900 text-lg">
            {initialData ? 'Edit Student Details' : 'Enroll New Student'}
          </h3>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && <div className="p-3 bg-rose-50 text-rose-700 text-xs rounded-lg">{error}</div>}

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="First Name"
              value={formData.first_name}
              onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
              required
            />
            <Input
              label="Last Name"
              value={formData.last_name}
              onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Select
              label="Gender"
              value={formData.gender}
              onChange={(e) => setFormData({ ...formData, gender: e.target.value })}
            >
              <option value="Male">Male</option>
              <option value="Female">Female</option>
            </Select>

            <Select
              label="Assigned Class"
              value={formData.class_id}
              onChange={(e) => setFormData({ ...formData, class_id: e.target.value })}
            >
              <option value="">-- Select Class --</option>
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  Grade {c.class_level} ({c.stream})
                </option>
              ))}
            </Select>
          </div>

          <Input
            label="Date of Birth"
            type="date"
            value={formData.date_of_birth}
            onChange={(e) => setFormData({ ...formData, date_of_birth: e.target.value })}
          />

          {!initialData && (
            <p className="text-xs text-slate-500 bg-slate-50 p-2.5 rounded-lg border border-slate-200">
              ℹ️ A unique, immutable National Roll Number will be automatically allocated upon enrollment.
            </p>
          )}

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <Button variant="outline" onClick={onClose} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" loading={loading}>
              {initialData ? 'Save Changes' : 'Confirm Enrollment'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
