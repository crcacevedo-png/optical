import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { BranchFilter } from '../components/BranchFilter';
import { AddPaymentDialog } from '../components/AddPaymentDialog';
import { HandCoins, AlertTriangle, Search, TrendingDown, Users, Receipt } from 'lucide-react';

const fmt = (n) =>
  `Q ${(Number(n) || 0).toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const agingBadge = (days) => {
  if (days <= 7) return { label: `${days} d`, cls: 'bg-emerald-100 text-emerald-700' };
  if (days <= 30) return { label: `${days} d`, cls: 'bg-amber-100 text-amber-700' };
  if (days <= 60) return { label: `${days} d`, cls: 'bg-orange-100 text-orange-700' };
  return { label: `${days} d`, cls: 'bg-red-100 text-red-700' };
};

export default function ReceivablesPage() {
  const [data, setData] = useState({ items: [], total_pending: 0, count: 0 });
  const [loading, setLoading] = useState(true);
  const [branchId, setBranchId] = useState('');
  const [search, setSearch] = useState('');
  const [paymentSale, setPaymentSale] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const params = branchId ? { branch_id: branchId } : {};
      const { data: d } = await api.get('/api/sales/receivables', { params });
      setData(d || { items: [], total_pending: 0, count: 0 });
    } catch (err) {
      console.error('No se pudieron cargar las cuentas por cobrar:', err);
    } finally {
      setLoading(false);
    }
  }, [branchId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filtered = data.items.filter((s) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (s.patient_name || '').toLowerCase().includes(q) ||
      (s.patient_phone || '').includes(q) ||
      (s._id || '').includes(q)
    );
  });

  // Aggregates
  const uniquePatients = new Set(data.items.map((s) => s.patient_name)).size;
  const oldestDays = data.items.reduce((max, s) => Math.max(max, s.days_pending || 0), 0);

  return (
    <div className="space-y-6" data-testid="receivables-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center">
              <HandCoins className="w-5 h-5 text-white" />
            </div>
            <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Cuentas por Cobrar</h1>
          </div>
          <p className="text-slate-500">Ventas con saldo pendiente. Registra abonos para cerrar la cuenta.</p>
        </div>
        <BranchFilter value={branchId} onChange={setBranchId} />
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="border-0 bg-gradient-to-br from-amber-500 to-orange-500 text-white" data-testid="kpi-total-pending">
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide opacity-80">Saldo total por cobrar</p>
                <p className="font-heading text-3xl font-bold mt-1">{fmt(data.total_pending)}</p>
                <p className="text-xs opacity-80 mt-1">{data.count} venta{data.count !== 1 ? 's' : ''} pendiente{data.count !== 1 ? 's' : ''}</p>
              </div>
              <TrendingDown className="w-8 h-8 opacity-40" />
            </div>
          </CardContent>
        </Card>
        <Card className="border-slate-200/80" data-testid="kpi-clients">
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Clientes con deuda</p>
                <p className="font-heading text-3xl font-bold text-slate-900 mt-1">{uniquePatients}</p>
                <p className="text-xs text-slate-400 mt-1">Distintos pacientes</p>
              </div>
              <div className="p-2.5 rounded-lg bg-blue-100"><Users className="w-5 h-5 text-blue-600" /></div>
            </div>
          </CardContent>
        </Card>
        <Card className="border-slate-200/80" data-testid="kpi-oldest">
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Cuenta mas antigua</p>
                <p className="font-heading text-3xl font-bold text-slate-900 mt-1">{oldestDays} dias</p>
                <p className="text-xs text-slate-400 mt-1">Vencimiento maximo</p>
              </div>
              <div className={`p-2.5 rounded-lg ${oldestDays > 60 ? 'bg-red-100' : oldestDays > 30 ? 'bg-amber-100' : 'bg-emerald-100'}`}>
                <AlertTriangle className={`w-5 h-5 ${oldestDays > 60 ? 'text-red-600' : oldestDays > 30 ? 'text-amber-600' : 'text-emerald-600'}`} />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <Input
          placeholder="Buscar por paciente, telefono o ID..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
          data-testid="receivables-search"
        />
      </div>

      {/* Table */}
      <Card className="border-slate-200/80">
        <CardHeader>
          <CardTitle className="font-heading text-lg flex items-center gap-2">
            <Receipt className="w-5 h-5 text-slate-600" />
            Ventas pendientes de cobro
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-pine-900"></div>
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12 text-slate-500" data-testid="receivables-empty">
              <HandCoins className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p className="font-medium text-slate-700">{data.count === 0 ? 'Sin cuentas por cobrar' : 'Sin resultados'}</p>
              <p className="text-sm">{data.count === 0 ? 'Todas las ventas estan pagadas.' : 'Ajusta el buscador.'}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="data-table-header">
                    <TableHead>Fecha</TableHead>
                    <TableHead>Cliente</TableHead>
                    <TableHead>Vendedor</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                    <TableHead className="text-right">Pagado</TableHead>
                    <TableHead className="text-right">Saldo</TableHead>
                    <TableHead className="text-center">Antiguedad</TableHead>
                    <TableHead className="text-right">Accion</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((s) => {
                    const aging = agingBadge(s.days_pending || 0);
                    return (
                      <TableRow key={s._id} data-testid={`receivable-row-${s._id}`}>
                        <TableCell className="text-sm">{(s.created_at || '').slice(0, 10)}</TableCell>
                        <TableCell>
                          <div>
                            <p className="font-medium text-slate-900 text-sm">{s.patient_name || 'Consumidor final'}</p>
                            {s.patient_phone && <p className="text-xs text-slate-500">{s.patient_phone}</p>}
                          </div>
                        </TableCell>
                        <TableCell className="text-sm text-slate-600">{s.seller_name || '-'}</TableCell>
                        <TableCell className="text-right text-sm">{fmt(s.total)}</TableCell>
                        <TableCell className="text-right text-sm text-slate-500">{fmt(s.amount_paid)}</TableCell>
                        <TableCell className="text-right font-bold text-amber-700">{fmt(s.balance)}</TableCell>
                        <TableCell className="text-center">
                          <Badge className={aging.cls}>{aging.label}</Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            className="bg-emerald-600 hover:bg-emerald-700 h-8 text-xs"
                            onClick={() => setPaymentSale(s)}
                            data-testid={`add-payment-${s._id}`}
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

      <AddPaymentDialog
        sale={paymentSale}
        open={!!paymentSale}
        onOpenChange={(o) => !o && setPaymentSale(null)}
        onSuccess={() => { setPaymentSale(null); fetchData(); }}
      />
    </div>
  );
}
