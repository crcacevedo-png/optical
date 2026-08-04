/**
 * Barra de estado de caja para el modulo Ventas.
 * Muestra si hay caja abierta y permite abrir/cerrar sin salir de /sales.
 * Ademas expone un detalle en vivo del cierre (por medio de pago) y el historial.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import {
  Landmark, LockOpen, Lock, Banknote, CreditCard, Smartphone, HandCoins,
  FileText, Eye, ClipboardList, TrendingUp, CheckCircle2, AlertTriangle, RefreshCw
} from 'lucide-react';
import { toast } from 'sonner';

const fmt = (n) => `Q ${(Number(n) || 0).toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const METHOD_META = {
  cash: { label: 'Efectivo', icon: Banknote, color: 'emerald' },
  card: { label: 'Tarjeta de credito', icon: CreditCard, color: 'blue' },
  transfer: { label: 'Transferencia', icon: Smartphone, color: 'violet' },
  check: { label: 'Cheque', icon: FileText, color: 'amber' },
  other: { label: 'Otro', icon: HandCoins, color: 'slate' },
};

function MethodTile({ method, amount }) {
  const meta = METHOD_META[method] || METHOD_META.other;
  const Icon = meta.icon;
  const bg = {
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    violet: 'bg-violet-50 text-violet-700 border-violet-200',
    amber: 'bg-amber-50 text-amber-800 border-amber-200',
    slate: 'bg-slate-50 text-slate-700 border-slate-200',
  }[meta.color];
  return (
    <div className={`border rounded-xl p-3 ${bg}`} data-testid={`sales-tile-${method}`}>
      <div className="flex items-center gap-1.5 mb-1">
        <Icon className="w-3.5 h-3.5" />
        <span className="text-[10px] font-bold uppercase tracking-wider">{meta.label}</span>
      </div>
      <p className="font-heading text-lg font-bold">{fmt(amount)}</p>
    </div>
  );
}

function RegisterDetailBody({ detail, live = false }) {
  if (!detail) return null;
  const methods = detail.totals_by_method || {};
  // Ensure the 4 key methods always appear
  const orderedKeys = ['cash', 'transfer', 'card', 'check', 'other'];
  const present = orderedKeys.filter((k) => k in methods || k !== 'other');
  return (
    <div className="space-y-5">
      {/* Meta */}
      <div className="grid grid-cols-2 gap-3 text-sm bg-slate-50 p-3 rounded-lg border border-slate-100">
        <div>
          <span className="text-slate-500">Abierta:</span>{' '}
          <strong>{(detail.opened_at || '').slice(0, 16).replace('T', ' ')}</strong>
          {detail.opened_by_name ? <> por {detail.opened_by_name}</> : null}
        </div>
        <div>
          <span className="text-slate-500">{live ? 'Estado:' : 'Cerrada:'}</span>{' '}
          {live ? <span className="text-emerald-700 font-medium">En curso</span> : (
            detail.closed_at
              ? <><strong>{(detail.closed_at || '').slice(0, 16).replace('T', ' ')}</strong>{detail.closed_by_name ? <> por {detail.closed_by_name}</> : null}</>
              : <span className="text-slate-500">-</span>
          )}
        </div>
        <div><span className="text-slate-500">Fondo inicial:</span> <strong>{fmt(detail.opening_amount)}</strong></div>
        <div>
          <span className="text-slate-500">Total {live ? 'recaudado (hasta ahora)' : 'recaudado'}:</span>{' '}
          <strong className="text-emerald-700">{fmt(detail.total_received)}</strong>
        </div>
        {detail.expected_cash != null && (
          <div><span className="text-slate-500">Efectivo esperado:</span> <strong>{fmt(detail.expected_cash)}</strong></div>
        )}
        {detail.counted_cash != null && (
          <div>
            <span className="text-slate-500">Diferencia:</span>{' '}
            <strong className={detail.cash_difference === 0 ? 'text-emerald-600' : detail.cash_difference > 0 ? 'text-blue-600' : 'text-red-600'}>
              {detail.cash_difference > 0 ? '+' : ''}{fmt(detail.cash_difference)}
            </strong>
            {detail.cash_difference === 0 && <CheckCircle2 className="inline w-4 h-4 text-emerald-600 ml-1" />}
            {detail.cash_difference < 0 && <AlertTriangle className="inline w-4 h-4 text-red-600 ml-1" />}
          </div>
        )}
      </div>

      {/* Totals by method - the required breakdown */}
      <div>
        <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
          {live ? 'Ingresos por metodo de pago (turno en curso)' : 'Ingresos por metodo de pago'}
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {present.map((m) => (
            <MethodTile key={m} method={m} amount={methods[m] || 0} />
          ))}
        </div>
      </div>

      {/* Receivables */}
      {detail.sales_in_window && detail.sales_in_window.filter((s) => (s.balance || 0) > 0).length > 0 && (
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
            <TrendingUp className="inline w-3.5 h-3.5 mr-1" />
            Cuentas por cobrar generadas ({detail.receivables_count} · {fmt(detail.receivables_total)})
          </p>
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-amber-50 text-xs text-amber-800">
                  <th className="text-left p-2.5 font-semibold">Cliente</th>
                  <th className="text-right p-2.5 font-semibold">Total</th>
                  <th className="text-right p-2.5 font-semibold">Pagado</th>
                  <th className="text-right p-2.5 font-semibold">Saldo</th>
                </tr>
              </thead>
              <tbody>
                {detail.sales_in_window.filter((s) => (s.balance || 0) > 0).map((s) => (
                  <tr key={s.sale_id} className="border-t border-slate-100">
                    <td className="p-2.5">{s.patient_name || 'Consumidor final'}</td>
                    <td className="p-2.5 text-right">{fmt(s.total)}</td>
                    <td className="p-2.5 text-right text-slate-500">{fmt(s.amount_paid)}</td>
                    <td className="p-2.5 text-right font-bold text-amber-700">{fmt(s.balance)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Payments detail */}
      {detail.payments_detail && detail.payments_detail.length > 0 && (
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
            Todos los pagos ({detail.payments_count})
          </p>
          <div className="border rounded-lg overflow-hidden max-h-72 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50">
                <tr className="text-slate-500">
                  <th className="text-left p-2 font-semibold">Hora</th>
                  <th className="text-left p-2 font-semibold">Metodo</th>
                  <th className="text-right p-2 font-semibold">Monto</th>
                  <th className="text-left p-2 font-semibold">Referencia</th>
                </tr>
              </thead>
              <tbody>
                {detail.payments_detail.map((p, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="p-2">{(p.created_at || '').slice(11, 16)}</td>
                    <td className="p-2">{METHOD_META[p.method]?.label || p.method}</td>
                    <td className="p-2 text-right font-medium">{fmt(p.amount)}</td>
                    <td className="p-2 text-slate-500">{p.note || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {detail.closing_notes && (
        <div className="text-sm">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500 mb-1">Notas de cierre</p>
          <p className="text-slate-700 bg-slate-50 border border-slate-100 rounded-lg p-3">{detail.closing_notes}</p>
        </div>
      )}
    </div>
  );
}

export function SalesCashBar({ onCashChange, onStateChange }) {
  const [loading, setLoading] = useState(true);
  const [current, setCurrent] = useState(null);
  const [showOpen, setShowOpen] = useState(false);
  const [showClose, setShowClose] = useState(false);
  const [showLive, setShowLive] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [livePreview, setLivePreview] = useState(null);
  const [history, setHistory] = useState([]);
  const [detail, setDetail] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [openAmount, setOpenAmount] = useState('');
  const [openNotes, setOpenNotes] = useState('');
  const [countedCash, setCountedCash] = useState('');
  const [closeNotes, setCloseNotes] = useState('');

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await api.get('/api/cash-register/current');
      const reg = data?.register || null;
      setCurrent(reg);
      onStateChange?.(!!reg, reg);
    } catch {
      setCurrent(null);
      onStateChange?.(false, null);
    } finally {
      setLoading(false);
    }
  }, [onStateChange]);

  useEffect(() => { load(); }, [load]);

  const handleOpen = async () => {
    try {
      setSubmitting(true);
      await api.post('/api/cash-register/open', {
        opening_amount: parseFloat(openAmount) || 0,
        opening_notes: openNotes || '',
      });
      toast.success('Caja abierta');
      setShowOpen(false);
      setOpenAmount(''); setOpenNotes('');
      load();
      onCashChange?.();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setSubmitting(false); }
  };

  const handleClose = async () => {
    try {
      setSubmitting(true);
      const { data } = await api.post('/api/cash-register/close', {
        counted_cash: countedCash === '' ? null : parseFloat(countedCash),
        closing_notes: closeNotes || '',
      });
      toast.success(`Caja cerrada. Total recaudado ${fmt(data.register.total_received)}.`, { duration: 5000 });
      setShowClose(false);
      setCountedCash(''); setCloseNotes('');
      // Show detail modal automatically after close
      setDetail(data.register);
      load();
      onCashChange?.();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setSubmitting(false); }
  };

  const openLive = async () => {
    try {
      const { data } = await api.get('/api/cash-register/current/preview');
      setLivePreview(data);
      setShowLive(true);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const openHistory = async () => {
    try {
      const { data } = await api.get('/api/cash-register');
      setHistory(data || []);
      setShowHistory(true);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const openDetailById = async (id) => {
    try {
      const { data } = await api.get(`/api/cash-register/${id}`);
      setDetail(data);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  if (loading) return null;

  const isOpen = !!current;

  return (
    <>
      <Card
        className={`border-2 ${isOpen ? 'border-emerald-300 bg-emerald-50/40' : 'border-amber-300 bg-amber-50/40'}`}
        data-testid="sales-cash-bar"
      >
        <CardContent className="p-3 sm:p-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${isOpen ? 'bg-emerald-500' : 'bg-amber-500'}`}>
                <Landmark className="w-5 h-5 text-white" />
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Caja</p>
                <p className="font-heading text-base font-semibold text-slate-900 leading-tight">
                  {isOpen ? 'Abierta' : 'Cerrada'}
                </p>
                {isOpen && (
                  <p className="text-xs text-slate-500 mt-0.5">
                    Fondo {fmt(current.opening_amount)} · Abierta por {current.opened_by_name} el {(current.opened_at || '').slice(0, 16).replace('T', ' ')}
                  </p>
                )}
                {!isOpen && (
                  <p className="text-xs text-slate-500 mt-0.5">Abre la caja para empezar a registrar ventas del dia.</p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {isOpen && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={openLive}
                  data-testid="sales-view-live-btn"
                >
                  <Eye className="w-4 h-4 mr-1.5" /> Ver cierre en vivo
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={openHistory}
                data-testid="sales-view-history-btn"
              >
                <ClipboardList className="w-4 h-4 mr-1.5" /> Historial
              </Button>
              {isOpen ? (
                <Button
                  className="bg-red-600 hover:bg-red-700"
                  size="sm"
                  onClick={() => setShowClose(true)}
                  data-testid="sales-close-cash-btn"
                >
                  <Lock className="w-4 h-4 mr-1.5" /> Cerrar caja
                </Button>
              ) : (
                <Button
                  className="bg-emerald-600 hover:bg-emerald-700"
                  size="sm"
                  onClick={() => setShowOpen(true)}
                  data-testid="sales-open-cash-btn"
                >
                  <LockOpen className="w-4 h-4 mr-1.5" /> Abrir caja
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Open Dialog */}
      <Dialog open={showOpen} onOpenChange={setShowOpen}>
        <DialogContent className="sm:max-w-md" data-testid="sales-open-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading flex items-center gap-2">
              <LockOpen className="w-5 h-5 text-emerald-600" /> Abrir caja
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Fondo inicial (efectivo)</Label>
              <Input type="number" step="0.01" min="0" value={openAmount}
                onChange={(e) => setOpenAmount(e.target.value)} placeholder="0.00" autoFocus
                data-testid="sales-opening-amount" />
              <p className="text-xs text-slate-500 mt-1">Dinero fisico con el que inicia la caja del dia.</p>
            </div>
            <div>
              <Label>Notas (opcional)</Label>
              <Textarea rows={2} value={openNotes} onChange={(e) => setOpenNotes(e.target.value)}
                placeholder="Ej. Cambio de billetes de Q100" />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setShowOpen(false)}>Cancelar</Button>
              <Button className="bg-emerald-600 hover:bg-emerald-700" onClick={handleOpen}
                disabled={submitting} data-testid="sales-open-submit">
                {submitting ? 'Abriendo...' : 'Abrir caja'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Close Dialog */}
      <Dialog open={showClose} onOpenChange={setShowClose}>
        <DialogContent className="sm:max-w-md" data-testid="sales-close-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading flex items-center gap-2">
              <Lock className="w-5 h-5 text-red-600" /> Cerrar caja
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-slate-600">
              Al cerrar la caja se calcularan los totales por medio de pago recibidos durante el turno,
              y se listaran las cuentas por cobrar creadas.
            </p>
            <div>
              <Label>Efectivo contado al cierre (opcional)</Label>
              <Input type="number" step="0.01" min="0" value={countedCash}
                onChange={(e) => setCountedCash(e.target.value)} placeholder="0.00"
                data-testid="sales-counted-cash" />
              <p className="text-xs text-slate-500 mt-1">Si lo llenas, se calcula la diferencia con el efectivo esperado.</p>
            </div>
            <div>
              <Label>Notas de cierre</Label>
              <Textarea rows={2} value={closeNotes} onChange={(e) => setCloseNotes(e.target.value)}
                placeholder="Observaciones o incidencias" />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setShowClose(false)}>Cancelar</Button>
              <Button className="bg-red-600 hover:bg-red-700" onClick={handleClose}
                disabled={submitting} data-testid="sales-close-submit">
                {submitting ? 'Cerrando...' : 'Cerrar caja'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Live preview Dialog (caja abierta) */}
      <Dialog open={showLive} onOpenChange={(o) => { if (!o) setLivePreview(null); setShowLive(o); }}>
        <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="sales-live-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading flex items-center gap-2">
              <Eye className="w-5 h-5 text-emerald-600" /> Cierre en vivo
              <Button variant="ghost" size="sm" className="ml-auto mr-2" onClick={openLive} data-testid="sales-live-refresh">
                <RefreshCw className="w-4 h-4" />
              </Button>
            </DialogTitle>
          </DialogHeader>
          <RegisterDetailBody detail={livePreview} live />
        </DialogContent>
      </Dialog>

      {/* History Dialog */}
      <Dialog open={showHistory} onOpenChange={setShowHistory}>
        <DialogContent className="sm:max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="sales-history-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading flex items-center gap-2">
              <ClipboardList className="w-5 h-5 text-slate-600" /> Historial de cajas
            </DialogTitle>
          </DialogHeader>
          {history.length === 0 ? (
            <div className="text-center py-8 text-slate-500">
              <Landmark className="w-12 h-12 mx-auto mb-2 opacity-30" />
              <p>Sin registros aun</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="data-table-header">
                    <TableHead>Apertura</TableHead>
                    <TableHead>Cierre</TableHead>
                    <TableHead>Abierta por</TableHead>
                    <TableHead className="text-right">Fondo</TableHead>
                    <TableHead className="text-right">Recaudado</TableHead>
                    <TableHead className="text-center">Estado</TableHead>
                    <TableHead className="text-right">Ver</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((r) => (
                    <TableRow key={r._id} data-testid={`sales-cash-row-${r._id}`}>
                      <TableCell className="text-xs">{(r.opened_at || '').slice(0, 16).replace('T', ' ')}</TableCell>
                      <TableCell className="text-xs">{r.closed_at ? (r.closed_at || '').slice(0, 16).replace('T', ' ') : '-'}</TableCell>
                      <TableCell className="text-sm">{r.opened_by_name}</TableCell>
                      <TableCell className="text-right text-sm">{fmt(r.opening_amount)}</TableCell>
                      <TableCell className="text-right font-medium">{r.total_received != null ? fmt(r.total_received) : '-'}</TableCell>
                      <TableCell className="text-center">
                        <Badge className={r.status === 'open' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-700'}>
                          {r.status === 'open' ? 'Abierta' : 'Cerrada'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button size="sm" variant="ghost" onClick={() => openDetailById(r._id)} data-testid={`sales-cash-view-${r._id}`}>
                          <Eye className="w-4 h-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Detail (post-close & from history) */}
      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="sales-detail-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading flex items-center gap-2">
              <Landmark className="w-5 h-5 text-emerald-600" /> Detalle de caja
            </DialogTitle>
          </DialogHeader>
          <RegisterDetailBody detail={detail} />
        </DialogContent>
      </Dialog>
    </>
  );
}
