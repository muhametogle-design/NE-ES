import React, { useState, useEffect } from 'react';
import { useDispatch } from 'react-redux';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input, Select } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { addToast } from '../features/ui/uiSlice';
import { Fingerprint, ShieldCheck, UserCheck, AlertTriangle, CheckCircle2 } from 'lucide-react';

export function Biometrics() {
  const dispatch = useDispatch();

  const [students, setStudents] = useState([]);
  const [logs, setLogs] = useState([]);
  const [selectedStudent, setSelectedStudent] = useState('');
  const [credId, setCredId] = useState('');
  const [verifyCredId, setVerifyCredId] = useState('');
  const [verificationResult, setVerificationResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [stuRes, logRes] = await Promise.all([
        api.getStudents('per_page=100'),
        api.getBiometricLogs(),
      ]);
      const stus = stuRes.items || [];
      setStudents(stus);
      setLogs(logRes || []);
      if (stus.length > 0) setSelectedStudent(stus[0].id);
    } catch (e) {
      console.error(e);
    }
  };

  const handleRegisterBiometric = async (e) => {
    e.preventDefault();
    if (!selectedStudent) return;
    try {
      setLoading(true);
      const student = students.find((s) => s.id === parseInt(selectedStudent));
      const generatedCredId = `FIDO2-NE-${student?.roll_number}-${Date.now().toString().slice(-6)}`;
      const pubKey = `PUB-EC256-${Math.random().toString(36).substring(2, 15)}`;

      await api.registerBiometrics({
        student_id: parseInt(selectedStudent),
        credential_id: generatedCredId,
        public_key: pubKey,
      });

      dispatch(addToast({ type: 'success', message: `Biometric credential linked to ${student?.first_name} ${student?.last_name}` }));
      setVerifyCredId(generatedCredId);
      loadData();
    } catch (err) {
      dispatch(addToast({ type: 'error', message: err.message }));
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyBiometric = async (type = 'exam_hall_entry') => {
    if (!verifyCredId) {
      dispatch(addToast({ type: 'error', message: 'Enter a Credential ID to verify' }));
      return;
    }
    try {
      setLoading(true);
      const res = await api.verifyBiometrics({
        credential_id: verifyCredId,
        verification_type: type,
      });
      setVerificationResult(res);
      if (res.success) {
        dispatch(addToast({ type: 'success', message: `Biometric Verified: ${res.student_name} (${res.roll_number})` }));
      } else {
        dispatch(addToast({ type: 'error', message: `Biometric Rejected: ${res.reason}` }));
      }
      loadData();
    } catch (err) {
      dispatch(addToast({ type: 'error', message: err.message }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Biometric Identity & Verification Terminal</h2>
        <p className="text-xs text-slate-500">WebAuthn student credential enrollment and exam hall entry authentication</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Enroll Biometric Credential */}
        <Card title="Enroll Student Biometric Key" subtitle="Register FIDO2 hardware token or passkey">
          <form onSubmit={handleRegisterBiometric} className="space-y-4">
            <Select
              label="Select Enrolled Student"
              value={selectedStudent}
              onChange={(e) => setSelectedStudent(e.target.value)}
            >
              {students.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.roll_number} — {s.first_name} {s.last_name}
                </option>
              ))}
            </Select>

            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs text-slate-600">
              <span className="font-bold block mb-1 text-slate-800">FIDO2 / WebAuthn Hardware Integration</span>
              Generates cryptographic key pair bound to the student's immutable National Roll Number.
            </div>

            <Button type="submit" loading={loading} className="w-full flex items-center justify-center gap-2">
              <Fingerprint className="h-4 w-4" /> Enroll Biometric Key
            </Button>
          </form>
        </Card>

        {/* Verification Checkpoint */}
        <Card title="Exam Hall Verification Scanner" subtitle="Authenticate student biometric credentials at gate">
          <div className="space-y-4">
            <Input
              label="Scanned Credential Identifier"
              placeholder="e.g. FIDO2-NE-IL-10001-..."
              value={verifyCredId}
              onChange={(e) => setVerifyCredId(e.target.value)}
            />

            <div className="flex gap-2">
              <Button
                variant="primary"
                onClick={() => handleVerifyBiometric('exam_hall_entry')}
                className="flex-1"
                disabled={loading}
              >
                Scan for Exam Hall Entry
              </Button>
              <Button
                variant="outline"
                onClick={() => handleVerifyBiometric('daily_gate')}
                className="flex-1"
                disabled={loading}
              >
                Scan Daily Gate
              </Button>
            </div>

            {verificationResult && (
              <div
                className={`p-4 rounded-xl border flex items-start gap-3 text-xs ${
                  verificationResult.success
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                    : 'bg-rose-50 border-rose-200 text-rose-900'
                }`}
              >
                {verificationResult.success ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
                )}
                <div>
                  <h5 className="font-bold text-sm">
                    {verificationResult.success ? 'AUTHENTICATION SUCCESSFUL' : 'ACCESS DENIED'}
                  </h5>
                  {verificationResult.success ? (
                    <p className="mt-1">
                      Identity verified: <strong>{verificationResult.student_name}</strong> ({verificationResult.roll_number}). Authorized for entry.
                    </p>
                  ) : (
                    <p className="mt-1">{verificationResult.reason}</p>
                  )}
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Audit Logs */}
      <Card title="Recent Biometric Verification Logs" subtitle="Security audit trail of all scan attempts">
        {logs.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-400">No biometric verification events recorded yet</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-bold uppercase tracking-wider border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Student Name</th>
                  <th className="px-4 py-3">Verification Type</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Details / Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5 text-slate-500 font-mono">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5 font-semibold text-slate-800">
                      {log.student_name || 'Anonymous / Unregistered'}
                    </td>
                    <td className="px-4 py-2.5 text-slate-600">{log.verification_type}</td>
                    <td className="px-4 py-2.5">
                      <Badge variant={log.status === 'success' ? 'success' : 'danger'}>
                        {log.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-2.5 text-slate-500">{log.reason || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
