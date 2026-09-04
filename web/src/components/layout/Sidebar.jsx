import React from 'react';
import { NavLink } from 'react-router-dom';
import { useSelector } from 'react-redux';
import {
  LayoutDashboard, Users, CalendarCheck, RefreshCw, BookOpen,
  Fingerprint, DollarSign, Database, ShieldAlert, Building2,
  Search, FileText, UserCheck, GraduationCap
} from 'lucide-react';

export function Sidebar() {
  const { user } = useSelector((state) => state.auth);
  const { sidebarOpen } = useSelector((state) => state.ui);

  if (!user) return null;

  const isStateRole = ['state_admin', 'inspector'].includes(user.role);
  const isTeacher = user.role === 'teacher';
  const isManager = user.role === 'school_manager';

  const schoolLinks = [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    ...(isTeacher ? [{ name: 'Teacher Portal', path: '/teacher-portal', icon: UserCheck }] : []),
    { name: 'Students', path: '/students', icon: Users },
    { name: 'Attendance', path: '/attendance', icon: CalendarCheck },
    { name: 'Substitutions', path: '/substitutions', icon: RefreshCw },
    { name: 'Syllabus Pacing', path: '/syllabus', icon: BookOpen },
    { name: 'Biometrics & ID', path: '/biometrics', icon: Fingerprint },
    ...(isManager ? [{ name: 'Finance & Tuition', path: '/finance', icon: DollarSign }] : []),
    { name: 'Report Cards', path: '/report-cards', icon: GraduationCap },
    { name: 'Backups', path: '/backups', icon: Database },
  ];

  const stateLinks = [
    { name: 'State Overview', path: '/state', icon: LayoutDashboard },
    { name: 'School Directory', path: '/state/directory', icon: Building2 },
    { name: 'Student Registry', path: '/state/lookup', icon: Search },
    { name: 'Compliance Alarms', path: '/state/alarms', icon: ShieldAlert },
    { name: 'Reports & Logs', path: '/state/reports', icon: FileText },
  ];

  const links = isStateRole ? stateLinks : schoolLinks;

  return (
    <aside
      className={`${
        sidebarOpen ? 'w-64' : 'w-20'
      } transition-all duration-200 bg-slate-900 text-slate-300 flex flex-col shrink-0 border-r border-slate-800 z-30`}
    >
      <div className="h-16 flex items-center px-4 border-b border-slate-800 gap-3">
        <div className="h-9 w-9 bg-emerald-500 rounded-lg flex items-center justify-center font-bold text-white shadow-md shrink-0">
          NE
        </div>
        {sidebarOpen && (
          <div className="overflow-hidden">
            <h1 className="font-bold text-white text-sm tracking-wide leading-tight">NE-EMIS</h1>
            <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">
              {isStateRole ? 'State Ministry' : 'School System'}
            </p>
          </div>
        )}
      </div>

      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {links.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/dashboard' || item.path === '/state'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-semibold tracking-wide transition-colors ${
                  isActive
                    ? 'bg-emerald-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800'
                }`
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              {sidebarOpen && <span className="truncate">{item.name}</span>}
            </NavLink>
          );
        })}
      </nav>

      <div className="p-3 border-t border-slate-800">
        <div className={`flex items-center gap-3 ${sidebarOpen ? 'px-2' : 'justify-center'}`}>
          <div className="h-8 w-8 rounded-full bg-slate-700 flex items-center justify-center font-bold text-xs text-white shrink-0">
            {user.first_name?.[0] || 'U'}
          </div>
          {sidebarOpen && (
            <div className="overflow-hidden text-xs">
              <p className="font-semibold text-white truncate">{user.first_name} {user.last_name}</p>
              <p className="text-[10px] text-slate-400 uppercase tracking-wider truncate">{user.role.replace('_', ' ')}</p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
