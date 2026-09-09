import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '../components/ui/tabs';
import { 
  Plus, TrendingUp, TrendingDown, DollarSign, 
  ArrowUpCircle, ArrowDownCircle, Wallet, Filter, BarChart3
} from 'lucide-react';
import { toast } from 'sonner';
import { BranchFilter } from '../components/BranchFilter';

export default function FinancePage() {
  const [entries, setEntries] = useState([]);
  const [summary, setSummary] = useState(null);
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [activeTab, setActiveTab] = useState('all');
  const [branchId, setBranchId] = useState('');
  const [dateFrom, setDateFrom] = useState(new Date().toISOString().slice(0, 8) + '01');
  const [dateTo, setDateTo] = useState(new Date().toISOString().slice(0, 10));

  const [formData, setFormData] = useState({
    type: 'ingreso',
    category: '',
    amount: '',
    description: '',
    date: new Date().toISOString().slice(0, 10),
    reference: '',
    supplier_id: ''
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
      const [entriesRes, summaryRes] = await Promise.all([
        api.get('/api/finance', { params }),
        api.get('/api/finance/summary', { params })
      ]);
      setEntries(entriesRes.data || []);
      setSummary(summaryRes.data);
    } catch (error) {
      console.error('Error fetching finance data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/api/finance', {
        ...formData,
        amount: parseFloat(formData.amount),
        supplier_id: formData.type === 'egreso' && formData.supplier_id ? formData.supplier_id : null
      });
      toast.success('Entrada registrada exitosamente');
      setShowDialog(false);
      setFormData({
        type: 'ingreso', category: '', amount: '', description: '',
        date: new Date().toISOString().slice(0, 10), reference: '', supplier_id: ''
      });
      fetchData();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const formatCurrency = (amount) => {
    return `Q ${(amount || 0).toLocaleString('es-GT', { minimumFractionDigits: 2 })}`;
  };

  const filteredEntries = entries.filter(e => {
    if (activeTab === 'all') return true;
    return e.type === activeTab;
  });

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
                    onClick={() => setFormData({...formData, type: 'ingreso', category: '', supplier_id: ''})}
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
                <div className="space-y-2" data-testid="supplier-field">
                  <Label>Proveedor</Label>
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
          </div>
        </CardContent>
      </Card>

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
                <p className={`text-sm font-medium ${summary?.profit >= 0 ? 'text-blue-800' : 'text-amber-800'}`}>Utilidad</p>
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

      {/* Transactions */}
      <Card className="border-slate-200/80">
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <CardTitle className="font-heading text-lg">Movimientos</CardTitle>
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList>
                <TabsTrigger value="all">Todos</TabsTrigger>
                <TabsTrigger value="ingreso">Ingresos</TabsTrigger>
                <TabsTrigger value="egreso">Egresos</TabsTrigger>
              </TabsList>
            </Tabs>
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
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredEntries.map((entry) => (
                <TableRow key={entry._id} className="data-table-row" data-testid={`finance-row-${entry._id}`}>
                  <TableCell>{entry.date}</TableCell>
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
                  <TableCell className="capitalize">{entry.category?.replace('_', ' ')}</TableCell>
                  <TableCell className="text-slate-600">{entry.supplier_name || '—'}</TableCell>
                  <TableCell>{entry.description}</TableCell>
                  <TableCell className={`text-right font-medium ${
                    entry.type === 'ingreso' ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {entry.type === 'ingreso' ? '+' : '-'}{formatCurrency(entry.amount)}
                  </TableCell>
                </TableRow>
              ))}
              {filteredEntries.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-slate-500">
                    <Wallet className="w-12 h-12 mx-auto mb-2 opacity-30" />
                    <p>No hay movimientos registrados</p>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
