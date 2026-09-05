import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import {
  Mail, RefreshCw, Send, CheckCircle2, Clock, XCircle, Loader2,
  Paperclip, Inbox, AlertTriangle,
} from 'lucide-react';
import { toast } from 'sonner';

const PAGE_SIZE = 50;

const STATUS_META = {
  sent: { label: 'Enviado', icon: CheckCircle2, cls: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
  pending: { label: 'Pendiente', icon: Clock, cls: 'bg-amber-100 text-amber-700 border-amber-200' },
  sending: { label: 'Enviando', icon: Loader2, cls: 'bg-blue-100 text-blue-700 border-blue-200' },
  failed: { label: 'Fallido', icon: XCircle, cls: 'bg-red-100 text-red-700 border-red-200' },
};

const TABS = [
  { key: 'all', label: 'Todos' },
  { key: 'pending', label: 'Pendientes' },
  { key: 'sending', label: 'Enviando' },
  { key: 'sent', label: 'Enviados' },
  { key: 'failed', label: 'Fallidos' },
];

const StatCard = ({ label, value, icon: Icon, color, testId }) => (
  <Card className={`border-l-4 ${color}`} data-testid={testId}>
    <CardContent className="p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500 font-semibold">{label}</p>
          <p className="text-2xl font-bold mt-1 text-slate-900">{value}</p>
        </div>
        <Icon className="w-5 h-5 text-slate-400" />
      </div>
    </CardContent>
  </Card>
);

const StatusBadge = ({ status }) => {
  const meta = STATUS_META[status] || { label: status, icon: Mail, cls: 'bg-slate-100 text-slate-600 border-slate-200' };
  const Icon = meta.icon;
  return (
    <Badge variant="outline" className={`gap-1 font-medium ${meta.cls}`} data-testid={`status-badge-${status}`}>
      <Icon className={`w-3 h-3 ${status === 'sending' ? 'animate-spin' : ''}`} />
      {meta.label}
    </Badge>
  );
};

const fmtDate = (iso) => {
  if (!iso) return '-';
  try {
    const d = new Date(iso);
    return d.toLocaleString('es-GT', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch { return String(iso).slice(0, 16); }
};

export default function EmailQueuePage() {
  const [stats, setStats] = useState({ total: 0, pending: 0, sending: 0, sent: 0, failed: 0 });
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [resendingId, setResendingId] = useState(null);
  const [retryingAll, setRetryingAll] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const params = { limit: PAGE_SIZE, skip: page * PAGE_SIZE };
      if (tab !== 'all') params.status = tab;
      if (search.trim()) params.search = search.trim();
      const [{ data: list }, { data: st }] = await Promise.all([
        api.get('/api/email-queue', { params }),
        api.get('/api/email-queue/stats'),
      ]);
      setItems(list.items || []);
      setTotal(list.total || 0);
      setStats(st || {});
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail) || 'Error al cargar la cola de correos');
    } finally {
      setLoading(false);
    }
  }, [tab, search, page]);

  useEffect(() => { load(); }, [load]);

  const handleResend = async (id) => {
    try {
      setResendingId(id);
      await api.post(`/api/email-queue/${id}/resend`);
      toast.success('Correo reencolado. Se enviará en segundo plano.');
      await load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail) || 'No se pudo reencolar');
    } finally {
      setResendingId(null);
    }
  };

  const handleRetryAll = async () => {
    try {
      setRetryingAll(true);
      const { data } = await api.post('/api/email-queue/retry-failed');
      toast.success(`${data.reenqueued || 0} correos fallidos reencolados.`);
      await load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail) || 'No se pudo reintentar');
    } finally {
      setRetryingAll(false);
    }
  };

  const onTabChange = (k) => { setPage(0); setTab(k); };
  const onSearchSubmit = (e) => { e.preventDefault(); setPage(0); load(); };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6" data-testid="email-queue-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Mail className="w-6 h-6 text-indigo-600" /> Cola de Correos
          </h1>
          <p className="text-sm text-slate-500 mt-1">Monitorea y reenvía los correos del sistema (bienvenidas, alertas, recordatorios, cotizaciones).</p>
        </div>
        <div className="flex items-center gap-2">
          {stats.failed > 0 && (
            <Button variant="outline" onClick={handleRetryAll} disabled={retryingAll}
              className="border-red-200 text-red-600 hover:bg-red-50" data-testid="retry-all-failed-btn">
              {retryingAll ? <Loader2 className="w-4 h-4 animate-spin" /> : <AlertTriangle className="w-4 h-4" />}
              Reintentar fallidos ({stats.failed})
            </Button>
          )}
          <Button variant="outline" onClick={load} disabled={loading} data-testid="refresh-queue-btn">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Actualizar
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatCard label="Total" value={stats.total ?? 0} icon={Inbox} color="border-slate-300" testId="stat-total" />
        <StatCard label="Enviados" value={stats.sent ?? 0} icon={CheckCircle2} color="border-emerald-400" testId="stat-sent" />
        <StatCard label="Pendientes" value={stats.pending ?? 0} icon={Clock} color="border-amber-400" testId="stat-pending" />
        <StatCard label="Enviando" value={stats.sending ?? 0} icon={Send} color="border-blue-400" testId="stat-sending" />
        <StatCard label="Fallidos" value={stats.failed ?? 0} icon={XCircle} color="border-red-400" testId="stat-failed" />
      </div>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
            <div className="flex items-center gap-1 flex-wrap" data-testid="status-tabs">
              {TABS.map((t) => (
                <button
                  key={t.key}
                  onClick={() => onTabChange(t.key)}
                  data-testid={`tab-${t.key}`}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                    tab === t.key ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <form onSubmit={onSearchSubmit} className="flex items-center gap-2">
              <Input
                placeholder="Buscar por destinatario…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-56 h-9"
                data-testid="search-recipient-input"
              />
              <Button type="submit" variant="secondary" size="sm" data-testid="search-btn">Buscar</Button>
            </form>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-slate-500 border-b border-slate-200">
                  <th className="py-2 px-3">Estado</th>
                  <th className="py-2 px-3">Destinatario</th>
                  <th className="py-2 px-3">Asunto</th>
                  <th className="py-2 px-3">Tipo</th>
                  <th className="py-2 px-3 text-center">Intentos</th>
                  <th className="py-2 px-3">Último error</th>
                  <th className="py-2 px-3">Fecha</th>
                  <th className="py-2 px-3 text-right">Acción</th>
                </tr>
              </thead>
              <tbody data-testid="email-queue-tbody">
                {loading ? (
                  <tr><td colSpan={8} className="py-10 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline mr-2" /> Cargando…</td></tr>
                ) : items.length === 0 ? (
                  <tr><td colSpan={8} className="py-10 text-center text-slate-400" data-testid="empty-state">
                    <Inbox className="w-8 h-8 mx-auto mb-2 opacity-40" /> No hay correos en esta vista.
                  </td></tr>
                ) : items.map((it) => (
                  <tr key={it._id} className="border-b border-slate-100 hover:bg-slate-50/60" data-testid={`email-row-${it._id}`}>
                    <td className="py-2.5 px-3"><StatusBadge status={it.status} /></td>
                    <td className="py-2.5 px-3 text-slate-700">{it.to}</td>
                    <td className="py-2.5 px-3 text-slate-600 max-w-[260px] truncate" title={it.subject}>
                      <span className="inline-flex items-center gap-1">
                        {it.attachment_count > 0 && <Paperclip className="w-3.5 h-3.5 text-slate-400 shrink-0" title={(it.attachment_names || []).join(', ')} />}
                        {it.subject}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      {it.tag ? <Badge variant="outline" className="text-xs text-slate-500">{it.tag}</Badge> : <span className="text-slate-300">-</span>}
                    </td>
                    <td className="py-2.5 px-3 text-center text-slate-600">{it.attempts ?? 0}<span className="text-slate-300">/{it.max_attempts ?? 5}</span></td>
                    <td className="py-2.5 px-3 text-xs text-red-500 max-w-[200px] truncate" title={it.last_error || ''}>{it.last_error || '-'}</td>
                    <td className="py-2.5 px-3 text-xs text-slate-500 whitespace-nowrap">{fmtDate(it.created_at)}</td>
                    <td className="py-2.5 px-3 text-right">
                      <Button
                        size="sm" variant="outline"
                        onClick={() => handleResend(it._id)}
                        disabled={resendingId === it._id || it.status === 'sending'}
                        data-testid={`resend-btn-${it._id}`}
                        className="gap-1"
                      >
                        {resendingId === it._id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                        Reenviar
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {total > PAGE_SIZE && (
            <div className="flex items-center justify-between mt-4 text-sm text-slate-500">
              <span>Página {page + 1} de {totalPages} · {total} correos</span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))} data-testid="prev-page-btn">Anterior</Button>
                <Button variant="outline" size="sm" disabled={page + 1 >= totalPages} onClick={() => setPage((p) => p + 1)} data-testid="next-page-btn">Siguiente</Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
