import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Textarea } from '../components/ui/textarea';
import { Tabs, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Plus, FileText, Trash2, ShoppingCart, Search,
  Download, ArrowRightLeft, Eye, Clock, CheckCircle,
  XCircle, AlertTriangle, Package
} from 'lucide-react';
import { toast } from 'sonner';
import { QuotationDetailDialog, ConvertToSaleDialog } from '../components/quotations/QuotationDialogs';
import { CreateQuotationDialog } from '../components/quotations/CreateQuotationDialog';

import { BranchFilter } from '../components/BranchFilter';

const formatCurrency = (amount) => `Q${(amount || 0).toLocaleString('es-GT', { minimumFractionDigits: 2 })}`;

const statusConfig = {
  pendiente: { label: 'Pendiente', color: 'bg-amber-100 text-amber-800', icon: Clock },
  aceptada: { label: 'Aceptada', color: 'bg-blue-100 text-blue-800', icon: CheckCircle },
  convertida: { label: 'Convertida', color: 'bg-green-100 text-green-800', icon: ArrowRightLeft },
  rechazada: { label: 'Rechazada', color: 'bg-red-100 text-red-800', icon: XCircle },
  vencida: { label: 'Vencida', color: 'bg-slate-100 text-slate-600', icon: AlertTriangle },
};

export default function QuotationsPage() {
  const [quotations, setQuotations] = useState([]);
  const [patients, setPatients] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showDetailDialog, setShowDetailDialog] = useState(false);
  const [showConvertDialog, setShowConvertDialog] = useState(false);
  const [selectedQuotation, setSelectedQuotation] = useState(null);
  const [statusFilter, setStatusFilter] = useState('todas');
  const [searchTerm, setSearchTerm] = useState('');

  // Create form state
  const [cart, setCart] = useState([]);
  const [form, setForm] = useState({
    patient_id: '',
    discount: 0,
    notes: '',
    payment_conditions: '',
    validity_days: 15,
  });
  const [productSearch, setProductSearch] = useState('');
  const [patientSearch, setPatientSearch] = useState('');

  // Convert form
  const [convertForm, setConvertForm] = useState({
    payment_method: 'efectivo',
    amount_paid: 0,
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [qRes, pRes, prRes] = await Promise.all([
        api.get('/api/quotations'),
        api.get('/api/patients?limit=200'),
        api.get('/api/inventory/products'),
      ]);
      setQuotations(qRes.data);
      setPatients(pRes.data.patients || []);
      setProducts(prRes.data);
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const addToCart = (product) => {
    const existing = cart.find(i => i.product_id === product._id);
    if (existing) {
      setCart(cart.map(i =>
        i.product_id === product._id
          ? { ...i, quantity: i.quantity + 1, subtotal: (i.quantity + 1) * i.unit_price }
          : i
      ));
    } else {
      setCart([...cart, {
        product_id: product._id,
        name: product.name,
        quantity: 1,
        unit_price: product.sale_price,
        subtotal: product.sale_price,
      }]);
    }
  };

  const updateCartItem = (idx, field, value) => {
    const updated = [...cart];
    updated[idx][field] = value;
    if (field === 'quantity' || field === 'unit_price') {
      updated[idx].subtotal = updated[idx].quantity * updated[idx].unit_price;
    }
    setCart(updated);
  };

  const removeFromCart = (idx) => setCart(cart.filter((_, i) => i !== idx));

  const cartSubtotal = cart.reduce((sum, i) => sum + i.subtotal, 0);
  const cartTotal = cartSubtotal - (form.discount || 0);

  const handleCreateQuotation = async () => {
    if (!form.patient_id) return toast.error('Seleccione un paciente');
    if (cart.length === 0) return toast.error('Agregue al menos un producto');

    try {
      await api.post('/api/quotations', {
        patient_id: form.patient_id,
        items: cart,
        subtotal: cartSubtotal,
        discount: form.discount || 0,
        total: cartTotal,
        notes: form.notes,
        payment_conditions: form.payment_conditions,
        validity_days: form.validity_days,
      });
      toast.success('Cotizacion creada exitosamente');
      setShowCreateDialog(false);
      resetForm();
      loadData();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  const resetForm = () => {
    setCart([]);
    setForm({ patient_id: '', discount: 0, notes: '', payment_conditions: '', validity_days: 15 });
    setProductSearch('');
    setPatientSearch('');
  };

  const handleStatusChange = async (id, status) => {
    try {
      await api.put(`/api/quotations/${id}/status`, { status });
      toast.success(`Cotizacion marcada como ${status}`);
      loadData();
      setShowDetailDialog(false);
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  const handleConvert = async () => {
    if (!selectedQuotation) return;
    try {
      await api.post(`/api/quotations/${selectedQuotation._id}/convert?payment_method=${convertForm.payment_method}&amount_paid=${convertForm.amount_paid || selectedQuotation.total}`);
      toast.success('Cotizacion convertida a venta exitosamente');
      setShowConvertDialog(false);
      setShowDetailDialog(false);
      loadData();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  const downloadPdf = async (id) => {
    try {
      const res = await api.get(`/api/quotations/${id}/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `cotizacion_${id}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      toast.error('Error al descargar PDF');
    }
  };

  const openDetail = async (q) => {
    try {
      const res = await api.get(`/api/quotations/${q._id}`);
      setSelectedQuotation(res.data);
      setShowDetailDialog(true);
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  const filteredQuotations = quotations.filter(q => {
    const matchesStatus = statusFilter === 'todas' || q.status === statusFilter;
    const matchesSearch = !searchTerm ||
      (q.patient_name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (q.quotation_number || '').toLowerCase().includes(searchTerm.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const filteredProducts = products.filter(p =>
    p.name.toLowerCase().includes(productSearch.toLowerCase()) ||
    (p.sku || '').toLowerCase().includes(productSearch.toLowerCase())
  );

  const filteredPatients = patients.filter(p =>
    `${p.first_name} ${p.last_name}`.toLowerCase().includes(patientSearch.toLowerCase()) ||
    (p.phone || '').includes(patientSearch)
  );

  const selectedPatientName = patients.find(p => p._id === form.patient_id);

  return (
    <div className="space-y-6" data-testid="quotations-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Cotizaciones</h1>
          <p className="text-slate-500 text-sm mt-1">Crea y gestiona cotizaciones para tus clientes</p>
        </div>
        <Button
          onClick={() => { resetForm(); setShowCreateDialog(true); }}
          className="bg-pine-700 hover:bg-pine-800"
          data-testid="new-quotation-btn"
        >
          <Plus className="w-4 h-4 mr-2" /> Nueva Cotizacion
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4 pb-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                placeholder="Buscar por paciente o numero..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
                data-testid="quotation-search"
              />
            </div>
            <Tabs value={statusFilter} onValueChange={setStatusFilter} className="w-full sm:w-auto">
              <TabsList className="grid grid-cols-4 sm:flex">
                <TabsTrigger value="todas" data-testid="filter-todas">Todas</TabsTrigger>
                <TabsTrigger value="pendiente" data-testid="filter-pendiente">Pendientes</TabsTrigger>
                <TabsTrigger value="aceptada" data-testid="filter-aceptada">Aceptadas</TabsTrigger>
                <TabsTrigger value="convertida" data-testid="filter-convertida">Convertidas</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </CardContent>
      </Card>

      {/* Quotations List */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-8 text-center text-slate-500">Cargando cotizaciones...</div>
          ) : filteredQuotations.length === 0 ? (
            <div className="p-12 text-center">
              <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500 font-medium">No hay cotizaciones</p>
              <p className="text-slate-400 text-sm mt-1">Crea tu primera cotizacion para empezar</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>No.</TableHead>
                  <TableHead>Paciente</TableHead>
                  <TableHead>Items</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Fecha</TableHead>
                  <TableHead>Vigencia</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredQuotations.map((q) => {
                  const sc = statusConfig[q.status] || statusConfig.pendiente;
                  const StatusIcon = sc.icon;
                  return (
                    <TableRow key={q._id} className="cursor-pointer hover:bg-slate-50" data-testid={`quotation-row-${q._id}`}>
                      <TableCell className="font-mono font-medium text-sm">{q.quotation_number}</TableCell>
                      <TableCell>
                        <div className="font-medium text-sm">{q.patient_name || 'Sin paciente'}</div>
                        {q.patient_phone && <div className="text-xs text-slate-400">{q.patient_phone}</div>}
                      </TableCell>
                      <TableCell>
                        <span className="text-sm text-slate-600">{q.items?.length || 0} productos</span>
                      </TableCell>
                      <TableCell className="text-right font-semibold">{formatCurrency(q.total)}</TableCell>
                      <TableCell>
                        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${sc.color}`}>
                          <StatusIcon className="w-3 h-3" /> {sc.label}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm text-slate-500">{q.created_at?.slice(0, 10)}</TableCell>
                      <TableCell className="text-sm text-slate-500">{q.expiry_date}</TableCell>
                      <TableCell>
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="sm" onClick={() => openDetail(q)} data-testid={`view-quotation-${q._id}`}>
                            <Eye className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => downloadPdf(q._id)} data-testid={`download-pdf-${q._id}`}>
                            <Download className="w-4 h-4" />
                          </Button>
                          {(q.status === 'pendiente' || q.status === 'aceptada') && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-green-600"
                              onClick={() => {
                                setSelectedQuotation(q);
                                setConvertForm({ payment_method: 'efectivo', amount_paid: q.total });
                                setShowConvertDialog(true);
                              }}
                              data-testid={`convert-quotation-${q._id}`}
                            >
                              <ShoppingCart className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <CreateQuotationDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        resetForm={resetForm}
        form={form}
        setForm={setForm}
        patientSearch={patientSearch}
        setPatientSearch={setPatientSearch}
        filteredPatients={filteredPatients}
        selectedPatientName={selectedPatientName}
        productSearch={productSearch}
        setProductSearch={setProductSearch}
        filteredProducts={filteredProducts}
        cart={cart}
        addToCart={addToCart}
        updateCartItem={updateCartItem}
        removeFromCart={removeFromCart}
        cartSubtotal={cartSubtotal}
        cartTotal={cartTotal}
        onSubmit={handleCreateQuotation}
        formatCurrency={formatCurrency}
      />

      <QuotationDetailDialog
        open={showDetailDialog}
        onOpenChange={setShowDetailDialog}
        quotation={selectedQuotation}
        statusConfig={statusConfig}
        onDownloadPdf={downloadPdf}
        onStatusChange={handleStatusChange}
        onOpenConvert={(q) => {
          setConvertForm({ payment_method: 'efectivo', amount_paid: q.total });
          setShowConvertDialog(true);
        }}
        formatCurrency={formatCurrency}
      />
      <ConvertToSaleDialog
        open={showConvertDialog}
        onOpenChange={setShowConvertDialog}
        quotation={selectedQuotation}
        form={convertForm}
        setForm={setConvertForm}
        onConfirm={handleConvert}
        formatCurrency={formatCurrency}
      />
    </div>
  );
}
