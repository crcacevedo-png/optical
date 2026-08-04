import React from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Plus, Trash2, Banknote, CreditCard, Smartphone, HandCoins } from 'lucide-react';

export const PAYMENT_METHODS = [
  { value: 'cash', label: 'Efectivo', icon: Banknote },
  { value: 'card', label: 'Tarjeta', icon: CreditCard },
  { value: 'transfer', label: 'Transferencia', icon: Smartphone },
  { value: 'other', label: 'Otro', icon: HandCoins },
];

export const paymentMethodLabel = (v) =>
  PAYMENT_METHODS.find((m) => m.value === v)?.label || v || '-';

const fmt = (n) =>
  `Q ${(Number(n) || 0).toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/**
 * Editor dinamico de pagos: cada fila = metodo + monto.
 * onChange devuelve el array actualizado [{method, amount, note?}]
 */
export function PaymentLinesEditor({ payments, onChange, total, testIdPrefix = 'pay' }) {
  const totalPaid = payments.reduce((s, p) => s + (Number(p.amount) || 0), 0);
  const balance = Math.max(0, (Number(total) || 0) - totalPaid);
  const overpaid = totalPaid - (Number(total) || 0);

  const update = (idx, patch) => {
    onChange(payments.map((p, i) => (i === idx ? { ...p, ...patch } : p)));
  };

  const remove = (idx) => onChange(payments.filter((_, i) => i !== idx));

  const add = () => {
    // Sugerir monto = saldo pendiente si queda; sino 0
    const suggested = balance > 0 ? balance : 0;
    onChange([...payments, { method: 'cash', amount: suggested, note: '' }]);
  };

  const payFull = () => {
    onChange([{ method: 'cash', amount: Number(total) || 0, note: '' }]);
  };

  return (
    <div className="space-y-2.5" data-testid={`${testIdPrefix}-editor`}>
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-700">Pagos</p>
        <div className="flex gap-2">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 text-xs"
            onClick={payFull}
            data-testid={`${testIdPrefix}-pay-full`}
          >
            Pagar total
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            onClick={add}
            data-testid={`${testIdPrefix}-add-line`}
          >
            <Plus className="w-3.5 h-3.5 mr-1" /> Agregar pago
          </Button>
        </div>
      </div>

      {payments.length === 0 && (
        <div className="text-center py-4 border border-dashed border-slate-200 rounded-lg text-sm text-slate-400">
          Sin pagos. Se registrara como <span className="font-medium text-amber-600">Cuenta por cobrar</span>.
        </div>
      )}

      {payments.map((p, idx) => (
        <div
          key={idx}
          className="grid grid-cols-[1fr_130px_36px] gap-2 items-center"
          data-testid={`${testIdPrefix}-line-${idx}`}
        >
          <Select value={p.method} onValueChange={(v) => update(idx, { method: v })}>
            <SelectTrigger className="h-9" data-testid={`${testIdPrefix}-method-${idx}`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PAYMENT_METHODS.map((m) => (
                <SelectItem key={m.value} value={m.value}>
                  <div className="flex items-center gap-2">
                    <m.icon className="w-3.5 h-3.5" /> {m.label}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            type="number"
            step="0.01"
            min="0"
            value={p.amount}
            onChange={(e) => update(idx, { amount: e.target.value })}
            placeholder="0.00"
            className="h-9 text-right"
            data-testid={`${testIdPrefix}-amount-${idx}`}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-9 w-9 text-slate-400 hover:text-red-500"
            onClick={() => remove(idx)}
            data-testid={`${testIdPrefix}-remove-${idx}`}
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      ))}

      {/* Summary */}
      <div className="rounded-lg bg-slate-50 px-3 py-2.5 text-sm border border-slate-100 space-y-1">
        <div className="flex justify-between">
          <span className="text-slate-500">Total venta</span>
          <span className="font-medium">{fmt(total)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">Total pagado</span>
          <span className="font-medium" data-testid={`${testIdPrefix}-total-paid`}>{fmt(totalPaid)}</span>
        </div>
        {balance > 0 && (
          <div className="flex justify-between text-amber-600 font-medium" data-testid={`${testIdPrefix}-balance`}>
            <span>Saldo pendiente</span>
            <span>{fmt(balance)}</span>
          </div>
        )}
        {overpaid > 0.01 && (
          <div className="flex justify-between text-red-600 font-medium" data-testid={`${testIdPrefix}-overpaid`}>
            <span>Sobrepago</span>
            <span>{fmt(overpaid)}</span>
          </div>
        )}
      </div>
    </div>
  );
}
