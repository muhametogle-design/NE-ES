import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useSelector } from 'react-redux';

export function ProtectedRoute({ allowedRoles = [] }) {
  const { user, token } = useSelector((state) => state.auth);

  if (!token && !user) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles.length > 0 && user && !allowedRoles.includes(user.role)) {
    // Redirect based on role
    if (['state_admin', 'inspector'].includes(user.role)) {
      return <Navigate to="/state" replace />;
    }
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
