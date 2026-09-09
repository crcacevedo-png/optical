import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { BranchFilter } from '../components/BranchFilter';
import { PAYMENT_METHODS } from '../components/PaymentLinesEditor';
import { HandCoins, AlertTriangle, Search, TrendingDown, Truck, Receipt, CalendarClock } from 'lucide-react';
import { toast } from 'sonner';

const fmt = (n) =>
  `Q ${(Number(n) || 0).toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const agingBadge = (days) => {
  if (days <= 7) return { label: `${days} d`, cls: 'bg-emerald-100 text-emerald-700' };
  if (days <= 30) return { label: `${days} d`, cls: 'bg-amber-100 text-amber-700' };
  if (days <= 60) return { label: `${days} d`, cls: 'bg-orange-100 text-orange-700' };
  return { label: `${days} d`, cls: 'bg-red-100 text-red-700' };
};

function PayableAbonoDialog({ entry, open, onOpenChange, onSuccess }) {
  const [method, setMethod] = useState('cash');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open && entry) {
      setAmount(String(entry.balance || 0));
      setMethod('cash');
      setNote('');
    }
  }, [open, entry]);

  if (!entry) return null;
  const numAmount = Number(amount) || 0;
  const invalid = numAmount <= 0 || numAmount > (entry.balance || 0) + 0.001;

  const submit = async (e) => {
    e.preventDefault();
    if (invalid) { toast.error('Monto inválido'); return; }
    try {
      setSubmitting(true);
      await api.post(
        `/api/finance/payables/${entry._id}/payment?amount=${numAmount}&method=${method}&note=${encodeURIComponent(note || '')}`
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
      <DialogContent className="sm:max-w-md" data-testid="payable-abono-dialog">
        <DialogHeader>
          <DialogTitle className="font-heading flex items-center gap-2">
            <HandCoins className="w-5 h-5 text-emerald-600" /> Registrar abono a proveedor
          </DialogTitle>
        </DialogHeader>

        <div className="rounded-lg bg-slate-50 border border-slate-100 px-4 py-3 text-sm space-y-1">
          <div className="flex justify-between"><span className="text-slate-500">Proveedor</span><span className="font-medium">{entry.supplier_name || '(sin proveedor)'}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">Concepto</span><span className="truncate max-w-[220px]">{entry.description}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">Total</span><span>{fmt(entry.amount)}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">Ya pagado</span><span>{fmt(entry.amount_paid)}</span></div>
          <div className="flex justify-between text-amber-700 font-semibold pt-1 border-t border-slate-200">
            <span>Saldo pendiente</span><span>{fmt(entry.balance)}</span>
          </div>
        </div>

        <form onSubmit={submit} className="space-y-3 mt-2">
          <div>
            <Label>Método de pago</Label>
            <Select value={method} onValueChange={setMethod}>
              <SelectTrigger data-testid="payable-pay-method"><SelectValue /></SelectTrigger>
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
              max={entry.balance}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              data-testid="payable-pay-amount"
              autoFocus
            />
          </div>
          <div>
            <Label>Nota (opcional)</Label>
            <Input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="No. de factura, referencia, etc."
              maxLength={200}
              data-testid="payable-pay-note"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button
              type="submit"
              className="bg-emerald-600 hover:bg-emerald-700"
              disabled={invalid || submitting}
              data-testid="payable-pay-submit"
            >
              {submitting ? 'Registrando...' : `Registrar ${fmt(numAmount)}`}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function PayablesPage() {
  const [data, setData] = useState({ items: [], total_pending: 0, count: 0, by_supplier: [] });
  const [loading, setLoading] = useState(true);
  const [branchId, setBranchId] = useState('');
  const [search, setSearch] = useState('');
  const [payEntry, setPayEntry] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const params = branchId ? { branch_id: branchId } : {};
      const { data: d } = await api.get('/api/finance/payables', { params });
      setData(d || { items: [], total_pending: 0, count: 0, by_supplier: [] });
    } catch (err) {
      console.error('No se pudieron cargar las cuentas por pagar:', err);
    } finally {
      setLoading(false);
    }
  }, [branchId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filtered = data.items.filter((e) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (e.supplier_name || '').toLowerCase().includes(q) ||
      (e.description || '').toLowerCase().includes(q)
    );
  });

  const uniqueSuppliers = (data.by_supplier || []).length;
  const overdueCount = data.items.filter((e) => e.is_overdue).length;

  return (
    <div className="space-y-6" data-testid="payables-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-rose-500 to-red-500 flex items-center justify-center">
              <Truck className="w-5 h-5 text-white" />
            </div>
            <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Cuentas por Pagar</h1>
          </div>
          <p className="text-slate-500">Egresos a crédito con saldo pendiente. Registra abonos para cerrar la deuda.</p>
        </div>
        <BranchFilter value={branchId} onChange={setBranchId} />
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="border-0 bg-gradient-to-br from-rose-500 to-red-500 text-white" data-testid="kpi-total-payable">
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide opacity-80">Saldo total por pagar</p>
                <p className="font-heading text-3xl font-bold mt-1">{fmt(data.total_pending)}</p>
                <p className="text-xs opacity-80 mt-1">{data.count} egreso{data.count !== 1 ? 's' : ''} a crédito</p>
              </div>
              <TrendingDown className="w-8 h-8 opacity-40" />
            </div>
          </CardContent>
        </Card>
        <Card className="border-slate-200/80" data-testid="kpi-suppliers">
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Proveedores con deuda</p>
                <p className="font-heading text-3xl font-bold text-slate-900 mt-1">{uniqueSuppliers}</p>
                <p className="text-xs text-slate-400 mt-1">Distintos proveedores</p>
              </div>
              <div className="p-2.5 rounded-lg bg-blue-100"><Truck className="w-5 h-5 text-blue-600" /></div>
            </div>
          </CardContent>
        </Card>
        <Card className="border-slate-200/80" data-testid="kpi-overdue">
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Vencidas</p>
                <p className="font-heading text-3xl font-bold text-slate-900 mt-1">{overdueCount}</p>
                <p className="text-xs text-slate-400 mt-1">Con fecha vencida</p>
              </div>
              <div className={`p-2.5 rounded-lg ${overdueCount > 0 ? 'bg-red-100' : 'bg-emerald-100'}`}>
                <AlertTriangle className={`w-5 h-5 ${overdueCount > 0 ? 'text-red-600' : 'text-emerald-600'}`} />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Saldo por proveedor */}
      {(data.by_supplier || []).length > 0 && (
        <Card className="border-slate-200/80" data-testid="payables-by-supplier">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Truck className="w-4 h-4 text-red-600" /> Saldo por Proveedor
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {data.by_supplier.map((s) => {
                const pct = data.total_pending > 0 ? (s.balance / data.total_pending) * 100 : 0;
                return (
                  <div key={s.name} className="flex items-center gap-3">
                    <span className="text-xs text-slate-600 w-40 truncate">{s.name}</span>
                    <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full bg-red-500 rounded-full transition-all" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-xs font-medium text-slate-700 w-24 text-right">{fmt(s.balance)}</span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <Input
          placeholder="Buscar por proveedor o concepto..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
          data-testid="payables-search"
        />
      </div>

      {/* Table */}
      <Card className="border-slate-200/80">
        <CardHeader>
          <CardTitle className="font-heading text-lg flex items-center gap-2">
            <Receipt className="w-5 h-5 text-slate-600" />
            Egresos a crédito pendientes
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-pine-900"></div>
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12 text-slate-500" data-testid="payables-empty">
              <Truck className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p className="font-medium text-slate-700">{data.count === 0 ? 'Sin cuentas por pagar' : 'Sin resultados'}</p>
              <p className="text-sm">{data.count === 0 ? 'No tienes egresos a crédito pendientes.' : 'Ajusta el buscador.'}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="data-table-header">
                    <TableHead>Fecha</TableHead>
                    <TableHead>Proveedor</TableHead>
                    <TableHead>Concepto</TableHead>
                    <TableHead>Vencimiento</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                    <TableHead className="text-right">Pagado</TableHead>
                    <TableHead className="text-right">Saldo</TableHead>
                    <TableHead className="text-center">Antigüedad</TableHead>
                    <TableHead className="text-right">Acción</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((e) => {
                    const aging = agingBadge(e.days_pending || 0);
                    return (
                      <TableRow key={e._id} data-testid={`payable-row-${e._id}`}>
                        <TableCell className="text-sm">{(e.date || (e.created_at || '').slice(0, 10))}</TableCell>
                        <TableCell className="font-medium text-slate-900 text-sm">{e.supplier_name || '(sin proveedor)'}</TableCell>
                        <TableCell className="text-sm text-slate-600 max-w-[220px] truncate">{e.description}</TableCell>
                        <TableCell className="text-sm">
                          {e.due_date ? (
                            <span className={`inline-flex items-center gap-1 ${e.is_overdue ? 'text-red-600 font-medium' : 'text-slate-600'}`}>
                              <CalendarClock className="w-3.5 h-3.5" />{e.due_date}
                              {e.is_overdue && <Badge className="bg-red-100 text-red-700 ml-1">Vencida</Badge>}
                            </span>
                          ) : <span className="text-slate-400">—</span>}
                        </TableCell>
                        <TableCell className="text-right text-sm">{fmt(e.amount)}</TableCell>
                        <TableCell className="text-right text-sm text-slate-500">{fmt(e.amount_paid)}</TableCell>
                        <TableCell className="text-right font-bold text-amber-700">{fmt(e.balance)}</TableCell>
                        <TableCell className="text-center">
                          <Badge className={aging.cls}>{aging.label}</Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            className="bg-emerald-600 hover:bg-emerald-700 h-8 text-xs"
                            onClick={() => setPayEntry(e)}
                            data-testid={`add-abono-${e._id}`}
                          >
                            <HandCoins className="w-3.5 h-3.5 mr-1" /> Abonar
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <PayableAbonoDialog
        entry={payEntry}
        open={!!payEntry}
        onOpenChange={(o) => !o && setPayEntry(null)}
        onSuccess={() => { setPayEntry(null); fetchData(); }}
      />
    </div>
  );
}
