import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import {
  Landmark, LockOpen, Lock, DollarSign, CreditCard, Smartphone, HandCoins,
  Banknote, ClipboardList, TrendingUp, AlertTriangle, CheckCircle2, RefreshCw
} from 'lucide-react';
import { toast } from 'sonner';

const fmt = (n) =>
  `Q ${(Number(n) || 0).toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const METHOD_META = {
  cash: { label: 'Efectivo', icon: Banknote, color: 'emerald' },
  card: { label: 'Tarjeta', icon: CreditCard, color: 'blue' },
  transfer: { label: 'Transferencia', icon: Smartphone, color: 'violet' },
  other: { label: 'Otro', icon: HandCoins, color: 'slate' },
};

function MethodTile({ method, amount, testId }) {
  const meta = METHOD_META[method] || METHOD_META.other;
  const Icon = meta.icon;
  const bg = {
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    violet: 'bg-violet-50 text-violet-700 border-violet-200',
    slate: 'bg-slate-50 text-slate-700 border-slate-200',
  }[meta.color];
  return (
    <div className={`border rounded-xl p-4 ${bg}`} data-testid={testId}>
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-4 h-4" />
        <span className="text-xs font-bold uppercase tracking-wider">{meta.label}</span>
      </div>
      <p className="font-heading text-2xl font-bold">{fmt(amount)}</p>
    </div>
  );
}

export default function CashRegisterPage() {
  const [loading, setLoading] = useState(true);
  const [current, setCurrent] = useState(null);
  const [history, setHistory] = useState([]);
  const [detail, setDetail] = useState(null);

  // Dialogs
  const [showOpen, setShowOpen] = useState(false);
  const [showClose, setShowClose] = useState(false);
  const [openForm, setOpenForm] = useState({ opening_amount: '', opening_notes: '' });
  const [closeForm, setCloseForm] = useState({ counted_cash: '', closing_notes: '' });
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [curRes, histRes] = await Promise.all([
        api.get('/api/cash-register/current'),
        api.get('/api/cash-register'),
      ]);
      setCurrent(curRes.data?.register || null);
      setHistory(histRes.data || []);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleOpen = async () => {
    try {
      setSubmitting(true);
      await api.post('/api/cash-register/open', {
        opening_amount: parseFloat(openForm.opening_amount) || 0,
        opening_notes: openForm.opening_notes || '',
      });
      toast.success('Caja abierta');
      setShowOpen(false);
      setOpenForm({ opening_amount: '', opening_notes: '' });
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = async () => {
    try {
      setSubmitting(true);
      const { data } = await api.post('/api/cash-register/close', {
        counted_cash: closeForm.counted_cash === '' ? null : parseFloat(closeForm.counted_cash),
        closing_notes: closeForm.closing_notes || '',
      });
      toast.success('Caja cerrada');
      setShowClose(false);
      setCloseForm({ counted_cash: '', closing_notes: '' });
      setDetail(data.register);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="cash-loading">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
      </div>
    );
  }

  const isOpen = !!current;

  return (
    <div className="space-y-6" data-testid="cash-register-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
              <Landmark className="w-5 h-5 text-white" />
            </div>
            <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Caja</h1>
          </div>
          <p className="text-slate-500 text-sm">
            Gestion diaria de apertura y cierre por sucursal.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} data-testid="cash-refresh">
          <RefreshCw className="w-4 h-4 mr-1.5" /> Refrescar
        </Button>
      </div>

      {/* Current status card */}
      <Card
        className={`border-2 ${isOpen ? 'border-emerald-300 bg-emerald-50/30' : 'border-slate-200 bg-slate-50/30'}`}
        data-testid="cash-current-status"
      >
        <CardContent className="p-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className={`w-14 h-14 rounded-2xl flex items-center justify-center ${isOpen ? 'bg-emerald-500' : 'bg-slate-400'}`}>
                {isOpen ? <LockOpen className="w-7 h-7 text-white" /> : <Lock className="w-7 h-7 text-white" />}
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Estado</p>
                <p className="font-heading text-xl font-bold text-slate-900">
                  {isOpen ? 'Caja abierta' : 'Caja cerrada'}
                </p>
                {isOpen && (
                  <p className="text-xs text-slate-500 mt-0.5">
                    Abierta por <strong>{current.opened_by_name}</strong> el {(current.opened_at || '').slice(0, 16).replace('T', ' ')}
                  </p>
                )}
              </div>
            </div>
            {isOpen ? (
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <p className="text-xs text-slate-500 uppercase tracking-wide">Fondo inicial</p>
                  <p className="font-heading text-xl font-bold text-slate-900">{fmt(current.opening_amount)}</p>
                </div>
                <Button
                  className="bg-red-600 hover:bg-red-700"
                  onClick={() => setShowClose(true)}
                  data-testid="close-cash-btn"
                >
                  <Lock className="w-4 h-4 mr-2" /> Cerrar caja
                </Button>
              </div>
            ) : (
              <Button
                className="bg-emerald-600 hover:bg-emerald-700"
                onClick={() => setShowOpen(true)}
                data-testid="open-cash-btn"
              >
                <LockOpen className="w-4 h-4 mr-2" /> Abrir caja
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* History */}
      <Card className="border-slate-200/80">
        <CardHeader>
          <CardTitle className="font-heading text-lg flex items-center gap-2">
            <ClipboardList className="w-5 h-5 text-slate-600" /> Historial de cierres
          </CardTitle>
        </CardHeader>
        <CardContent>
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
                    <TableHead>Sucursal</TableHead>
                    <TableHead>Abierta por</TableHead>
                    <TableHead className="text-right">Fondo</TableHead>
                    <TableHead className="text-right">Recaudado</TableHead>
                    <TableHead className="text-right">Cuentas x cobrar</TableHead>
                    <TableHead className="text-center">Estado</TableHead>
                    <TableHead className="text-right">Ver</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((r) => (
                    <TableRow key={r._id} data-testid={`cash-row-${r._id}`}>
                      <TableCell className="text-xs">{(r.opened_at || '').slice(0, 16).replace('T', ' ')}</TableCell>
                      <TableCell className="text-xs">{r.closed_at ? (r.closed_at || '').slice(0, 16).replace('T', ' ') : '-'}</TableCell>
                      <TableCell className="text-sm">{r.branch_name || '-'}</TableCell>
                      <TableCell className="text-sm">{r.opened_by_name}</TableCell>
                      <TableCell className="text-right text-sm">{fmt(r.opening_amount)}</TableCell>
                      <TableCell className="text-right font-medium">{r.total_received != null ? fmt(r.total_received) : '-'}</TableCell>
                      <TableCell className="text-right text-sm text-amber-700">
                        {r.receivables_total != null ? `${fmt(r.receivables_total)} (${r.receivables_count || 0})` : '-'}
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge className={r.status === 'open' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-700'}>
                          {r.status === 'open' ? 'Abierta' : 'Cerrada'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button size="sm" variant="ghost" onClick={async () => {
                          const { data } = await api.get(`/api/cash-register/${r._id}`);
                          setDetail(data);
                        }} data-testid={`cash-view-${r._id}`}>Ver</Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Open Dialog */}
      <Dialog open={showOpen} onOpenChange={setShowOpen}>
        <DialogContent className="sm:max-w-md" data-testid="open-cash-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading flex items-center gap-2">
              <LockOpen className="w-5 h-5 text-emerald-600" /> Abrir caja
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Fondo inicial (efectivo)</Label>
              <Input
                type="number" step="0.01" min="0"
                value={openForm.opening_amount}
                onChange={(e) => setOpenForm({ ...openForm, opening_amount: e.target.value })}
                placeholder="0.00"
                autoFocus
                data-testid="opening-amount"
              />
              <p className="text-xs text-slate-500 mt-1">Dinero fisico con el que inicia la caja del dia.</p>
            </div>
            <div>
              <Label>Notas (opcional)</Label>
              <Textarea
                rows={2}
                value={openForm.opening_notes}
                onChange={(e) => setOpenForm({ ...openForm, opening_notes: e.target.value })}
                placeholder="Ej. Cambio de billetes de Q100"
                data-testid="opening-notes"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setShowOpen(false)}>Cancelar</Button>
              <Button
                className="bg-emerald-600 hover:bg-emerald-700"
                onClick={handleOpen}
                disabled={submitting}
                data-testid="open-cash-submit"
              >
                {submitting ? 'Abriendo...' : 'Abrir caja'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Close Dialog */}
      <Dialog open={showClose} onOpenChange={setShowClose}>
        <DialogContent className="sm:max-w-md" data-testid="close-cash-dialog">
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
              <Input
                type="number" step="0.01" min="0"
                value={closeForm.counted_cash}
                onChange={(e) => setCloseForm({ ...closeForm, counted_cash: e.target.value })}
                placeholder="0.00"
                data-testid="counted-cash"
              />
              <p className="text-xs text-slate-500 mt-1">Si lo llenas, se calcula la diferencia con el efectivo esperado.</p>
            </div>
            <div>
              <Label>Notas de cierre</Label>
              <Textarea
                rows={2}
                value={closeForm.closing_notes}
                onChange={(e) => setCloseForm({ ...closeForm, closing_notes: e.target.value })}
                placeholder="Observaciones o incidencias"
                data-testid="closing-notes"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setShowClose(false)}>Cancelar</Button>
              <Button
                className="bg-red-600 hover:bg-red-700"
                onClick={handleClose}
                disabled={submitting}
                data-testid="close-cash-submit"
              >
                {submitting ? 'Cerrando...' : 'Cerrar caja'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Detail Dialog */}
      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="cash-detail-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading flex items-center gap-2">
              <Landmark className="w-5 h-5 text-emerald-600" /> Detalle de caja
            </DialogTitle>
          </DialogHeader>
          {detail && (
            <div className="space-y-5">
              {/* Meta */}
              <div className="grid grid-cols-2 gap-3 text-sm bg-slate-50 p-4 rounded-lg border border-slate-100">
                <div><span className="text-slate-500">Abierta:</span> <strong>{(detail.opened_at || '').slice(0, 16).replace('T', ' ')}</strong> por {detail.opened_by_name}</div>
                <div>
                  <span className="text-slate-500">Cerrada:</span>{' '}
                  {detail.closed_at ? <><strong>{(detail.closed_at || '').slice(0, 16).replace('T', ' ')}</strong> por {detail.closed_by_name}</> : <span className="text-emerald-700 font-medium">En curso</span>}
                </div>
                <div><span className="text-slate-500">Fondo inicial:</span> <strong>{fmt(detail.opening_amount)}</strong></div>
                <div><span className="text-slate-500">Total recaudado:</span> <strong className="text-emerald-700">{fmt(detail.total_received)}</strong></div>
                {detail.counted_cash != null && (
                  <>
                    <div><span className="text-slate-500">Efectivo esperado:</span> <strong>{fmt(detail.expected_cash)}</strong></div>
                    <div>
                      <span className="text-slate-500">Diferencia:</span>{' '}
                      <strong className={detail.cash_difference === 0 ? 'text-emerald-600' : detail.cash_difference > 0 ? 'text-blue-600' : 'text-red-600'}>
                        {detail.cash_difference > 0 ? '+' : ''}{fmt(detail.cash_difference)}
                      </strong>
                      {detail.cash_difference === 0 && <CheckCircle2 className="inline w-4 h-4 text-emerald-600 ml-1" />}
                      {detail.cash_difference < 0 && <AlertTriangle className="inline w-4 h-4 text-red-600 ml-1" />}
                    </div>
                  </>
                )}
              </div>

              {/* Totals by method */}
              {detail.totals_by_method && (
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Recaudado por medio de pago</p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {Object.entries(detail.totals_by_method).map(([m, amt]) => (
                      <MethodTile key={m} method={m} amount={amt} testId={`tile-${m}`} />
                    ))}
                  </div>
                </div>
              )}

              {/* Receivables in window */}
              {detail.sales_in_window && detail.sales_in_window.filter(s => (s.balance || 0) > 0).length > 0 && (
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
                        {detail.sales_in_window.filter(s => (s.balance || 0) > 0).map((s) => (
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

              {/* Payments detail (compact) */}
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
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
