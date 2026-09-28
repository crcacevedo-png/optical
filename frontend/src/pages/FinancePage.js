import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api, formatApiErrorDetail, useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Checkbox } from '../components/ui/checkbox';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '../components/ui/tabs';
import { 
  Plus, TrendingUp, TrendingDown, DollarSign, 
  ArrowUpCircle, ArrowDownCircle, Wallet, Filter, BarChart3, Truck, Download, Ban, FileText, Percent, Package, AlertTriangle
} from 'lucide-react';
import { toast } from 'sonner';
import { BranchFilter } from '../components/BranchFilter';

export default function FinancePage() {
  const { user } = useAuth();
  const [entries, setEntries] = useState([]);
  const [summary, setSummary] = useState(null);
  const [pl, setPl] = useState(null);
  const [prof, setProf] = useState(null);
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [activeTab, setActiveTab] = useState('all');
  const [supplierFilter, setSupplierFilter] = useState('all');
  const [branchId, setBranchId] = useState('');
  const [dateFrom, setDateFrom] = useState(new Date().toISOString().slice(0, 8) + '01');
  const [dateTo, setDateTo] = useState(new Date().toISOString().slice(0, 10));
  const [voidTarget, setVoidTarget] = useState(null);
  const [voidReason, setVoidReason] = useState('');
  const [voiding, setVoiding] = useState(false);

  const [formData, setFormData] = useState({
    type: 'ingreso',
    category: '',
    amount: '',
    description: '',
    date: new Date().toISOString().slice(0, 10),
    reference: '',
    supplier_id: '',
    is_credit: false,
    amount_paid: '',
    due_date: '',
    payment_method: 'cash'
  });

  const incomeCategories = [
    { value: 'sales', label: 'Ventas' },
    { value: 'services', label: 'Servicios' },
    { value: 'other_income', label: 'Otros Ingresos' }
  ];

  const expenseCategories = [
    { value: 'payroll', label: 'Planilla' },
    { value: 'rent', label: 'Alquiler' },
    { value: 'utilities', label: 'Servicios' },
    { value: 'suppliers', label: 'Proveedores' },
    { value: 'marketing', label: 'Marketing' },
    { value: 'maintenance', label: 'Mantenimiento' },
    { value: 'other_expense', label: 'Otros Gastos' }
  ];

  useEffect(() => {
    fetchData();
  }, [branchId, dateFrom, dateTo]);

  useEffect(() => {
    api.get('/api/suppliers')
      .then(({ data }) => setSuppliers(data || []))
      .catch(() => setSuppliers([]));
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const params = {};
      if (branchId) params.branch_id = branchId;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const [entriesRes, summaryRes, plRes, profRes] = await Promise.all([
        api.get('/api/finance', { params }),
        api.get('/api/finance/summary', { params }),
        api.get('/api/finance/income-statement', { params }),
        api.get('/api/finance/profitability', { params })
      ]);
      setEntries(entriesRes.data || []);
      setSummary(summaryRes.data);
      setPl(plRes.data);
      setProf(profRes.data);
    } catch (error) {
      console.error('Error fetching finance data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const requiresSupplier = formData.type === 'egreso' && (formData.category === 'suppliers' || formData.is_credit);
    if (requiresSupplier && !formData.supplier_id) {
      toast.error(formData.is_credit
        ? 'Selecciona un proveedor para el egreso a crédito'
        : 'Selecciona un proveedor para egresos de la categoría Proveedores');
      return;
    }
    const isCredit = formData.type === 'egreso' && formData.is_credit;
    try {
      await api.post('/api/finance', {
        ...formData,
        amount: parseFloat(formData.amount),
        supplier_id: formData.type === 'egreso' && formData.supplier_id ? formData.supplier_id : null,
        is_credit: isCredit,
        amount_paid: isCredit ? parseFloat(formData.amount_paid || 0) : null,
        due_date: isCredit ? (formData.due_date || null) : null,
        payment_method: formData.type === 'egreso' ? formData.payment_method : null
      });
      toast.success('Entrada registrada exitosamente');
      setShowDialog(false);
      setFormData({
        type: 'ingreso', category: '', amount: '', description: '',
        date: new Date().toISOString().slice(0, 10), reference: '', supplier_id: '',
        is_credit: false, amount_paid: '', due_date: '', payment_method: 'cash'
      });
      fetchData();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const formatCurrency = (amount) => {
    return `Q ${(amount || 0).toLocaleString('es-GT', { minimumFractionDigits: 2 })}`;
  };

  const canVoid = (entry) =>
    user && user.role !== 'superadmin' && !entry.is_voided &&
    (user.role === 'admin' || entry.created_by === user._id);

  const handleVoid = async () => {
    if (!voidTarget) return;
    const reason = (voidReason || '').trim();
    if (!reason) { toast.error('Indica el motivo de la anulación'); return; }
    try {
      setVoiding(true);
      await api.post(`/api/finance/${voidTarget._id}/void`, { reason });
      toast.success('Movimiento anulado');
      setVoidTarget(null);
      setVoidReason('');
      fetchData();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    } finally {
      setVoiding(false);
    }
  };

  const handleExportPurchases = async () => {
    const toastId = toast.loading('Generando reporte de compras...');
    try {
      const params = {};
      if (branchId) params.branch_id = branchId;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const response = await api.get('/api/finance/purchases-report.xlsx', { params, responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const cd = response.headers?.['content-disposition'] || '';
      const match = cd.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : 'compras-proveedores.xlsx';
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.success('Reporte descargado', { id: toastId });
    } catch (error) {
      toast.error('No se pudo generar el reporte', { id: toastId });
    }
  };

  const handleExportExpenses = async () => {
    const toastId = toast.loading('Generando reporte de egresos...');
    try {
      const params = {};
      if (branchId) params.branch_id = branchId;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const response = await api.get('/api/finance/expenses-report.xlsx', { params, responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const cd = response.headers?.['content-disposition'] || '';
      const match = cd.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : 'egresos.xlsx';
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.success('Reporte descargado', { id: toastId });
    } catch (error) {
      toast.error('No se pudo generar el reporte', { id: toastId });
    }
  };

  const handleExportPL = async (format) => {
    const toastId = toast.loading('Generando estado de resultados...');
    try {
      const params = {};
      if (branchId) params.branch_id = branchId;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const ext = format === 'pdf' ? 'pdf' : 'xlsx';
      const mime = format === 'pdf'
        ? 'application/pdf'
        : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
      const response = await api.get(`/api/finance/income-statement.${ext}`, { params, responseType: 'blob' });
      const blob = new Blob([response.data], { type: mime });
      const url = URL.createObjectURL(blob);
      if (format === 'pdf') {
        window.open(url, '_blank');
      } else {
        const cd = response.headers?.['content-disposition'] || '';
        const match = cd.match(/filename="?([^"]+)"?/);
        const link = document.createElement('a');
        link.href = url;
        link.download = match ? match[1] : 'estado-resultados.xlsx';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      }
      toast.success('Listo', { id: toastId });
    } catch (error) {
      toast.error('No se pudo generar el estado de resultados', { id: toastId });
    }
  };

  const filteredEntries = entries.filter(e => {
    if (activeTab !== 'all' && e.type !== activeTab) return false;
    if (supplierFilter !== 'all' && e.supplier_id !== supplierFilter) return false;
    return true;
  });

  // Proveedores que aparecen en los movimientos del periodo (para el filtro)
  const supplierOptions = Object.values(entries.reduce((acc, e) => {
    if (e.type === 'egreso' && !e.is_voided && e.supplier_id && e.supplier_name && !acc[e.supplier_id]) {
      acc[e.supplier_id] = { id: e.supplier_id, name: e.supplier_name };
    }
    return acc;
  }, {}));

  // Total pagado por proveedor en el periodo seleccionado (excluye anulados)
  const supplierTotalsMap = entries.reduce((acc, e) => {
    if (e.type === 'egreso' && !e.is_voided && e.supplier_name) {
      const key = e.supplier_id || e.supplier_name;
      if (!acc[key]) acc[key] = { name: e.supplier_name, amount: 0 };
      acc[key].amount += e.amount || 0;
    }
    return acc;
  }, {});
  const supplierTotals = Object.values(supplierTotalsMap).sort((a, b) => b.amount - a.amount);
  const totalSupplierExpense = supplierTotals.reduce((s, x) => s + x.amount, 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="finance-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Finanzas</h1>
          <p className="text-slate-500 mt-1">Control de ingresos y egresos</p>
        </div>
        <div className="flex items-center gap-2">
          <BranchFilter value={branchId} onChange={setBranchId} />
          <Dialog open={showDialog} onOpenChange={setShowDialog}>
            <DialogTrigger asChild>
              <Button className="bg-pine-900 hover:bg-pine-700" data-testid="add-entry-btn">
                <Plus className="w-4 h-4 mr-2" /> Nueva Entrada
              </Button>
            </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="font-heading">Nueva Entrada Financiera</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label>Tipo</Label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setFormData({...formData, type: 'ingreso', category: '', supplier_id: '', is_credit: false, amount_paid: '', due_date: '', payment_method: 'cash'})}
                    className={`flex-1 p-3 rounded-lg border flex items-center justify-center gap-2 transition-colors ${
                      formData.type === 'ingreso'
                        ? 'border-green-500 bg-green-50 text-green-700'
                        : 'border-slate-200 hover:border-slate-300'
                    }`}
                    data-testid="type-income"
                  >
                    <ArrowUpCircle className="w-5 h-5" />
                    <span className="font-medium">Ingreso</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setFormData({...formData, type: 'egreso', category: ''})}
                    className={`flex-1 p-3 rounded-lg border flex items-center justify-center gap-2 transition-colors ${
                      formData.type === 'egreso'
                        ? 'border-red-500 bg-red-50 text-red-700'
                        : 'border-slate-200 hover:border-slate-300'
                    }`}
                    data-testid="type-expense"
                  >
                    <ArrowDownCircle className="w-5 h-5" />
                    <span className="font-medium">Egreso</span>
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Categoría *</Label>
                  <Select value={formData.category} onValueChange={(v) => setFormData({...formData, category: v})}>
                    <SelectTrigger data-testid="entry-category">
                      <SelectValue placeholder="Seleccionar" />
                    </SelectTrigger>
                    <SelectContent>
                      {(formData.type === 'ingreso' ? incomeCategories : expenseCategories).map((c) => (
                        <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Monto *</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={formData.amount}
                    onChange={(e) => setFormData({...formData, amount: e.target.value})}
                    required
                    data-testid="entry-amount"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Descripción *</Label>
                <Input
                  value={formData.description}
                  onChange={(e) => setFormData({...formData, description: e.target.value})}
                  required
                  data-testid="entry-description"
                />
              </div>

              {formData.type === 'egreso' && (
                <div className="space-y-2" data-testid="payment-method-field">
                  <Label>Método de pago</Label>
                  <Select
                    value={formData.payment_method}
                    onValueChange={(v) => setFormData({...formData, payment_method: v})}
                  >
                    <SelectTrigger data-testid="entry-payment-method">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cash">Efectivo</SelectItem>
                      <SelectItem value="card">Tarjeta</SelectItem>
                      <SelectItem value="transfer">Transferencia</SelectItem>
                      <SelectItem value="check">Cheque</SelectItem>
                      <SelectItem value="other">Otro</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-[11px] text-slate-400">Solo los egresos en <b>efectivo</b> se descuentan del arqueo de caja del turno.</p>
                </div>
              )}

              {formData.type === 'egreso' && (
                <div className="space-y-2" data-testid="supplier-field">
                  <Label>Proveedor {(formData.category === 'suppliers' || formData.is_credit) ? '*' : ''}</Label>
                  {suppliers.length > 0 ? (
                    <Select
                      value={formData.supplier_id || 'none'}
                      onValueChange={(v) => setFormData({...formData, supplier_id: v === 'none' ? '' : v})}
                    >
                      <SelectTrigger data-testid="entry-supplier">
                        <SelectValue placeholder="Seleccionar proveedor (opcional)" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Sin proveedor</SelectItem>
                        {suppliers.map((s) => (
                          <SelectItem key={s._id} value={s._id}>{s.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <p className="text-xs text-slate-500">
                      No tienes proveedores registrados.{' '}
                      <Link to="/suppliers" className="text-pine-700 font-medium hover:underline" data-testid="add-supplier-link">
                        Agrega uno en Proveedores
                      </Link>.
                    </p>
                  )}
                </div>
              )}

              {formData.type === 'egreso' && (
                <div className="space-y-3 rounded-lg border border-slate-200 p-3" data-testid="credit-block">
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="is-credit"
                      checked={formData.is_credit}
                      onCheckedChange={(v) => setFormData({...formData, is_credit: !!v})}
                      data-testid="entry-is-credit"
                    />
                    <Label htmlFor="is-credit" className="cursor-pointer">Egreso a crédito (cuenta por pagar)</Label>
                  </div>
                  {formData.is_credit && (
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Monto pagado ahora</Label>
                        <Input
                          type="number"
                          step="0.01"
                          min="0"
                          placeholder="0.00"
                          value={formData.amount_paid}
                          onChange={(e) => setFormData({...formData, amount_paid: e.target.value})}
                          data-testid="entry-amount-paid"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Fecha de vencimiento</Label>
                        <Input
                          type="date"
                          value={formData.due_date}
                          onChange={(e) => setFormData({...formData, due_date: e.target.value})}
                          data-testid="entry-due-date"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Fecha</Label>
                  <Input
                    type="date"
                    value={formData.date}
                    onChange={(e) => setFormData({...formData, date: e.target.value})}
                    data-testid="entry-date"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Referencia</Label>
                  <Input
                    value={formData.reference}
                    onChange={(e) => setFormData({...formData, reference: e.target.value})}
                    placeholder="No. de factura, etc."
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowDialog(false)}>
                  Cancelar
                </Button>
                <Button type="submit" className="bg-pine-900 hover:bg-pine-700" data-testid="save-entry">
                  Guardar
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      {/* Date Filters */}
      <Card className="border-slate-200/80">
        <CardContent className="py-3 px-4">
          <div className="flex items-center gap-3 flex-wrap">
            <Filter className="w-4 h-4 text-slate-400" />
            <div className="flex items-center gap-2">
              <Label className="text-xs text-slate-500 whitespace-nowrap">Desde:</Label>
              <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
                className="h-8 text-sm w-auto" data-testid="finance-date-from" />
            </div>
            <div className="flex items-center gap-2">
              <Label className="text-xs text-slate-500 whitespace-nowrap">Hasta:</Label>
              <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
                className="h-8 text-sm w-auto" data-testid="finance-date-to" />
            </div>
            <Button
              variant="outline"
              size="sm"
              className="sm:ml-auto border-red-200 text-red-700 hover:bg-red-50"
              onClick={handleExportExpenses}
              data-testid="export-expenses-btn"
            >
              <Download className="w-4 h-4 mr-1.5" /> Exportar egresos (Excel)
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Estado de Resultados (P&L, base caja) */}
      {pl && (
        <Card className="border-slate-200/80" data-testid="income-statement-card">
          <CardHeader>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <CardTitle className="font-heading text-lg flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-pine-700" /> Estado de Resultados
                <span className="text-xs font-normal text-slate-400">base caja · {pl.period?.from} a {pl.period?.to}</span>
              </CardTitle>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" className="border-emerald-200 text-emerald-800 hover:bg-emerald-50" onClick={() => handleExportPL('xlsx')} data-testid="export-pl-excel-btn">
                  <Download className="w-4 h-4 mr-1.5" /> Excel
                </Button>
                <Button variant="outline" size="sm" className="border-pine-200 text-pine-800 hover:bg-pine-50" onClick={() => handleExportPL('pdf')} data-testid="export-pl-pdf-btn">
                  <FileText className="w-4 h-4 mr-1.5" /> PDF
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div data-testid="pl-income">
                <p className="text-xs font-bold uppercase tracking-wider text-green-700 mb-2">Ingresos</p>
                <div className="space-y-1">
                  {pl.income.length === 0 ? (
                    <p className="text-sm text-slate-400">Sin ingresos en el periodo</p>
                  ) : pl.income.map((r) => (
                    <div key={r.category} className="flex justify-between text-sm">
                      <span className="text-slate-600 capitalize">{r.label}</span>
                      <span className="font-medium text-green-700">{formatCurrency(r.amount)}</span>
                    </div>
                  ))}
                </div>
                <div className="flex justify-between text-sm font-bold border-t border-slate-200 mt-2 pt-2">
                  <span>Total ingresos</span>
                  <span className="text-green-700" data-testid="pl-total-income">{formatCurrency(pl.total_income)}</span>
                </div>
              </div>
              <div data-testid="pl-expenses">
                <p className="text-xs font-bold uppercase tracking-wider text-red-700 mb-2">Egresos</p>
                <div className="space-y-1">
                  {pl.expenses.length === 0 ? (
                    <p className="text-sm text-slate-400">Sin egresos en el periodo</p>
                  ) : pl.expenses.map((r) => (
                    <div key={r.category} className="flex justify-between text-sm">
                      <span className="text-slate-600 capitalize">{r.label}</span>
                      <span className="font-medium text-red-600">{formatCurrency(r.amount)}</span>
                    </div>
                  ))}
                </div>
                <div className="flex justify-between text-sm font-bold border-t border-slate-200 mt-2 pt-2">
                  <span>Total egresos</span>
                  <span className="text-red-600" data-testid="pl-total-expense">{formatCurrency(pl.total_expense)}</span>
                </div>
              </div>
            </div>
            <div className={`mt-4 rounded-xl p-4 flex items-center justify-between ${pl.net_profit >= 0 ? 'bg-emerald-50 border border-emerald-200' : 'bg-red-50 border border-red-200'}`} data-testid="pl-net-profit">
              <span className="font-heading text-base font-bold text-slate-800">Flujo de caja neto</span>
              <span className={`font-heading text-2xl font-bold ${pl.net_profit >= 0 ? 'text-emerald-700' : 'text-red-600'}`}>{formatCurrency(pl.net_profit)}</span>
            </div>
            <p className="text-[11px] text-slate-400 mt-2">Base caja (cobros − pagos): incluye ingresos cobrados y egresos pagados (los egresos a crédito cuentan solo por lo abonado). Excluye anulados. <b>No</b> descuenta el costo de la mercadería vendida — para eso mira la Rentabilidad por productos abajo.</p>
          </CardContent>
        </Card>
      )}

      {/* Rentabilidad por productos vendidos (margen, base devengado) */}
      {prof && (
        <Card className="border-slate-200/80" data-testid="profitability-card">
          <CardHeader>
            <CardTitle className="font-heading text-lg flex items-center gap-2">
              <Percent className="w-5 h-5 text-pine-700" /> Rentabilidad por productos
              <span className="text-xs font-normal text-slate-400">margen · devengado · {prof.period?.from} a {prof.period?.to}</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="rounded-xl p-4 bg-slate-50 border border-slate-200" data-testid="prof-revenue">
                <p className="text-xs font-medium text-slate-500">Ingreso por ventas (con costo)</p>
                <p className="font-heading text-xl font-bold text-slate-800 mt-1">{formatCurrency(prof.revenue_with_cost)}</p>
              </div>
              <div className="rounded-xl p-4 bg-amber-50 border border-amber-200" data-testid="prof-cogs">
                <p className="text-xs font-medium text-amber-800">Costo de lo vendido (COGS)</p>
                <p className="font-heading text-xl font-bold text-amber-700 mt-1">{formatCurrency(prof.cogs)}</p>
              </div>
              <div className={`rounded-xl p-4 border ${prof.gross_margin >= 0 ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'}`} data-testid="prof-gross-margin">
                <p className={`text-xs font-medium ${prof.gross_margin >= 0 ? 'text-emerald-800' : 'text-red-800'}`}>Utilidad bruta / margen</p>
                <p className={`font-heading text-xl font-bold mt-1 ${prof.gross_margin >= 0 ? 'text-emerald-700' : 'text-red-600'}`}>
                  {formatCurrency(prof.gross_margin)} <span className="text-sm font-semibold">({prof.gross_margin_pct}%)</span>
                </p>
              </div>
            </div>

            {prof.items_without_cost > 0 && (
              <div className="mt-3 flex items-start gap-2 rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-600" data-testid="prof-no-cost-note">
                <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                <span>{prof.items_without_cost} ítem(s) vendidos por {formatCurrency(prof.revenue_without_cost)} <b>sin costo registrado</b> (ventas anteriores a esta función o ítems sin producto de inventario) — no cuentan en el margen. El margen aplica a las ventas nuevas.</span>
              </div>
            )}

            {prof.by_product && prof.by_product.length > 0 && (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm" data-testid="prof-by-product-table">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wide text-slate-500 border-b border-slate-200">
                      <th className="py-2 pr-2">Producto</th>
                      <th className="py-2 px-2 text-right">Unid.</th>
                      <th className="py-2 px-2 text-right">Ingreso</th>
                      <th className="py-2 px-2 text-right">Costo</th>
                      <th className="py-2 px-2 text-right">Margen</th>
                      <th className="py-2 pl-2 text-right">%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {prof.by_product.slice(0, 25).map((p, i) => (
                      <tr key={p.product_id || `m-${i}`} className="border-b border-slate-100" data-testid={`prof-product-row-${i}`}>
                        <td className="py-2 pr-2 text-slate-700 flex items-center gap-1.5">
                          <Package className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <span className="truncate max-w-[220px]">{p.name}</span>
                          {!p.has_cost && <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">sin costo</span>}
                        </td>
                        <td className="py-2 px-2 text-right text-slate-600">{p.units}</td>
                        <td className="py-2 px-2 text-right text-slate-700">{formatCurrency(p.revenue)}</td>
                        <td className="py-2 px-2 text-right text-amber-700">{p.has_cost ? formatCurrency(p.cogs) : '—'}</td>
                        <td className={`py-2 px-2 text-right font-semibold ${!p.has_cost ? 'text-slate-400' : (p.margin >= 0 ? 'text-emerald-700' : 'text-red-600')}`}>{p.has_cost ? formatCurrency(p.margin) : '—'}</td>
                        <td className="py-2 pl-2 text-right text-slate-500">{p.margin_pct != null ? `${p.margin_pct}%` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="text-[11px] text-slate-400 mt-2">Base devengado (por fecha de venta): margen = ingreso de la venta − costo de la mercadería vendida (costo fotografiado al momento de vender). Es distinto del flujo de caja neto de arriba.</p>
          </CardContent>
        </Card>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-green-50 border-green-200">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-green-800">Ingresos</p>
                <p className="font-heading text-2xl font-bold text-green-700 mt-1">
                  {formatCurrency(summary?.income)}
                </p>
                <p className="text-xs text-green-600 mt-1">{summary?.period?.from} - {summary?.period?.to}</p>
              </div>
              <TrendingUp className="w-10 h-10 text-green-500 opacity-50" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-red-50 border-red-200">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-red-800">Egresos</p>
                <p className="font-heading text-2xl font-bold text-red-700 mt-1">
                  {formatCurrency(summary?.expense)}
                </p>
                <p className="text-xs text-red-600 mt-1">{summary?.period?.from} - {summary?.period?.to}</p>
              </div>
              <TrendingDown className="w-10 h-10 text-red-500 opacity-50" />
            </div>
          </CardContent>
        </Card>

        <Card className={summary?.profit >= 0 ? 'bg-blue-50 border-blue-200' : 'bg-amber-50 border-amber-200'}>
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className={`text-sm font-medium ${summary?.profit >= 0 ? 'text-blue-800' : 'text-amber-800'}`}>Flujo de caja</p>
                <p className={`font-heading text-2xl font-bold mt-1 ${summary?.profit >= 0 ? 'text-blue-700' : 'text-amber-700'}`}>
                  {formatCurrency(summary?.profit)}
                </p>
                <p className={`text-xs mt-1 ${summary?.profit >= 0 ? 'text-blue-600' : 'text-amber-600'}`}>
                  {summary?.period?.from} - {summary?.period?.to}
                </p>
              </div>
              <DollarSign className={`w-10 h-10 opacity-50 ${summary?.profit >= 0 ? 'text-blue-500' : 'text-amber-500'}`} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Category Breakdown */}
      {(Object.keys(summary?.income_by_category || {}).length > 0 || Object.keys(summary?.expense_by_category || {}).length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="category-breakdown">
          {Object.keys(summary?.income_by_category || {}).length > 0 && (
            <Card className="border-slate-200/80">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-green-600" /> Ingresos por Categoria
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {Object.entries(summary.income_by_category).sort(([,a],[,b]) => b - a).map(([cat, amount]) => {
                    const pct = summary.income > 0 ? (amount / summary.income) * 100 : 0;
                    return (
                      <div key={cat} className="flex items-center gap-3" data-testid={`income-cat-${cat}`}>
                        <span className="text-xs text-slate-600 w-24 capitalize truncate">{cat.replace('_', ' ')}</span>
                        <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div className="h-full bg-green-500 rounded-full transition-all" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-xs font-medium text-slate-700 w-20 text-right">{formatCurrency(amount)}</span>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}
          {Object.keys(summary?.expense_by_category || {}).length > 0 && (
            <Card className="border-slate-200/80">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-red-600" /> Egresos por Categoria
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {Object.entries(summary.expense_by_category).sort(([,a],[,b]) => b - a).map(([cat, amount]) => {
                    const pct = summary.expense > 0 ? (amount / summary.expense) * 100 : 0;
                    return (
                      <div key={cat} className="flex items-center gap-3" data-testid={`expense-cat-${cat}`}>
                        <span className="text-xs text-slate-600 w-24 capitalize truncate">{cat.replace('_', ' ')}</span>
                        <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div className="h-full bg-red-500 rounded-full transition-all" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-xs font-medium text-slate-700 w-20 text-right">{formatCurrency(amount)}</span>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Total por Proveedor */}
      {supplierTotals.length > 0 && (
        <Card className="border-slate-200/80" data-testid="supplier-totals-card">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between gap-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Truck className="w-4 h-4 text-red-600" /> Egresos por Proveedor
              </CardTitle>
              <Button
                size="sm"
                variant="outline"
                onClick={handleExportPurchases}
                className="h-8 text-xs"
                data-testid="export-purchases-btn"
              >
                <Download className="w-3.5 h-3.5 mr-1.5" /> Exportar a Excel
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {supplierTotals.map((s) => {
                const pct = totalSupplierExpense > 0 ? (s.amount / totalSupplierExpense) * 100 : 0;
                return (
                  <div key={s.name} className="flex items-center gap-3" data-testid={`supplier-total-${s.name}`}>
                    <span className="text-xs text-slate-600 w-40 truncate">{s.name}</span>
                    <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full bg-red-500 rounded-full transition-all" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-xs font-medium text-slate-700 w-24 text-right">{formatCurrency(s.amount)}</span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Transactions */}
      <Card className="border-slate-200/80">
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <CardTitle className="font-heading text-lg">Movimientos</CardTitle>
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
              {supplierOptions.length > 0 && (
                <Select value={supplierFilter} onValueChange={setSupplierFilter}>
                  <SelectTrigger className="h-9 w-full sm:w-52" data-testid="supplier-filter">
                    <SelectValue placeholder="Todos los proveedores" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos los proveedores</SelectItem>
                    {supplierOptions.map((s) => (
                      <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList>
                  <TabsTrigger value="all">Todos</TabsTrigger>
                  <TabsTrigger value="ingreso">Ingresos</TabsTrigger>
                  <TabsTrigger value="egreso">Egresos</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="data-table-header">
                <TableHead>Fecha</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Categoría</TableHead>
                <TableHead>Proveedor</TableHead>
                <TableHead>Descripción</TableHead>
                <TableHead className="text-right">Monto</TableHead>
                <TableHead className="text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredEntries.map((entry) => (
                <TableRow
                  key={entry._id}
                  className={`data-table-row ${entry.is_voided ? 'opacity-60' : ''}`}
                  data-testid={`finance-row-${entry._id}`}
                >
                  <TableCell className={entry.is_voided ? 'line-through text-slate-400' : ''}>{entry.date}</TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                      entry.type === 'ingreso' 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {entry.type === 'ingreso' ? <ArrowUpCircle className="w-3 h-3" /> : <ArrowDownCircle className="w-3 h-3" />}
                      {entry.type === 'ingreso' ? 'Ingreso' : 'Egreso'}
                    </span>
                  </TableCell>
                  <TableCell className={`capitalize ${entry.is_voided ? 'line-through text-slate-400' : ''}`}>{entry.category?.replace('_', ' ')}</TableCell>
                  <TableCell className="text-slate-600">{entry.supplier_name || '—'}</TableCell>
                  <TableCell className={entry.is_voided ? 'line-through text-slate-400' : ''}>{entry.description}
                    {entry.is_credit && entry.balance > 0 && !entry.is_voided && (
                      <span className="ml-2 inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-700" data-testid={`credit-badge-${entry._id}`}>
                        Crédito · saldo {formatCurrency(entry.balance)}
                      </span>
                    )}
                    {entry.is_voided && (
                      <span
                        className="ml-2 inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-200 text-slate-600"
                        title={entry.void_reason ? `Motivo: ${entry.void_reason}` : 'Anulado'}
                        data-testid={`voided-badge-${entry._id}`}
                      >
                        Anulado{entry.voided_by_name ? ` · ${entry.voided_by_name}` : ''}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className={`text-right font-medium ${
                    entry.is_voided ? 'line-through text-slate-400' : (entry.type === 'ingreso' ? 'text-green-600' : 'text-red-600')
                  }`}>
                    {entry.type === 'ingreso' ? '+' : '-'}{formatCurrency(entry.amount)}
                  </TableCell>
                  <TableCell className="text-right">
                    {canVoid(entry) && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        onClick={() => { setVoidTarget(entry); setVoidReason(''); }}
                        data-testid={`void-btn-${entry._id}`}
                      >
                        <Ban className="w-4 h-4 mr-1" /> Anular
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {filteredEntries.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-slate-500">
                    <Wallet className="w-12 h-12 mx-auto mb-2 opacity-30" />
                    <p>No hay movimientos registrados</p>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Diálogo de anulación */}
      <Dialog open={!!voidTarget} onOpenChange={(o) => { if (!o) { setVoidTarget(null); setVoidReason(''); } }}>
        <DialogContent className="sm:max-w-md" data-testid="void-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading flex items-center gap-2">
              <Ban className="w-5 h-5 text-red-600" /> Anular movimiento
            </DialogTitle>
          </DialogHeader>
          {voidTarget && (
            <div className="space-y-3">
              <div className="bg-slate-50 border border-slate-100 rounded-lg p-3 text-sm">
                <p><span className="text-slate-500">Tipo:</span> {voidTarget.type === 'ingreso' ? 'Ingreso' : 'Egreso'}</p>
                <p><span className="text-slate-500">Monto:</span> {formatCurrency(voidTarget.amount)}</p>
                {voidTarget.description && <p><span className="text-slate-500">Descripción:</span> {voidTarget.description}</p>}
              </div>
              <p className="text-sm text-slate-600">
                El movimiento quedará marcado como <strong>Anulado</strong> (visible en el historial) y dejará de contar en los totales, cuentas por pagar y en la caja. No se puede deshacer.
              </p>
              <div>
                <Label>Motivo de la anulación *</Label>
                <Input
                  value={voidReason}
                  onChange={(e) => setVoidReason(e.target.value)}
                  placeholder="Ej. Monto equivocado / duplicado"
                  autoFocus
                  data-testid="void-reason-input"
                />
              </div>
              <div className="flex justify-end gap-2 pt-1">
                <Button variant="outline" onClick={() => { setVoidTarget(null); setVoidReason(''); }}>Cancelar</Button>
                <Button
                  className="bg-red-600 hover:bg-red-700"
                  onClick={handleVoid}
                  disabled={voiding}
                  data-testid="void-confirm-btn"
                >
                  {voiding ? 'Anulando...' : 'Anular movimiento'}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
