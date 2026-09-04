import React, { useState, useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { toggleSidebar } from '../../features/ui/uiSlice';
import { logoutUser } from '../../features/auth/authSlice';
import { DataSaverToggle } from '../ui/DataSaverToggle';
import { Menu, LogOut, Radio, Clock, ShieldCheck } from 'lucide-react';

export function Header() {
  const dispatch = useDispatch();
  const { user } = useSelector((state) => state.auth);
  const [time, setTime] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTime(
        now.toLocaleTimeString('en-US', {
          timeZone: 'Africa/Nairobi',
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        }) + ' EAT'
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between shrink-0 z-20">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={() => dispatch(toggleSidebar())}
          className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 focus:outline-none"
        >
          <Menu className="h-5 w-5" />
        </button>

        <div className="hidden sm:flex items-center gap-2 text-xs font-semibold text-slate-600 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200">
          <Clock className="h-3.5 w-3.5 text-slate-400" />
          <span>{time}</span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <DataSaverToggle />

        <div className="flex items-center gap-2 pl-2 border-l border-slate-200">
          <div className="hidden md:flex flex-col text-right">
            <span className="text-xs font-bold text-slate-800 leading-tight">
              {user?.first_name} {user?.last_name}
            </span>
            <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
              {user?.role?.replace('_', ' ')}
            </span>
          </div>

          <button
            type="button"
            onClick={() => dispatch(logoutUser())}
            title="Log Out"
            className="p-2 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
