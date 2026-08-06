import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail, useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { LifeBuoy, Plus, MessageCircle, Send, Lock, RefreshCw, AlertTriangle, CheckCircle2, Clock, Store } from 'lucide-react';
import { toast } from 'sonner';

const STATUS_META = {
  abierto: { label: 'Abierto', color: 'bg-blue-100 text-blue-800 border-blue-200', icon: AlertTriangle },
  en_progreso: { label: 'En progreso', color: 'bg-amber-100 text-amber-800 border-amber-200', icon: Clock },
  resuelto: { label: 'Resuelto', color: 'bg-emerald-100 text-emerald-800 border-emerald-200', icon: CheckCircle2 },
  cerrado: { label: 'Cerrado', color: 'bg-slate-200 text-slate-700 border-slate-300', icon: Lock },
};

const PRIORITY_META = {
  baja: { label: 'Baja', color: 'bg-slate-100 text-slate-700' },
  media: { label: 'Media', color: 'bg-amber-100 text-amber-800' },
  alta: { label: 'Alta', color: 'bg-red-100 text-red-700' },
};

const CATEGORY_LABELS = {
  bug: 'Bug / Error',
  consulta: 'Consulta',
  mejora: 'Sugerencia / Mejora',
  facturacion: 'Facturacion / Pagos',
  otro: 'Otro',
};

const fmtDate = (iso) => (iso || '').slice(0, 16).replace('T', ' ');

export default function SupportTicketsPage() {
  const { user } = useAuth();
  const isSuperAdmin = user?.role === 'superadmin';

  const [tickets, setTickets] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [detail, setDetail] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ subject: '', category: 'consulta', priority: 'media', message: '' });
  const [submitting, setSubmitting] = useState(false);
  const [reply, setReply] = useState('');
  const [sendingReply, setSendingReply] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const params = filter !== 'all' ? { status: filter } : {};
      const [tRes, sRes] = await Promise.all([
        api.get('/api/support-tickets', { params }),
        api.get('/api/support-tickets/stats/summary'),
      ]);
      setTickets(tRes.data || []);
      setStats(sRes.data);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.subject.trim() || !form.message.trim()) {
      toast.error('Completa asunto y descripcion');
      return;
    }
    try {
      setSubmitting(true);
      await api.post('/api/support-tickets', form);
      toast.success('Ticket enviado. El equipo Cortexia respondera pronto.');
      setShowCreate(false);
      setForm({ subject: '', category: 'consulta', priority: 'media', message: '' });
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSubmitting(false);
    }
  };

  const openDetail = async (id) => {
    try {
      const { data } = await api.get(`/api/support-tickets/${id}`);
      setDetail(data);
      setReply('');
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const sendReply = async () => {
    if (!reply.trim() || !detail) return;
    try {
      setSendingReply(true);
      await api.post(`/api/support-tickets/${detail._id}/reply`, { message: reply });
      await openDetail(detail._id);
      load();
      setReply('');
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSendingReply(false);
    }
  };

  const changeStatus = async (status) => {
    if (!detail) return;
    try {
      await api.patch(`/api/support-tickets/${detail._id}/status`, { status });
      toast.success('Estado actualizado');
      await openDetail(detail._id);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  return (
    <div className="space-y-6" data-testid="support-tickets-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center">
              <LifeBuoy className="w-5 h-5 text-white" />
            </div>
            <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">
              {isSuperAdmin ? 'Tickets de Soporte' : 'Soporte'}
            </h1>
          </div>
          <p className="text-slate-500 text-sm">
            {isSuperAdmin
              ? 'Tickets enviados por las opticas del sistema.'
              : 'Envia consultas, reportes de bugs o sugerencias al equipo Cortexia.'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={load} data-testid="support-refresh">
            <RefreshCw className="w-4 h-4 mr-1.5" /> Refrescar
          </Button>
          {!isSuperAdmin && (
            <Dialog open={showCreate} onOpenChange={setShowCreate}>
              <DialogTrigger asChild>
                <Button className="bg-indigo-600 hover:bg-indigo-700" data-testid="support-new-btn">
                  <Plus className="w-4 h-4 mr-1.5" /> Nuevo ticket
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-lg" data-testid="support-new-dialog">
                <DialogHeader>
                  <DialogTitle className="font-heading flex items-center gap-2">
                    <LifeBuoy className="w-5 h-5 text-indigo-600" /> Nuevo ticket de soporte
                  </DialogTitle>
                </DialogHeader>
                <form onSubmit={submit} className="space-y-3">
                  <div>
                    <Label>Asunto</Label>
                    <Input
                      value={form.subject}
                      onChange={(e) => setForm({ ...form, subject: e.target.value })}
                      placeholder="Resumen breve del problema o consulta"
                      required minLength={3} maxLength={200}
                      data-testid="support-subject"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label>Categoria</Label>
                      <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                        <SelectTrigger data-testid="support-category"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
                            <SelectItem key={k} value={k}>{v}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Prioridad</Label>
                      <Select value={form.priority} onValueChange={(v) => setForm({ ...form, priority: v })}>
                        <SelectTrigger data-testid="support-priority"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {Object.entries(PRIORITY_META).map(([k, v]) => (
                            <SelectItem key={k} value={k}>{v.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div>
                    <Label>Descripcion</Label>
                    <Textarea
                      rows={6} value={form.message}
                      onChange={(e) => setForm({ ...form, message: e.target.value })}
                      placeholder="Describe el problema o consulta con el mayor detalle posible. Incluye pasos para reproducir si es un bug."
                      required minLength={5} maxLength={5000}
                      data-testid="support-message"
                    />
                    <p className="text-xs text-slate-500 mt-1">{form.message.length}/5000</p>
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <Button type="button" variant="outline" onClick={() => setShowCreate(false)}>Cancelar</Button>
                    <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700" disabled={submitting} data-testid="support-submit">
                      <Send className="w-4 h-4 mr-1.5" /> {submitting ? 'Enviando...' : 'Enviar ticket'}
                    </Button>
                  </div>
                </form>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { key: 'open', label: 'Abiertos', filter: 'abierto', color: 'from-blue-500 to-blue-600', icon: AlertTriangle },
            { key: 'in_progress', label: 'En progreso', filter: 'en_progreso', color: 'from-amber-500 to-orange-500', icon: Clock },
            { key: 'resolved', label: 'Resueltos', filter: 'resuelto', color: 'from-emerald-500 to-teal-500', icon: CheckCircle2 },
            { key: 'closed', label: 'Cerrados', filter: 'cerrado', color: 'from-slate-400 to-slate-500', icon: Lock },
          ].map(({ key, label, filter: f, color, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setFilter(f)}
              className={`text-left border rounded-xl p-3 hover:shadow-sm transition-shadow ${filter === f ? 'ring-2 ring-indigo-400' : ''}`}
              data-testid={`support-stat-${key}`}
            >
              <div className="flex items-center gap-2">
                <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${color} flex items-center justify-center`}>
                  <Icon className="w-4 h-4 text-white" />
                </div>
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wider">{label}</p>
                  <p className="font-heading text-xl font-bold text-slate-900 leading-tight">{stats[key] || 0}</p>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Filter reset */}
      {filter !== 'all' && (
        <button onClick={() => setFilter('all')} className="text-xs text-indigo-600 hover:underline">
          Limpiar filtro
        </button>
      )}

      {/* Tickets list */}
      <Card className="border-slate-200/80">
        <CardHeader>
          <CardTitle className="font-heading text-lg flex items-center gap-2">
            <MessageCircle className="w-5 h-5 text-slate-600" />
            {isSuperAdmin ? 'Todos los tickets' : 'Mis tickets'}
            <Badge variant="outline" className="ml-1">{tickets.length}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
            </div>
          ) : tickets.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <LifeBuoy className="w-16 h-16 mx-auto mb-3 opacity-30" />
              <p className="font-medium">Sin tickets</p>
              {!isSuperAdmin && <p className="text-sm mt-1">Crea uno para contactar al equipo Cortexia.</p>}
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {tickets.map((t) => {
                const s = STATUS_META[t.status] || STATUS_META.abierto;
                const p = PRIORITY_META[t.priority] || PRIORITY_META.media;
                const SIcon = s.icon;
                return (
                  <button
                    key={t._id}
                    onClick={() => openDetail(t._id)}
                    className="w-full text-left py-3 px-2 -mx-2 hover:bg-slate-50/60 rounded-lg transition-colors"
                    data-testid={`support-ticket-${t._id}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <p className="font-semibold text-slate-900 truncate">{t.subject}</p>
                          <Badge className={`${s.color} border`} variant="outline">
                            <SIcon className="w-3 h-3 mr-1" />{s.label}
                          </Badge>
                          <Badge className={p.color} variant="outline">{p.label}</Badge>
                          <Badge variant="outline" className="text-xs">{CATEGORY_LABELS[t.category]}</Badge>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-slate-500 mt-1">
                          {isSuperAdmin && (
                            <span className="inline-flex items-center gap-1">
                              <Store className="w-3 h-3" />{t.company_name || '-'} ·
                            </span>
                          )}
                          <span>{t.created_by_name}</span>
                          <span>·</span>
                          <span>{fmtDate(t.created_at)}</span>
                          <span>·</span>
                          <span className="inline-flex items-center gap-1"><MessageCircle className="w-3 h-3" />{t.message_count}</span>
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Detail dialog */}
      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="support-detail-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading flex items-start gap-2">
              <LifeBuoy className="w-5 h-5 text-indigo-600 mt-0.5" />
              <span className="flex-1">{detail?.subject}</span>
            </DialogTitle>
          </DialogHeader>
          {detail && (
            <div className="space-y-4">
              {/* Meta */}
              <div className="flex flex-wrap items-center gap-2 pb-3 border-b border-slate-100">
                <Badge className={`${STATUS_META[detail.status]?.color} border`} variant="outline">
                  {STATUS_META[detail.status]?.label}
                </Badge>
                <Badge className={PRIORITY_META[detail.priority]?.color} variant="outline">
                  {PRIORITY_META[detail.priority]?.label}
                </Badge>
                <Badge variant="outline" className="text-xs">{CATEGORY_LABELS[detail.category]}</Badge>
                {isSuperAdmin && detail.company_name && (
                  <Badge variant="outline" className="text-xs">
                    <Store className="w-3 h-3 mr-1" />{detail.company_name}
                  </Badge>
                )}
              </div>

              {/* Messages thread */}
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {(detail.messages || []).map((m, idx) => {
                  const isSuper = m.author_role === 'superadmin';
                  return (
                    <div
                      key={idx}
                      className={`p-3 rounded-lg border ${isSuper ? 'bg-indigo-50 border-indigo-200 ml-6' : 'bg-slate-50 border-slate-200 mr-6'}`}
                      data-testid={`support-msg-${idx}`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className={`text-xs font-semibold ${isSuper ? 'text-indigo-700' : 'text-slate-700'}`}>
                          {m.author_name}
                          {isSuper && <span className="ml-1 text-[10px] uppercase font-bold">· Cortexia</span>}
                        </span>
                        <span className="text-[11px] text-slate-500">{fmtDate(m.created_at)}</span>
                      </div>
                      <p className="text-sm text-slate-800 whitespace-pre-wrap">{m.message}</p>
                    </div>
                  );
                })}
              </div>

              {/* Reply */}
              {detail.status !== 'cerrado' && (
                <div className="pt-3 border-t border-slate-100">
                  <Textarea
                    rows={3}
                    value={reply}
                    onChange={(e) => setReply(e.target.value)}
                    placeholder={isSuperAdmin ? 'Responder al usuario...' : 'Agregar mas informacion...'}
                    data-testid="support-reply-input"
                  />
                  <div className="flex justify-between items-center mt-2 gap-2 flex-wrap">
                    <div className="flex gap-1 flex-wrap">
                      {isSuperAdmin && (
                        <>
                          <Button size="sm" variant="outline" onClick={() => changeStatus('en_progreso')} data-testid="support-status-progress">
                            <Clock className="w-3.5 h-3.5 mr-1" /> En progreso
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => changeStatus('resuelto')} className="text-emerald-700 border-emerald-200 hover:bg-emerald-50" data-testid="support-status-resolved">
                            <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Resuelto
                          </Button>
                        </>
                      )}
                      <Button size="sm" variant="outline" onClick={() => changeStatus('cerrado')} className="text-slate-600" data-testid="support-status-closed">
                        <Lock className="w-3.5 h-3.5 mr-1" /> Cerrar
                      </Button>
                    </div>
                    <Button
                      size="sm" onClick={sendReply}
                      disabled={sendingReply || !reply.trim()}
                      className="bg-indigo-600 hover:bg-indigo-700"
                      data-testid="support-reply-submit"
                    >
                      <Send className="w-3.5 h-3.5 mr-1" /> {sendingReply ? 'Enviando...' : 'Enviar respuesta'}
                    </Button>
                  </div>
                </div>
              )}
              {detail.status === 'cerrado' && (
                <div className="pt-3 border-t border-slate-100 text-center text-sm text-slate-500">
                  <Lock className="w-4 h-4 inline mr-1" /> Este ticket esta cerrado.
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
