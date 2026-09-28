import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api, formatApiErrorDetail, useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { CreditCard, CheckCircle2, Zap, Package, Users, Building2, TrendingUp, XCircle, Clock, ShieldCheck, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

const fmt = (n, cur = 'USD') => {
  const c = (cur || 'USD').toUpperCase();
  const symbol = c === 'GTQ' ? 'Q' : (c === 'USD' ? '$' : c);
  return `${symbol} ${(Number(n) || 0).toFixed(2)}`;
};

const CYCLE_META = {
  monthly: { label: 'Mensual', suffix: '/mes' },
  yearly: { label: 'Anual', suffix: '/año', badge: 'Ahorra 16%' },
};

export default function MyPlanPage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const [plans, setPlans] = useState([]);
  const [usage, setUsage] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [cycle, setCycle] = useState('monthly');
  const [processingId, setProcessingId] = useState(null);
  const [pollingSession, setPollingSession] = useState(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [plansRes, usageRes, txRes] = await Promise.all([
        api.get('/api/plans'),
        api.get(`/api/plans/usage/${user.company_id}`),
        api.get('/api/billing/my-transactions?limit=10').catch(() => ({ data: [] })),
      ]);
      setPlans(plansRes.data || []);
      setUsage(usageRes.data);
      setTransactions(txRes.data || []);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, [user.company_id]);

  useEffect(() => { load(); }, [load]);

  // Al volver de Stripe con ?session_id=... hacer polling hasta que se confirme
  useEffect(() => {
    const sid = params.get('session_id');
    const status = params.get('status');
    if (status === 'cancelled') {
      toast.info('Pago cancelado. Puedes intentar nuevamente cuando quieras.');
      params.delete('status');
      setParams(params, { replace: true });
    } else if (sid && !pollingSession) {
      setPollingSession(sid);
    }
  }, [params, pollingSession, setParams]);

  useEffect(() => {
    if (!pollingSession) return;
    let attempts = 0;
    const iv = setInterval(async () => {
      attempts += 1;
      try {
        const { data } = await api.get(`/api/billing/status/${pollingSession}`);
        if (data.payment_status === 'paid') {
          clearInterval(iv);
          toast.success(`¡Pago exitoso! Tu plan ${data.plan_name} (${data.billing_cycle === 'yearly' ? 'anual' : 'mensual'}) esta activo.`, { duration: 6000 });
          params.delete('session_id');
          params.delete('status');
          setParams(params, { replace: true });
          setPollingSession(null);
          load();
        } else if (data.payment_status === 'failed' || data.payment_status === 'expired') {
          clearInterval(iv);
          toast.error('El pago no se completo. Intenta nuevamente.');
          setPollingSession(null);
        } else if (attempts > 30) {
          clearInterval(iv);
          toast.info('El pago sigue procesandose. Recarga en unos minutos.');
          setPollingSession(null);
        }
      } catch {
        if (attempts > 30) { clearInterval(iv); setPollingSession(null); }
      }
    }, 2000);
    return () => clearInterval(iv);
  }, [pollingSession, params, setParams, load]);

  const priceFor = (plan) => {
    const key = cycle === 'yearly' ? 'price_yearly' : 'price_monthly';
    if (plan[key] != null) return Number(plan[key]);
    const base = Number(plan.price || 0);
    return cycle === 'yearly' ? base * 10 : base;
  };

  const startCheckout = async (plan) => {
    if (plan._id === usage?.plan?._id && cycle === (usage?.plan?.billing_cycle || 'monthly')) {
      toast.info('Ya tienes este plan activo.');
      return;
    }
    try {
      setProcessingId(plan._id);
      const { data } = await api.post('/api/billing/checkout', {
        plan_id: plan._id,
        billing_cycle: cycle,
        origin_url: window.location.origin,
      });
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
      setProcessingId(null);
    }
  };

  const currentPlanId = usage?.plan?._id;

  return (
    <div className="space-y-6" data-testid="my-plan-page">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2.5 mb-1">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
            <CreditCard className="w-5 h-5 text-white" />
          </div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Mi Plan</h1>
        </div>
        <p className="text-slate-500 text-sm">
          Administra tu suscripcion. Los cambios se aplican al confirmarse el pago con prorrateo automatico.
        </p>
      </div>

      {/* Current plan + usage */}
      {usage && (
        <Card className="border-slate-200/80" data-testid="current-plan-card">
          <CardHeader>
            <CardTitle className="font-heading text-lg flex items-center justify-between gap-2">
              <span className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-600" />
                Plan actual: {usage.plan?.name || 'Sin plan asignado'}
              </span>
              {usage.plan && (
                <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200" variant="outline">
                  Activo
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {usage.plan && (
              <div className="flex items-center justify-between rounded-lg bg-slate-50 border border-slate-100 px-3 py-2.5" data-testid="monthly-cost-row">
                <span className="text-sm text-slate-600">Costo mensual</span>
                <span className="text-lg font-heading font-bold text-slate-900" data-testid="monthly-cost-value">
                  {fmt(usage.monthly_cost ?? usage.plan_monthly_cost ?? 0, usage.plan?.currency)}
                </span>
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <UsageBar label="Pacientes" icon={Users} count={usage.patients_count} max={usage.max_patients} pct={usage.patients_percent} warn={usage.patients_warning} />
              <UsageBar label="Sucursales" icon={Building2} count={usage.branches_count} max={usage.max_branches} pct={usage.branches_percent} warn={usage.branches_warning} />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Cycle toggle */}
      <div className="flex items-center justify-center">
        <div className="inline-flex bg-slate-100 rounded-full p-1" data-testid="cycle-toggle">
          {['monthly', 'yearly'].map((c) => (
            <button
              key={c}
              onClick={() => setCycle(c)}
              className={`px-5 py-2 rounded-full text-sm font-medium transition-all ${cycle === c ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
              data-testid={`cycle-${c}`}
            >
              {CYCLE_META[c].label}
              {c === 'yearly' && (
                <Badge className="ml-1.5 bg-emerald-100 text-emerald-700 border-emerald-200 text-[10px]" variant="outline">
                  {CYCLE_META[c].badge}
                </Badge>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Plans grid */}
      {loading ? (
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {plans.map((plan) => {
            const price = priceFor(plan);
            const isCurrent = plan._id === currentPlanId;
            const isPro = plan.name?.toLowerCase().includes('pro') || plan.name?.toLowerCase().includes('premium');
            return (
              <Card
                key={plan._id}
                className={`relative ${isCurrent ? 'ring-2 ring-emerald-400 border-emerald-300' : 'border-slate-200/80'} ${isPro ? 'shadow-lg' : ''}`}
                data-testid={`plan-card-${plan._id}`}
              >
                {isPro && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge className="bg-gradient-to-r from-purple-500 to-indigo-500 text-white border-0 shadow">
                      <Zap className="w-3 h-3 mr-1" /> Popular
                    </Badge>
                  </div>
                )}
                <CardHeader>
                  <CardTitle className="font-heading text-lg flex items-center gap-2">
                    <Package className="w-5 h-5 text-slate-600" />
                    {plan.name}
                    {isCurrent && (
                      <Badge className="ml-auto bg-emerald-100 text-emerald-700 border-emerald-200" variant="outline">
                        Actual
                      </Badge>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <p className="text-3xl font-heading font-bold text-slate-900">
                      {price === 0 ? 'Gratis' : fmt(price, plan.currency)}
                      {price > 0 && (
                        <span className="text-sm font-normal text-slate-500 ml-1">
                          {CYCLE_META[cycle].suffix}
                        </span>
                      )}
                    </p>
                    {cycle === 'yearly' && price > 0 && (
                      <p className="text-xs text-emerald-600 mt-1">
                        Equivale a {fmt(price / 12, plan.currency)}/mes
                      </p>
                    )}
                  </div>

                  <ul className="space-y-2 text-sm">
                    <li className="flex items-center gap-2 text-slate-700">
                      <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                      Hasta {plan.max_patients?.toLocaleString() || 0} pacientes
                    </li>
                    <li className="flex items-center gap-2 text-slate-700">
                      <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                      {plan.max_branches} {plan.max_branches === 1 ? 'sucursal' : 'sucursales'}
                    </li>
                    {(plan.features || []).map((f, i) => (
                      <li key={i} className="flex items-start gap-2 text-slate-700">
                        <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>

                  <Button
                    onClick={() => startCheckout(plan)}
                    disabled={processingId === plan._id || (isCurrent && cycle === (usage?.plan?.billing_cycle || 'monthly'))}
                    className={`w-full ${isCurrent ? '' : 'bg-emerald-600 hover:bg-emerald-700'}`}
                    variant={isCurrent ? 'outline' : 'default'}
                    data-testid={`select-plan-${plan._id}`}
                  >
                    {processingId === plan._id ? 'Redirigiendo...' :
                     isCurrent && cycle === (usage?.plan?.billing_cycle || 'monthly') ? 'Plan actual' :
                     isCurrent ? `Cambiar a ${CYCLE_META[cycle].label.toLowerCase()}` :
                     price === 0 ? 'Contactar SuperAdmin' :
                     <>Elegir plan <ArrowRight className="w-4 h-4 ml-1" /></>}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Info banner */}
      <Card className="border-blue-200 bg-blue-50/50">
        <CardContent className="p-4 flex items-start gap-3">
          <TrendingUp className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
          <div className="text-sm text-slate-700">
            <p className="font-semibold text-slate-900 mb-1">Prorrateo automatico</p>
            <p>Al cambiar de plan Stripe calcula automaticamente la diferencia proporcional al tiempo restante de tu ciclo actual. Solo pagas la diferencia real.</p>
          </div>
        </CardContent>
      </Card>

      {/* Transactions */}
      {transactions.length > 0 && (
        <Card className="border-slate-200/80" data-testid="transactions-card">
          <CardHeader>
            <CardTitle className="font-heading text-lg flex items-center gap-2">
              <Clock className="w-5 h-5 text-slate-600" /> Historial de pagos
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="divide-y divide-slate-100">
              {transactions.map((t) => {
                const paid = t.payment_status === 'paid';
                const failed = ['failed', 'expired'].includes(t.payment_status);
                return (
                  <div key={t._id} className="py-3 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-medium text-slate-900 truncate">
                        {t.plan_name} · {t.billing_cycle === 'yearly' ? 'Anual' : 'Mensual'}
                      </p>
                      <p className="text-xs text-slate-500">
                        {(t.created_at || '').slice(0, 16).replace('T', ' ')} · {fmt(t.amount, t.currency)}
                      </p>
                    </div>
                    <Badge
                      className={paid ? 'bg-emerald-100 text-emerald-700 border-emerald-200'
                        : failed ? 'bg-red-100 text-red-700 border-red-200'
                        : 'bg-amber-100 text-amber-700 border-amber-200'}
                      variant="outline"
                    >
                      {paid ? <><CheckCircle2 className="w-3 h-3 mr-1" />Pagado</>
                       : failed ? <><XCircle className="w-3 h-3 mr-1" />Fallido</>
                       : <><Clock className="w-3 h-3 mr-1" />Pendiente</>}
                    </Badge>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function UsageBar({ label, icon: Icon, count, max, pct, warn }) {
  const barColor = warn ? 'bg-amber-500' : pct > 80 ? 'bg-orange-500' : 'bg-emerald-500';
  return (
    <div className="bg-slate-50 border border-slate-100 rounded-lg p-3">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2 text-sm">
          <Icon className="w-4 h-4 text-slate-500" />
          <span className="font-medium text-slate-700">{label}</span>
        </div>
        <span className="text-sm font-semibold text-slate-900">
          {count?.toLocaleString() || 0} / {max?.toLocaleString() || 0}
        </span>
      </div>
      <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
        <div className={`h-full ${barColor} transition-all`} style={{ width: `${Math.min(pct || 0, 100)}%` }} />
      </div>
    </div>
  );
}
