import React, { useState, useEffect } from 'react';
import { api } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import {
  Building2, Users, GitBranch, DollarSign, TrendingUp, TrendingDown, AlertTriangle,
  CreditCard, ArrowRight, Crown, UserCheck, ShoppingBag, Activity, BarChart3,
  Package, ShoppingCart, Truck, Zap, ArrowUpRight, ArrowDownRight
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, AreaChart, Area
} from 'recharts';

const PIE_COLORS = ['#64748B', '#3B82F6', '#F59E0B', '#10B981', '#8B5CF6', '#EF4444'];
const FUNNEL_COLORS = { free: '#94A3B8', basic: '#3B82F6', enterprise: '#F59E0B' };
const MODULE_COLORS = { Inventario: '#0F4C3A', Ventas: '#3B82F6', Proveedores: '#8B5CF6', Finanzas: '#F59E0B' };

export default function SuperAdminDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/api/superadmin/dashboard')
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
      </div>
    );
  }

  const {
    totals, companies_by_plan, estimated_revenue, arpu, churn_rate,
    revenue_by_plan, funnel, patient_growth, engagement,
    top_companies, module_usage, platform_volume,
    companies_at_limit, recent_plan_changes, new_companies_month
  } = data;

  return (
    <div className="space-y-6" data-testid="superadmin-dashboard">
      <div>
        <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Dashboard SaaS</h1>
        <p className="text-slate-500 mt-1">Metricas de la plataforma Cortexia Optical</p>
      </div>

      {/* === ROW 1: Revenue & Key KPIs === */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <KpiCard icon={DollarSign} iconBg="bg-emerald-50" iconColor="text-emerald-600"
          value={`$${estimated_revenue.toLocaleString()}`} label="MRR" testid="kpi-mrr" />
        <KpiCard icon={Building2} iconBg="bg-blue-50" iconColor="text-blue-600"
          value={totals.companies} label="Opticas activas" testid="kpi-companies"
          badge={new_companies_month > 0 ? `+${new_companies_month}` : null} />
        <KpiCard icon={Users} iconBg="bg-green-50" iconColor="text-green-600"
          value={totals.patients.toLocaleString()} label="Pacientes" testid="kpi-patients" />
        <KpiCard icon={Crown} iconBg="bg-amber-50" iconColor="text-amber-600"
          value={`Q${arpu}`} label="ARPU" testid="kpi-arpu" />
        <KpiCard icon={TrendingDown} iconBg="bg-red-50" iconColor="text-red-500"
          value={`${churn_rate}%`} label="Churn rate" testid="kpi-churn" />
      </div>

      {/* === ROW 2: Engagement Mini Cards === */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MiniCard icon={Activity} color="text-blue-600" bg="bg-blue-50"
          value={engagement.active_7d} label="Activos 7 dias" total={engagement.total_users} testid="eng-7d" />
        <MiniCard icon={Activity} color="text-green-600" bg="bg-green-50"
          value={engagement.active_30d} label="Activos 30 dias" total={engagement.total_users} testid="eng-30d" />
        <MiniCard icon={ShoppingBag} color="text-purple-600" bg="bg-purple-50"
          value={`Q${platform_volume.sales_volume_month.toLocaleString()}`} label="Ventas del mes" testid="vol-month" />
        <MiniCard icon={UserCheck} color="text-slate-600" bg="bg-slate-50"
          value={platform_volume.avg_patients_per_company} label="Pac. promedio/optica" testid="avg-patients" />
      </div>

      {/* === ROW 3: Charts === */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Pie: Companies by Plan */}
        <Card className="border-slate-200/80">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-600">Opticas por Plan</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <ResponsiveContainer width="100%" height={210}>
              <PieChart>
                <Pie data={companies_by_plan} dataKey="value" nameKey="name" cx="50%" cy="50%"
                  outerRadius={72} innerRadius={38} paddingAngle={3}
                  label={({ name, value }) => `${name} (${value})`}>
                  {companies_by_plan.map((entry, i) => (
                    <Cell key={`pie-${entry.name}`} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => [`${v} opticas`, 'Cantidad']} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Bar: Patient Growth */}
        <Card className="border-slate-200/80 lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-600">Crecimiento de Pacientes (6 meses)</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <ResponsiveContainer width="100%" height={210}>
              <AreaChart data={patient_growth}>
                <defs>
                  <linearGradient id="patientGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0F4C3A" stopOpacity={0.15}/>
                    <stop offset="95%" stopColor="#0F4C3A" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => [`${v} pacientes`, 'Nuevos']} />
                <Area type="monotone" dataKey="count" stroke="#0F4C3A" strokeWidth={2} fill="url(#patientGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* === ROW 4: Revenue + Funnel === */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue by Plan */}
        <Card className="border-slate-200/80">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-600">Revenue por Plan</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {revenue_by_plan.length > 0 ? (
              <ResponsiveContainer width="100%" height={190}>
                <BarChart data={revenue_by_plan} layout="vertical" barSize={22}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `Q${v}`} />
                  <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} width={80} />
                  <Tooltip formatter={(v) => [`$${v.toLocaleString()}`, 'Revenue']} />
                  <Bar dataKey="value" fill="#F59E0B" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <p className="text-sm text-slate-400 text-center py-8">Sin revenue</p>}
          </CardContent>
        </Card>

        {/* Plan Conversion Funnel */}
        <Card className="border-slate-200/80">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-600">Funnel de Conversion</CardTitle>
          </CardHeader>
          <CardContent className="pt-0 space-y-3">
            <div className="space-y-2">
              {[
                { label: 'Free', value: funnel.free, color: FUNNEL_COLORS.free, max: Math.max(funnel.free, funnel.basic, funnel.enterprise, 1) },
                { label: 'Basic', value: funnel.basic, color: FUNNEL_COLORS.basic, max: Math.max(funnel.free, funnel.basic, funnel.enterprise, 1) },
                { label: 'Enterprise', value: funnel.enterprise, color: FUNNEL_COLORS.enterprise, max: Math.max(funnel.free, funnel.basic, funnel.enterprise, 1) },
              ].map(f => (
                <div key={f.label} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-slate-700">{f.label}</span>
                    <span className="font-bold text-slate-900">{f.value}</span>
                  </div>
                  <div className="h-5 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-500" style={{
                      width: `${Math.max((f.value / f.max) * 100, 4)}%`,
                      backgroundColor: f.color
                    }} />
                  </div>
                </div>
              ))}
            </div>
            <div className="flex items-center justify-between pt-2 border-t text-xs">
              <span className="flex items-center gap-1 text-green-600">
                <ArrowUpRight className="w-3.5 h-3.5" /> {funnel.upgrades_total} upgrades
              </span>
              <span className="flex items-center gap-1 text-red-500">
                <ArrowDownRight className="w-3.5 h-3.5" /> {funnel.downgrades_total} downgrades
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* === ROW 5: Top Companies + Module Usage === */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top 5 Companies */}
        <Card className="border-slate-200/80">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-600">Top 5 Opticas por Actividad</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {top_companies.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-6">Sin datos</p>
            ) : (
              <div className="space-y-2">
                {top_companies.map((c, i) => (
                  <div key={`top-${c.name}-${i}`} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-slate-50 transition-colors" data-testid={`top-company-${i}`}>
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                      i === 0 ? 'bg-amber-100 text-amber-700' : i === 1 ? 'bg-slate-200 text-slate-600' : i === 2 ? 'bg-orange-100 text-orange-700' : 'bg-slate-100 text-slate-500'
                    }`}>{i + 1}</div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm text-slate-800 truncate">{c.name}</p>
                      <div className="flex gap-3 text-[10px] text-slate-400 mt-0.5">
                        <span>{c.patients} pac</span>
                        <span>{c.sales} ventas</span>
                        <span>{c.consultations} cons</span>
                      </div>
                    </div>
                    <Badge className="bg-slate-100 text-slate-500 text-[10px]">{c.plan}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Module Usage */}
        <Card className="border-slate-200/80">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-600">Uso de Modulos Opcionales</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <ResponsiveContainer width="100%" height={190}>
              <BarChart data={module_usage} barSize={30}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip formatter={(v) => [`${v} opticas`, 'Tienen acceso']} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {module_usage.map((entry, i) => (
                    <Cell key={`mod-${entry.name}`} fill={MODULE_COLORS[entry.name] || PIE_COLORS[i]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <p className="text-[10px] text-slate-400 text-center mt-1">Opticas con acceso al modulo segun su plan</p>
          </CardContent>
        </Card>
      </div>

      {/* === ROW 6: Alerts + Recent Changes === */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Companies at Limit */}
        <Card className={`border-slate-200/80 ${companies_at_limit.length > 0 ? 'border-amber-200' : ''}`}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-600 flex items-center gap-2">
              {companies_at_limit.length > 0 && <AlertTriangle className="w-4 h-4 text-amber-500" />}
              Opticas Cerca del Limite ({companies_at_limit.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {companies_at_limit.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-6">Sin alertas</p>
            ) : (
              <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                {companies_at_limit.map((c, i) => (
                  <div key={`limit-${c.name}`} className="p-2.5 rounded-lg border border-amber-100 bg-amber-50/50" data-testid={`limit-alert-${i}`}>
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm text-slate-800">{c.name}</span>
                      <Badge className="bg-slate-100 text-slate-600 text-[10px]">{c.plan_name}</Badge>
                    </div>
                    <div className="flex gap-4 mt-1 text-xs">
                      {c.patients_warning && (
                        <span className={c.patients_percent >= 100 ? 'text-red-600 font-medium' : 'text-amber-600'}>
                          {c.patients}/{c.max_patients} pac ({c.patients_percent}%)
                        </span>
                      )}
                      {c.branches_warning && (
                        <span className={c.branches_percent >= 100 ? 'text-red-600 font-medium' : 'text-amber-600'}>
                          {c.branches}/{c.max_branches} suc ({c.branches_percent}%)
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Plan Changes */}
        <Card className="border-slate-200/80">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-600">Cambios de Plan Recientes</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {recent_plan_changes.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-6">Sin cambios</p>
            ) : (
              <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                {recent_plan_changes.map((h, i) => (
                  <div key={h._id || i} className="flex items-center gap-3 p-2 rounded-lg hover:bg-slate-50 transition-colors" data-testid={`recent-change-${i}`}>
                    <div className="w-6 h-6 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0">
                      <CreditCard className="w-3 h-3 text-blue-600" />
                    </div>
                    <div className="flex-1 flex items-center gap-1.5 flex-wrap min-w-0">
                      <span className="font-medium text-xs text-slate-800 truncate">{h.company_name}</span>
                      <Badge className="bg-slate-100 text-slate-500 text-[9px]">{h.old_plan_name || '?'}</Badge>
                      <ArrowRight className="w-2.5 h-2.5 text-slate-400" />
                      <Badge className="bg-pine-100 text-pine-700 text-[9px]">{h.new_plan_name}</Badge>
                    </div>
                    <span className="text-[10px] text-slate-400 flex-shrink-0">{h.changed_at?.slice(0, 10)}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* === CSP Violations Widget === */}
      <CspViolationsWidget />
    </div>
  );
}

function CspViolationsWidget() {
  const [violations, setViolations] = useState(null);
  const [blockedIps, setBlockedIps] = useState({ items: [], active: 0 });
  const [unblocking, setUnblocking] = useState(null);

  const load = async () => {
    try {
      const [v, b] = await Promise.all([
        api.get('/api/security/csp-violations?limit=50&hours=24'),
        api.get('/api/security/blocked-ips?limit=20'),
      ]);
      setViolations(v.data);
      setBlockedIps(b.data);
    } catch {
      setViolations({ items: [], total: 0, breakdown_by_directive: {}, breakdown_by_blocked_uri: {} });
    }
  };

  useEffect(() => { load(); }, []);

  const doUnblock = async (ip) => {
    if (!window.confirm(`Desbloquear ${ip}?`)) return;
    setUnblocking(ip);
    try {
      await api.delete(`/api/security/blocked-ips/${encodeURIComponent(ip)}`);
      await load();
    } catch (e) {
      alert('Error al desbloquear: ' + (e?.response?.data?.detail || e.message));
    } finally {
      setUnblocking(null);
    }
  };

  if (!violations) return null;
  const dirs = violations.breakdown_by_directive || {};
  const dirEntries = Object.entries(dirs).sort((a, b) => b[1] - a[1]);
  const isEmpty = violations.total === 0;
  const activeIps = (blockedIps.items || []).filter(b => b.active);
  return (
    <Card className={`border-slate-200/80 ${activeIps.length > 0 ? 'border-red-300' : (isEmpty ? '' : 'border-amber-200')}`} data-testid="csp-widget">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-slate-600 flex items-center gap-2">
          <Activity className={`w-4 h-4 ${activeIps.length > 0 ? 'text-red-500' : (isEmpty ? 'text-slate-400' : 'text-amber-500')}`} />
          Violaciones CSP (ultimas 24h) — {violations.total}
          {activeIps.length > 0 && (
            <span className="ml-auto inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-100 border border-red-200 text-xs font-bold text-red-700">
              {activeIps.length} IP{activeIps.length !== 1 ? 's' : ''} bloqueada{activeIps.length !== 1 ? 's' : ''}
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0 space-y-3">
        {isEmpty ? (
          <p className="text-sm text-slate-400 text-center py-4">
            Sin violaciones de CSP en las ultimas 24h.
          </p>
        ) : (
          <>
            <div className="flex flex-wrap gap-1.5">
              {dirEntries.slice(0, 8).map(([d, c]) => (
                <span key={d} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-xs">
                  <span className="font-mono text-amber-900">{d}</span>
                  <span className="font-bold text-amber-700">{c}</span>
                </span>
              ))}
            </div>
            <div className="max-h-[140px] overflow-y-auto space-y-1.5 pr-1">
              {violations.items.slice(0, 10).map((v) => (
                <div key={v._id} className="flex items-center gap-3 p-2 rounded-lg bg-slate-50 text-xs" data-testid={`csp-violation-${v._id}`}>
                  <span className="font-mono text-amber-800 truncate max-w-[140px]">{v.violated_directive}</span>
                  <span className="text-slate-500 truncate flex-1" title={v.blocked_uri}>{v.blocked_uri || '(inline)'}</span>
                  {v.ip && <span className="text-slate-400 font-mono text-[10px]">{v.ip}</span>}
                  <span className="text-slate-400 whitespace-nowrap">{v.created_at?.slice(11, 16)}</span>
                </div>
              ))}
            </div>
          </>
        )}
        {/* Sub-panel: IPs bloqueadas activas */}
        {activeIps.length > 0 && (
          <div className="pt-3 border-t border-slate-200">
            <p className="text-xs font-semibold text-slate-500 mb-2 uppercase">IPs auto-bloqueadas</p>
            <div className="space-y-1.5">
              {activeIps.map((b) => (
                <div key={b._id} className="flex items-center gap-2 p-2 rounded-lg bg-red-50 border border-red-100 text-xs" data-testid={`blocked-ip-${b.ip}`}>
                  <span className="font-mono font-semibold text-red-900">{b.ip}</span>
                  <span className="text-red-700 flex-1 truncate">{b.reason}</span>
                  <span className="text-red-500 whitespace-nowrap">expira {b.blocked_until?.slice(11, 16)}</span>
                  <button
                    onClick={() => doUnblock(b.ip)}
                    disabled={unblocking === b.ip}
                    className="text-[10px] px-2 py-0.5 rounded bg-white border border-red-200 text-red-700 hover:bg-red-100"
                    data-testid={`unblock-${b.ip}`}
                  >
                    {unblocking === b.ip ? '...' : 'Desbloquear'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* === Reusable Components === */
function KpiCard({ icon: Icon, iconBg, iconColor, value, label, testid, badge }) {
  return (
    <Card className="border-slate-200/80" data-testid={testid}>
      <CardContent className="p-4">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-xl ${iconBg}`}>
            <Icon className={`w-5 h-5 ${iconColor}`} />
          </div>
          <div>
            <p className="text-xl font-bold text-slate-900">{value}</p>
            <p className="text-[11px] text-slate-500">{label}</p>
          </div>
        </div>
        {badge && (
          <p className="text-[10px] text-green-600 mt-1.5 flex items-center gap-0.5">
            <TrendingUp className="w-3 h-3" /> {badge} este mes
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function MiniCard({ icon: Icon, color, bg, value, label, total, testid }) {
  return (
    <Card className="border-slate-200/80" data-testid={testid}>
      <CardContent className="p-3.5 flex items-center gap-3">
        <div className={`p-2 rounded-lg ${bg}`}><Icon className={`w-4 h-4 ${color}`} /></div>
        <div>
          <p className="text-lg font-bold text-slate-900">{value}</p>
          <p className="text-[10px] text-slate-500">{label}{total ? ` / ${total}` : ''}</p>
        </div>
      </CardContent>
    </Card>
  );
}
