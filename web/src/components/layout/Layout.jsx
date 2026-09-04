import React, { useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { addToast, removeToast } from '../../features/ui/uiSlice';
import { addLiveAlarm } from '../../features/state/stateSlice';
import { X, AlertTriangle, CheckCircle, Info } from 'lucide-react';

export function Layout() {
  const dispatch = useDispatch();
  const { user, token } = useSelector((state) => state.auth);
  const toasts = useSelector((state) => state.ui.toasts);

  // WebSocket Live Connection
  useEffect(() => {
    if (!token) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws?token=${token}`;
    let socket;

    try {
      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        // Send heartbeat ping periodically
        const pingInterval = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send('ping');
          }
        }, 30000);
        socket._pingInterval = pingInterval;
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'red_alarm') {
            dispatch(
              addToast({
                type: 'error',
                message: `RED ALARM: ${data.school_name || 'School'} missed daily compliance deadline!`,
              })
            );
            dispatch(
              addLiveAlarm({
                id: Date.now(),
                school_id: data.school_id,
                school_code: data.school_code,
                school_name: data.school_name,
                type: 'Red_Alarm',
                status: 'Delivered',
                content: data.message,
                created_at: data.timestamp || new Date().toISOString(),
              })
            );
          }
        } catch (e) {
          // Plain message
        }
      };

      socket.onclose = () => {
        if (socket._pingInterval) clearInterval(socket._pingInterval);
      };
    } catch (e) {
      console.warn('WebSocket connection error:', e);
    }

    return () => {
      if (socket) {
        if (socket._pingInterval) clearInterval(socket._pingInterval);
        socket.close();
      }
    };
  }, [token, dispatch]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>

      {/* Toast Notifications */}
      <div className="fixed bottom-5 right-5 z-50 space-y-2 max-w-sm w-full">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`p-4 rounded-xl shadow-lg border flex items-start justify-between gap-3 text-xs font-semibold ${
              toast.type === 'error'
                ? 'bg-rose-900 text-white border-rose-800'
                : toast.type === 'success'
                ? 'bg-emerald-900 text-white border-emerald-800'
                : 'bg-slate-900 text-white border-slate-800'
            }`}
          >
            <div className="flex items-center gap-2">
              {toast.type === 'error' && <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0" />}
              {toast.type === 'success' && <CheckCircle className="h-4 w-4 text-emerald-400 shrink-0" />}
              {toast.type === 'info' && <Info className="h-4 w-4 text-blue-400 shrink-0" />}
              <span>{toast.message}</span>
            </div>
            <button
              type="button"
              onClick={() => dispatch(removeToast(toast.id))}
              className="text-slate-400 hover:text-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
