import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription
} from '../components/ui/dialog';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from '../components/ui/table';
import { toast } from 'sonner';
import {
  Plus, Megaphone, Edit, Trash2, Info, AlertTriangle, Sparkles, Eye, EyeOff, CalendarDays,
  BarChart3, MousePointerClick, X as XIcon
} from 'lucide-react';

const TYPE_OPTIONS = [
  { value: 'info', label: 'Informativo', icon: Info, color: 'bg-blue-100 text-blue-700' },
  { value: 'warning', label: 'Alerta', icon: AlertTriangle, color: 'bg-amber-100 text-amber-700' },
  { value: 'promo', label: 'Promocion', icon: Sparkles, color: 'bg-green-100 text-green-700' },
];

const PLAN_OPTIONS = ['Free', 'Basic', 'Enterprise'];

const emptyForm = {
  title: '', message: '', type: 'info', target_plans: [], target_cities: [],
  start_date: new Date().toISOString().slice(0, 10), end_date: ''
};

export default function AnnouncementsPage() {
  const [announcements, setAnnouncements] = useState([]);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [toDelete, setToDelete] = useState(null);
  const [metricsDialogOpen, setMetricsDialogOpen] = useState(false);
  const [metricsData, setMetricsData] = useState(null);
  const [metricsAnn, setMetricsAnn] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [annRes, planRes] = await Promise.all([
        api.get('/api/announcements'),
        api.get('/api/plans')
      ]);
      setAnnouncements(annRes.data);
      setPlans(planRes.data);
    } catch (err) {
      toast.error('Error al cargar anuncios');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const openNew = () => {
    setEditing(null);
    setForm({ ...emptyForm, start_date: new Date().toISOString().slice(0, 10) });
    setDialogOpen(true);
  };

  const openEdit = (ann) => {
    setEditing(ann);
    setForm({
      title: ann.title, message: ann.message, type: ann.type,
      target_plans: ann.target_plans || [],
      target_cities: ann.target_cities || [],
      start_date: ann.start_date || '', end_date: ann.end_date || ''
    });
    setDialogOpen(true);
  };

  const togglePlan = (plan) => {
    setForm(prev => ({
      ...prev,
      target_plans: prev.target_plans.includes(plan)
        ? prev.target_plans.filter(p => p !== plan)
        : [...prev.target_plans, plan]
    }));
  };

  const handleSave = async () => {
    if (!form.title.trim() || !form.message.trim()) {
      toast.error('Titulo y mensaje son requeridos');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        ...form,
        target_cities: form.target_cities.length > 0 ? form.target_cities : [],
        end_date: form.end_date || null
      };
      if (editing) {
        await api.put(`/api/announcements/${editing._id}`, payload);
        toast.success('Anuncio actualizado');
      } else {
        await api.post('/api/announcements', payload);
        toast.success('Anuncio creado');
      }
      setDialogOpen(false);
      fetchData();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (ann) => {
    try {
      await api.put(`/api/announcements/${ann._id}`, { is_active: !ann.is_active });
      fetchData();
    } catch (err) {
      toast.error('Error al cambiar estado');
    }
  };

  const handleDelete = async () => {
    if (!toDelete) return;
    try {
      await api.delete(`/api/announcements/${toDelete._id}`);
      toast.success('Anuncio eliminado');
      setDeleteDialogOpen(false);
      setToDelete(null);
      fetchData();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const openMetrics = async (ann) => {
    setMetricsAnn(ann);
    setMetricsData(null);
    setMetricsDialogOpen(true);
    try {
      const res = await api.get(`/api/announcements/${ann._id}/metrics`);
      setMetricsData(res.data);
    } catch {
      toast.error('Error al cargar metricas');
    }
  };

  const getTypeBadge = (type) => {
    const t = TYPE_OPTIONS.find(o => o.value === type) || TYPE_OPTIONS[0];
    return <Badge className={`${t.color} text-xs`}>{t.label}</Badge>;
  };

  const planNames = plans.map(p => p.name);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="announcements-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Comunicacion</h1>
          <p className="text-slate-500 mt-1">Anuncios y notificaciones para las opticas</p>
        </div>
        <Button onClick={openNew} className="bg-pine-900 hover:bg-pine-800" data-testid="new-announcement-btn">
          <Plus className="w-4 h-4 mr-2" /> Nuevo Anuncio
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="border-slate-200/80">
          <CardContent className="p-4 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-50"><Megaphone className="w-5 h-5 text-blue-600" /></div>
            <div>
              <p className="text-2xl font-bold">{announcements.length}</p>
              <p className="text-xs text-slate-500">Total anuncios</p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-slate-200/80">
          <CardContent className="p-4 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-green-50"><Eye className="w-5 h-5 text-green-600" /></div>
            <div>
              <p className="text-2xl font-bold">{announcements.filter(a => a.is_active).length}</p>
              <p className="text-xs text-slate-500">Activos</p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-slate-200/80">
          <CardContent className="p-4 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-slate-50"><EyeOff className="w-5 h-5 text-slate-500" /></div>
            <div>
              <p className="text-2xl font-bold">{announcements.filter(a => !a.is_active).length}</p>
              <p className="text-xs text-slate-500">Inactivos</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Table */}
      <Card className="border-slate-200/80">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Anuncio</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead className="hidden md:table-cell">Segmento</TableHead>
                <TableHead className="hidden md:table-cell">Vigencia</TableHead>
                <TableHead className="text-center hidden sm:table-cell">Metricas</TableHead>
                <TableHead className="text-center">Activo</TableHead>
                <TableHead className="text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {announcements.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-12 text-slate-500">
                    <Megaphone className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p className="font-medium">Sin anuncios</p>
                    <p className="text-sm mt-1">Crea tu primer anuncio para las opticas</p>
                  </TableCell>
                </TableRow>
              ) : (
                announcements.map(ann => (
                  <TableRow key={ann._id} data-testid={`announcement-row-${ann._id}`}>
                    <TableCell>
                      <div>
                        <p className="font-medium text-slate-900 text-sm">{ann.title}</p>
                        <p className="text-xs text-slate-500 truncate max-w-[250px]">{ann.message}</p>
                      </div>
                    </TableCell>
                    <TableCell>{getTypeBadge(ann.type)}</TableCell>
                    <TableCell className="hidden md:table-cell">
                      <div className="flex flex-wrap gap-1">
                        {(ann.target_plans || []).length === 0 && (ann.target_cities || []).length === 0
                          ? <Badge variant="outline" className="text-[10px]">Todos</Badge>
                          : <>
                              {(ann.target_plans || []).map(p => <Badge key={p} variant="secondary" className="text-[10px]">{p}</Badge>)}
                              {(ann.target_cities || []).map(c => <Badge key={c} variant="outline" className="text-[10px]">{c}</Badge>)}
                            </>
                        }
                      </div>
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-xs text-slate-500">
                      <div className="flex items-center gap-1">
                        <CalendarDays className="w-3 h-3" />
                        {ann.start_date} {ann.end_date ? `- ${ann.end_date}` : ''}
                      </div>
                    </TableCell>
                    <TableCell className="text-center hidden sm:table-cell">
                      <button
                        onClick={() => openMetrics(ann)}
                        className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs hover:bg-slate-100 transition-colors"
                        data-testid={`metrics-btn-${ann._id}`}
                      >
                        <Eye className="w-3 h-3 text-blue-500" />
                        <span className="font-medium text-slate-700">{ann.views_count || 0}</span>
                        <span className="text-slate-300">|</span>
                        <MousePointerClick className="w-3 h-3 text-amber-500" />
                        <span className="font-medium text-slate-700">{ann.dismissals_count || 0}</span>
                      </button>
                    </TableCell>
                    <TableCell className="text-center">
                      <Switch
                        checked={ann.is_active}
                        onCheckedChange={() => handleToggleActive(ann)}
                        data-testid={`toggle-${ann._id}`}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" onClick={() => openEdit(ann)} data-testid={`edit-ann-${ann._id}`}>
                          <Edit className="w-4 h-4 text-slate-500" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => { setToDelete(ann); setDeleteDialogOpen(true); }} data-testid={`delete-ann-${ann._id}`}>
                          <Trash2 className="w-4 h-4 text-red-500" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-heading">{editing ? 'Editar Anuncio' : 'Nuevo Anuncio'}</DialogTitle>
            <DialogDescription>{editing ? 'Modifica el anuncio' : 'Crea un nuevo anuncio para las opticas'}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label>Titulo *</Label>
              <Input value={form.title} onChange={(e) => setForm({...form, title: e.target.value})}
                placeholder="Ej: Mantenimiento programado" data-testid="ann-title-input" />
            </div>
            <div className="space-y-1.5">
              <Label>Mensaje *</Label>
              <Textarea value={form.message} onChange={(e) => setForm({...form, message: e.target.value})}
                placeholder="Escribe el contenido del anuncio..." rows={3} data-testid="ann-message-input" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Tipo</Label>
                <Select value={form.type} onValueChange={(v) => setForm({...form, type: v})}>
                  <SelectTrigger data-testid="ann-type-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {TYPE_OPTIONS.map(t => (
                      <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Ciudad (opcional)</Label>
                <Input value={(form.target_cities || []).join(', ')}
                  onChange={(e) => setForm({...form, target_cities: e.target.value ? e.target.value.split(',').map(c => c.trim()).filter(Boolean) : []})}
                  placeholder="Ej: Guatemala, Mixco" data-testid="ann-cities-input" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Dirigido a planes</Label>
              <div className="flex flex-wrap gap-2" data-testid="ann-plans-filter">
                {planNames.map(p => (
                  <button key={p} type="button" onClick={() => togglePlan(p)}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                      form.target_plans.includes(p) ? 'bg-pine-900 text-white border-pine-900' : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'
                    }`} data-testid={`ann-plan-${p.toLowerCase()}`}>{p}</button>
                ))}
              </div>
              <p className="text-[10px] text-slate-400">Si no seleccionas ninguno, se envia a todos</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Fecha inicio</Label>
                <Input type="date" value={form.start_date} onChange={(e) => setForm({...form, start_date: e.target.value})}
                  data-testid="ann-start-date" />
              </div>
              <div className="space-y-1.5">
                <Label>Fecha fin (opcional)</Label>
                <Input type="date" value={form.end_date} onChange={(e) => setForm({...form, end_date: e.target.value})}
                  data-testid="ann-end-date" />
                <p className="text-[10px] text-slate-400">Vacio = sin fecha de expiracion</p>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={handleSave} disabled={saving} className="bg-pine-900 hover:bg-pine-800" data-testid="ann-save-btn">
              {saving ? 'Guardando...' : editing ? 'Actualizar' : 'Crear Anuncio'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Eliminar Anuncio</DialogTitle>
            <DialogDescription>Eliminar <strong>{toDelete?.title}</strong>? Esta accion no se puede deshacer.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>Cancelar</Button>
            <Button variant="destructive" onClick={handleDelete} data-testid="ann-delete-confirm">Eliminar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Metrics Dialog */}
      <Dialog open={metricsDialogOpen} onOpenChange={setMetricsDialogOpen}>
        <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-heading flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-pine-700" /> Metricas del Anuncio
            </DialogTitle>
            <DialogDescription>{metricsAnn?.title}</DialogDescription>
          </DialogHeader>
          {!metricsData ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-pine-900"></div>
            </div>
          ) : (
            <div className="space-y-5 py-2">
              {/* Summary Cards */}
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-lg bg-blue-50 text-center">
                  <Eye className="w-5 h-5 text-blue-600 mx-auto" />
                  <p className="text-2xl font-bold text-blue-900 mt-1">{metricsData.views_count}</p>
                  <p className="text-[10px] text-blue-600 font-medium">Opticas vieron</p>
                </div>
                <div className="p-3 rounded-lg bg-amber-50 text-center">
                  <MousePointerClick className="w-5 h-5 text-amber-600 mx-auto" />
                  <p className="text-2xl font-bold text-amber-900 mt-1">{metricsData.dismissals_count}</p>
                  <p className="text-[10px] text-amber-600 font-medium">Descartaron</p>
                </div>
                <div className="p-3 rounded-lg bg-slate-50 text-center">
                  <BarChart3 className="w-5 h-5 text-slate-600 mx-auto" />
                  <p className="text-2xl font-bold text-slate-900 mt-1">
                    {metricsData.views_count > 0 ? Math.round((metricsData.dismissals_count / metricsData.views_count) * 100) : 0}%
                  </p>
                  <p className="text-[10px] text-slate-600 font-medium">Tasa descarte</p>
                </div>
              </div>

              {/* Views Detail */}
              {metricsData.view_details.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Opticas que vieron ({metricsData.views_count})</p>
                  <div className="space-y-1.5 max-h-[150px] overflow-y-auto pr-1">
                    {metricsData.view_details.map((v, i) => (
                      <div key={`view-${v.company_name}-${v.date}`} className="flex items-center justify-between p-2 rounded-lg bg-blue-50/50 border border-blue-100" data-testid={`view-detail-${i}`}>
                        <div>
                          <p className="text-sm font-medium text-slate-800">{v.company_name}</p>
                          <p className="text-[10px] text-slate-500">{v.user_name}</p>
                        </div>
                        <span className="text-[10px] text-slate-400">{v.date}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Dismissals Detail */}
              {metricsData.dismiss_details.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Opticas que descartaron ({metricsData.dismissals_count})</p>
                  <div className="space-y-1.5 max-h-[150px] overflow-y-auto pr-1">
                    {metricsData.dismiss_details.map((d, i) => (
                      <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-amber-50/50 border border-amber-100" data-testid={`dismiss-detail-${i}`}>
                        <div>
                          <p className="text-sm font-medium text-slate-800">{d.company_name}</p>
                          <p className="text-[10px] text-slate-500">{d.user_name}</p>
                        </div>
                        <span className="text-[10px] text-slate-400">{d.date}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {metricsData.views_count === 0 && metricsData.dismissals_count === 0 && (
                <p className="text-sm text-slate-400 text-center py-4">Sin metricas aun. Las opticas aun no han visto este anuncio.</p>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
