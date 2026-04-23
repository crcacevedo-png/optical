import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { Toaster } from './components/ui/sonner';
import ProtectedRoute from './components/ProtectedRoute';
import MainLayout from './components/MainLayout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import PatientsPage from './pages/PatientsPage';
import AgendaPage from './pages/AgendaPage';
import ConsultationsPage from './pages/ConsultationsPage';
import PrescriptionsPage from './pages/PrescriptionsPage';
import InventoryPage from './pages/InventoryPage';
import SalesPage from './pages/SalesPage';
import QuotationsPage from './pages/QuotationsPage';
import AdminOpticasPage from './pages/AdminOpticasPage';
import FinancePage from './pages/FinancePage';
import BranchesPage from './pages/BranchesPage';
import UsersPage from './pages/UsersPage';
import ReportsPage from './pages/ReportsPage';
import SettingsPage from './pages/SettingsPage';
import SuppliersPage from './pages/SuppliersPage';
import './App.css';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <MainLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="patients" element={<PatientsPage />} />
            <Route path="agenda" element={<AgendaPage />} />
            <Route path="consultations" element={<ConsultationsPage />} />
            <Route path="prescriptions" element={<PrescriptionsPage />} />
            <Route path="inventory" element={<InventoryPage />} />
            <Route path="sales" element={<SalesPage />} />
            <Route path="quotations" element={<QuotationsPage />} />
            <Route path="admin/opticas" element={<AdminOpticasPage />} />
            <Route path="finance" element={<FinancePage />} />
            <Route path="branches" element={<BranchesPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="suppliers" element={<SuppliersPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </AuthProvider>
  );
}

export default App;
