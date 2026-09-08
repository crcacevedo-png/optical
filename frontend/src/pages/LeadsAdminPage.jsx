import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Switch } from '../components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription } from '../components/ui/dialog';
import {
  UserPlus, Download, Link2, Copy, MessageCircle, Search, Users, Tag,
  Ticket, Plus, RefreshCw, AlertTriangle, Inbox, ChevronDown, ChevronRight,
  Building2, KeyRound, CheckCircle2, Loader2,
} from 'lucide-react';
import { toast } from 'sonner';

const waLink = (wa) => `https://wa.me/${(wa || '').replace(/[^0-9]/g, '')}`;
const fmtDate = (iso) => {
  if (!iso) return '-';
  try { return new Date(iso).toLocaleString('es-GT', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }); }
  catch { return String(iso).slice(0, 16); }
};

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

export default function LeadsAdminPage() {
  const publicLink = `${window.location.origin}/registro`;
  const [stats, setStats] = useState({ total: 0, with_code: 0, without_code: 0, possible_duplicates: 0 });
  const [tab, setTab] = useState('envios');

  // Envios
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [fCode, setFCode] = useState('');
  const [fSource, setFSource] = useState('');
  const [fStatus, setFStatus] = useState('');
  const [fDup, setFDup] = useState(false);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 100;

  // Alta de cuenta
  const [accountLead, setAccountLead] = useState(null);
  const [accountPassword, setAccountPassword] = useState('');
  const [creatingAccount, setCreatingAccount] = useState(false);
  const [accountResult, setAccountResult] = useState(null);

  // Filtros disponibles
  const [codes, setCodes] = useState([]);
  const [sources, setSources] = useState([]);

  // Agrupado
  const [groups, setGroups] = useState([]);
  const [openGroup, setOpenGroup] = useState(null);

  // Codigos
  const [newCode, setNewCode] = useState('');
  const [newLabel, setNewLabel] = useState('');
  const [creating, setCreating] = useState(false);

  const copy = (text, msg) => { navigator.clipboard?.writeText(text); toast.success(msg || 'Copiado'); };

  const loadStats = useCallback(async () => {
    try {
      const [{ data: s }, { data: src }, { data: c }] = await Promise.all([
        api.get('/api/leads/stats'),
        api.get('/api/leads/sources'),
        api.get('/api/leads/codes'),
      ]);
      setStats(s); setSources(src.sources || []); setCodes(c.items || []);
    } catch (err) { toast.error(formatApiErrorDetail(err?.response?.data?.detail) || 'Error al cargar'); }
  }, []);

  const loadLeads = useCallback(async () => {
    try {
      setLoading(true);
      const params = { limit: PAGE_SIZE, skip: page * PAGE_SIZE };
      if (fCode) params.promo_code = fCode;
      if (fSource) params.source = fSource;
      if (fStatus) params.status = fStatus;
      if (fDup) params.duplicates = true;
      if (search.trim()) params.search = search.trim();
      const { data } = await api.get('/api/leads', { params });
      setItems(data.items || []); setTotal(data.total || 0);
    } catch (err) { toast.error(formatApiErrorDetail(err?.response?.data?.detail) || 'Error al cargar envíos'); }
    finally { setLoading(false); }
  }, [fCode, fSource, fStatus, fDup, search, page]);

  const loadGrouped = useCallback(async () => {
    try { const { data } = await api.get('/api/leads/grouped'); setGroups(data.groups || []); }
    catch (err) { toast.error(formatApiErrorDetail(err?.response?.data?.detail) || 'Error al agrupar'); }
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => { if (tab === 'envios') loadLeads(); }, [tab, loadLeads]);
  useEffect(() => { if (tab === 'agrupado') loadGrouped(); }, [tab, loadGrouped]);

  const doExport = async () => {
    try {
      const params = {};
      if (fCode) params.promo_code = fCode;
      if (fSource) params.source = fSource;
      if (fDup) params.duplicates = true;
      if (search.trim()) params.search = search.trim();
      const res = await api.get('/api/leads/export', { params, responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url; a.download = `Cortexia_Leads_${Date.now()}.xlsx`; a.click();
      URL.revokeObjectURL(url);
      toast.success('Exportación descargada');
    } catch (err) { toast.error('No se pudo exportar'); }
  };

  const changeStatus = async (lead, status) => {
    try {
      await api.patch(`/api/leads/${lead._id}/status`, { status });
      setItems((prev) => prev.map((x) => (x._id === lead._id ? { ...x, status } : x)));
      loadStats();
    } catch (err) { toast.error('No se pudo actualizar el estado'); }
  };

  const openAccount = (lead) => { setAccountLead(lead); setAccountPassword(''); setAccountResult(null); };

  const submitAccount = async () => {
    if (!accountLead) return;
    try {
      setCreatingAccount(true);
      const { data } = await api.post(`/api/leads/${accountLead._id}/create-account`,
        { admin_password: accountPassword.trim() || undefined });
      setAccountResult(data);
      toast.success('Cuenta creada correctamente');
      setItems((prev) => prev.map((x) => (x._id === accountLead._id ? { ...x, status: 'cuenta_creada' } : x)));
      loadStats();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail) || 'No se pudo crear la cuenta');
    } finally { setCreatingAccount(false); }
  };

  const createCode = async (e) => {
    e.preventDefault();
    if (!newCode.trim()) return;
    try {
      setCreating(true);
      await api.post('/api/leads/codes', { code: newCode.trim(), label: newLabel.trim() });
      toast.success('Código creado');
      setNewCode(''); setNewLabel('');
      loadStats();
    } catch (err) { toast.error(formatApiErrorDetail(err?.response?.data?.detail) || 'No se pudo crear'); }
    finally { setCreating(false); }
  };

  const toggleCode = async (c) => {
    try {
      await api.patch(`/api/leads/codes/${c._id}`, { is_active: !c.is_active });
      setCodes((prev) => prev.map((x) => (x._id === c._id ? { ...x, is_active: !x.is_active } : x)));
    } catch (err) { toast.error('No se pudo actualizar'); }
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6" data-testid="leads-admin-page">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <UserPlus className="w-6 h-6 text-indigo-600" /> Solicitudes de cuenta
          </h1>
          <p className="text-sm text-slate-500 mt-1">Solicitudes de apertura de cuenta desde el formulario público. Datos visibles solo para SuperAdmin.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1 bg-slate-100 rounded-full pl-3 pr-1 py-1">
            <Link2 className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-xs text-slate-600 max-w-[220px] truncate">{publicLink}</span>
            <Button size="sm" variant="ghost" className="h-7 rounded-full" onClick={() => copy(publicLink, 'Enlace público copiado')} data-testid="copy-public-link-btn">
              <Copy className="w-3.5 h-3.5" /> Copiar
            </Button>
          </div>
          <a href={publicLink} target="_blank" rel="noreferrer">
            <Button size="sm" variant="outline" data-testid="open-public-form-btn">Abrir formulario</Button>
          </a>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Total solicitudes" value={stats.total} icon={Users} color="border-indigo-400" testId="stat-total" />
        <StatCard label="Con código" value={stats.with_code} icon={Tag} color="border-emerald-400" testId="stat-with-code" />
        <StatCard label="Sin código" value={stats.without_code} icon={Inbox} color="border-slate-300" testId="stat-without-code" />
        <StatCard label="Posibles duplicados" value={stats.possible_duplicates} icon={AlertTriangle} color="border-amber-400" testId="stat-duplicates" />
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList data-testid="leads-tabs">
          <TabsTrigger value="envios" data-testid="tab-envios">Solicitudes</TabsTrigger>
          <TabsTrigger value="agrupado" data-testid="tab-agrupado">Agrupado por código</TabsTrigger>
          <TabsTrigger value="codigos" data-testid="tab-codigos">Códigos</TabsTrigger>
        </TabsList>

        {/* ENVIOS */}
        <TabsContent value="envios">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-end justify-between flex-wrap gap-3 mb-4">
                <div className="flex items-end gap-2 flex-wrap">
                  <div>
                    <label className="text-xs text-slate-500 block mb-1">Código</label>
                    <select value={fCode} onChange={(e) => { setPage(0); setFCode(e.target.value); }} className="h-9 rounded-md border border-slate-200 text-sm px-2 bg-white" data-testid="filter-code">
                      <option value="">Todos</option>
                      <option value="sin_codigo">Sin código</option>
                      {codes.map((c) => <option key={c._id} value={c.code}>{c.code}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 block mb-1">Origen</label>
                    <select value={fSource} onChange={(e) => { setPage(0); setFSource(e.target.value); }} className="h-9 rounded-md border border-slate-200 text-sm px-2 bg-white" data-testid="filter-source">
                      <option value="">Todos</option>
                      {sources.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 block mb-1">Estado</label>
                    <select value={fStatus} onChange={(e) => { setPage(0); setFStatus(e.target.value); }} className="h-9 rounded-md border border-slate-200 text-sm px-2 bg-white" data-testid="filter-status">
                      <option value="">Todos</option>
                      <option value="nueva">Nueva</option>
                      <option value="contactada">Contactada</option>
                      <option value="cuenta_creada">Cuenta creada</option>
                    </select>
                  </div>
                  <label className="flex items-center gap-2 text-sm text-slate-600 h-9">
                    <Switch checked={fDup} onCheckedChange={(v) => { setPage(0); setFDup(v); }} data-testid="filter-duplicates" />
                    Solo duplicados
                  </label>
                </div>
                <div className="flex items-end gap-2">
                  <form onSubmit={(e) => { e.preventDefault(); setPage(0); loadLeads(); }} className="flex items-center gap-2">
                    <div className="relative">
                      <Search className="w-4 h-4 text-slate-400 absolute left-2.5 top-2.5" />
                      <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Nombre, correo o número…" className="h-9 pl-8 w-56" data-testid="search-input" />
                    </div>
                    <Button type="submit" size="sm" variant="secondary" data-testid="search-btn">Buscar</Button>
                  </form>
                  <Button size="sm" variant="outline" onClick={loadLeads} data-testid="refresh-btn"><RefreshCw className="w-4 h-4" /></Button>
                  <Button size="sm" onClick={doExport} data-testid="export-btn" className="bg-emerald-600 hover:bg-emerald-700"><Download className="w-4 h-4" /> Exportar</Button>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wide text-slate-500 border-b border-slate-200">
                      <th className="py-2 px-3">Nombre</th>
                      <th className="py-2 px-3">Óptica</th>
                      <th className="py-2 px-3">Ubicación</th>
                      <th className="py-2 px-3">WhatsApp</th>
                      <th className="py-2 px-3">Correo</th>
                      <th className="py-2 px-3">Código</th>
                      <th className="py-2 px-3">Origen</th>
                      <th className="py-2 px-3">Estado</th>
                      <th className="py-2 px-3">Fecha</th>
                      <th className="py-2 px-3 text-right">Acción</th>
                    </tr>
                  </thead>
                  <tbody data-testid="leads-tbody">
                    {loading ? (
                      <tr><td colSpan={10} className="py-10 text-center text-slate-400"><RefreshCw className="w-5 h-5 animate-spin inline mr-2" /> Cargando…</td></tr>
                    ) : items.length === 0 ? (
                      <tr><td colSpan={10} className="py-10 text-center text-slate-400" data-testid="leads-empty"><Inbox className="w-8 h-8 mx-auto mb-2 opacity-40" /> No hay solicitudes.</td></tr>
                    ) : items.map((it) => (
                      <tr key={it._id} className="border-b border-slate-100 hover:bg-slate-50/60" data-testid={`lead-row-${it._id}`}>
                        <td className="py-2.5 px-3 text-slate-800 font-medium">
                          {it.name}
                          {it.is_possible_duplicate && <Badge variant="outline" className="ml-2 text-[10px] bg-amber-50 text-amber-600 border-amber-200">dup</Badge>}
                        </td>
                        <td className="py-2.5 px-3 text-slate-600">{it.optica_name || <span className="text-slate-300">—</span>}</td>
                        <td className="py-2.5 px-3 text-xs text-slate-500">{it.location || <span className="text-slate-300">—</span>}</td>
                        <td className="py-2.5 px-3 text-slate-600">{it.whatsapp}</td>
                        <td className="py-2.5 px-3 text-slate-600">{it.email}</td>
                        <td className="py-2.5 px-3">{it.promo_code ? <Badge className="bg-indigo-100 text-indigo-700 border-indigo-200" variant="outline">{it.promo_code}</Badge> : <span className="text-slate-300">Sin código</span>}</td>
                        <td className="py-2.5 px-3 text-xs text-slate-500">{it.source}</td>
                        <td className="py-2.5 px-3">
                          {it.status === 'cuenta_creada' ? (
                            <Badge variant="outline" className="bg-emerald-100 text-emerald-700 border-emerald-200">Cuenta creada</Badge>
                          ) : (
                            <select value={it.status || 'nueva'} onChange={(e) => changeStatus(it, e.target.value)}
                              className="h-8 rounded-md border border-slate-200 text-xs px-1.5 bg-white" data-testid={`status-select-${it._id}`}>
                              <option value="nueva">Nueva</option>
                              <option value="contactada">Contactada</option>
                            </select>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-xs text-slate-500 whitespace-nowrap">{fmtDate(it.created_at)}</td>
                        <td className="py-2.5 px-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <a href={waLink(it.whatsapp)} target="_blank" rel="noreferrer">
                              <Button size="sm" variant="outline" className="gap-1 text-emerald-600 border-emerald-200 hover:bg-emerald-50" data-testid={`wa-btn-${it._id}`}>
                                <MessageCircle className="w-3.5 h-3.5" /> WhatsApp
                              </Button>
                            </a>
                            {it.status !== 'cuenta_creada' && (
                              <Button size="sm" onClick={() => openAccount(it)} data-testid={`open-account-btn-${it._id}`} className="gap-1 bg-[#1B2A49] hover:bg-[#111d33]">
                                <Building2 className="w-3.5 h-3.5" /> Abrir cuenta
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {total > PAGE_SIZE && (
                <div className="flex items-center justify-between mt-4 text-sm text-slate-500">
                  <span>Página {page + 1} de {totalPages} · {total} leads</span>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>Anterior</Button>
                    <Button variant="outline" size="sm" disabled={page + 1 >= totalPages} onClick={() => setPage((p) => p + 1)}>Siguiente</Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* AGRUPADO */}
        <TabsContent value="agrupado">
          <div className="space-y-3">
            {groups.length === 0 && <Card><CardContent className="p-8 text-center text-slate-400">Sin datos aún.</CardContent></Card>}
            {groups.map((g) => {
              const key = g.code || 'sin_codigo';
              const open = openGroup === key;
              return (
                <Card key={key} data-testid={`group-${key}`}>
                  <button className="w-full flex items-center justify-between p-4 text-left" onClick={() => setOpenGroup(open ? null : key)} data-testid={`group-toggle-${key}`}>
                    <div className="flex items-center gap-2">
                      {open ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
                      {g.code
                        ? <Badge className="bg-indigo-100 text-indigo-700 border-indigo-200" variant="outline">{g.code}</Badge>
                        : <span className="font-medium text-slate-500">Sin código</span>}
                      {g.label && <span className="text-sm text-slate-500">— {g.label}</span>}
                      {g.code && !g.is_active && <Badge variant="outline" className="text-[10px] text-slate-400">inactivo</Badge>}
                    </div>
                    <div className="flex items-center gap-3">
                      {g.code && (
                        <span onClick={(e) => { e.stopPropagation(); copy(`${publicLink}?codigo=${g.code}`, 'Enlace con código copiado'); }}
                          className="text-xs text-indigo-600 hover:underline inline-flex items-center gap-1 cursor-pointer" data-testid={`copy-code-link-${key}`}>
                          <Copy className="w-3 h-3" /> enlace
                        </span>
                      )}
                      <Badge variant="secondary" className="font-bold">{g.count} {g.count === 1 ? 'miembro' : 'miembros'}</Badge>
                    </div>
                  </button>
                  {open && (
                    <CardContent className="pt-0">
                      {g.members.length === 0 ? <p className="text-sm text-slate-400 pb-3">Sin miembros.</p> : (
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead><tr className="text-left text-xs uppercase text-slate-400 border-b border-slate-100">
                              <th className="py-1.5 px-3">Nombre</th><th className="py-1.5 px-3">Óptica</th><th className="py-1.5 px-3">WhatsApp</th><th className="py-1.5 px-3">Correo</th><th className="py-1.5 px-3">Origen</th><th className="py-1.5 px-3">Fecha</th><th className="py-1.5 px-3"></th>
                            </tr></thead>
                            <tbody>
                              {g.members.map((m) => (
                                <tr key={m.id} className="border-b border-slate-50">
                                  <td className="py-2 px-3">{m.name}{m.is_possible_duplicate && <Badge variant="outline" className="ml-2 text-[10px] bg-amber-50 text-amber-600 border-amber-200">dup</Badge>}</td>
                                  <td className="py-2 px-3 text-slate-600">{m.optica_name || <span className="text-slate-300">—</span>}</td>
                                  <td className="py-2 px-3 text-slate-600">{m.whatsapp}</td>
                                  <td className="py-2 px-3 text-slate-600">{m.email}</td>
                                  <td className="py-2 px-3 text-xs text-slate-500">{m.source}</td>
                                  <td className="py-2 px-3 text-xs text-slate-500">{fmtDate(m.created_at)}</td>
                                  <td className="py-2 px-3 text-right"><a href={waLink(m.whatsapp)} target="_blank" rel="noreferrer" className="text-emerald-600 inline-flex items-center gap-1 text-xs"><MessageCircle className="w-3.5 h-3.5" /></a></td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </CardContent>
                  )}
                </Card>
              );
            })}
          </div>
        </TabsContent>

        {/* CODIGOS */}
        <TabsContent value="codigos">
          <Card className="mb-4">
            <CardContent className="p-4">
              <form onSubmit={createCode} className="flex items-end gap-2 flex-wrap" data-testid="create-code-form">
                <div>
                  <label className="text-xs text-slate-500 block mb-1">Código</label>
                  <Input value={newCode} onChange={(e) => setNewCode(e.target.value.toUpperCase())} placeholder="EJ: VERANO2026" className="h-9 w-44 uppercase" data-testid="new-code-input" />
                </div>
                <div>
                  <label className="text-xs text-slate-500 block mb-1">Descripción (opcional)</label>
                  <Input value={newLabel} onChange={(e) => setNewLabel(e.target.value)} placeholder="Campaña de verano" className="h-9 w-64" data-testid="new-code-label-input" />
                </div>
                <Button type="submit" disabled={creating || !newCode.trim()} data-testid="create-code-btn"><Plus className="w-4 h-4" /> Crear código</Button>
              </form>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200">
                    <th className="py-2 px-3">Código</th><th className="py-2 px-3">Descripción</th><th className="py-2 px-3 text-center">Leads</th><th className="py-2 px-3">Enlace</th><th className="py-2 px-3 text-right">Activo</th>
                  </tr></thead>
                  <tbody data-testid="codes-tbody">
                    {codes.length === 0 ? (
                      <tr><td colSpan={5} className="py-10 text-center text-slate-400"><Ticket className="w-8 h-8 mx-auto mb-2 opacity-40" /> Aún no has creado códigos.</td></tr>
                    ) : codes.map((c) => (
                      <tr key={c._id} className="border-b border-slate-100" data-testid={`code-row-${c._id}`}>
                        <td className="py-2.5 px-3"><Badge className="bg-indigo-100 text-indigo-700 border-indigo-200" variant="outline">{c.code}</Badge></td>
                        <td className="py-2.5 px-3 text-slate-600">{c.label || <span className="text-slate-300">—</span>}</td>
                        <td className="py-2.5 px-3 text-center font-semibold">{c.lead_count ?? 0}</td>
                        <td className="py-2.5 px-3">
                          <span onClick={() => copy(`${publicLink}?codigo=${c.code}`, 'Enlace con código copiado')} className="text-xs text-indigo-600 hover:underline inline-flex items-center gap-1 cursor-pointer" data-testid={`copy-link-${c._id}`}>
                            <Copy className="w-3 h-3" /> copiar enlace
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right"><Switch checked={c.is_active} onCheckedChange={() => toggleCode(c)} data-testid={`toggle-code-${c._id}`} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={!!accountLead} onOpenChange={(o) => { if (!o) { setAccountLead(null); setAccountResult(null); } }}>
        <DialogContent data-testid="account-dialog">
          {!accountResult ? (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2"><Building2 className="w-5 h-5 text-indigo-600" /> Abrir cuenta</DialogTitle>
                <DialogDescription>Se creará la óptica y su usuario administrador, y se enviará un correo de bienvenida con las credenciales.</DialogDescription>
              </DialogHeader>
              {accountLead && (
                <div className="space-y-3 text-sm">
                  <div className="bg-slate-50 rounded-lg p-3 space-y-1">
                    <div><span className="text-slate-500">Óptica:</span> <b>{accountLead.optica_name || accountLead.name}</b></div>
                    <div><span className="text-slate-500">Administrador:</span> {accountLead.name}</div>
                    <div><span className="text-slate-500">Correo (usuario):</span> {accountLead.email}</div>
                    {accountLead.location && <div><span className="text-slate-500">Ubicación:</span> {accountLead.location}</div>}
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 block mb-1">Contraseña temporal (opcional)</label>
                    <Input value={accountPassword} onChange={(e) => setAccountPassword(e.target.value)} placeholder="Dejar vacío para generar automáticamente" data-testid="account-password-input" />
                  </div>
                </div>
              )}
              <DialogFooter>
                <Button variant="outline" onClick={() => setAccountLead(null)} data-testid="cancel-account-btn">Cancelar</Button>
                <Button onClick={submitAccount} disabled={creatingAccount} data-testid="confirm-create-account-btn" className="bg-[#1B2A49] hover:bg-[#111d33]">
                  {creatingAccount ? <><Loader2 className="w-4 h-4 animate-spin mr-1" /> Creando…</> : 'Crear cuenta'}
                </Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-emerald-700"><CheckCircle2 className="w-5 h-5" /> Cuenta creada</DialogTitle>
              </DialogHeader>
              <div className="space-y-3 text-sm" data-testid="account-result">
                <p className="text-slate-600">La óptica y su administrador fueron creados. Se envió un correo de bienvenida con las credenciales.</p>
                <div className="bg-slate-50 rounded-lg p-3 space-y-2">
                  <div><span className="text-slate-500">Usuario:</span> <b>{accountResult.admin_email}</b></div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-slate-500">Contraseña temporal:</span>
                    <code className="bg-white border rounded px-2 py-0.5" data-testid="temp-password">{accountResult.temp_password}</code>
                    <Button size="sm" variant="ghost" className="h-7" onClick={() => copy(accountResult.temp_password, 'Contraseña copiada')}><Copy className="w-3.5 h-3.5" /></Button>
                  </div>
                  <p className="text-xs text-amber-600 flex items-center gap-1"><KeyRound className="w-3 h-3" /> Comparte estas credenciales de forma segura. Se recomienda cambiar la contraseña al primer ingreso.</p>
                </div>
              </div>
              <DialogFooter>
                <Button onClick={() => { setAccountLead(null); setAccountResult(null); }} data-testid="close-account-dialog-btn">Listo</Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
