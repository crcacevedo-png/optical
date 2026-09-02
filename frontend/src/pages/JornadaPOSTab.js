// Tab de Punto de Venta de la Jornada
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { toast } from 'sonner';
import { ShoppingCart, Search, Plus, Minus, Trash2, User, Stethoscope, Eye, MessageCircle, Printer } from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';

const fmtQ = (n) => `Q ${(Number(n) || 0).toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const METHODS = [
  { key: 'cash', label: 'Efectivo' },
  { key: 'card', label: 'Tarjeta' },
  { key: 'transfer', label: 'Transferencia' },
  { key: 'check', label: 'Cheque' },
  { key: 'other', label: 'Otro' },
];

export default function JornadaPOSTab({ jornada, reload }) {
  const jid = jornada._id;
  const [inventory, setInventory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [cart, setCart] = useState([]); // [{product_id, name, price, quantity, stock}]
  const [patient, setPatient] = useState(null);
  const [patientQuery, setPatientQuery] = useState('');
  const [patientOptions, setPatientOptions] = useState([]);
  const [discount, setDiscount] = useState(0);
  const [payments, setPayments] = useState([{ method: 'cash', amount: 0, reference: '' }]);
  const [processing, setProcessing] = useState(false);
  const [recentSales, setRecentSales] = useState([]);
  // Iter 3.1 - encadenar consulta/receta y ticket
  const [consultationId, setConsultationId] = useState(null);
  const [prescriptionId, setPrescriptionId] = useState(null);
  const [consultDialog, setConsultDialog] = useState(false);
  const [rxDialog, setRxDialog] = useState(false);
  const [ticketDialog, setTicketDialog] = useState(null); // saved sale info
  const [consultForm, setConsultForm] = useState({ reason: '', observations: '', vision_od: '', vision_oi: '' });
  const [rxForm, setRxForm] = useState({ od_sphere: '', od_cylinder: '', od_axis: '', od_addition: '', oi_sphere: '', oi_cylinder: '', oi_axis: '', oi_addition: '', lens_type: '', observations: '' });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [invRes, salesRes] = await Promise.all([
        api.get(`/api/jornadas/${jid}/inventory`),
        api.get(`/api/jornadas/${jid}/sales`, { params: { limit: 10 } }),
      ]);
      setInventory(invRes.data.items || []);
      setRecentSales(salesRes.data.items || []);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setLoading(false); }
  }, [jid]);
  useEffect(() => { load(); }, [load]);

  // Search patient (debounced) - only jornada patients
  useEffect(() => {
    if (!patientQuery || patientQuery.length < 2) { setPatientOptions([]); return; }
    const t = setTimeout(async () => {
      try {
        const res = await api.get(`/api/jornadas/${jid}/patients`);
        const q = patientQuery.toLowerCase();
        setPatientOptions((res.data.items || []).filter(p =>
          `${p.first_name} ${p.last_name}`.toLowerCase().includes(q) ||
          (p.phone || '').includes(q) ||
          (p.dpi || '').includes(q)
        ).slice(0, 5));
      } catch { /* ignore */ }
    }, 300);
    return () => clearTimeout(t);
  }, [patientQuery, jid]);

  const filteredInventory = useMemo(() => {
    if (!search) return inventory.filter(i => i.current_qty > 0);
    const q = search.toLowerCase();
    return inventory.filter(i =>
      i.current_qty > 0 && (
        (i.product_name || '').toLowerCase().includes(q) ||
        (i.product_sku || '').toLowerCase().includes(q) ||
        (i.product_brand || '').toLowerCase().includes(q)
      )
    );
  }, [inventory, search]);

  const subtotal = cart.reduce((s, it) => s + it.price * it.quantity, 0);
  const total = Math.max(0, subtotal - (parseFloat(discount) || 0));
  const paid = payments.reduce((s, p) => s + (parseFloat(p.amount) || 0), 0);
  const balance = total - paid;

  const addToCart = (item) => {
    setCart(prev => {
      const existing = prev.find(x => x.product_id === item.product_id);
      const available = item.current_qty;
      if (existing) {
        if (existing.quantity >= available) { toast.warning('Stock alcanzado'); return prev; }
        return prev.map(x => x.product_id === item.product_id ? { ...x, quantity: x.quantity + 1 } : x);
      }
      return [...prev, { product_id: item.product_id, name: item.product_name, price: item.unit_price, quantity: 1, stock: available }];
    });
  };

  const updateQty = (product_id, delta) => {
    setCart(prev => prev.map(x => {
      if (x.product_id !== product_id) return x;
      const nq = x.quantity + delta;
      if (nq < 1) return x;
      if (nq > x.stock) { toast.warning('Stock alcanzado'); return x; }
      return { ...x, quantity: nq };
    }));
  };

  const removeFromCart = (product_id) => setCart(prev => prev.filter(x => x.product_id !== product_id));

  const setPaymentAmount = (idx, amount) => setPayments(prev => prev.map((p, i) => i === idx ? { ...p, amount } : p));
  const setPaymentMethod = (idx, method) => setPayments(prev => prev.map((p, i) => i === idx ? { ...p, method } : p));
  const addPayment = () => setPayments(prev => [...prev, { method: 'cash', amount: 0, reference: '' }]);
  const removePayment = (idx) => setPayments(prev => prev.filter((_, i) => i !== idx));

  const resetSale = () => {
    setCart([]);
    setPatient(null);
    setPatientQuery('');
    setDiscount(0);
    setPayments([{ method: 'cash', amount: 0, reference: '' }]);
    setConsultationId(null);
    setPrescriptionId(null);
  };

  const saveConsultation = async () => {
    if (!patient) { toast.error('Selecciona un paciente primero'); return; }
    setProcessing(true);
    try {
      const res = await api.post(`/api/jornadas/${jid}/consultations`, {
        patient_id: patient._id, ...consultForm,
      });
      setConsultationId(res.data._id);
      toast.success('Consulta registrada y vinculada');
      setConsultDialog(false);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setProcessing(false); }
  };

  const saveRx = async () => {
    if (!patient) { toast.error('Selecciona un paciente primero'); return; }
    setProcessing(true);
    try {
      const payload = { patient_id: patient._id, consultation_id: consultationId };
      Object.entries(rxForm).forEach(([k, v]) => {
        if (v !== '' && v !== null) {
          payload[k] = ['lens_type', 'observations'].includes(k) ? v : parseFloat(v);
        }
      });
      const res = await api.post(`/api/jornadas/${jid}/prescriptions/eyeglass`, payload);
      setPrescriptionId(res.data._id);
      toast.success('Receta creada y vinculada');
      setRxDialog(false);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setProcessing(false); }
  };

  const submitSale = async () => {
    if (cart.length === 0) { toast.error('Carrito vacio'); return; }
    if (paid <= 0 && total > 0) { toast.error('Debe registrar al menos un pago (o balance sera saldo pendiente)'); }
    setProcessing(true);
    try {
      const res = await api.post(`/api/jornadas/${jid}/sales`, {
        patient_id: patient?._id || null,
        patient_name_override: patient ? null : (patientQuery || null),
        items: cart.map(c => ({ product_id: c.product_id, name: c.name, quantity: c.quantity, price: c.price, total: c.price * c.quantity })),
        payments: payments.filter(p => parseFloat(p.amount) > 0).map(p => ({ method: p.method, amount: parseFloat(p.amount), reference: p.reference })),
        discount: parseFloat(discount) || 0,
        notes: null,
        consultation_id: consultationId,
        prescription_id: prescriptionId,
      });
      toast.success(balance > 0.01 ? `Venta con saldo pendiente ${fmtQ(balance)}` : 'Venta registrada');
      // Guardar info para modal de ticket
      setTicketDialog({
        sale_id: res.data._id, total, patient_name: patient ? `${patient.first_name} ${patient.last_name}` : (patientQuery || 'Consumidor final'),
        patient_phone: patient?.whatsapp || patient?.phone,
      });
      resetSale();
      load(); reload?.();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setProcessing(false); }
  };

  if (jornada.status !== 'activa') {
    return (
      <Card className="border-dashed border-slate-300"><CardContent className="py-8 text-center">
        <ShoppingCart className="w-10 h-10 text-slate-400 mx-auto mb-2" />
        <p className="text-sm text-slate-600">El POS solo esta disponible con la jornada Activa</p>
      </CardContent></Card>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Inventario del POS */}
      <div className="lg:col-span-2 space-y-3">
        <div className="relative">
          <Search className="absolute left-2 top-2.5 w-4 h-4 text-slate-400" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar producto por nombre, SKU o marca..." className="pl-8" data-testid="jpos-search" />
        </div>
        {loading ? (
          <div className="flex items-center justify-center h-32"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-pine-900" /></div>
        ) : filteredInventory.length === 0 ? (
          <Card className="border-dashed"><CardContent className="py-6 text-center">
            <p className="text-sm text-slate-500">Sin productos disponibles</p>
          </CardContent></Card>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-[500px] overflow-y-auto pr-1" data-testid="jpos-products">
            {filteredInventory.map(it => (
              <button
                key={it._id}
                onClick={() => addToCart(it)}
                className="p-3 rounded-lg border-2 border-slate-200 hover:border-pine-500 hover:bg-pine-50 text-left transition-colors"
                data-testid={`jpos-prod-${it.product_id}`}
              >
                <p className="text-sm font-medium truncate text-slate-800">{it.product_name}</p>
                <p className="text-xs text-slate-400 truncate">{it.product_sku || '—'}</p>
                <div className="mt-1 flex items-center justify-between">
                  <p className="font-heading text-sm font-bold text-pine-900">{fmtQ(it.unit_price)}</p>
                  <Badge variant="outline" className="text-[10px]">{it.current_qty}</Badge>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Carrito y checkout */}
      <div className="space-y-3">
        <Card><CardContent className="pt-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold">Carrito ({cart.length})</p>
            {cart.length > 0 && <Button size="sm" variant="ghost" onClick={resetSale}><Trash2 className="w-3.5 h-3.5" /></Button>}
          </div>
          {cart.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-3">Vacio</p>
          ) : (
            <div className="space-y-2 max-h-48 overflow-y-auto" data-testid="jpos-cart">
              {cart.map(it => (
                <div key={it.product_id} className="flex items-center gap-2 text-sm">
                  <div className="flex-1 min-w-0">
                    <p className="truncate">{it.name}</p>
                    <p className="text-xs text-slate-500">{fmtQ(it.price)}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => updateQty(it.product_id, -1)}><Minus className="w-3 h-3" /></Button>
                    <span className="w-6 text-center text-sm">{it.quantity}</span>
                    <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => updateQty(it.product_id, 1)}><Plus className="w-3 h-3" /></Button>
                    <Button size="icon" variant="ghost" className="h-6 w-6 text-rose-500" onClick={() => removeFromCart(it.product_id)}><Trash2 className="w-3 h-3" /></Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Patient */}
          <div className="pt-2 border-t border-slate-100 space-y-1.5">
            <Label className="text-xs">Paciente</Label>
            {patient ? (
              <div className="flex items-center gap-2 p-1.5 bg-emerald-50 rounded text-sm">
                <User className="w-3.5 h-3.5 text-emerald-600" />
                <span className="flex-1 truncate">{patient.first_name} {patient.last_name}</span>
                <Button size="sm" variant="ghost" onClick={() => { setPatient(null); setPatientQuery(''); }}>Cambiar</Button>
              </div>
            ) : (
              <div className="relative">
                <Input value={patientQuery} onChange={(e) => setPatientQuery(e.target.value)} placeholder="Buscar / Consumidor final" className="text-sm" data-testid="jpos-patient-search" />
                {patientOptions.length > 0 && (
                  <div className="absolute z-10 top-full mt-1 w-full border rounded-md shadow-md bg-white max-h-32 overflow-y-auto">
                    {patientOptions.map(p => (
                      <button key={p._id} type="button" onClick={() => { setPatient(p); setPatientQuery(''); setPatientOptions([]); }} className="w-full text-left px-2 py-1.5 text-sm hover:bg-slate-50 border-b last:border-0">
                        <p className="font-medium">{p.first_name} {p.last_name}</p>
                        <p className="text-xs text-slate-400">{p.phone}</p>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            {patient && (
              <div className="flex gap-1.5 pt-1">
                <Button
                  size="sm" variant={consultationId ? "default" : "outline"}
                  className={`flex-1 h-7 text-[11px] ${consultationId ? 'bg-emerald-600 hover:bg-emerald-700' : ''}`}
                  onClick={() => setConsultDialog(true)}
                  data-testid="jpos-consult-btn"
                >
                  <Stethoscope className="w-3 h-3 mr-1" /> {consultationId ? 'Consulta OK' : 'Consulta'}
                </Button>
                <Button
                  size="sm" variant={prescriptionId ? "default" : "outline"}
                  className={`flex-1 h-7 text-[11px] ${prescriptionId ? 'bg-emerald-600 hover:bg-emerald-700' : ''}`}
                  onClick={() => setRxDialog(true)}
                  data-testid="jpos-rx-btn"
                >
                  <Eye className="w-3 h-3 mr-1" /> {prescriptionId ? 'Receta OK' : 'Receta'}
                </Button>
              </div>
            )}
          </div>

          {/* Discount */}
          <div className="space-y-1.5">
            <Label className="text-xs">Descuento (Q)</Label>
            <Input type="number" min="0" step="0.01" value={discount} onChange={(e) => setDiscount(e.target.value)} data-testid="jpos-discount" />
          </div>

          {/* Totals */}
          <div className="pt-2 border-t border-slate-100 text-sm space-y-1">
            <div className="flex justify-between"><span className="text-slate-500">Subtotal</span><span>{fmtQ(subtotal)}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Descuento</span><span>-{fmtQ(discount)}</span></div>
            <div className="flex justify-between font-heading font-bold text-base"><span>Total</span><span className="text-pine-900">{fmtQ(total)}</span></div>
          </div>

          {/* Payments */}
          <div className="space-y-2 pt-2 border-t border-slate-100">
            <div className="flex items-center justify-between"><Label className="text-xs">Pagos</Label><Button size="sm" variant="ghost" onClick={addPayment}><Plus className="w-3.5 h-3.5" /></Button></div>
            {payments.map((p, idx) => (
              <div key={idx} className="flex gap-1.5" data-testid={`jpos-payment-${idx}`}>
                <Select value={p.method} onValueChange={(v) => setPaymentMethod(idx, v)}>
                  <SelectTrigger className="w-24 h-8 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>{METHODS.map(m => <SelectItem key={m.key} value={m.key}>{m.label}</SelectItem>)}</SelectContent>
                </Select>
                <Input type="number" min="0" step="0.01" value={p.amount} onChange={(e) => setPaymentAmount(idx, e.target.value)} className="h-8 text-sm" placeholder="0.00" />
                {payments.length > 1 && <Button size="icon" variant="ghost" className="h-8 w-8 text-rose-500" onClick={() => removePayment(idx)}><Trash2 className="w-3.5 h-3.5" /></Button>}
              </div>
            ))}
            <div className="flex justify-between text-xs pt-1">
              <span className="text-slate-500">Pagado</span><span>{fmtQ(paid)}</span>
            </div>
            {balance > 0.01 && <p className="text-xs text-amber-700">Quedara con saldo pendiente {fmtQ(balance)}</p>}
            {balance < -0.01 && <p className="text-xs text-emerald-700">Vuelto: {fmtQ(Math.abs(balance))}</p>}
          </div>

          <Button className="w-full bg-pine-900 hover:bg-pine-800" disabled={processing || cart.length === 0} onClick={submitSale} data-testid="jpos-submit">
            {processing ? 'Procesando...' : `Cobrar ${fmtQ(total)}`}
          </Button>
        </CardContent></Card>

        {recentSales.length > 0 && (
          <Card><CardContent className="pt-4">
            <p className="text-xs font-semibold text-slate-500 mb-2">Ventas recientes</p>
            <div className="space-y-1.5 max-h-36 overflow-y-auto text-xs">
              {recentSales.map(s => (
                <div key={s._id} className="flex items-center justify-between p-1.5 rounded hover:bg-slate-50">
                  <button type="button" className="text-slate-500 hover:text-pine-900 truncate max-w-[140px] text-left" onClick={() => setTicketDialog({ sale_id: s._id, total: s.total, patient_name: s.patient_name, patient_phone: null })} data-testid={`jpos-recent-${s._id}`}>
                    {s.patient_name}
                  </button>
                  <span className="font-semibold">{fmtQ(s.total)}</span>
                </div>
              ))}
            </div>
          </CardContent></Card>
        )}
      </div>

      {/* Consulta rapida */}
      <Dialog open={consultDialog} onOpenChange={setConsultDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Consulta rapida</DialogTitle>
            <DialogDescription>Registra la consulta y se vinculara automaticamente a esta venta.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>Motivo</Label>
              <Input value={consultForm.reason} onChange={(e) => setConsultForm({ ...consultForm, reason: e.target.value })} placeholder="Ej. Vision borrosa" data-testid="jpos-consult-reason" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <Label>Vision OD</Label>
                <Input value={consultForm.vision_od} onChange={(e) => setConsultForm({ ...consultForm, vision_od: e.target.value })} placeholder="20/20" data-testid="jpos-consult-od" />
              </div>
              <div className="space-y-1.5">
                <Label>Vision OS</Label>
                <Input value={consultForm.vision_oi} onChange={(e) => setConsultForm({ ...consultForm, vision_oi: e.target.value })} placeholder="20/40" data-testid="jpos-consult-oi" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Observaciones</Label>
              <Textarea rows={2} value={consultForm.observations} onChange={(e) => setConsultForm({ ...consultForm, observations: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConsultDialog(false)}>Cancelar</Button>
            <Button className="bg-pine-900 hover:bg-pine-800" disabled={processing} onClick={saveConsultation} data-testid="jpos-consult-save">
              {processing ? 'Guardando...' : 'Guardar consulta'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Receta rapida */}
      <Dialog open={rxDialog} onOpenChange={setRxDialog}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Receta de lentes rapida</DialogTitle>
            <DialogDescription>La receta quedara vinculada al paciente y a la venta.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-5 gap-2 items-end">
              <Label className="text-xs">Ojo</Label>
              <Label className="text-xs text-center">Esfera</Label>
              <Label className="text-xs text-center">Cilindro</Label>
              <Label className="text-xs text-center">Eje</Label>
              <Label className="text-xs text-center">Add</Label>
            </div>
            {['od', 'oi'].map((eye) => (
              <div key={eye} className="grid grid-cols-5 gap-2 items-center">
                <Label className="text-xs font-semibold uppercase">{eye === 'oi' ? 'OS' : eye}</Label>
                <Input type="number" step="0.25" value={rxForm[`${eye}_sphere`]} onChange={(e) => setRxForm({ ...rxForm, [`${eye}_sphere`]: e.target.value })} className="text-center text-xs h-8" data-testid={`jpos-rx-${eye}-sphere`} />
                <Input type="number" step="0.25" value={rxForm[`${eye}_cylinder`]} onChange={(e) => setRxForm({ ...rxForm, [`${eye}_cylinder`]: e.target.value })} className="text-center text-xs h-8" />
                <Input type="number" step="1" value={rxForm[`${eye}_axis`]} onChange={(e) => setRxForm({ ...rxForm, [`${eye}_axis`]: e.target.value })} className="text-center text-xs h-8" />
                <Input type="number" step="0.25" value={rxForm[`${eye}_addition`]} onChange={(e) => setRxForm({ ...rxForm, [`${eye}_addition`]: e.target.value })} className="text-center text-xs h-8" />
              </div>
            ))}
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <Label>Tipo de lente</Label>
                <Input value={rxForm.lens_type} onChange={(e) => setRxForm({ ...rxForm, lens_type: e.target.value })} placeholder="Monofocal / Progresivo" />
              </div>
              <div className="space-y-1.5">
                <Label>Observaciones</Label>
                <Input value={rxForm.observations} onChange={(e) => setRxForm({ ...rxForm, observations: e.target.value })} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRxDialog(false)}>Cancelar</Button>
            <Button className="bg-pine-900 hover:bg-pine-800" disabled={processing} onClick={saveRx} data-testid="jpos-rx-save">
              {processing ? 'Guardando...' : 'Guardar receta'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Ticket / WhatsApp share */}
      <Dialog open={ticketDialog !== null} onOpenChange={(o) => { if (!o) setTicketDialog(null); }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-center">Venta registrada</DialogTitle>
          </DialogHeader>
          {ticketDialog && (
            <div className="space-y-3">
              <div className="text-center py-3">
                <p className="text-xs text-slate-400 uppercase">Total cobrado</p>
                <p className="font-heading text-3xl font-bold text-pine-900">{fmtQ(ticketDialog.total)}</p>
                <p className="text-sm text-slate-500 mt-1">{ticketDialog.patient_name}</p>
              </div>
              <a
                href={`${process.env.REACT_APP_BACKEND_URL}/api/jornadas/${jid}/sales/${ticketDialog.sale_id}/receipt.pdf`}
                target="_blank" rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 w-full bg-pine-900 hover:bg-pine-800 text-white text-sm font-medium py-2.5 rounded-md transition-colors"
                data-testid="ticket-view-pdf"
              >
                <Printer className="w-4 h-4" /> Ver / Imprimir ticket
              </a>
              {ticketDialog.patient_phone && (
                <a
                  href={`https://wa.me/${(ticketDialog.patient_phone || '').replace(/\D/g, '')}?text=${encodeURIComponent(`Gracias por su compra en la jornada. Ticket: ${process.env.REACT_APP_BACKEND_URL}/api/jornadas/${jid}/sales/${ticketDialog.sale_id}/receipt.pdf`)}`}
                  target="_blank" rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 w-full bg-[#25D366] hover:bg-[#20b859] text-white text-sm font-medium py-2.5 rounded-md transition-colors"
                  data-testid="ticket-whatsapp"
                >
                  <MessageCircle className="w-4 h-4" /> Compartir por WhatsApp
                </a>
              )}
              <Button variant="outline" className="w-full" onClick={() => setTicketDialog(null)}>Cerrar</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
