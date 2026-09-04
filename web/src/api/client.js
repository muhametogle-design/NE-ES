const API_BASE = '/api';

export async function apiRequest(endpoint, options = {}) {
  const token = localStorage.getItem('access_token');
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (response.status === 401) {
    // Only redirect if not already on login
    if (!window.location.pathname.includes('/login')) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
  }

  const contentType = response.headers.get('content-type');
  let data;
  if (contentType && contentType.includes('application/json')) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const errorMsg = data?.detail || data?.message || response.statusText || 'Request failed';
    throw new Error(errorMsg);
  }

  return data;
}

export const api = {
  // Auth
  login: (credentials) => apiRequest('/auth/login', { method: 'POST', body: JSON.stringify(credentials) }),
  getMe: () => apiRequest('/auth/me'),
  logout: () => apiRequest('/auth/logout', { method: 'POST' }),
  changePassword: (data) => apiRequest('/auth/change-password', { method: 'POST', body: JSON.stringify(data) }),
  setPin: (data) => apiRequest('/auth/set-pin', { method: 'POST', body: JSON.stringify(data) }),

  // School
  getStudents: (params = '') => apiRequest(`/v1/school/students?${params}`),
  getStudent: (id) => apiRequest(`/v1/school/students/${id}`),
  createStudent: (data) => apiRequest('/v1/school/students', { method: 'POST', body: JSON.stringify(data) }),
  updateStudent: (id, data) => apiRequest(`/v1/school/students/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteStudent: (id) => apiRequest(`/v1/school/students/${id}`, { method: 'DELETE' }),

  getClasses: () => apiRequest('/v1/school/classes'),
  createClass: (data) => apiRequest('/v1/school/classes', { method: 'POST', body: JSON.stringify(data) }),
  getClassBreakdown: (id) => apiRequest(`/v1/school/classes/${id}/breakdown`),

  getSubjects: (level) => apiRequest(`/v1/school/subjects${level ? `?level=${level}` : ''}`),
  createSubject: (data) => apiRequest('/v1/school/subjects', { method: 'POST', body: JSON.stringify(data) }),

  getTeachers: () => apiRequest('/v1/school/teachers'),
  getTeacher: (id) => apiRequest(`/v1/school/teachers/${id}`),
  createTeacher: (data) => apiRequest('/v1/school/teachers', { method: 'POST', body: JSON.stringify(data) }),
  createAssignment: (data) => apiRequest('/v1/school/assignments', { method: 'POST', body: JSON.stringify(data) }),

  getTimetable: (params = '') => apiRequest(`/v1/school/timetable?${params}`),
  createTimetableSlot: (data) => apiRequest('/v1/school/timetable', { method: 'POST', body: JSON.stringify(data) }),
  deleteTimetableSlot: (id) => apiRequest(`/v1/school/timetable/${id}`, { method: 'DELETE' }),

  getAttendance: (classId, subjectId, date) => apiRequest(`/v1/school/attendance?class_id=${classId}&subject_id=${subjectId}&att_date=${date}`),
  markAttendance: (data) => apiRequest('/v1/school/attendance', { method: 'POST', body: JSON.stringify(data) }),
  submitDailyAttendance: () => apiRequest('/v1/school/attendance/submit', { method: 'POST' }),

  getGrades: (subjectId, classId, term) => apiRequest(`/v1/school/grades?subject_id=${subjectId}&class_id=${classId}&term=${term}`),
  enterGrades: (data) => apiRequest('/v1/school/grades', { method: 'POST', body: JSON.stringify(data) }),
  publishGrades: (data) => apiRequest('/v1/school/grades/publish', { method: 'POST', body: JSON.stringify(data) }),

  getAbsences: () => apiRequest('/v1/school/absences'),
  reportAbsence: (data) => apiRequest('/v1/school/absences', { method: 'POST', body: JSON.stringify(data) }),
  getSubstitutions: () => apiRequest('/v1/school/substitutions'),
  getSubstitutionCandidates: (slotId, date) => apiRequest(`/v1/school/substitutions/candidates?slot_id=${slotId}&abs_date=${date}`),
  assignSubstitution: (data) => apiRequest('/v1/school/substitutions', { method: 'POST', body: JSON.stringify(data) }),
  confirmSubstitution: (id) => apiRequest(`/v1/school/substitutions/${id}/confirm`, { method: 'POST' }),

  getSyllabusPlans: (classId) => apiRequest(`/v1/school/syllabus/plans${classId ? `?class_id=${classId}` : ''}`),
  createSyllabusPlan: (data) => apiRequest('/v1/school/syllabus/plans', { method: 'POST', body: JSON.stringify(data) }),
  createSyllabusTopic: (data) => apiRequest('/v1/school/syllabus/topics', { method: 'POST', body: JSON.stringify(data) }),
  recordSyllabusProgress: (data) => apiRequest('/v1/school/syllabus/progress', { method: 'POST', body: JSON.stringify(data) }),
  getSyllabusStatus: () => apiRequest('/v1/school/syllabus/status'),

  getBiometricLogs: () => apiRequest('/v1/school/biometrics/logs'),
  registerBiometrics: (data) => apiRequest('/v1/school/biometrics/register/verify', { method: 'POST', body: JSON.stringify(data) }),
  verifyBiometrics: (data) => apiRequest('/v1/school/biometrics/verify', { method: 'POST', body: JSON.stringify(data) }),

  getBackups: () => apiRequest('/v1/school/backups'),
  createBackup: () => apiRequest('/v1/school/backups/create', { method: 'POST' }),
  verifyBackup: (id) => apiRequest(`/v1/school/backups/${id}/verify`, { method: 'POST' }),

  getFinanceSummary: () => apiRequest('/v1/school/finance/summary'),
  getInvoices: () => apiRequest('/v1/school/finance/invoices'),
  createInvoice: (data) => apiRequest('/v1/school/finance/invoices', { method: 'POST', body: JSON.stringify(data) }),
  recordPayment: (invId, data) => apiRequest(`/v1/school/finance/invoices/${invId}/payments`, { method: 'POST', body: JSON.stringify(data) }),
  getTuitionRates: () => apiRequest('/v1/school/finance/rates'),
  createTuitionRate: (data) => apiRequest('/v1/school/finance/rates', { method: 'POST', body: JSON.stringify(data) }),

  getSchoolProfile: () => apiRequest('/v1/school/profile'),
  getSchoolAnalytics: () => apiRequest('/v1/school/analytics/enrollment'),

  // State
  getStateSchools: () => apiRequest('/v1/state/schools'),
  getStateSchool: (id) => apiRequest(`/v1/state/schools/${id}`),
  createStateSchool: (data) => apiRequest('/v1/state/schools', { method: 'POST', body: JSON.stringify(data) }),
  getStateClasses: (schoolId) => apiRequest(`/v1/state/institutions/${schoolId}/classes`),
  getStateClassBreakdown: (schoolId, classId) => apiRequest(`/v1/state/institutions/${schoolId}/classes/${classId}/breakdown`),
  getStateTeachers: (schoolId) => apiRequest(`/v1/state/institutions/${schoolId}/teachers`),
  getStateTeacher: (id) => apiRequest(`/v1/state/teachers/${id}`),
  getRollSequence: (schoolId) => apiRequest(`/v1/state/schools/${schoolId}/roll-sequence`),
  updateRollSequence: (schoolId, data) => apiRequest(`/v1/state/schools/${schoolId}/roll-sequence`, { method: 'PATCH', body: JSON.stringify(data) }),
  searchStateStudents: (q) => apiRequest(`/v1/state/students/search?q=${encodeURIComponent(q)}`),
  lookupStateStudent: (id) => apiRequest(`/v1/state/students/lookup?ne_sid=${encodeURIComponent(id)}`),
  getComplianceMap: () => apiRequest('/v1/state/compliance-map'),
  getStateAlarms: () => apiRequest('/v1/state/alarms'),
  dismissAlarm: (id) => apiRequest(`/v1/state/alarms/dismiss?alarm_id=${id}`, { method: 'POST' }),
  runStateAudit: () => apiRequest('/v1/state/audit/run', { method: 'POST' }),
  getStateSummary: () => apiRequest('/v1/state/analytics/summary'),
  getStateRankings: () => apiRequest('/v1/state/analytics/school-rankings'),
  getStateGender: () => apiRequest('/v1/state/analytics/gender-distribution'),
};
