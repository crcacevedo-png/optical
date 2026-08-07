import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/progress';
import { Badge } from '../components/ui/badge';
import {
  Activity, Database, Server, Zap, TrendingUp, AlertTriangle,
  CheckCircle2, RefreshCw, HardDrive, Cpu, MemoryStick, Clock, Info
} from 'lucide-react';

const SIGNAL_STYLES = {
  info: { icon: Info, cls: 'bg-blue-50 border-blue-200 text-blue-800' },
  warning: { icon: AlertTriangle, cls: 'bg-amber-50 border-amber-200 text-amber-800' },
  critical: { icon: AlertTriangle, cls: 'bg-red-50 border-red-200 text-red-800' },
};

const fmt = (n) => (n ?? 0).toLocaleString('es-GT');
const fmtSecs = (s) => {
  if (!s) return '0s';
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${sec}s` : `${sec}s`;
};

function StatCard({ icon: Icon, title, value, subtitle, color = 'slate', testId }) {
  const colorMap = {
    slate: 'bg-slate-100 text-slate-700',
    blue: 'bg-blue-100 text-blue-700',
    emerald: 'bg-emerald-100 text-emerald-700',
    amber: 'bg-amber-100 text-amber-700',
    violet: 'bg-violet-100 text-violet-700',
  };
  return (
    <Card className="border-slate-200/80" data-testid={testId}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
            <p className="font-heading text-2xl font-bold text-slate-900 mt-1 truncate">{value}</p>
            {subtitle && <p className="text-xs text-slate-400 mt-1">{subtitle}</p>}
          </div>
          <div className={`p-2.5 rounded-lg ${colorMap[color]} shrink-0 ml-3`}>
            <Icon className="w-5 h-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ProgressRow({ label, percent, subtitle, warn = 80, danger = 90 }) {
  const color = percent >= danger ? 'bg-red-500' : percent >= warn ? 'bg-amber-500' : 'bg-emerald-500';
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <p className="text-sm text-slate-700 font-medium">{label}</p>
        <p className="text-sm font-bold text-slate-900">{percent}%</p>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} transition-all`} style={{ width: `${Math.min(percent, 100)}%` }} />
      </div>
      {subtitle && <p className="text-[11px] text-slate-500 mt-1">{subtitle}</p>}
    </div>
  );
}

export default function HealthMetricsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const load = useCallback(async () => {
    try {
      setRefreshing(true);
      const { data: d } = await api.get('/api/health/metrics');
      setData(d);
      setLastUpdate(new Date());
    } catch (err) {
      // silent
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, [autoRefresh, load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="health-loading">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
      </div>
    );
  }
  if (!data) return null;

  const collections = Object.entries(data.collection_counts || {})
    .filter(([, v]) => v !== null)
    .sort((a, b) => (b[1] || 0) - (a[1] || 0));

  const memHost = data.system?.memory_percent ?? 0;
  const diskHost = data.system?.disk_percent ?? 0;
  const cpuHost = data.system?.cpu_percent ?? 0;

  return (
    <div className="space-y-6" data-testid="health-metrics-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-teal-500 flex items-center justify-center">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Metricas del Sistema</h1>
          </div>
          <p className="text-slate-500 text-sm">
            Monitoreo en tiempo real de la infraestructura, base de datos y cache.
            {lastUpdate && <span className="ml-2 text-slate-400">· Ultimo update: {lastUpdate.toLocaleTimeString('es-GT')}</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant={autoRefresh ? 'default' : 'outline'}
            size="sm"
            onClick={() => setAutoRefresh(!autoRefresh)}
            data-testid="toggle-auto-refresh"
          >
            <Clock className="w-4 h-4 mr-1.5" />
            Auto {autoRefresh ? 'ON' : 'OFF'}
          </Button>
          <Button variant="outline" size="sm" onClick={load} disabled={refreshing} data-testid="refresh-metrics">
            <RefreshCw className={`w-4 h-4 mr-1.5 ${refreshing ? 'animate-spin' : ''}`} />
            Refrescar
          </Button>
        </div>
      </div>

      {/* Signals */}
      {data.signals?.length > 0 && (
        <div className="space-y-2" data-testid="health-signals">
          {data.signals.map((s, i) => {
            const style = SIGNAL_STYLES[s.level] || SIGNAL_STYLES.info;
            const Icon = style.icon;
            return (
              <div key={i} className={`${style.cls} border rounded-lg p-3 flex items-start gap-2.5`}>
                <Icon className="w-5 h-5 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-xs font-bold uppercase tracking-wide opacity-70">{s.level}</p>
                  <p className="text-sm font-medium">{s.msg}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
      {data.signals?.length === 0 && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 flex items-center gap-2.5" data-testid="all-green">
          <CheckCircle2 className="w-5 h-5 text-emerald-600" />
          <p className="text-sm text-emerald-800 font-medium">Todos los sistemas operando dentro de rangos normales.</p>
        </div>
      )}

      {/* Top KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Database}
          title="Ping MongoDB"
          value={`${data.mongo?.ping_ms ?? 0} ms`}
          subtitle={data.mongo?.reachable ? 'Conectado' : 'Sin conexion'}
          color={data.mongo?.reachable ? 'emerald' : 'amber'}
          testId="kpi-mongo-ping"
        />
        <StatCard
          icon={Server}
          title="Uptime del Backend"
          value={fmtSecs(data.process?.uptime_seconds)}
          subtitle={`PID ${data.process?.pid} · ${data.process?.threads} threads`}
          color="blue"
          testId="kpi-uptime"
        />
        <StatCard
          icon={MemoryStick}
          title="RAM del Backend"
          value={`${data.process?.rss_mb} MB`}
          subtitle={`Host: ${data.system?.memory_used_mb} / ${data.system?.memory_total_mb} MB`}
          color="violet"
          testId="kpi-ram"
        />
        <StatCard
          icon={TrendingUp}
          title="Logins ultimas 24h"
          value={fmt(data.activity_24h?.logins_24h)}
          subtitle={`${fmt(data.activity_24h?.failed_logins_24h)} fallidos`}
          color="emerald"
          testId="kpi-logins"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Host resources */}
        <Card className="border-slate-200/80 lg:col-span-2" data-testid="host-resources">
          <CardHeader className="pb-3">
            <CardTitle className="font-heading text-lg flex items-center gap-2">
              <Cpu className="w-5 h-5 text-slate-600" />
              Recursos del Host (Pod)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <ProgressRow
              label="CPU"
              percent={Math.round(cpuHost)}
              subtitle={`${data.system?.cpu_count} cores disponibles`}
            />
            <ProgressRow
              label="Memoria"
              percent={Math.round(memHost)}
              subtitle={`${fmt(data.system?.memory_used_mb)} MB / ${fmt(data.system?.memory_total_mb)} MB`}
            />
            <ProgressRow
              label="Disco"
              percent={Math.round(diskHost)}
              subtitle={
                data.system?.disk_is_shared_node
                  ? `Nodo K8s compartido · Datos de tu app: ${fmt(data.system?.app_data_mb || 0)} MB`
                  : `${data.system?.disk_used_gb} GB / ${data.system?.disk_total_gb} GB`
              }
            />
          </CardContent>
        </Card>

        {/* Cache stats */}
        <Card className="border-slate-200/80" data-testid="cache-stats">
          <CardHeader className="pb-3">
            <CardTitle className="font-heading text-lg flex items-center gap-2">
              <Zap className="w-5 h-5 text-amber-500" />
              Cache
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {Object.entries(data.cache || {}).map(([name, s]) => (
              <div key={name} className="border-l-2 border-amber-300 pl-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-0.5">
                  {name.replace('_cache', '').replace('_', ' ')}
                </p>
                <p className="font-heading text-lg font-bold text-slate-900">{s.hit_rate}% hit rate</p>
                <p className="text-[11px] text-slate-500">
                  {fmt(s.hits)} hits · {fmt(s.misses)} misses · {s.size} keys · TTL {s.default_ttl_seconds}s
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* MongoDB stats */}
        <Card className="border-slate-200/80" data-testid="mongo-stats">
          <CardHeader className="pb-3">
            <CardTitle className="font-heading text-lg flex items-center gap-2">
              <Database className="w-5 h-5 text-emerald-600" />
              Base de Datos
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wide">Colecciones</p>
                <p className="font-bold text-slate-900 text-lg">{data.mongo?.collections ?? '-'}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wide">Documentos totales</p>
                <p className="font-bold text-slate-900 text-lg">{fmt(data.mongo?.objects_total)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wide">Datos</p>
                <p className="font-bold text-slate-900 text-lg">{data.mongo?.data_size_mb} MB</p>
              </div>
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wide">Indices</p>
                <p className="font-bold text-slate-900 text-lg">{data.mongo?.index_size_mb} MB</p>
              </div>
              <div className="col-span-2 pt-2 border-t border-slate-100 mt-1">
                <p className="text-xs text-slate-500 uppercase tracking-wide">Tamaño total en disco</p>
                <p className="font-bold text-slate-900 text-xl">{data.mongo?.total_size_mb} MB</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Activity 24h */}
        <Card className="border-slate-200/80" data-testid="activity-24h">
          <CardHeader className="pb-3">
            <CardTitle className="font-heading text-lg flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-blue-600" />
              Actividad últimas 24h
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2.5 text-sm">
              {[
                { k: 'logins_24h', label: 'Logins exitosos', color: 'emerald' },
                { k: 'failed_logins_24h', label: 'Logins fallidos', color: 'red' },
                { k: 'audit_events_24h', label: 'Eventos auditados', color: 'slate' },
                { k: 'new_users_24h', label: 'Nuevos usuarios', color: 'blue' },
                { k: 'sales_24h', label: 'Ventas registradas', color: 'violet' },
              ].map(({ k, label }) => (
                <div key={k} className="flex items-center justify-between py-1.5 border-b border-slate-100 last:border-0">
                  <p className="text-slate-600">{label}</p>
                  <p className="font-bold text-slate-900">{fmt(data.activity_24h?.[k])}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Collection counts */}
      <Card className="border-slate-200/80" data-testid="collection-counts">
        <CardHeader className="pb-3">
          <CardTitle className="font-heading text-lg flex items-center gap-2">
            <HardDrive className="w-5 h-5 text-slate-600" />
            Documentos por Colección
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {collections.map(([name, count]) => (
              <div key={name} className="flex items-center justify-between px-3 py-2 rounded-lg bg-slate-50 border border-slate-100">
                <p className="text-xs text-slate-600 truncate">{name}</p>
                <Badge variant="secondary" className="ml-2 shrink-0 font-mono">{fmt(count)}</Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
