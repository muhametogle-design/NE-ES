/**
 * NE-EMIS Administrative Terminal Vanilla JS Application
 */

const state = {
  token: typeof localStorage !== 'undefined' ? localStorage.getItem('access_token') : null,
  user: null,
  schools: [],
  compliance: [],
  alarms: [],
};

async function api(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(`/api${path}`, { ...options, headers });
  if (res.status === 401) {
    state.token = null;
    state.user = null;
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('access_token');
    }
  }
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || data.message || 'API error');
  }
  return data;
}

async function login(email, password) {
  try {
    const res = await api('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    state.token = res.access_token;
    state.user = res.user;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('access_token', res.access_token);
    }
    render();
  } catch (err) {
    alert(`Login failed: ${err.message}`);
  }
}

async function logout() {
  try {
    await api('/auth/logout', { method: 'POST' });
  } catch (e) {
    // Ignore
  }
  state.token = null;
  state.user = null;
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem('access_token');
  }
  render();
}

async function triggerManualAudit() {
  try {
    const res = await api('/v1/state/audit/run', { method: 'POST' });
    alert(`Audit Complete: ${res.message || 'Success'}`);
    loadDashboard();
  } catch (err) {
    alert(`Audit Error: ${err.message}`);
  }
}

async function loadDashboard() {
  if (!state.token) return;
  try {
    const [me, schools, cmap, alms] = await Promise.all([
      api('/auth/me').catch(() => null),
      api('/v1/state/schools').catch(() => []),
      api('/v1/state/compliance-map').catch(() => []),
      api('/v1/state/alarms').catch(() => []),
    ]);
    state.user = me;
    state.schools = schools;
    state.compliance = cmap;
    state.alarms = alms;
    render();
  } catch (e) {
    console.error('Failed loading state data:', e);
  }
}

function render() {
  const root = document.getElementById('app');
  const statusEl = document.getElementById('auth-status');
  if (!root) return;

  if (!state.token || !state.user) {
    if (statusEl) statusEl.textContent = 'Status: Unauthenticated';
    root.innerHTML = `
      <div class="bg-slate-900 p-8 rounded-2xl border border-slate-800 shadow-xl max-w-md mx-auto space-y-4">
        <h2 class="text-lg font-bold text-white">Administrative Sign In</h2>
        <div class="space-y-3 text-sm">
          <input id="login-email" type="email" placeholder="Email Address" value="stateadmin@education.gov" class="w-full px-3.5 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white" />
          <input id="login-password" type="password" placeholder="Password" value="StateAdmin@2026" class="w-full px-3.5 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white" />
          <button id="btn-login" class="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 font-bold rounded-lg text-white transition-colors">Sign In to Terminal</button>
        </div>
      </div>
    `;

    const btn = document.getElementById('btn-login');
    if (btn) {
      btn.onclick = () => {
        const email = document.getElementById('login-email').value;
        const pass = document.getElementById('login-password').value;
        login(email, pass);
      };
    }
    return;
  }

  if (statusEl) {
    statusEl.innerHTML = `Active User: <strong class="text-emerald-400">${state.user.first_name} ${state.user.last_name} (${state.user.role})</strong>`;
  }

  root.innerHTML = `
    <div class="space-y-6">
      <div class="flex justify-between items-center bg-slate-900 p-4 rounded-xl border border-slate-800">
        <div class="flex gap-2">
          <button id="btn-audit" class="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs rounded-lg">Execute Compliance Audit</button>
          <button id="btn-refresh" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs rounded-lg">Refresh Metrics</button>
        </div>
        <button id="btn-logout" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-rose-400 font-bold text-xs rounded-lg">Sign Out</button>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="bg-slate-900 p-5 rounded-xl border border-slate-800">
          <p class="text-xs uppercase text-slate-400 font-semibold">Monitored Schools</p>
          <h3 class="text-2xl font-bold text-white mt-1">${state.schools.length}</h3>
        </div>
        <div class="bg-slate-900 p-5 rounded-xl border border-slate-800">
          <p class="text-xs uppercase text-slate-400 font-semibold">Active Compliance Alarms</p>
          <h3 class="text-2xl font-bold text-rose-400 mt-1">${state.alarms.length}</h3>
        </div>
        <div class="bg-slate-900 p-5 rounded-xl border border-slate-800">
          <p class="text-xs uppercase text-slate-400 font-semibold">District Office</p>
          <h3 class="text-lg font-bold text-emerald-400 mt-1">Laascaanood (Sool Region)</h3>
        </div>
      </div>

      <div class="bg-slate-900 p-6 rounded-2xl border border-slate-800 space-y-4">
        <h3 class="font-bold text-white text-base">Institution Compliance Registry</h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          ${state.compliance
            .map(
              (c) => `
            <div class="p-3.5 rounded-xl border ${
              c.alarm
                ? 'bg-rose-950/50 border-rose-800 text-rose-200'
                : c.submitted
                ? 'bg-emerald-950/50 border-emerald-800 text-emerald-200'
                : 'bg-amber-950/50 border-amber-800 text-amber-200'
            } text-xs space-y-1">
              <div class="font-bold text-white flex justify-between">
                <span>${c.school_code}</span>
                <span class="text-[10px] uppercase font-mono">${c.alarm ? 'RED ALARM' : c.submitted ? 'OK' : 'PENDING'}</span>
              </div>
              <p class="truncate text-slate-300">${c.school_name}</p>
            </div>
          `
            )
            .join('')}
        </div>
      </div>
    </div>
  `;

  document.getElementById('btn-audit').onclick = triggerManualAudit;
  document.getElementById('btn-refresh').onclick = loadDashboard;
  document.getElementById('btn-logout').onclick = logout;
}

if (typeof window !== 'undefined') {
  window.addEventListener('DOMContentLoaded', () => {
    if (state.token) {
      loadDashboard();
    } else {
      render();
    }
  });
}
