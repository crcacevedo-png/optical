import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Plus, FileText, Trash2, ShoppingCart, Search,
  Download, ArrowRightLeft, Eye, Clock, CheckCircle,
  XCircle, AlertTriangle, Package
} from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

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

      {/* ===== CREATE DIALOG ===== */}
      <Dialog open={showCreateDialog} onOpenChange={(open) => { if (!open) resetForm(); setShowCreateDialog(open); }}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-xl">Nueva Cotizacion</DialogTitle>
          </DialogHeader>

          <div className="space-y-6">
            {/* Patient Selection */}
            <div className="space-y-2">
              <Label className="font-semibold">Paciente *</Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <Input
                  placeholder="Buscar paciente por nombre o telefono..."
                  value={patientSearch}
                  onChange={(e) => setPatientSearch(e.target.value)}
                  className="pl-9"
                  data-testid="patient-search-input"
                />
              </div>
              {patientSearch && !form.patient_id && (
                <div className="border rounded-lg max-h-32 overflow-y-auto">
                  {filteredPatients.slice(0, 5).map(p => (
                    <button
                      key={p._id}
                      className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50 flex justify-between"
                      onClick={() => {
                        setForm({ ...form, patient_id: p._id });
                        setPatientSearch(`${p.first_name} ${p.last_name}`);
                      }}
                      data-testid={`select-patient-${p._id}`}
                    >
                      <span className="font-medium">{p.first_name} {p.last_name}</span>
                      <span className="text-slate-400">{p.phone}</span>
                    </button>
                  ))}
                </div>
              )}
              {form.patient_id && selectedPatientName && (
                <div className="flex items-center gap-2 px-3 py-2 bg-pine-50 rounded-lg">
                  <CheckCircle className="w-4 h-4 text-pine-600" />
                  <span className="text-sm font-medium text-pine-800">{selectedPatientName.first_name} {selectedPatientName.last_name}</span>
                  <Button variant="ghost" size="sm" className="ml-auto h-6 text-xs" onClick={() => { setForm({ ...form, patient_id: '' }); setPatientSearch(''); }}>
                    Cambiar
                  </Button>
                </div>
              )}
            </div>

            {/* Products */}
            <div className="space-y-2">
              <Label className="font-semibold">Productos</Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <Input
                  placeholder="Buscar producto..."
                  value={productSearch}
                  onChange={(e) => setProductSearch(e.target.value)}
                  className="pl-9"
                  data-testid="product-search-input"
                />
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 max-h-48 overflow-y-auto">
                {filteredProducts.slice(0, 12).map(p => (
                  <button
                    key={p._id}
                    onClick={() => addToCart(p)}
                    className="p-2.5 border rounded-lg text-left hover:border-pine-300 hover:bg-pine-50 transition-colors"
                    data-testid={`add-product-${p._id}`}
                  >
                    <div className="text-sm font-medium truncate">{p.name}</div>
                    <div className="text-xs text-slate-400">{p.sku}</div>
                    <div className="text-sm font-semibold text-pine-700 mt-1">{formatCurrency(p.sale_price)}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Cart */}
            {cart.length > 0 && (
              <div className="space-y-3">
                <Label className="font-semibold flex items-center gap-2">
                  <Package className="w-4 h-4" /> Productos en cotizacion ({cart.length})
                </Label>
                <div className="border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Producto</TableHead>
                        <TableHead className="w-24">Cant</TableHead>
                        <TableHead className="w-32">Precio Unit.</TableHead>
                        <TableHead className="w-28 text-right">Subtotal</TableHead>
                        <TableHead className="w-10"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {cart.map((item, idx) => (
                        <TableRow key={idx}>
                          <TableCell className="text-sm font-medium">{item.name}</TableCell>
                          <TableCell>
                            <Input
                              type="number"
                              min="1"
                              value={item.quantity}
                              onChange={(e) => updateCartItem(idx, 'quantity', parseInt(e.target.value) || 1)}
                              className="h-8 w-20"
                              data-testid={`cart-qty-${idx}`}
                            />
                          </TableCell>
                          <TableCell>
                            <Input
                              type="number"
                              min="0"
                              step="0.01"
                              value={item.unit_price}
                              onChange={(e) => updateCartItem(idx, 'unit_price', parseFloat(e.target.value) || 0)}
                              className="h-8 w-28"
                              data-testid={`cart-price-${idx}`}
                            />
                          </TableCell>
                          <TableCell className="text-right font-medium">{formatCurrency(item.subtotal)}</TableCell>
                          <TableCell>
                            <Button variant="ghost" size="sm" onClick={() => removeFromCart(idx)} className="text-red-500 h-7 w-7 p-0">
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                {/* Totals */}
                <div className="flex justify-end">
                  <div className="w-72 space-y-2 bg-slate-50 p-4 rounded-lg">
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-500">Subtotal:</span>
                      <span className="font-medium">{formatCurrency(cartSubtotal)}</span>
                    </div>
                    <div className="flex justify-between text-sm items-center gap-2">
                      <span className="text-slate-500">Descuento:</span>
                      <Input
                        type="number"
                        min="0"
                        step="0.01"
                        value={form.discount}
                        onChange={(e) => setForm({ ...form, discount: parseFloat(e.target.value) || 0 })}
                        className="h-8 w-28 text-right"
                        data-testid="discount-input"
                      />
                    </div>
                    <div className="flex justify-between font-bold text-lg border-t pt-2">
                      <span>Total:</span>
                      <span className="text-pine-700">{formatCurrency(cartTotal)}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Notes & Conditions */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Notas</Label>
                <Textarea
                  placeholder="Observaciones o detalles adicionales..."
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  rows={3}
                  data-testid="notes-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Condiciones de Pago</Label>
                <Textarea
                  placeholder="Ej: 50% anticipo, 50% al entregar"
                  value={form.payment_conditions}
                  onChange={(e) => setForm({ ...form, payment_conditions: e.target.value })}
                  rows={3}
                  data-testid="payment-conditions-input"
                />
              </div>
            </div>

            {/* Validity */}
            <div className="w-48">
              <Label>Vigencia (dias)</Label>
              <Select value={String(form.validity_days)} onValueChange={(v) => setForm({ ...form, validity_days: parseInt(v) })}>
                <SelectTrigger data-testid="validity-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="7">7 dias</SelectItem>
                  <SelectItem value="15">15 dias</SelectItem>
                  <SelectItem value="30">30 dias</SelectItem>
                  <SelectItem value="60">60 dias</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-2">
              <Button variant="outline" onClick={() => setShowCreateDialog(false)}>Cancelar</Button>
              <Button
                onClick={handleCreateQuotation}
                className="bg-pine-700 hover:bg-pine-800"
                disabled={!form.patient_id || cart.length === 0}
                data-testid="save-quotation-btn"
              >
                <FileText className="w-4 h-4 mr-2" /> Crear Cotizacion
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ===== DETAIL DIALOG ===== */}
      <Dialog open={showDetailDialog} onOpenChange={setShowDetailDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          {selectedQuotation && (
            <>
              <DialogHeader>
                <div className="flex items-center justify-between">
                  <DialogTitle className="text-xl">
                    Cotizacion {selectedQuotation.quotation_number}
                  </DialogTitle>
                  {(() => {
                    const sc = statusConfig[selectedQuotation.status] || statusConfig.pendiente;
                    const StatusIcon = sc.icon;
                    return (
                      <span className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-medium ${sc.color}`}>
                        <StatusIcon className="w-4 h-4" /> {sc.label}
                      </span>
                    );
                  })()}
                </div>
              </DialogHeader>

              <div className="space-y-5">
                {/* Patient info */}
                <div className="bg-slate-50 p-4 rounded-lg">
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div><span className="text-slate-500">Paciente:</span> <span className="font-medium">{selectedQuotation.patient_name}</span></div>
                    <div><span className="text-slate-500">Telefono:</span> {selectedQuotation.patient_phone}</div>
                    <div><span className="text-slate-500">Fecha:</span> {selectedQuotation.created_at?.slice(0, 10)}</div>
                    <div><span className="text-slate-500">Vigencia hasta:</span> {selectedQuotation.expiry_date}</div>
                  </div>
                </div>

                {/* Items */}
                <div>
                  <Label className="font-semibold mb-2 block">Productos</Label>
                  <div className="border rounded-lg overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Producto</TableHead>
                          <TableHead className="text-center">Cant</TableHead>
                          <TableHead className="text-right">P. Unit.</TableHead>
                          <TableHead className="text-right">Subtotal</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {(selectedQuotation.items || []).map((item, idx) => (
                          <TableRow key={idx}>
                            <TableCell className="font-medium text-sm">{item.name}</TableCell>
                            <TableCell className="text-center">{item.quantity}</TableCell>
                            <TableCell className="text-right">{formatCurrency(item.unit_price)}</TableCell>
                            <TableCell className="text-right font-medium">{formatCurrency(item.subtotal)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>

                {/* Totals */}
                <div className="flex justify-end">
                  <div className="w-64 space-y-1.5">
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-500">Subtotal:</span>
                      <span>{formatCurrency(selectedQuotation.subtotal)}</span>
                    </div>
                    {selectedQuotation.discount > 0 && (
                      <div className="flex justify-between text-sm text-red-600">
                        <span>Descuento:</span>
                        <span>-{formatCurrency(selectedQuotation.discount)}</span>
                      </div>
                    )}
                    <div className="flex justify-between font-bold text-lg border-t pt-1.5">
                      <span>Total:</span>
                      <span className="text-pine-700">{formatCurrency(selectedQuotation.total)}</span>
                    </div>
                  </div>
                </div>

                {/* Notes */}
                {selectedQuotation.notes && (
                  <div>
                    <Label className="font-semibold text-sm text-slate-500">Notas</Label>
                    <p className="text-sm mt-1">{selectedQuotation.notes}</p>
                  </div>
                )}
                {selectedQuotation.payment_conditions && (
                  <div>
                    <Label className="font-semibold text-sm text-slate-500">Condiciones de Pago</Label>
                    <p className="text-sm mt-1">{selectedQuotation.payment_conditions}</p>
                  </div>
                )}

                {/* Actions */}
                <div className="flex flex-wrap gap-2 pt-2 border-t">
                  <Button variant="outline" size="sm" onClick={() => downloadPdf(selectedQuotation._id)} data-testid="detail-download-pdf">
                    <Download className="w-4 h-4 mr-2" /> Descargar PDF
                  </Button>

                  {selectedQuotation.status === 'pendiente' && (
                    <>
                      <Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={() => handleStatusChange(selectedQuotation._id, 'aceptada')} data-testid="accept-quotation-btn">
                        <CheckCircle className="w-4 h-4 mr-2" /> Aceptar
                      </Button>
                      <Button size="sm" variant="destructive" onClick={() => handleStatusChange(selectedQuotation._id, 'rechazada')} data-testid="reject-quotation-btn">
                        <XCircle className="w-4 h-4 mr-2" /> Rechazar
                      </Button>
                    </>
                  )}

                  {(selectedQuotation.status === 'pendiente' || selectedQuotation.status === 'aceptada') && (
                    <Button
                      size="sm"
                      className="bg-green-600 hover:bg-green-700"
                      onClick={() => {
                        setConvertForm({ payment_method: 'efectivo', amount_paid: selectedQuotation.total });
                        setShowConvertDialog(true);
                      }}
                      data-testid="convert-to-sale-btn"
                    >
                      <ShoppingCart className="w-4 h-4 mr-2" /> Convertir a Venta
                    </Button>
                  )}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* ===== CONVERT TO SALE DIALOG ===== */}
      <Dialog open={showConvertDialog} onOpenChange={setShowConvertDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Convertir a Venta</DialogTitle>
          </DialogHeader>
          {selectedQuotation && (
            <div className="space-y-4">
              <div className="bg-green-50 p-4 rounded-lg text-center">
                <p className="text-sm text-green-700">Total de la cotizacion</p>
                <p className="text-2xl font-bold text-green-800">{formatCurrency(selectedQuotation.total)}</p>
              </div>

              <div className="space-y-2">
                <Label>Metodo de Pago</Label>
                <Select value={convertForm.payment_method} onValueChange={(v) => setConvertForm({ ...convertForm, payment_method: v })}>
                  <SelectTrigger data-testid="convert-payment-method">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="efectivo">Efectivo</SelectItem>
                    <SelectItem value="tarjeta">Tarjeta</SelectItem>
                    <SelectItem value="transferencia">Transferencia</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Monto a pagar</Label>
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={convertForm.amount_paid}
                  onChange={(e) => setConvertForm({ ...convertForm, amount_paid: parseFloat(e.target.value) || 0 })}
                  data-testid="convert-amount-paid"
                />
                {convertForm.amount_paid < selectedQuotation.total && (
                  <p className="text-xs text-amber-600">
                    Saldo pendiente: {formatCurrency(selectedQuotation.total - convertForm.amount_paid)}
                  </p>
                )}
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <Button variant="outline" onClick={() => setShowConvertDialog(false)}>Cancelar</Button>
                <Button className="bg-green-600 hover:bg-green-700" onClick={handleConvert} data-testid="confirm-convert-btn">
                  <ShoppingCart className="w-4 h-4 mr-2" /> Confirmar Venta
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
