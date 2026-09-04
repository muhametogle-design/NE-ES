import React, { useState, useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { MetricCard } from '../components/ui/Charts';
import { addToast } from '../features/ui/uiSlice';
import {
  Building2, Users, AlertTriangle, ShieldCheck,
  Send, RefreshCw, CheckCircle2, Clock, Check
} from 'lucide-react';

export function StateDashboard() {
  const dispatch = useDispatch();

  const [summary, setSummary] = useState(null);
  const [complianceMap, setComplianceMap] = useState([]);
  const [alarms, setAlarms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [auditing, setAuditing] = useState(false);

  const loadStateData = async () => {
    try {
      setLoading(true);
      const [sum, cmap, alms] = await Promise.all([
        api.getStateSummary(),
        api.getComplianceMap(),
        api.getStateAlarms(),
      ]);
      setSummary(sum);
      setComplianceMap(cmap || []);
      setAlarms(alms || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStateData();
  }, []);

  const handleRunAudit = async () => {
    try {
      setAuditing(true);
      const res = await api.runStateAudit();
      dispatch(addToast({ type: 'success', message: 'Manual attendance audit executed across all private schools!' }));
      loadStateData();
    } catch (err) {
      dispatch(addToast({ type: 'error', message: err.message }));
    } finally {
      setAuditing(false);
    }
  };

  const handleDismissAlarm = async (alarmId) => {
    try {
      await api.dismissAlarm(alarmId);
      dispatch(addToast({ type: 'success', message: 'Compliance alarm dismissed' }));
      loadStateData();
    } catch (err) {
      dispatch(addToast({ type: 'error', message: err.message }));
    }
  };

  return (
    <div className="space-y-6">
      {/* State Ministry Banner */}
      <div className="bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950 p-6 rounded-2xl text-white shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4 border border-slate-800 gradient-bg">
        <div>
          <Badge variant="info" size="sm" className="mb-2">Ministry of Education Oversight Portal</Badge>
          <h2 className="text-2xl font-black tracking-tight">Regional Compliance & Accreditation Center</h2>
          <p className="text-xs text-slate-400 mt-1">
            Monitoring 5 Accredited Private Institutions in North-East District • Laascaanood Regional Office
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="danger"
            onClick={handleRunAudit}
            loading={auditing}
            className="flex items-center gap-2"
          >
            <ShieldCheck className="h-4 w-4" /> Run 15:00 Audit Now
          </Button>
          <Button variant="outline" onClick={loadStateData} className="text-slate-900">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Monitored Institutions"
          value={summary?.total_schools || 5}
          subtitle="All Private High Schools"
          icon={Building2}
        />
        <MetricCard
          title="Total Student Population"
          value={summary?.total_students || '—'}
          subtitle="Active National Roll Numbers"
          icon={Users}
        />
        <MetricCard
          title="Today's Compliance Rate"
          value={`${summary?.compliance_rate || 80}%`}
          subtitle="On-time daily submissions"
          trend={summary?.compliance_rate >= 80 ? 'up' : 'down'}
          icon={CheckCircle2}
        />
        <MetricCard
          title="Active Compliance Alarms"
          value={summary?.active_alarms_today || 0}
          subtitle="Schools in breach today"
          trend="down"
          icon={AlertTriangle}
        />
      </div>

      {/* Live Compliance Grid */}
      <Card
        title="Live Institution Attendance Compliance Grid"
        subtitle="Real-time transmission status (Deadline: 12:00 EAT • Alarm Trigger: 15:00 EAT)"
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {complianceMap.map((item) => (
            <div
              key={item.school_id}
              className={`p-4 rounded-xl border flex flex-col justify-between transition-all ${
                item.alarm
                  ? 'bg-rose-50 border-rose-300 text-rose-950 shadow-xs'
                  : item.submitted
                  ? 'bg-emerald-50/50 border-emerald-200 text-slate-800'
                  : 'bg-amber-50/50 border-amber-200 text-slate-800'
              }`}
            >
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="h-8 w-8 rounded-lg bg-slate-900 text-white font-bold text-xs flex items-center justify-center">
                    {item.school_code}
                  </span>
                  <Badge variant={item.alarm ? 'danger' : item.submitted ? 'success' : 'warning'}>
                    {item.alarm ? 'RED ALARM' : item.submitted ? 'Submitted' : 'Pending'}
                  </Badge>
                </div>
                <h4 className="font-bold text-xs leading-snug line-clamp-2">{item.school_name}</h4>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-200/60 text-[11px] text-slate-600">
                {item.submitted ? (
                  <span className="text-emerald-700 font-semibold flex items-center gap-1">
                    <Check className="h-3.5 w-3.5" /> In: {item.submitted_at ? new Date(item.submitted_at).toLocaleTimeString() : 'On Time'}
                  </span>
                ) : item.alarm ? (
                  <span className="text-rose-700 font-bold flex items-center gap-1">
                    <AlertTriangle className="h-3.5 w-3.5" /> Deadline Missed!
                  </span>
                ) : (
                  <span className="text-amber-700 flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5" /> Awaiting transmission
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Alarm Log Feed */}
      <Card title="Compliance Alarm & Breach Log Feed" subtitle="Certified communications issued to institutions">
        {alarms.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-400">No active compliance breach communications</div>
        ) : (
          <div className="divide-y divide-slate-100">
            {alarms.map((alarm) => (
              <div key={alarm.id} className="py-3.5 flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-rose-100 text-rose-700 rounded-lg mt-0.5 shrink-0">
                    <AlertTriangle className="h-4 w-4" />
                  </div>
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900 text-xs">
                        {alarm.school_name} ({alarm.school_code})
                      </span>
                      <Badge variant="danger" size="sm">{alarm.type}</Badge>
                      <Badge variant={alarm.status === 'Resolved' ? 'default' : 'warning'} size="sm">
                        {alarm.status}
                      </Badge>
                    </div>
                    <p className="text-xs text-slate-600">{alarm.content}</p>
                    <p className="text-[10px] text-slate-400 font-mono">
                      Issued: {new Date(alarm.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>

                {alarm.status !== 'Resolved' && (
                  <Button size="sm" variant="outline" onClick={() => handleDismissAlarm(alarm.id)}>
                    Dismiss
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
