import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import {
  Wallet, CalendarClock, Clock, Lock, AlertTriangle, TrendingDown, RefreshCw, ArrowRight, ExternalLink,
} from 'lucide-react';
import { toast } from 'sonner';

const fmt = (n, cur = 'USD') => {
  const c = (cur || 'USD').toUpperCase();
  const symbol = c === 'GTQ' ? 'Q' : c === 'USD' ? '$' : c;
  return `${symbol} ${(Number(n) || 0).toFixed(2)}`;
};

const fmtDate = (iso) => (iso ? String(iso).slice(0, 10) : '—');

const STATUS_LABEL = {
  active: 'Activa', trialing: 'Prueba', past_due: 'Pago vencido',
  unpaid: 'Impaga', incomplete: 'Incompleta', canceled: 'Cancelada',
  incomplete_expired: 'Expirada',
};

function Kpi({ icon: Icon, label, value, tone, testId }) {
  const tones = {
    slate: 'bg-slate-100 text-slate-600',
    amber: 'bg-amber-100 text-amber-600',
    red: 'bg-red-100 text-red-600',
    emerald: 'bg-emerald-100 text-emerald-600',
    blue: 'bg-blue-100 text-blue-600',
  };
  return (
    <Card className="border-slate-200/80" data-testid={testId}>
      <CardContent className="p-4 flex items-center gap-3">
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${tones[tone] || tones.slate}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="min-w-0">
          <p className="text-2xl font-heading font-bold text-slate-900 leading-tight">{value}</p>
          <p className="text-xs text-slate-500">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function CompanyRow({ row, right, testId }) {
  return (
    <div className="py-3 flex items-center justify-between gap-3 border-b border-slate-100 last:border-0" data-testid={testId}>
      <div className="min-w-0">
        <Link to="/admin/opticas" className="font-medium text-slate-900 truncate hover:text-emerald-700 flex items-center gap-1">
          {row.company_name} <ExternalLink className="w-3 h-3 opacity-50" />
        </Link>
        <p className="text-xs text-slate-500">
          {row.plan_name} · {row.billing_cycle === 'yearly' ? 'Anual' : 'Mensual'} · {fmt(row.monthly_cost, row.currency)}/mes
          {row.subscription_status ? ` · ${STATUS_LABEL[row.subscription_status] || row.subscription_status}` : ''}
        </p>
      </div>
      <div className="shrink-0 text-right">{right}</div>
    </div>
  );
}

function ListCard({ title, icon: Icon, items, empty, renderRight, testId, headerTone = 'text-slate-700' }) {
  return (
    <Card className="border-slate-200/80" data-testid={testId}>
      <CardHeader className="pb-2">
        <CardTitle className={`font-heading text-base flex items-center gap-2 ${headerTone}`}>
          <Icon className="w-4.5 h-4.5" /> {title}
          <Badge variant="outline" className="ml-auto bg-slate-50 text-slate-600 border-slate-200">{items.length}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-sm text-slate-400 py-4 text-center">{empty}</p>
        ) : (
          <div>{items.map((row, i) => (
            <CompanyRow key={row.company_id + i} row={row} right={renderRight(row)} testId={`${testId}-row-${i}`} />
          ))}</div>
        )}
      </CardContent>
    </Card>
  );
}

export default function CollectionsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await api.get('/api/billing/admin/collections');
      setData(data);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || 'No se pudo cargar el panel de cobros.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const kpis = data?.kpis || {};

  return (
    <div className="space-y-6" data-testid="collections-page">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#1B2A49] to-slate-700 flex items-center justify-center">
              <Wallet className="w-5 h-5 text-white" />
            </div>
            <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Cobros</h1>
          </div>
          <p className="text-slate-500 text-sm">
            Estado de cobro de las membresías: renovaciones, pagos fallidos, suspensiones e ingresos en riesgo.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading} data-testid="collections-refresh-btn">
          <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Actualizar
        </Button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <Kpi icon={CalendarClock} tone="blue" label="Renovaciones próximas (7d)" value={kpis.upcoming_renewals ?? 0} testId="kpi-upcoming" />
        <Kpi icon={Clock} tone="amber" label={`En gracia (${data?.grace_days ?? 3}d)`} value={kpis.in_grace ?? 0} testId="kpi-grace" />
        <Kpi icon={Lock} tone="red" label="Suspendidas" value={kpis.suspended ?? 0} testId="kpi-suspended" />
        <Kpi icon={AlertTriangle} tone="amber" label="Discrepancia de monto" value={kpis.amount_mismatches ?? 0} testId="kpi-mismatch" />
        <Kpi icon={TrendingDown} tone="red" label="Ingresos en riesgo (MRR)" value={fmt(kpis.mrr_at_risk ?? 0)} testId="kpi-mrr-risk" />
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#1B2A49]"></div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ListCard
            title="Pagos fallidos / en gracia" icon={Clock} headerTone="text-amber-700"
            items={data?.grace || []} empty="Sin cuentas en periodo de gracia."
            testId="collections-grace-list"
            renderRight={(row) => (
              <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
                {row.days_remaining != null ? `${row.days_remaining} día${row.days_remaining === 1 ? '' : 's'}` : '—'}
              </Badge>
            )}
          />
          <ListCard
            title="Suspendidas" icon={Lock} headerTone="text-red-700"
            items={data?.suspended || []} empty="Sin cuentas suspendidas."
            testId="collections-suspended-list"
            renderRight={(row) => (
              <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
                Desde {fmtDate(row.suspended_at)}
              </Badge>
            )}
          />
          <ListCard
            title="Renovaciones próximas" icon={CalendarClock} headerTone="text-blue-700"
            items={data?.upcoming || []} empty="Sin renovaciones en los próximos días."
            testId="collections-upcoming-list"
            renderRight={(row) => (
              <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                {row.days_to_renewal != null ? `en ${row.days_to_renewal} día${row.days_to_renewal === 1 ? '' : 's'}` : fmtDate(row.current_period_end)}
              </Badge>
            )}
          />
          <ListCard
            title="Discrepancia de monto" icon={AlertTriangle} headerTone="text-amber-700"
            items={data?.mismatches || []} empty="Todos los montos coinciden con su plan."
            testId="collections-mismatch-list"
            renderRight={(row) => {
              const d = row.amount_mismatch_detail || {};
              const exp = ((d.expected_cents || 0) / 100).toFixed(2);
              const act = ((d.actual_cents || 0) / 100).toFixed(2);
              return (
                <div className="text-xs text-right">
                  <p className="text-slate-500">Plan: <span className="font-medium text-slate-700">{exp}</span></p>
                  <p className="text-slate-500">Stripe: <span className="font-medium text-red-600">{act}</span></p>
                </div>
              );
            }}
          />
        </div>
      )}

      <Card className="border-blue-200 bg-blue-50/50">
        <CardContent className="p-4 flex items-start gap-3">
          <ArrowRight className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
          <div className="text-sm text-slate-700">
            <p className="font-semibold text-slate-900 mb-1">Cómo funciona</p>
            <p>
              El sistema sincroniza a diario con Stripe. Un pago fallido inicia {data?.grace_days ?? 3} días de gracia
              (la óptica sigue operando con avisos); al vencer sin pago, se suspende. La reactivación es automática al regularizar.
              Las cuentas de cortesía están exentas.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
