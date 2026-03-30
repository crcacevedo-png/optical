import React, { useState, useEffect } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { 
  Plus, TrendingUp, TrendingDown, DollarSign, 
  ArrowUpCircle, ArrowDownCircle, Wallet
} from 'lucide-react';
import { toast } from 'sonner';

export default function FinancePage() {
  const [entries, setEntries] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [activeTab, setActiveTab] = useState('all');

  const [formData, setFormData] = useState({
    type: 'income',
    category: '',
    amount: '',
    description: '',
    date: new Date().toISOString().slice(0, 10),
    reference: ''
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
  }, []);

  const fetchData = async () => {
    try {
      const [entriesRes, summaryRes] = await Promise.all([
        api.get('/api/finance'),
        api.get('/api/finance/summary')
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
        amount: parseFloat(formData.amount)
      });
      toast.success('Entrada registrada exitosamente');
      setShowDialog(false);
      setFormData({
        type: 'income', category: '', amount: '', description: '',
        date: new Date().toISOString().slice(0, 10), reference: ''
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
                    onClick={() => setFormData({...formData, type: 'income', category: ''})}
                    className={`flex-1 p-3 rounded-lg border flex items-center justify-center gap-2 transition-colors ${
                      formData.type === 'income'
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
                    onClick={() => setFormData({...formData, type: 'expense', category: ''})}
                    className={`flex-1 p-3 rounded-lg border flex items-center justify-center gap-2 transition-colors ${
                      formData.type === 'expense'
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
                      {(formData.type === 'income' ? incomeCategories : expenseCategories).map((c) => (
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

      {/* Transactions */}
      <Card className="border-slate-200/80">
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <CardTitle className="font-heading text-lg">Movimientos</CardTitle>
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList>
                <TabsTrigger value="all">Todos</TabsTrigger>
                <TabsTrigger value="income">Ingresos</TabsTrigger>
                <TabsTrigger value="expense">Egresos</TabsTrigger>
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
                      entry.type === 'income' 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {entry.type === 'income' ? <ArrowUpCircle className="w-3 h-3" /> : <ArrowDownCircle className="w-3 h-3" />}
                      {entry.type === 'income' ? 'Ingreso' : 'Egreso'}
                    </span>
                  </TableCell>
                  <TableCell className="capitalize">{entry.category?.replace('_', ' ')}</TableCell>
                  <TableCell>{entry.description}</TableCell>
                  <TableCell className={`text-right font-medium ${
                    entry.type === 'income' ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {entry.type === 'income' ? '+' : '-'}{formatCurrency(entry.amount)}
                  </TableCell>
                </TableRow>
              ))}
              {filteredEntries.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-8 text-slate-500">
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
