import React, { useState, useEffect } from 'react';
import { api, useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { 
  BarChart3, TrendingUp, Users, ShoppingBag, 
  Calendar, FileText, DollarSign, Package, Building2, Download, Landmark, Banknote, CreditCard, Smartphone
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { toast } from 'sonner';

export default function ReportsPage() {
  const { user } = useAuth();
  const [salesReport, setSalesReport] = useState(null);
  const [financeSummary, setFinanceSummary] = useState(null);
  const [cashReport, setCashReport] = useState(null);
  const [downloadingCash, setDownloadingCash] = useState(false);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [branches, setBranches] = useState([]);
  const [selectedBranch, setSelectedBranch] = useState('all');
  const [dateRange, setDateRange] = useState({
    from: new Date().toISOString().slice(0, 8) + '01',
    to: new Date().toISOString().slice(0, 10)
  });

  const isAdmin = user?.role === 'admin';

  useEffect(() => {
    if (isAdmin) {
      api.get('/api/branches').then(res => setBranches(res.data)).catch(() => {});
    }
  }, [isAdmin]);

  useEffect(() => {
    fetchReports();
  }, [dateRange, selectedBranch]);

  const fetchReports = async () => {
    try {
      const params = { date_from: dateRange.from, date_to: dateRange.to };
      if (selectedBranch && selectedBranch !== 'all') {
        params.branch_id = selectedBranch;
      }
      const [salesRes, financeRes, cashRes] = await Promise.all([
        api.get('/api/reports/sales', { params }),
        api.get('/api/finance/summary', { params }),
        api.get('/api/cash-register/report', { params })
      ]);
      setSalesReport(salesRes.data);
      setFinanceSummary(financeRes.data);
      setCashReport(cashRes.data);
    } catch (error) {
      console.error('Error fetching reports:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount) => {
    return `Q ${(amount || 0).toLocaleString('es-GT', { minimumFractionDigits: 2 })}`;
  };

  const handleExportExcel = async () => {
    setExporting(true);
    try {
      const params = { date_from: dateRange.from, date_to: dateRange.to };
      if (selectedBranch && selectedBranch !== 'all') {
        params.branch_id = selectedBranch;
      }
      const response = await api.get('/api/reports/export/excel', {
        params,
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `reporte_${dateRange.from}_${dateRange.to}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Reporte exportado exitosamente');
    } catch (error) {
      toast.error('Error al exportar reporte');
    } finally {
      setExporting(false);
    }
  };

  const handleExportCashPdf = async () => {
    setDownloadingCash(true);
    try {
      const params = { date_from: dateRange.from, date_to: dateRange.to };
      if (selectedBranch && selectedBranch !== 'all') {
        params.branch_id = selectedBranch;
      }
      const response = await api.get('/api/cash-register/report/pdf', { params, responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `reporte_cierres_${dateRange.from}_${dateRange.to}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Reporte de cierres descargado');
    } catch (error) {
      toast.error('Error al descargar el reporte');
    } finally {
      setDownloadingCash(false);
    }
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
          <p className="text-slate-500 mt-1">
            Análisis y estadísticas del negocio
            {selectedBranch !== 'all' && branches.length > 0 && (
              <span className="ml-2 inline-flex items-center gap-1 text-pine-700 font-medium">
                <Building2 className="w-3.5 h-3.5" />
                {branches.find(b => b._id === selectedBranch)?.name}
              </span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 items-end">
          {isAdmin && branches.length > 0 && (
            <div className="space-y-1">
              <Label className="text-xs">Sucursal</Label>
              <Select value={selectedBranch} onValueChange={setSelectedBranch} data-testid="report-branch-select">
                <SelectTrigger className="w-44" data-testid="report-branch-trigger">
                  <SelectValue placeholder="Todas las sucursales" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all" data-testid="report-branch-all">Todas las sucursales</SelectItem>
                  {branches.map(b => (
                    <SelectItem key={b._id} value={b._id} data-testid={`report-branch-${b._id}`}>{b.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
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
          <Button
            onClick={handleExportExcel}
            disabled={exporting}
            variant="outline"
            className="border-pine-200 text-pine-700 hover:bg-pine-50"
            data-testid="export-excel-btn"
          >
            <Download className="w-4 h-4 mr-2" />
            {exporting ? 'Exportando...' : 'Excel'}
          </Button>
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

      {/* Reporte de Cierres de Caja */}
      <Card className="border-slate-200/80" data-testid="cash-report-card">
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <div>
            <CardTitle className="font-heading text-lg flex items-center gap-2">
              <Landmark className="w-5 h-5 text-emerald-600" /> Reporte de Cierres de Caja
            </CardTitle>
            <p className="text-xs text-slate-500 mt-1">
              Resumen consolidado de cierres del periodo por metodo de pago.
            </p>
          </div>
          <Button
            onClick={handleExportCashPdf}
            disabled={downloadingCash || !cashReport?.count}
            className="bg-emerald-600 hover:bg-emerald-700"
            data-testid="cash-report-pdf-btn"
          >
            <Download className="w-4 h-4 mr-2" />
            {downloadingCash ? 'Descargando...' : 'Descargar PDF'}
          </Button>
        </CardHeader>
        <CardContent>
          {!cashReport || cashReport.count === 0 ? (
            <div className="text-center py-8 text-slate-500">
              <Landmark className="w-12 h-12 mx-auto mb-2 opacity-30" />
              <p>Sin cierres registrados en este periodo</p>
            </div>
          ) : (
            <div className="space-y-5">
              {/* Method tiles */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3" data-testid="cash-report-tiles">
                {[
                  { key: 'cash', label: 'Efectivo', icon: Banknote, color: 'emerald' },
                  { key: 'transfer', label: 'Transferencia', icon: Smartphone, color: 'violet' },
                  { key: 'card', label: 'Tarjeta', icon: CreditCard, color: 'blue' },
                  { key: 'check', label: 'Cheque', icon: FileText, color: 'amber' },
                  { key: 'other', label: 'Otro', icon: DollarSign, color: 'slate' },
                ].map(({ key, label, icon: Icon, color }) => {
                  const bg = {
                    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
                    violet: 'bg-violet-50 text-violet-700 border-violet-200',
                    blue: 'bg-blue-50 text-blue-700 border-blue-200',
                    amber: 'bg-amber-50 text-amber-800 border-amber-200',
                    slate: 'bg-slate-50 text-slate-700 border-slate-200',
                  }[color];
                  return (
                    <div key={key} className={`border rounded-xl p-3 ${bg}`} data-testid={`cash-report-tile-${key}`}>
                      <div className="flex items-center gap-1.5 mb-1">
                        <Icon className="w-3.5 h-3.5" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">{label}</span>
                      </div>
                      <p className="font-heading text-lg font-bold">{formatCurrency(cashReport.totals_by_method?.[key])}</p>
                    </div>
                  );
                })}
              </div>

              {/* Grand totals */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm bg-slate-50 border border-slate-100 rounded-lg p-4">
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wide">Cierres</p>
                  <p className="font-heading text-xl font-bold text-slate-900">{cashReport.count}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wide">Total recaudado</p>
                  <p className="font-heading text-xl font-bold text-emerald-700">{formatCurrency(cashReport.grand_total_received)}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wide">Cuentas x cobrar</p>
                  <p className="font-heading text-xl font-bold text-amber-700">{formatCurrency(cashReport.grand_receivables_total)}</p>
                </div>
                {cashReport.grand_cash_difference != null && (
                  <div>
                    <p className="text-xs text-slate-500 uppercase tracking-wide">Diferencia efectivo</p>
                    <p className={`font-heading text-xl font-bold ${cashReport.grand_cash_difference === 0 ? 'text-emerald-700' : cashReport.grand_cash_difference > 0 ? 'text-blue-700' : 'text-red-600'}`}>
                      {cashReport.grand_cash_difference > 0 ? '+' : ''}{formatCurrency(cashReport.grand_cash_difference)}
                    </p>
                  </div>
                )}
              </div>

              {/* Rows table */}
              <div className="overflow-x-auto border rounded-lg">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50">
                    <tr className="text-xs text-slate-500 uppercase tracking-wider">
                      <th className="text-left p-2.5 font-semibold">Cierre</th>
                      <th className="text-left p-2.5 font-semibold">Sucursal</th>
                      <th className="text-left p-2.5 font-semibold">Cerrada por</th>
                      <th className="text-right p-2.5 font-semibold">Efectivo</th>
                      <th className="text-right p-2.5 font-semibold">Transf.</th>
                      <th className="text-right p-2.5 font-semibold">Tarjeta</th>
                      <th className="text-right p-2.5 font-semibold">Cheque</th>
                      <th className="text-right p-2.5 font-semibold">Total</th>
                      <th className="text-right p-2.5 font-semibold">Cta x Cob</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cashReport.rows.map((r) => (
                      <tr key={r._id} className="border-t border-slate-100 hover:bg-slate-50/60" data-testid={`cash-report-row-${r._id}`}>
                        <td className="p-2.5 text-slate-700 text-xs">{(r.closed_at || '').slice(0, 16).replace('T', ' ')}</td>
                        <td className="p-2.5 text-slate-700">{r.branch_name || '-'}</td>
                        <td className="p-2.5 text-slate-700">{r.closed_by_name || '-'}</td>
                        <td className="p-2.5 text-right">{formatCurrency(r.totals_by_method?.cash)}</td>
                        <td className="p-2.5 text-right">{formatCurrency(r.totals_by_method?.transfer)}</td>
                        <td className="p-2.5 text-right">{formatCurrency(r.totals_by_method?.card)}</td>
                        <td className="p-2.5 text-right">{formatCurrency(r.totals_by_method?.check)}</td>
                        <td className="p-2.5 text-right font-bold text-emerald-700">{formatCurrency(r.total_received)}</td>
                        <td className="p-2.5 text-right text-amber-700">{formatCurrency(r.receivables_total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
