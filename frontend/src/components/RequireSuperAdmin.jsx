import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

// Restringe una ruta al rol superadmin. Si no lo es, redirige al dashboard.
export default function RequireSuperAdmin({ children }) {
  const { user } = useAuth();
  if (user === null) return null; // aún verificando la sesión
  if (!user || user.role !== 'superadmin') return <Navigate to="/dashboard" replace />;
  return children;
}
