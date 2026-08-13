/* eslint-disable react/no-unstable-nested-components */
import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Sparkles, AlertTriangle, Clock, XCircle, TrendingUp, Zap,
  Mail, RefreshCw, CheckCircle2, Store,
} from 'lucide-react';
import { toast } from 'sonner';

const StatCard = ({ label, value, sub, icon: Icon, color, testId }) => (
  <Card className={`border-l-4 ${color}`} data-testid={testId}>
    <CardContent className="p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500 font-semibold">{label}</p>
          <p className="text-2xl font-bold mt-1 text-slate-900">{value}</p>
          {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
        </div>
        <Icon className="w-5 h-5 text-slate-400" />
      </div>
    </CardContent>
  </Card>
);

const CompanyRow = ({ c, extraCol, actionSlot }) => (
  <tr className="border-b border-slate-100 hover:bg-slate-50/50">
    <td className="py-2.5 px-3">
      <div className="flex items-center gap-2">
        <Store className="w-4 h-4 text-slate-400" />
        <div>
          <div className="font-medium text-slate-900 text-sm">{c.name}</div>
          <div className="text-xs text-slate-500">{c.plan_name}</div>
        </div>
      </div>
    </td>
    <td className="py-2.5 px-3 text-xs text-slate-600">
      <div>{c.admin_name || '-'}</div>
      <div className="text-slate-400">{c.admin_email || '-'}</div>
    </td>
    <td className="py-2.5 px-3 text-xs text-slate-600">
      {c.created_at?.slice(0, 10)}
    </td>
    <td className="py-2.5 px-3 text-xs text-slate-600">
      {extraCol}
    </td>
    <td className="py-2.5 px-3 text-right">
      {actionSlot}
    </td>
  </tr>
);

export default function RetentionDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('never_activated');
  const [reactivateTarget, setReactivateTarget] = useState(null);
  const [reactivating, setReactivating] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await api.get('/api/superadmin/retention');
      setData(data);
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail) || 'Error al cargar');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const doReactivate = async () => {
    if (!reactivateTarget) return;
    setReactivating(true);
    try {
      const { data: resp } = await api.post(`/api/companies/${reactivateTarget._id}/reactivate`);
      toast.success(`Reactivada: ${reactivateTarget.name}. Email enviado a ${resp.admin_email}`);
      setReactivateTarget(null);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail) || 'Error al reactivar');
    } finally {
      setReactivating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
      </div>
    );
  }
  if (!data) return null;

  const { kpis, thresholds, segments } = data;

  return (
    <div className="space-y-6" data-testid="retention-dashboard">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-purple-600" />
            Retencion de Opticas
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            Monitorea la salud de tu base y reactiva ópticas en riesgo con un solo click
          </p>
        </div>
        <Button variant="outline" onClick={load} data-testid="refresh-btn">
          <RefreshCw className="w-4 h-4 mr-2" /> Actualizar
        </Button>
      </div>

      {/* KPIs principales */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total"
          value={kpis.total}
          sub={`${kpis.active} activas / ${kpis.inactive} inactivas`}
          icon={Store}
          color="border-blue-500"
          testId="kpi-total"
        />
        <StatCard
          label="Tasa de activacion"
          value={`${kpis.activation_rate}%`}
          sub="Admins que ya hicieron primer login"
          icon={TrendingUp}
          color="border-green-500"
          testId="kpi-activation-rate"
        />
        <StatCard
          label="Recien activadas"
          value={kpis.recently_activated}
          sub="Primer login < 7 dias"
          icon={Zap}
          color="border-purple-500"
          testId="kpi-recently"
        />
        <StatCard
          label="Sin activar"
          value={kpis.never_activated}
          sub="Admin no ingreso aun"
          icon={Clock}
          color="border-slate-500"
          testId="kpi-never"
        />
        <StatCard
          label="En riesgo"
          value={kpis.at_risk}
          sub={`>${thresholds.at_risk_days}d sin login`}
          icon={AlertTriangle}
          color="border-amber-500"
          testId="kpi-at-risk"
        />
        <StatCard
          label="Expiradas"
          value={kpis.expired}
          sub={`>${thresholds.deadline_days}d, desactivadas`}
          icon={XCircle}
          color="border-red-500"
          testId="kpi-expired"
        />
      </div>

      {/* Segments Tabs */}
      <Card>
        <CardContent className="pt-6">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="mb-4">
              <TabsTrigger value="never_activated" data-testid="tab-never">
                Sin activar ({segments.never_activated.length})
              </TabsTrigger>
              <TabsTrigger value="at_risk" data-testid="tab-at-risk">
                En riesgo ({segments.at_risk.length})
              </TabsTrigger>
              <TabsTrigger value="expired" data-testid="tab-expired">
                Expiradas ({segments.expired.length})
              </TabsTrigger>
              <TabsTrigger value="recently_activated" data-testid="tab-recent">
                Recien activadas ({segments.recently_activated.length})
              </TabsTrigger>
            </TabsList>

            {/* NEVER ACTIVATED */}
            <TabsContent value="never_activated">
              {segments.never_activated.length === 0 ? (
                <EmptyState msg="Todas las opticas ya activaron. Excelente!" />
              ) : (
                <ListTable
                  rows={segments.never_activated}
                  extra={(c) => (
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-[11px] font-medium border ${
                      c.days_since_created >= 23 ? 'bg-amber-100 text-amber-800 border-amber-200' : 'bg-slate-100 text-slate-700 border-slate-200'
                    }`}>
                      Hace {c.days_since_created}d
                    </span>
                  )}
                  extraLabel="Dias sin activar"
                  action={(c) => (
                    <a
                      href={`mailto:${c.admin_email}?subject=Activa%20tu%20cuenta%20Cortexia&body=Hola%20${encodeURIComponent(c.admin_name || 'Administrador')}%2C%20tu%20optica%20${encodeURIComponent(c.name)}%20aun%20no%20ha%20sido%20activada.%20Te%20esperamos!`}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200"
                      data-testid={`email-${c._id}`}
                    >
                      <Mail className="w-3 h-3" /> Enviar email
                    </a>
                  )}
                />
              )}
            </TabsContent>

            {/* AT RISK */}
            <TabsContent value="at_risk">
              {segments.at_risk.length === 0 ? (
                <EmptyState msg="Ninguna optica en riesgo. Sigue asi!" />
              ) : (
                <ListTable
                  rows={segments.at_risk}
                  extra={(c) => (
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-[11px] font-medium border ${
                      c.days_since_last_login > 60 ? 'bg-red-100 text-red-800 border-red-200'
                        : c.days_since_last_login > 30 ? 'bg-orange-100 text-orange-800 border-orange-200'
                        : 'bg-amber-100 text-amber-800 border-amber-200'
                    }`}>
                      Hace {c.days_since_last_login}d sin login
                    </span>
                  )}
                  extraLabel="Ultimo acceso"
                  action={(c) => (
                    <a
                      href={`mailto:${c.admin_email}?subject=Te%20extranamos%20en%20Cortexia&body=Hola%20${encodeURIComponent(c.admin_name || 'Administrador')}%2C%20notamos%20que%20no%20has%20ingresado%20a%20${encodeURIComponent(c.name)}%20hace%20un%20tiempo.%20Necesitas%20ayuda%3F`}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200"
                      data-testid={`email-${c._id}`}
                    >
                      <Mail className="w-3 h-3" /> Contactar
                    </a>
                  )}
                />
              )}
            </TabsContent>

            {/* EXPIRED */}
            <TabsContent value="expired">
              {segments.expired.length === 0 ? (
                <EmptyState msg="Ninguna optica expirada. Excelente retencion!" />
              ) : (
                <ListTable
                  rows={segments.expired}
                  extra={(c) => (
                    <span className="inline-flex px-2 py-0.5 rounded-full text-[11px] font-medium border bg-red-100 text-red-800 border-red-200">
                      Desactivada hace {c.days_since_created - thresholds.deadline_days}d
                    </span>
                  )}
                  extraLabel="Estado"
                  action={(c) => (
                    <Button
                      size="sm"
                      className="bg-emerald-600 hover:bg-emerald-700 text-white h-7 px-3 text-xs"
                      onClick={() => setReactivateTarget(c)}
                      data-testid={`reactivate-${c._id}`}
                    >
                      <Sparkles className="w-3 h-3 mr-1" /> Reactivar
                    </Button>
                  )}
                />
              )}
            </TabsContent>

            {/* RECENTLY ACTIVATED */}
            <TabsContent value="recently_activated">
              {segments.recently_activated.length === 0 ? (
                <EmptyState msg="Aun no hay activaciones recientes." />
              ) : (
                <ListTable
                  rows={segments.recently_activated}
                  extra={(c) => (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border bg-green-100 text-green-800 border-green-200">
                      <CheckCircle2 className="w-3 h-3" /> {c.patients_count} paciente{c.patients_count !== 1 ? 's' : ''}
                    </span>
                  )}
                  extraLabel="Actividad"
                  action={(c) => (
                    <Badge variant="outline" className="text-xs">
                      Primer login: {c.admin_first_login_at?.slice(0, 10)}
                    </Badge>
                  )}
                />
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Reactivation Confirmation Dialog */}
      <AlertDialog open={!!reactivateTarget} onOpenChange={(o) => { if (!o) setReactivateTarget(null); }}>
        <AlertDialogContent data-testid="reactivate-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Reactivar {reactivateTarget?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              Se realizaran estas acciones:
            </AlertDialogDescription>
          </AlertDialogHeader>
          <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
            <li>La optica volvera a estar <strong>activa</strong>.</li>
            <li>El admin (<strong>{reactivateTarget?.admin_email}</strong>) recibira un email
                con un link para <strong>establecer una nueva contrasena</strong> (valido 24h).</li>
            <li>Los recordatorios previos se reiniciaran para que el ciclo empiece de cero.</li>
          </ul>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="reactivate-cancel">Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={doReactivate}
              disabled={reactivating}
              className="bg-emerald-600 hover:bg-emerald-700"
              data-testid="reactivate-confirm"
            >
              {reactivating ? 'Reactivando...' : 'Si, reactivar'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

const EmptyState = ({ msg }) => (
  <div className="text-center py-8 text-slate-500">
    <CheckCircle2 className="w-10 h-10 mx-auto mb-2 opacity-30" />
    <p className="text-sm">{msg}</p>
  </div>
);

const ListTable = ({ rows, extra, extraLabel, action }) => (
  <div className="overflow-x-auto">
    <table className="w-full">
      <thead className="bg-slate-50 text-xs uppercase text-slate-500 border-b border-slate-200">
        <tr>
          <th className="text-left py-2.5 px-3 font-semibold">Optica</th>
          <th className="text-left py-2.5 px-3 font-semibold">Admin</th>
          <th className="text-left py-2.5 px-3 font-semibold">Creada</th>
          <th className="text-left py-2.5 px-3 font-semibold">{extraLabel}</th>
          <th className="text-right py-2.5 px-3 font-semibold">Accion</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(c => (
          <CompanyRow key={c._id} c={c} extraCol={extra(c)} actionSlot={action(c)} />
        ))}
      </tbody>
    </table>
  </div>
);
