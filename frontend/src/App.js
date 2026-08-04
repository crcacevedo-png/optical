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
import PlansPage from './pages/PlansPage';
import SuperAdminDashboard from './pages/SuperAdminDashboard';
import AnnouncementsPage from './pages/AnnouncementsPage';
import AuditLogPage from './pages/AuditLogPage';
import OnboardingPage from './pages/OnboardingPage';
import HealthMetricsPage from './pages/HealthMetricsPage';
import ReceivablesPage from './pages/ReceivablesPage';
import CashRegisterPage from './pages/CashRegisterPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import './App.css';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
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
            <Route path="onboarding" element={<OnboardingPage />} />
            <Route path="patients" element={<PatientsPage />} />
            <Route path="agenda" element={<AgendaPage />} />
            <Route path="consultations" element={<ConsultationsPage />} />
            <Route path="prescriptions" element={<PrescriptionsPage />} />
            <Route path="inventory" element={<InventoryPage />} />
            <Route path="sales" element={<SalesPage />} />
            <Route path="receivables" element={<ReceivablesPage />} />
            <Route path="cash-register" element={<CashRegisterPage />} />
            <Route path="quotations" element={<QuotationsPage />} />
            <Route path="admin/opticas" element={<AdminOpticasPage />} />
            <Route path="admin/planes" element={<PlansPage />} />
            <Route path="admin/dashboard" element={<SuperAdminDashboard />} />
            <Route path="admin/comunicacion" element={<AnnouncementsPage />} />
            <Route path="admin/audit" element={<AuditLogPage />} />
            <Route path="admin/health" element={<HealthMetricsPage />} />
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
