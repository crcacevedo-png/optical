import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, formatApiErrorDetail, useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import {
  ArrowLeft, Tent, Calendar, MapPin, Building2, User, Wallet, Package, Users,
  ShoppingCart, DollarSign, Target, Edit, Play, PauseCircle, CheckCircle2, XCircle, RotateCcw, AlertCircle, LayoutDashboard,
} from 'lucide-react';
import JornadaCashTab from './JornadaCashTab';
import JornadaInventoryTab from './JornadaInventoryTab';
import JornadaPatientsTab from './JornadaPatientsTab';
import JornadaPOSTab from './JornadaPOSTab';

const STATUS_META = {
  planificada: { label: 'Planificada', cls: 'bg-slate-100 text-slate-700 border-slate-200' },
  activa: { label: 'Activa', cls: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
  en_cierre: { label: 'En cierre', cls: 'bg-amber-100 text-amber-700 border-amber-200' },
  cerrada: { label: 'Cerrada', cls: 'bg-blue-100 text-blue-700 border-blue-200' },
  cancelada: { label: 'Cancelada', cls: 'bg-rose-100 text-rose-700 border-rose-200' },
};

const fmtQ = (n) => `Q ${(Number(n) || 0).toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtDate = (iso) => (iso ? new Date(iso + 'T00:00:00').toLocaleDateString('es-GT', { day: '2-digit', month: 'short', year: 'numeric' }) : '');

export default function JornadaPanelPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionModal, setActionModal] = useState(null); // 'cancel' | 'reopen' | null
  const [reason, setReason] = useState('');
  const [processing, setProcessing] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.get(`/api/jornadas/${id}/summary`);
      setData(res.data);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
      if (err.response?.status === 404) navigate('/jornadas');
    } finally {
      setLoading(false);
    }
  }, [id, navigate]);

  useEffect(() => { load(); }, [load]);

  const doAction = async (action, body = null) => {
    setProcessing(true);
    try {
      const res = await api.post(`/api/jornadas/${id}/${action}`, body || {});
      toast.success(res.data.message || 'Accion realizada');
      if (res.data.warnings?.length) {
        res.data.warnings.forEach((w) => toast.warning(w));
      }
      setActionModal(null);
      setReason('');
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setProcessing(false);
    }
  };

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
      </div>
    );
  }

  const j = data.jornada;
  const kpis = data.kpis;
  const meta = STATUS_META[j.status] || STATUS_META.planificada;
  const isAdmin = user?.role === 'admin' || user?.role === 'superadmin';
  const canEdit = isAdmin && (j.status === 'planificada' || j.status === 'activa');

  return (
    <div className="space-y-6" data-testid="jornada-panel-page">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div className="flex items-start gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate('/jornadas')} data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Tent className="w-5 h-5 text-pine-700" />
              <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">{j.name}</h1>
              <Badge variant="outline" className={meta.cls} data-testid="jornada-status-badge">{meta.label}</Badge>
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
              <span className="flex items-center gap-1"><Calendar className="w-3.5 h-3.5" /> {fmtDate(j.start_date)} — {fmtDate(j.end_date)}</span>
              <span className="flex items-center gap-1"><Building2 className="w-3.5 h-3.5" /> {j.responsible_branch_name || '—'}</span>
              {j.location && <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> {j.location}</span>}
              {j.manager_name && <span className="flex items-center gap-1"><User className="w-3.5 h-3.5" /> {j.manager_name}</span>}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {canEdit && (
            <Button variant="outline" size="sm" onClick={() => navigate(`/jornadas/${id}/edit`)} data-testid="edit-btn">
              <Edit className="w-4 h-4 mr-1.5" /> Editar
            </Button>
          )}
          {isAdmin && j.status === 'planificada' && (
            <>
              <Button size="sm" onClick={() => doAction('activate')} disabled={processing} className="bg-emerald-600 hover:bg-emerald-700" data-testid="activate-btn">
                <Play className="w-4 h-4 mr-1.5" /> Activar
              </Button>
              <Button size="sm" variant="outline" onClick={() => setActionModal('cancel')} data-testid="cancel-btn">
                <XCircle className="w-4 h-4 mr-1.5" /> Cancelar
              </Button>
            </>
          )}
          {isAdmin && j.status === 'activa' && (
            <Button size="sm" onClick={() => doAction('start-closing')} disabled={processing} className="bg-amber-600 hover:bg-amber-700" data-testid="start-closing-btn">
              <PauseCircle className="w-4 h-4 mr-1.5" /> Iniciar cierre
            </Button>
          )}
          {isAdmin && j.status === 'en_cierre' && (
            <Button size="sm" onClick={() => doAction('close')} disabled={processing} className="bg-blue-600 hover:bg-blue-700" data-testid="close-btn">
              <CheckCircle2 className="w-4 h-4 mr-1.5" /> Finalizar cierre
            </Button>
          )}
          {user?.role === 'superadmin' && j.status === 'cerrada' && (
            <Button size="sm" variant="outline" onClick={() => setActionModal('reopen')} data-testid="reopen-btn">
              <RotateCcw className="w-4 h-4 mr-1.5" /> Reabrir
            </Button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="resumen" className="w-full" data-testid="jornada-tabs">
        <TabsList className="grid grid-cols-5 w-full lg:w-auto lg:inline-flex">
          <TabsTrigger value="resumen" data-testid="tab-resumen"><LayoutDashboard className="w-3.5 h-3.5 mr-1.5" /> Resumen</TabsTrigger>
          <TabsTrigger value="inventario" data-testid="tab-inventario"><Package className="w-3.5 h-3.5 mr-1.5" /> Inventario</TabsTrigger>
          <TabsTrigger value="pacientes" data-testid="tab-pacientes"><Users className="w-3.5 h-3.5 mr-1.5" /> Pacientes</TabsTrigger>
          <TabsTrigger value="pos" data-testid="tab-pos" disabled={j.status !== 'activa'}><ShoppingCart className="w-3.5 h-3.5 mr-1.5" /> POS</TabsTrigger>
          <TabsTrigger value="caja" data-testid="tab-caja"><Wallet className="w-3.5 h-3.5 mr-1.5" /> Caja</TabsTrigger>
        </TabsList>

        <TabsContent value="resumen" className="mt-4 space-y-4">
          {/* KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" data-testid="jornada-kpis">
            <KpiCard icon={ShoppingCart} label="Vendido" value={fmtQ(kpis.total_sold)} subtitle={`${kpis.sales_count} venta(s)`} color="from-emerald-500 to-teal-500" />
            <KpiCard icon={Users} label="Pacientes" value={kpis.patients_count} subtitle={kpis.goal_patients ? `Meta: ${kpis.goal_patients}` : '—'} color="from-blue-500 to-blue-600" pct={kpis.goal_patients_pct} />
            <KpiCard icon={Wallet} label="Saldo caja" value={fmtQ(kpis.cash_balance)} subtitle="Efectivo neto" color="from-amber-500 to-orange-500" />
            <KpiCard icon={Target} label="Meta comercial" value={kpis.goal_amount ? fmtQ(kpis.goal_amount) : '—'} subtitle={kpis.goal_amount_pct != null ? `${kpis.goal_amount_pct}% alcanzado` : 'Sin meta'} color="from-violet-500 to-purple-500" pct={kpis.goal_amount_pct} />
          </div>

          {/* Config summary + Descripcion */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card className="border-slate-200/80 lg:col-span-2" data-testid="jornada-config">
              <CardHeader className="pb-3"><CardTitle className="text-base font-heading">Configuracion</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm">
                <ConfigRow icon={Wallet} label="Caja">
                  {j.cash_config?.mode === 'own' ? (
                    <>Caja propia · Fondo inicial {fmtQ(j.cash_config?.initial_fund)}</>
                  ) : 'Caja de la sucursal'}
                </ConfigRow>
                <ConfigRow icon={Package} label="Inventario">
                  <div className="flex flex-wrap gap-1.5">
                    {j.inventory_config?.use_branch_stock && <Badge variant="secondary" className="bg-blue-50 text-blue-700 border-blue-200">Traslado sucursal</Badge>}
                    {j.inventory_config?.use_consignment && <Badge variant="secondary" className="bg-amber-50 text-amber-700 border-amber-200">Consignacion</Badge>}
                    {!j.inventory_config?.use_branch_stock && !j.inventory_config?.use_consignment && <span className="text-slate-400">Sin configurar</span>}
                  </div>
                </ConfigRow>
                {j.price_list_discount_percent != null && (
                  <ConfigRow icon={DollarSign} label="Descuento global">{j.price_list_discount_percent}%</ConfigRow>
                )}
                {j.partner_entity && (
                  <ConfigRow icon={Building2} label="Entidad aliada">{j.partner_entity}</ConfigRow>
                )}
                {(j.address || j.municipality || j.department) && (
                  <ConfigRow icon={MapPin} label="Direccion">
                    {[j.address, j.municipality, j.department].filter(Boolean).join(', ')}
                  </ConfigRow>
                )}
              </CardContent>
            </Card>

            <Card className="border-slate-200/80" data-testid="jornada-notes">
              <CardHeader className="pb-3"><CardTitle className="text-base font-heading">Notas internas</CardTitle></CardHeader>
              <CardContent>
                {j.description ? (
                  <p className="text-sm text-slate-600 whitespace-pre-wrap">{j.description}</p>
                ) : (
                  <p className="text-sm text-slate-400 italic">Sin notas</p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="inventario" className="mt-4"><JornadaInventoryTab jornada={j} reload={load} /></TabsContent>
        <TabsContent value="pacientes" className="mt-4"><JornadaPatientsTab jornada={j} reload={load} /></TabsContent>
        <TabsContent value="pos" className="mt-4"><JornadaPOSTab jornada={j} reload={load} /></TabsContent>
        <TabsContent value="caja" className="mt-4"><JornadaCashTab jornada={j} reload={load} /></TabsContent>
      </Tabs>

      {/* Cancel / Reopen modal */}
      <Dialog open={actionModal !== null} onOpenChange={(o) => { if (!o) { setActionModal(null); setReason(''); } }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{actionModal === 'cancel' ? 'Cancelar jornada' : 'Reabrir jornada'}</DialogTitle>
            <DialogDescription>
              {actionModal === 'cancel'
                ? 'Esta accion cambia el estado a Cancelada. Solo se puede cancelar si no hay ventas ni pacientes registrados. Queda registrado en auditoria.'
                : 'Reabrir una jornada cerrada queda registrado en auditoria con tu usuario y motivo.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label>Motivo *</Label>
            <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Escribe el motivo..." data-testid="reason-input" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setActionModal(null); setReason(''); }}>Cerrar</Button>
            <Button
              className={actionModal === 'cancel' ? 'bg-rose-600 hover:bg-rose-700' : 'bg-pine-900 hover:bg-pine-800'}
              disabled={!reason.trim() || processing}
              onClick={() => doAction(actionModal, { reason })}
              data-testid="confirm-action-btn"
            >
              {processing ? 'Procesando...' : (actionModal === 'cancel' ? 'Cancelar jornada' : 'Reabrir')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function KpiCard({ icon: Icon, label, value, subtitle, color, pct }) {
  return (
    <div className="bg-white border border-slate-200/80 rounded-xl p-4" data-testid={`kpi-${label.toLowerCase().replace(/\s+/g,'-')}`}>
      <div className="flex items-center gap-2.5 mb-1.5">
        <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${color} flex items-center justify-center`}>
          <Icon className="w-4 h-4 text-white" />
        </div>
        <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">{label}</p>
      </div>
      <p className="font-heading text-2xl font-bold text-slate-900 leading-tight">{value}</p>
      {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      {pct != null && (
        <div className="mt-2 h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div className="h-full bg-gradient-to-r from-pine-600 to-pine-500 transition-all" style={{ width: `${Math.min(100, pct)}%` }} />
        </div>
      )}
    </div>
  );
}

function ConfigRow({ icon: Icon, label, children }) {
  return (
    <div className="flex items-start gap-2.5">
      <Icon className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-slate-400 uppercase tracking-wide">{label}</p>
        <div className="text-slate-700">{children}</div>
      </div>
    </div>
  );
}
