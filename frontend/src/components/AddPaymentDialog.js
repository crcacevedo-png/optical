import React, { useState, useEffect } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { PAYMENT_METHODS } from './PaymentLinesEditor';
import { HandCoins } from 'lucide-react';
import { toast } from 'sonner';

const fmt = (n) =>
  `Q ${(Number(n) || 0).toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/**
 * Dialogo para registrar un abono sobre una venta pendiente.
 * Prop `sale`: objeto venta con {_id, balance, patient_name, total, amount_paid}
 * Prop `onSuccess`: callback tras registrar abono exitosamente
 */
export function AddPaymentDialog({ sale, open, onOpenChange, onSuccess }) {
  const [method, setMethod] = useState('cash');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open && sale) {
      setAmount(String(sale.balance || 0));
      setMethod('cash');
      setNote('');
    }
  }, [open, sale]);

  if (!sale) return null;

  const numAmount = Number(amount) || 0;
  const invalid = numAmount <= 0 || numAmount > (sale.balance || 0) + 0.001;

  const submit = async (e) => {
    e.preventDefault();
    if (invalid) {
      toast.error('Monto invalido');
      return;
    }
    try {
      setSubmitting(true);
      await api.post(
        `/api/sales/${sale._id}/payment?amount=${numAmount}&method=${method}&note=${encodeURIComponent(note || '')}`
      );
      toast.success('Abono registrado');
      onSuccess?.();
      onOpenChange(false);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="add-payment-dialog">
        <DialogHeader>
          <DialogTitle className="font-heading flex items-center gap-2">
            <HandCoins className="w-5 h-5 text-emerald-600" /> Registrar abono
          </DialogTitle>
        </DialogHeader>

        <div className="rounded-lg bg-slate-50 border border-slate-100 px-4 py-3 text-sm space-y-1">
          <div className="flex justify-between"><span className="text-slate-500">Cliente</span><span className="font-medium">{sale.patient_name || 'Consumidor final'}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">Total venta</span><span>{fmt(sale.total)}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">Ya pagado</span><span>{fmt(sale.amount_paid)}</span></div>
          <div className="flex justify-between text-amber-700 font-semibold pt-1 border-t border-slate-200">
            <span>Saldo pendiente</span><span>{fmt(sale.balance)}</span>
          </div>
        </div>

        <form onSubmit={submit} className="space-y-3 mt-2">
          <div>
            <Label>Metodo de pago</Label>
            <Select value={method} onValueChange={setMethod}>
              <SelectTrigger data-testid="add-pay-method"><SelectValue /></SelectTrigger>
              <SelectContent>
                {PAYMENT_METHODS.map((m) => (
                  <SelectItem key={m.value} value={m.value}>
                    <div className="flex items-center gap-2"><m.icon className="w-3.5 h-3.5" /> {m.label}</div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Monto a abonar</Label>
            <Input
              type="number"
              step="0.01"
              min="0.01"
              max={sale.balance}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              data-testid="add-pay-amount"
              autoFocus
            />
          </div>
          <div>
            <Label>Nota (opcional)</Label>
            <Input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Ej. Referencia de transferencia"
              maxLength={200}
              data-testid="add-pay-note"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button
              type="submit"
              className="bg-emerald-600 hover:bg-emerald-700"
              disabled={invalid || submitting}
              data-testid="add-pay-submit"
            >
              {submitting ? 'Registrando...' : `Registrar ${fmt(numAmount)}`}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
