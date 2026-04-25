import React, { useState, useEffect } from 'react';
import { api } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import {
  Building2, Users, GitBranch, DollarSign, TrendingUp, AlertTriangle,
  CreditCard, ArrowRight, Crown, UserCheck
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';

const PIE_COLORS = ['#64748B', '#3B82F6', '#F59E0B', '#10B981', '#8B5CF6', '#EF4444'];

export default function SuperAdminDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/api/superadmin/dashboard')
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
      </div>
    );
  }

  const { totals, companies_by_plan, estimated_revenue, revenue_by_plan, patient_growth, companies_at_limit, recent_plan_changes, new_companies_month } = data;

  return (
    <div className="space-y-6" data-testid="superadmin-dashboard">
      <div>
        <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Dashboard</h1>
        <p className="text-slate-500 mt-1">Vision general de la plataforma Cortexia Optical</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-slate-200/80" data-testid="kpi-companies">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-blue-50">
                <Building2 className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">{totals.companies}</p>
                <p className="text-xs text-slate-500">Opticas activas</p>
              </div>
            </div>
            {new_companies_month > 0 && (
              <p className="text-[11px] text-green-600 mt-2 flex items-center gap-1">
                <TrendingUp className="w-3 h-3" /> +{new_companies_month} este mes
              </p>
            )}
          </CardContent>
        </Card>
        <Card className="border-slate-200/80" data-testid="kpi-patients">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-green-50">
                <Users className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">{totals.patients.toLocaleString()}</p>
                <p className="text-xs text-slate-500">Pacientes totales</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="border-slate-200/80" data-testid="kpi-users">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-purple-50">
                <UserCheck className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">{totals.users}</p>
                <p className="text-xs text-slate-500">Usuarios activos</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="border-slate-200/80" data-testid="kpi-revenue">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-amber-50">
                <DollarSign className="w-5 h-5 text-amber-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">Q{estimated_revenue.toLocaleString()}</p>
                <p className="text-xs text-slate-500">Revenue mensual est.</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Companies by Plan - Pie */}
        <Card className="border-slate-200/80">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-600">Opticas por Plan</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {companies_by_plan.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={companies_by_plan}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={75}
                    innerRadius={40}
                    paddingAngle={3}
                    label={({ name, value }) => `${name} (${value})`}
                  >
                    {companies_by_plan.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => [`${v} opticas`, 'Cantidad']} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-slate-400 text-center py-8">Sin datos</p>
            )}
          </CardContent>
        </Card>

        {/* Patient Growth - Bar */}
        <Card className="border-slate-200/80 lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-600">Crecimiento de Pacientes (6 meses)</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={patient_growth} barSize={32}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => [`${v} pacientes`, 'Nuevos']} />
                <Bar dataKey="count" fill="#0F4C3A" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Revenue by Plan + Alerts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue by Plan */}
        <Card className="border-slate-200/80">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-600">Revenue Estimado por Plan</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {revenue_by_plan.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={revenue_by_plan} layout="vertical" barSize={24}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `Q${v}`} />
                  <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} width={80} />
                  <Tooltip formatter={(v) => [`Q${v.toLocaleString()}`, 'Revenue']} />
                  <Bar dataKey="value" fill="#F59E0B" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-slate-400 text-center py-8">Sin revenue</p>
            )}
          </CardContent>
        </Card>

        {/* Companies at Limit */}
        <Card className={`border-slate-200/80 ${companies_at_limit.length > 0 ? 'border-amber-200' : ''}`}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-600 flex items-center gap-2">
              {companies_at_limit.length > 0 && <AlertTriangle className="w-4 h-4 text-amber-500" />}
              Opticas Cerca del Limite ({companies_at_limit.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {companies_at_limit.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-8">Ninguna optica cerca del limite</p>
            ) : (
              <div className="space-y-2.5 max-h-[200px] overflow-y-auto pr-1">
                {companies_at_limit.map((c, i) => (
                  <div key={i} className="p-2.5 rounded-lg border border-amber-100 bg-amber-50/50" data-testid={`limit-alert-${i}`}>
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm text-slate-800">{c.name}</span>
                      <Badge className="bg-slate-100 text-slate-600 text-[10px]">{c.plan_name}</Badge>
                    </div>
                    <div className="flex gap-4 mt-1.5 text-xs text-slate-500">
                      {c.patients_warning && (
                        <span className={`flex items-center gap-1 ${c.patients_percent >= 100 ? 'text-red-600 font-medium' : 'text-amber-600'}`}>
                          <Users className="w-3 h-3" /> {c.patients}/{c.max_patients} pac ({c.patients_percent}%)
                        </span>
                      )}
                      {c.branches_warning && (
                        <span className={`flex items-center gap-1 ${c.branches_percent >= 100 ? 'text-red-600 font-medium' : 'text-amber-600'}`}>
                          <GitBranch className="w-3 h-3" /> {c.branches}/{c.max_branches} suc ({c.branches_percent}%)
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Plan Changes */}
      <Card className="border-slate-200/80">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-slate-600">Cambios de Plan Recientes</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {recent_plan_changes.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-6">Sin cambios recientes</p>
          ) : (
            <div className="space-y-2">
              {recent_plan_changes.map((h, i) => (
                <div key={h._id || i} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-slate-50 transition-colors" data-testid={`recent-change-${i}`}>
                  <div className="w-7 h-7 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0">
                    <CreditCard className="w-3.5 h-3.5 text-blue-600" />
                  </div>
                  <div className="flex-1 flex items-center gap-2 flex-wrap min-w-0">
                    <span className="font-medium text-sm text-slate-800 truncate">{h.company_name}</span>
                    <Badge className="bg-slate-100 text-slate-500 text-[10px]">{h.old_plan_name || 'Sin plan'}</Badge>
                    <ArrowRight className="w-3 h-3 text-slate-400 flex-shrink-0" />
                    <Badge className="bg-pine-100 text-pine-700 text-[10px]">{h.new_plan_name}</Badge>
                  </div>
                  <span className="text-[11px] text-slate-400 flex-shrink-0">{h.changed_at?.slice(0, 10)}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
