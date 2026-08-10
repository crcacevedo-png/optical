// Tab de Caja de la Jornada
import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import { Wallet, Plus, Minus, ArrowDownCircle, ArrowUpCircle, Lock, Play, CheckCircle2, AlertTriangle } from 'lucide-react';

const fmtQ = (n) => `Q ${(Number(n) || 0).toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const CATEGORIES = [
  { key: 'transporte', label: 'Transporte' },
  { key: 'alimentacion', label: 'Alimentacion' },
  { key: 'viaticos', label: 'Viaticos' },
  { key: 'alquiler', label: 'Alquiler de local' },
  { key: 'publicidad', label: 'Publicidad' },
  { key: 'colaboradores', label: 'Pago a colaboradores' },
  { key: 'devolucion', label: 'Devolucion a cliente' },
  { key: 'otro', label: 'Otro' },
];

const METHODS = [
  { key: 'cash', label: 'Efectivo' },
  { key: 'card', label: 'Tarjeta' },
  { key: 'transfer', label: 'Transferencia' },
  { key: 'check', label: 'Cheque' },
  { key: 'other', label: 'Otro' },
];

export default function JornadaCashTab({ jornada, reload }) {
  const jid = jornada._id;
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [openDialog, setOpenDialog] = useState(false);
  const [movDialog, setMovDialog] = useState(false);
  const [closeDialog, setCloseDialog] = useState(false);
  const [openForm, setOpenForm] = useState({ opening_amount: 0, notes: '' });
  const [movForm, setMovForm] = useState({ kind: 'egreso', amount: '', method: 'cash', description: '', category: 'transporte' });
  const [closeForm, setCloseForm] = useState({ counted_cash: '', counted_notes: '', transfer_to_branch: true });
  const [processing, setProcessing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/api/jornadas/${jid}/cash`);
      setData(res.data);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, [jid]);
  useEffect(() => { load(); }, [load]);

  const doOpen = async () => {
    setProcessing(true);
    try {
      await api.post(`/api/jornadas/${jid}/cash/open`, {
        opening_amount: parseFloat(openForm.opening_amount) || 0,
        notes: openForm.notes,
      });
      toast.success('Caja abierta');
      setOpenDialog(false);
      setOpenForm({ opening_amount: 0, notes: '' });
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setProcessing(false); }
  };

  const doMovement = async () => {
    if (!movForm.description.trim() || !movForm.amount) {
      toast.error('Descripcion y monto son obligatorios');
      return;
    }
    setProcessing(true);
    try {
      await api.post(`/api/jornadas/${jid}/cash/movements`, {
        kind: movForm.kind,
        amount: parseFloat(movForm.amount),
        method: movForm.method,
        description: movForm.description,
        category: movForm.category,
      });
      toast.success('Movimiento registrado');
      setMovDialog(false);
      setMovForm({ kind: 'egreso', amount: '', method: 'cash', description: '', category: 'transporte' });
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setProcessing(false); }
  };

  const doClose = async () => {
    setProcessing(true);
    try {
      const res = await api.post(`/api/jornadas/${jid}/cash/close`, {
        counted_cash: parseFloat(closeForm.counted_cash) || 0,
        counted_notes: closeForm.counted_notes,
        transfer_to_branch: closeForm.transfer_to_branch,
      });
      toast.success(`Caja cerrada · Neto ${fmtQ(res.data.net_cash)}`);
      if (Math.abs(res.data.diff) > 0.01) toast.warning(`Diferencia: ${fmtQ(res.data.diff)}`);
      setCloseDialog(false);
      setCloseForm({ counted_cash: '', counted_notes: '', transfer_to_branch: true });
      load();
      reload?.();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setProcessing(false); }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-40"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-pine-900" /></div>;
  }

  const usesBranchCash = jornada.cash_config?.mode !== 'own';
  if (usesBranchCash) {
    return (
      <Card className="border-dashed border-slate-300">
        <CardContent className="py-8 text-center">
          <Wallet className="w-10 h-10 text-slate-400 mx-auto mb-2" />
          <p className="text-sm text-slate-600">Esta jornada usa la caja de la sucursal responsable.</p>
          <p className="text-xs text-slate-400 mt-1">Todos los movimientos se registran alli.</p>
        </CardContent>
      </Card>
    );
  }

  const reg = data?.register;
  const totals = data?.totals;

  if (!reg) {
    return (
      <Card className="border-dashed border-slate-300">
        <CardContent className="py-8 text-center">
          <Wallet className="w-10 h-10 text-slate-400 mx-auto mb-2" />
          <p className="text-sm text-slate-600 mb-4">La caja de esta jornada aun no ha sido aperturada.</p>
          <Button onClick={() => setOpenDialog(true)} className="bg-pine-900 hover:bg-pine-800" data-testid="jcash-open-btn" disabled={jornada.status !== 'activa' && jornada.status !== 'planificada'}>
            <Play className="w-4 h-4 mr-2" /> Aperturar caja
          </Button>
        </CardContent>
        <Dialog open={openDialog} onOpenChange={setOpenDialog}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader><DialogTitle>Aperturar caja de jornada</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label>Fondo inicial (Q)</Label>
                <Input type="number" min="0" step="1" value={openForm.opening_amount} onChange={(e) => setOpenForm({ ...openForm, opening_amount: e.target.value })} data-testid="jcash-opening" />
              </div>
              <div className="space-y-1.5">
                <Label>Notas</Label>
                <Textarea rows={2} value={openForm.notes} onChange={(e) => setOpenForm({ ...openForm, notes: e.target.value })} data-testid="jcash-open-notes" />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpenDialog(false)}>Cancelar</Button>
              <Button className="bg-pine-900 hover:bg-pine-800" disabled={processing} onClick={doOpen} data-testid="jcash-open-confirm">
                {processing ? 'Abriendo...' : 'Aperturar'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </Card>
    );
  }

  const isOpen = reg.status === 'open';
  const diff = closeForm.counted_cash === '' ? 0 : parseFloat(closeForm.counted_cash) - (totals?.expected_cash || 0);

  return (
    <div className="space-y-4">
      {/* Estado y KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <MiniKpi label="Estado" value={<Badge className={isOpen ? 'bg-emerald-100 text-emerald-700 border-emerald-200' : 'bg-slate-100 text-slate-700 border-slate-200'}>{isOpen ? 'Abierta' : 'Cerrada'}</Badge>} />
        <MiniKpi label="Fondo inicial" value={fmtQ(totals?.opening_amount)} />
        <MiniKpi label="Efectivo esperado" value={fmtQ(totals?.expected_cash)} highlight />
        <MiniKpi label="Ingresos ventas" value={fmtQ(totals?.sales_total)} sub={`${totals?.sales_count || 0} venta(s)`} />
        <MiniKpi label="Egresos" value={fmtQ(totals?.egresos_total)} />
      </div>

      {/* Desglose por metodo */}
      <Card><CardContent className="pt-5">
        <p className="text-sm font-semibold text-slate-700 mb-3">Por metodo de pago</p>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-sm">
          {METHODS.map(m => (
            <div key={m.key} className="p-2 rounded bg-slate-50">
              <p className="text-[10px] text-slate-500 uppercase">{m.label}</p>
              <p className="font-semibold">{fmtQ(totals?.totals_by_method?.[m.key])}</p>
            </div>
          ))}
        </div>
      </CardContent></Card>

      {/* Acciones */}
      {isOpen && (jornada.status === 'activa' || jornada.status === 'en_cierre') && (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => { setMovForm({ ...movForm, kind: 'ingreso' }); setMovDialog(true); }} data-testid="jcash-add-ingreso"><ArrowDownCircle className="w-4 h-4 mr-1.5" /> Ingreso adicional</Button>
          <Button size="sm" variant="outline" onClick={() => { setMovForm({ ...movForm, kind: 'egreso' }); setMovDialog(true); }} data-testid="jcash-add-egreso"><ArrowUpCircle className="w-4 h-4 mr-1.5" /> Registrar egreso</Button>
          <Button size="sm" className="bg-amber-600 hover:bg-amber-700 ml-auto" onClick={() => setCloseDialog(true)} data-testid="jcash-close-btn"><Lock className="w-4 h-4 mr-1.5" /> Arqueo y cierre</Button>
        </div>
      )}

      {/* Egresos por categoria */}
      {totals?.egresos_total > 0 && (
        <Card><CardContent className="pt-5">
          <p className="text-sm font-semibold text-slate-700 mb-3">Egresos por categoria</p>
          <div className="space-y-1.5 text-sm">
            {Object.entries(totals.egresos_by_category || {}).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between p-2 rounded hover:bg-slate-50">
                <span className="text-slate-700">{CATEGORIES.find(c => c.key === k)?.label || k}</span>
                <span className="font-semibold">{fmtQ(v)}</span>
              </div>
            ))}
          </div>
        </CardContent></Card>
      )}

      {/* Historial de movimientos */}
      <Card><CardContent className="pt-5">
        <p className="text-sm font-semibold text-slate-700 mb-3">Movimientos ({reg.movements?.length || 0})</p>
        {(!reg.movements || reg.movements.length === 0) ? (
          <p className="text-xs text-slate-400 italic text-center py-3">Sin movimientos manuales</p>
        ) : (
          <div className="divide-y divide-slate-100 max-h-72 overflow-y-auto">
            {reg.movements.slice().reverse().map((m) => (
              <div key={m.id} className="flex items-center gap-3 py-2 text-sm">
                {m.kind === 'ingreso' ? <ArrowDownCircle className="w-4 h-4 text-emerald-500 flex-shrink-0" /> : <ArrowUpCircle className="w-4 h-4 text-rose-500 flex-shrink-0" />}
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-slate-800 truncate">{m.description}</p>
                  <p className="text-xs text-slate-400">{m.category || '—'} · {m.method} · {new Date(m.created_at).toLocaleString('es-GT')}</p>
                </div>
                <p className={`font-semibold ${m.kind === 'ingreso' ? 'text-emerald-700' : 'text-rose-700'}`}>{m.kind === 'egreso' ? '-' : '+'}{fmtQ(m.amount)}</p>
              </div>
            ))}
          </div>
        )}
      </CardContent></Card>

      {/* Cierre info si aplica */}
      {!isOpen && reg.close_totals && (
        <Card className="border-blue-200 bg-blue-50/50">
          <CardContent className="pt-5">
            <p className="text-sm font-semibold text-blue-800 mb-3 flex items-center gap-2"><CheckCircle2 className="w-4 h-4" /> Caja cerrada</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div><p className="text-xs text-slate-500">Efectivo contado</p><p className="font-semibold">{fmtQ(reg.counted_cash)}</p></div>
              <div><p className="text-xs text-slate-500">Diferencia</p><p className={`font-semibold ${Math.abs(reg.diff || 0) > 0.01 ? 'text-rose-600' : 'text-emerald-600'}`}>{fmtQ(reg.diff)}</p></div>
              <div><p className="text-xs text-slate-500">Cerrado por</p><p className="font-semibold">{reg.closed_by_name}</p></div>
              <div><p className="text-xs text-slate-500">Fecha</p><p className="font-semibold">{new Date(reg.closed_at).toLocaleString('es-GT')}</p></div>
            </div>
            {reg.counted_notes && <p className="text-xs text-slate-600 mt-2 italic">{reg.counted_notes}</p>}
          </CardContent>
        </Card>
      )}

      {/* Movement dialog */}
      <Dialog open={movDialog} onOpenChange={setMovDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle>{movForm.kind === 'ingreso' ? 'Ingreso adicional' : 'Registrar egreso'}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <Label>Monto (Q) *</Label>
                <Input type="number" min="0" step="0.01" value={movForm.amount} onChange={(e) => setMovForm({ ...movForm, amount: e.target.value })} data-testid="jcash-mov-amount" />
              </div>
              <div className="space-y-1.5">
                <Label>Metodo</Label>
                <Select value={movForm.method} onValueChange={(v) => setMovForm({ ...movForm, method: v })}>
                  <SelectTrigger data-testid="jcash-mov-method"><SelectValue /></SelectTrigger>
                  <SelectContent>{METHODS.map(m => <SelectItem key={m.key} value={m.key}>{m.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            {movForm.kind === 'egreso' && (
              <div className="space-y-1.5">
                <Label>Categoria</Label>
                <Select value={movForm.category} onValueChange={(v) => setMovForm({ ...movForm, category: v })}>
                  <SelectTrigger data-testid="jcash-mov-category"><SelectValue /></SelectTrigger>
                  <SelectContent>{CATEGORIES.map(c => <SelectItem key={c.key} value={c.key}>{c.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            )}
            <div className="space-y-1.5">
              <Label>Descripcion *</Label>
              <Input value={movForm.description} onChange={(e) => setMovForm({ ...movForm, description: e.target.value })} placeholder="Detalle del movimiento" data-testid="jcash-mov-desc" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMovDialog(false)}>Cancelar</Button>
            <Button className={movForm.kind === 'ingreso' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-rose-600 hover:bg-rose-700'} disabled={processing} onClick={doMovement} data-testid="jcash-mov-confirm">
              {processing ? 'Guardando...' : 'Registrar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Close dialog */}
      <Dialog open={closeDialog} onOpenChange={setCloseDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Arqueo y cierre de caja</DialogTitle>
            <DialogDescription>Ingresa el efectivo contado fisicamente para conciliar contra el saldo esperado.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="p-3 bg-slate-50 rounded-lg text-sm space-y-1">
              <div className="flex justify-between"><span className="text-slate-500">Fondo inicial</span><span>{fmtQ(totals?.opening_amount)}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">+ Ventas efectivo</span><span>{fmtQ(totals?.totals_by_method?.cash)}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">− Egresos</span><span>-{fmtQ(totals?.egresos_total)}</span></div>
              <div className="flex justify-between font-semibold pt-1 border-t border-slate-200"><span>Efectivo esperado</span><span>{fmtQ(totals?.expected_cash)}</span></div>
            </div>
            <div className="space-y-1.5">
              <Label>Efectivo contado (Q) *</Label>
              <Input type="number" step="0.01" value={closeForm.counted_cash} onChange={(e) => setCloseForm({ ...closeForm, counted_cash: e.target.value })} data-testid="jcash-close-counted" />
            </div>
            {Math.abs(diff) > 0.01 && closeForm.counted_cash !== '' && (
              <div className={`p-2 rounded-md text-sm flex items-center gap-2 ${diff < 0 ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-700'}`}>
                <AlertTriangle className="w-4 h-4" />
                Diferencia: {fmtQ(diff)} ({diff > 0 ? 'sobrante' : 'faltante'}) — motivo obligatorio
              </div>
            )}
            {Math.abs(diff) > 0.01 && (
              <div className="space-y-1.5">
                <Label>Motivo *</Label>
                <Textarea rows={2} value={closeForm.counted_notes} onChange={(e) => setCloseForm({ ...closeForm, counted_notes: e.target.value })} data-testid="jcash-close-notes" />
              </div>
            )}
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={closeForm.transfer_to_branch} onChange={(e) => setCloseForm({ ...closeForm, transfer_to_branch: e.target.checked })} data-testid="jcash-transfer" />
              Trasladar efectivo neto a la caja de la sucursal responsable
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCloseDialog(false)}>Cancelar</Button>
            <Button className="bg-amber-600 hover:bg-amber-700" disabled={processing || closeForm.counted_cash === '' || (Math.abs(diff) > 0.01 && !closeForm.counted_notes.trim())} onClick={doClose} data-testid="jcash-close-confirm">
              {processing ? 'Cerrando...' : 'Cerrar caja'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function MiniKpi({ label, value, sub, highlight }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? 'border-pine-300 bg-pine-50' : 'border-slate-200 bg-white'}`}>
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <div className={`font-heading text-lg font-bold ${highlight ? 'text-pine-900' : 'text-slate-900'} leading-tight mt-0.5`}>{value}</div>
      {sub && <p className="text-[10px] text-slate-400 mt-0.5">{sub}</p>}
    </div>
  );
}
