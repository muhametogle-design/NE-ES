import React, { useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { loginUser, clearError } from '../features/auth/authSlice';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { ShieldCheck, School, Lock, KeyRound, Mail, UserCheck } from 'lucide-react';

export function Login() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { loading, error } = useSelector((state) => state.auth);

  const [authMode, setAuthMode] = useState('email'); // 'email' | 'pin'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [staffId, setStaffId] = useState('');
  const [pin, setPin] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    dispatch(clearError());
    let payload = {};
    if (authMode === 'email') {
      payload = { email, password };
    } else {
      payload = { staff_identifier: staffId, pin };
    }

    const res = await dispatch(loginUser(payload));
    if (res.meta.requestStatus === 'fulfilled') {
      const role = res.payload.user.role;
      if (['state_admin', 'inspector'].includes(role)) {
        navigate('/state');
      } else {
        navigate('/dashboard');
      }
    }
  };

  const fillDemo = (type) => {
    dispatch(clearError());
    if (type === 'state') {
      setAuthMode('email');
      setEmail('stateadmin@education.gov');
      setPassword('StateAdmin@2026');
    } else if (type === 'manager') {
      setAuthMode('email');
      setEmail('manager@nugaal.edu.so');
      setPassword('School@2026');
    } else if (type === 'teacher') {
      setAuthMode('email');
      setEmail('ayaan.hassan@nugaal.edu.so');
      setPassword('Teach@2026');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 p-4 relative overflow-hidden">
      {/* Background visual accents */}
      <div className="absolute -top-32 -left-32 w-96 h-96 bg-emerald-600/20 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-32 -right-32 w-96 h-96 bg-blue-600/20 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-md w-full bg-white rounded-2xl shadow-2xl overflow-hidden border border-slate-200 z-10">
        <div className="bg-slate-950 p-6 text-center text-white border-b border-slate-800">
          <div className="h-12 w-12 bg-emerald-500 rounded-xl mx-auto flex items-center justify-center font-black text-2xl shadow-lg mb-3">
            NE
          </div>
          <h2 className="text-xl font-bold tracking-tight">NE-EMIS Authentication</h2>
          <p className="text-xs text-slate-400 mt-1">North-East Education Management & Compliance Network</p>
        </div>

        <div className="p-6">
          <div className="flex bg-slate-100 p-1 rounded-xl mb-6 border border-slate-200">
            <button
              type="button"
              onClick={() => { setAuthMode('email'); dispatch(clearError()); }}
              className={`flex-1 py-2 text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 ${
                authMode === 'email' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Mail className="h-3.5 w-3.5" /> Email & Password
            </button>
            <button
              type="button"
              onClick={() => { setAuthMode('pin'); dispatch(clearError()); }}
              className={`flex-1 py-2 text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 ${
                authMode === 'pin' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <KeyRound className="h-3.5 w-3.5" /> Staff ID & PIN
            </button>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium rounded-lg">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {authMode === 'email' ? (
              <>
                <Input
                  label="Official Email Address"
                  type="email"
                  placeholder="user@school.edu.so"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
                <Input
                  label="Password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </>
            ) : (
              <>
                <Input
                  label="National Staff Identifier"
                  placeholder="NE-TID-2026-XX123"
                  value={staffId}
                  onChange={(e) => setStaffId(e.target.value)}
                  required
                />
                <Input
                  label="Security PIN"
                  type="password"
                  maxLength={8}
                  placeholder="••••"
                  value={pin}
                  onChange={(e) => setPin(e.target.value)}
                  required
                />
              </>
            )}

            <Button type="submit" loading={loading} className="w-full mt-2" size="lg">
              Secure Sign In
            </Button>
          </form>

          {/* Quick Demo Fill Buttons */}
          <div className="mt-6 pt-6 border-t border-slate-100">
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 text-center mb-3">
              Fast Demo Logins
            </p>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => fillDemo('state')}
                className="px-2 py-1.5 text-[11px] font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-center"
              >
                State Admin
              </button>
              <button
                type="button"
                onClick={() => fillDemo('manager')}
                className="px-2 py-1.5 text-[11px] font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-800 rounded-lg text-center"
              >
                School Manager
              </button>
              <button
                type="button"
                onClick={() => fillDemo('teacher')}
                className="px-2 py-1.5 text-[11px] font-semibold bg-blue-50 hover:bg-blue-100 text-blue-800 rounded-lg text-center"
              >
                Teacher
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
