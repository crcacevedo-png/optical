import React, { useState, useEffect } from 'react';
import { api } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { 
  BarChart3, TrendingUp, Users, ShoppingBag, 
  Calendar, FileText, DollarSign, Package
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

export default function ReportsPage() {
  const [salesReport, setSalesReport] = useState(null);
  const [financeSummary, setFinanceSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState({
    from: new Date().toISOString().slice(0, 8) + '01',
    to: new Date().toISOString().slice(0, 10)
  });

  useEffect(() => {
    fetchReports();
  }, [dateRange]);

  const fetchReports = async () => {
    try {
      const [salesRes, financeRes] = await Promise.all([
        api.get('/api/reports/sales', { params: { date_from: dateRange.from, date_to: dateRange.to } }),
        api.get('/api/finance/summary', { params: { date_from: dateRange.from, date_to: dateRange.to } })
      ]);
      setSalesReport(salesRes.data);
      setFinanceSummary(financeRes.data);
    } catch (error) {
      console.error('Error fetching reports:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount) => {
    return `Q ${(amount || 0).toLocaleString('es-GT', { minimumFractionDigits: 2 })}`;
  };

  const COLORS = ['#0F4C3A', '#D97706', '#3B82F6', '#10B981'];

  const paymentMethodData = salesReport?.by_payment_method 
    ? Object.entries(salesReport.by_payment_method).map(([name, value]) => ({
        name: name === 'cash' ? 'Efectivo' : name === 'card' ? 'Tarjeta' : name === 'transfer' ? 'Transferencia' : name,
        value
      }))
    : [];

  const financeChartData = [
    { name: 'Ingresos', value: financeSummary?.income || 0, color: '#10B981' },
    { name: 'Egresos', value: financeSummary?.expense || 0, color: '#EF4444' },
    { name: 'Utilidad', value: financeSummary?.profit || 0, color: '#3B82F6' }
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="reports-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Reportes</h1>
          <p className="text-slate-500 mt-1">Análisis y estadísticas del negocio</p>
        </div>
        <div className="flex gap-2 items-end">
          <div className="space-y-1">
            <Label className="text-xs">Desde</Label>
            <Input
              type="date"
              value={dateRange.from}
              onChange={(e) => setDateRange({...dateRange, from: e.target.value})}
              className="w-36"
              data-testid="report-date-from"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Hasta</Label>
            <Input
              type="date"
              value={dateRange.to}
              onChange={(e) => setDateRange({...dateRange, to: e.target.value})}
              className="w-36"
              data-testid="report-date-to"
            />
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-slate-200/80">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Total Ventas</p>
                <p className="font-heading text-2xl font-bold text-slate-900 mt-1">
                  {formatCurrency(salesReport?.total)}
                </p>
              </div>
              <div className="p-2.5 rounded-lg bg-green-100">
                <ShoppingBag className="w-5 h-5 text-green-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200/80">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Transacciones</p>
                <p className="font-heading text-2xl font-bold text-slate-900 mt-1">
                  {salesReport?.count || 0}
                </p>
              </div>
              <div className="p-2.5 rounded-lg bg-blue-100">
                <FileText className="w-5 h-5 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200/80">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Promedio/Venta</p>
                <p className="font-heading text-2xl font-bold text-slate-900 mt-1">
                  {formatCurrency(salesReport?.average)}
                </p>
              </div>
              <div className="p-2.5 rounded-lg bg-purple-100">
                <TrendingUp className="w-5 h-5 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200/80">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Utilidad</p>
                <p className={`font-heading text-2xl font-bold mt-1 ${
                  (financeSummary?.profit || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                }`}>
                  {formatCurrency(financeSummary?.profit)}
                </p>
              </div>
              <div className={`p-2.5 rounded-lg ${
                (financeSummary?.profit || 0) >= 0 ? 'bg-green-100' : 'bg-red-100'
              }`}>
                <DollarSign className={`w-5 h-5 ${
                  (financeSummary?.profit || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                }`} />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Finance Chart */}
        <Card className="border-slate-200/80">
          <CardHeader>
            <CardTitle className="font-heading text-lg">Resumen Financiero</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={financeChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis dataKey="name" tick={{ fill: '#64748B', fontSize: 12 }} />
                  <YAxis tick={{ fill: '#64748B', fontSize: 12 }} />
                  <Tooltip 
                    formatter={(value) => formatCurrency(value)}
                    contentStyle={{ borderRadius: '8px', border: '1px solid #E2E8F0' }}
                  />
                  <Bar dataKey="value" fill="#0F4C3A" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Payment Methods */}
        <Card className="border-slate-200/80">
          <CardHeader>
            <CardTitle className="font-heading text-lg">Ventas por Método de Pago</CardTitle>
          </CardHeader>
          <CardContent>
            {paymentMethodData.length > 0 ? (
              <div className="h-[300px] flex items-center">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={paymentMethodData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={5}
                      dataKey="value"
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    >
                      {paymentMethodData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => formatCurrency(value)} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-slate-500">
                <div className="text-center">
                  <BarChart3 className="w-12 h-12 mx-auto mb-2 opacity-30" />
                  <p>Sin datos de ventas</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Detailed Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border-slate-200/80">
          <CardContent className="p-5">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-green-50">
                <TrendingUp className="w-6 h-6 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Ingresos del Período</p>
                <p className="font-heading text-xl font-bold text-green-600">
                  {formatCurrency(financeSummary?.income)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200/80">
          <CardContent className="p-5">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-red-50">
                <Package className="w-6 h-6 text-red-600" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Egresos del Período</p>
                <p className="font-heading text-xl font-bold text-red-600">
                  {formatCurrency(financeSummary?.expense)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200/80">
          <CardContent className="p-5">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-pine-50">
                <Calendar className="w-6 h-6 text-pine-600" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Período</p>
                <p className="font-heading text-sm font-medium text-slate-900">
                  {dateRange.from} al {dateRange.to}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
