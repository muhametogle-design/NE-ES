import React, { useState, useEffect } from 'react';
import { useDispatch } from 'react-redux';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { addToast } from '../features/ui/uiSlice';
import { Database, ShieldCheck, Download, CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react';

export function Backups() {
  const dispatch = useDispatch();

  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [verifyingId, setVerifyingId] = useState(null);
  const [verifyResult, setVerifyResult] = useState(null);

  const loadBackups = async () => {
    try {
      setLoading(true);
      const data = await api.getBackups();
      setBackups(data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBackups();
  }, []);

  const handleCreateBackup = async () => {
    try {
      setCreating(true);
      await api.createBackup();
      dispatch(addToast({ type: 'success', message: 'AES-256-GCM encrypted backup archive generated!' }));
      loadBackups();
    } catch (err) {
      dispatch(addToast({ type: 'error', message: err.message }));
    } finally {
      setCreating(false);
    }
  };

  const handleVerifyBackup = async (id) => {
    try {
      setVerifyingId(id);
      const res = await api.verifyBackup(id);
      setVerifyResult(res);
      if (res.valid) {
        dispatch(addToast({ type: 'success', message: 'Cryptographic integrity and decryption verified!' }));
      } else {
        dispatch(addToast({ type: 'error', message: `Verification failed: ${res.reason}` }));
      }
    } catch (err) {
      dispatch(addToast({ type: 'error', message: err.message }));
    } finally {
      setVerifyingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Encrypted Disaster Recovery & Backups</h2>
          <p className="text-xs text-slate-500">
            Hardware-accelerated AES-256-GCM snapshots with SHA-256 cryptographic digests
          </p>
        </div>
        <Button onClick={handleCreateBackup} loading={creating} className="flex items-center gap-1.5">
          <Database className="h-4 w-4" /> Create Encrypted Snapshot
        </Button>
      </div>

      {/* Verification Result Banner */}
      {verifyResult && (
        <div
          className={`p-4 rounded-xl border flex items-start gap-3 text-xs ${
            verifyResult.valid
              ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
              : 'bg-rose-50 border-rose-200 text-rose-900'
          }`}
        >
          {verifyResult.valid ? (
            <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />
          ) : (
            <AlertTriangle className="h-5 w-5 text-rose-600 shrink-0" />
          )}
          <div>
            <h5 className="font-bold text-sm">
              {verifyResult.valid ? 'INTEGRITY VERIFICATION PASSED' : 'INTEGRITY CHECK FAILED'}
            </h5>
            {verifyResult.valid ? (
              <p className="mt-1">
                Decryption succeeded. Archive contains {verifyResult.item_counts?.students} student records and {verifyResult.item_counts?.schools} school structures.
              </p>
            ) : (
              <p className="mt-1">{verifyResult.reason}</p>
            )}
          </div>
        </div>
      )}

      {/* Backups List */}
      <Card title="Stored Backup Archives" subtitle="Retention policy: 30 days">
        {loading ? (
          <div className="py-8 text-center text-xs text-slate-400">Loading backup registry...</div>
        ) : backups.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-400">No backup snapshots generated yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-bold uppercase tracking-wider border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Size</th>
                  <th className="px-4 py-3">SHA-256 Digest</th>
                  <th className="px-4 py-3">Cipher</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {backups.map((b) => (
                  <tr key={b.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono font-bold text-slate-900">
                      {new Date(b.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="info">{b.backup_type}</Badge>
                    </td>
                    <td className="px-4 py-3 text-slate-600 font-mono">
                      {(b.file_size_bytes / 1024).toFixed(1)} KB
                    </td>
                    <td className="px-4 py-3 text-slate-500 font-mono text-[11px] truncate max-w-[120px]">
                      {b.checksum_sha256?.substring(0, 12)}...
                    </td>
                    <td className="px-4 py-3 text-emerald-700 font-semibold">{b.encryption_algorithm}</td>
                    <td className="px-4 py-3 text-right space-x-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleVerifyBackup(b.id)}
                        loading={verifyingId === b.id}
                      >
                        Verify
                      </Button>
                      <a
                        href={`/api/v1/school/backups/${b.id}/download`}
                        download
                        className="inline-flex items-center px-3 py-1 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-800"
                      >
                        <Download className="h-3.5 w-3.5 mr-1" /> Download
                      </a>
                    </td>
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
