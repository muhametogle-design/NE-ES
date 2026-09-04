import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Building2, Phone, Mail, MapPin, Award, CheckCircle } from 'lucide-react';

export function SchoolPortal() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [formData, setFormData] = useState({
    contact_phone: '',
    contact_email: '',
    physical_address: '',
  });

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      setLoading(true);
      const data = await api.getSchoolProfile();
      setProfile(data);
      setFormData({
        contact_phone: data.contact_phone || '',
        contact_email: data.contact_email || '',
        physical_address: data.physical_address || '',
      });
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      await api.updateSchoolProfile(formData);
      setEditing(false);
      loadProfile();
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) return <div className="p-8 text-center text-sm text-slate-500">Loading school details...</div>;

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold text-slate-900">School Tenant Profile</h2>
          <p className="text-xs text-slate-500">Official license and institutional configuration</p>
        </div>
        <Button variant={editing ? 'outline' : 'primary'} onClick={() => setEditing(!editing)}>
          {editing ? 'Cancel' : 'Edit Contact Details'}
        </Button>
      </div>

      <Card>
        <div className="flex items-start gap-5 border-b border-slate-100 pb-6">
          <div className="h-16 w-16 bg-slate-900 text-white rounded-2xl flex items-center justify-center font-bold text-2xl shrink-0">
            {profile?.school_code}
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h3 className="text-2xl font-black text-slate-900">{profile?.school_name}</h3>
              <Badge variant="success">{profile?.accreditation_status || 'Accredited'}</Badge>
            </div>
            <p className="text-xs text-slate-500 font-medium">State License: {profile?.state_license_number}</p>
            <p className="text-xs text-slate-600">Proprietor: <span className="font-semibold">{profile?.proprietor_name}</span></p>
          </div>
        </div>

        {editing ? (
          <form onSubmit={handleSave} className="pt-6 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Official Contact Phone"
                value={formData.contact_phone}
                onChange={(e) => setFormData({ ...formData, contact_phone: e.target.value })}
              />
              <Input
                label="Official Contact Email"
                value={formData.contact_email}
                onChange={(e) => setFormData({ ...formData, contact_email: e.target.value })}
              />
            </div>
            <Input
              label="Physical Address / Campus Location"
              value={formData.physical_address}
              onChange={(e) => setFormData({ ...formData, physical_address: e.target.value })}
            />
            <div className="flex justify-end pt-3">
              <Button type="submit">Save Updates</Button>
            </div>
          </form>
        ) : (
          <div className="pt-6 grid grid-cols-1 md:grid-cols-3 gap-6 text-xs">
            <div className="flex items-center gap-3 text-slate-700">
              <Phone className="h-4 w-4 text-slate-400" />
              <span>{profile?.contact_phone || 'N/A'}</span>
            </div>
            <div className="flex items-center gap-3 text-slate-700">
              <Mail className="h-4 w-4 text-slate-400" />
              <span>{profile?.contact_email || 'N/A'}</span>
            </div>
            <div className="flex items-center gap-3 text-slate-700">
              <MapPin className="h-4 w-4 text-slate-400" />
              <span>{profile?.physical_address || 'N/A'}</span>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
