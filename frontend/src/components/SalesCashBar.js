/**
 * Barra de estado de caja para el modulo Ventas.
 * Muestra si hay caja abierta y permite abrir/cerrar sin salir de /sales.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Landmark, LockOpen, Lock } from 'lucide-react';
import { toast } from 'sonner';

const fmt = (n) => `Q ${(Number(n) || 0).toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export function SalesCashBar({ onCashChange }) {
  const [loading, setLoading] = useState(true);
  const [current, setCurrent] = useState(null);
  const [showOpen, setShowOpen] = useState(false);
  const [showClose, setShowClose] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [openAmount, setOpenAmount] = useState('');
  const [openNotes, setOpenNotes] = useState('');
  const [countedCash, setCountedCash] = useState('');
  const [closeNotes, setCloseNotes] = useState('');

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await api.get('/api/cash-register/current');
      setCurrent(data?.register || null);
    } catch {
      setCurrent(null);
    } finally {
      setLoading(false);
    }
  }, []);

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
      const r = data.register;
      const diffTxt = r.cash_difference != null
        ? ` Diferencia efectivo: ${r.cash_difference >= 0 ? '+' : ''}${fmt(r.cash_difference)}.`
        : '';
      toast.success(`Caja cerrada. Recaudado ${fmt(r.total_received)}.${diffTxt}`, { duration: 6000 });
      setShowClose(false);
      setCountedCash(''); setCloseNotes('');
      load();
      onCashChange?.();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setSubmitting(false); }
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
            <div>
              {isOpen ? (
                <Button
                  className="bg-red-600 hover:bg-red-700"
                  onClick={() => setShowClose(true)}
                  data-testid="sales-close-cash-btn"
                >
                  <Lock className="w-4 h-4 mr-2" /> Cerrar caja
                </Button>
              ) : (
                <Button
                  className="bg-emerald-600 hover:bg-emerald-700"
                  onClick={() => setShowOpen(true)}
                  data-testid="sales-open-cash-btn"
                >
                  <LockOpen className="w-4 h-4 mr-2" /> Abrir caja
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
    </>
  );
}
