import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { ProtectedRoute } from './components/ProtectedRoute';

// Pages
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { SchoolPortal } from './pages/SchoolPortal';
import { TeacherPortal } from './pages/TeacherPortal';
import { Students } from './pages/Students';
import { Attendance } from './pages/Attendance';
import { Substitutions } from './pages/Substitutions';
import { Syllabus } from './pages/Syllabus';
import { Biometrics } from './pages/Biometrics';
import { Finance } from './pages/Finance';
import { ReportCard } from './pages/ReportCard';
import { Backups } from './pages/Backups';

import { StateDashboard } from './pages/StateDashboard';
import { Directory } from './pages/Directory';
import { InstitutionDetail } from './pages/InstitutionDetail';
import { StateLookup } from './pages/StateLookup';

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />

        {/* Authenticated Application */}
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            {/* School Tenant Routes */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/school-portal" element={<SchoolPortal />} />
            <Route path="/teacher-portal" element={<TeacherPortal />} />
            <Route path="/students" element={<Students />} />
            <Route path="/attendance" element={<Attendance />} />
            <Route path="/substitutions" element={<Substitutions />} />
            <Route path="/syllabus" element={<Syllabus />} />
            <Route path="/biometrics" element={<Biometrics />} />
            <Route path="/finance" element={<Finance />} />
            <Route path="/report-cards" element={<ReportCard />} />
            <Route path="/backups" element={<Backups />} />

            {/* State Oversight Routes */}
            <Route path="/state" element={<StateDashboard />} />
            <Route path="/state/directory" element={<Directory />} />
            <Route path="/state/institutions/:id" element={<InstitutionDetail />} />
            <Route path="/state/lookup" element={<StateLookup />} />
            <Route path="/state/alarms" element={<StateDashboard />} />
            <Route path="/state/reports" element={<StateDashboard />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
