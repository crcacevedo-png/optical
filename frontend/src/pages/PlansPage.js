import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription
} from '../components/ui/dialog';
import { toast } from 'sonner';
import {
  Plus, CreditCard, Edit, Trash2, Package, ShoppingCart, Truck, DollarSign,
  Users, Building2, Crown, Infinity, TrendingUp, BarChart3, Zap, Activity, Tent
} from 'lucide-react';

const ALL_MODULES = [
  { key: 'inventario', label: 'Inventario', icon: Package },
  { key: 'ventas', label: 'Ventas', icon: ShoppingCart },
  { key: 'proveedores', label: 'Proveedores', icon: Truck },
  { key: 'finanzas', label: 'Finanzas', icon: DollarSign },
  { key: 'jornadas', label: 'Jornadas', icon: Tent },
];

const emptyForm = {
  name: '', price: 0, max_branches: 1, max_patients: 50, modules: []
};

const PLAN_COLORS = {
  'Free': 'from-slate-500 to-slate-600',
  'Basic': 'from-blue-500 to-blue-600',
  'Enterprise': 'from-amber-500 to-amber-600',
};

// Simbolo de moneda de la membresia (USD por defecto; Q solo si el plan quedara en GTQ)
const curSymbol = (c) => {
  const u = (c || 'USD').toUpperCase();
  return u === 'GTQ' ? 'Q' : (u === 'USD' ? '$' : u);
};

export default function PlansPage() {
  const [plans, setPlans] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [planToDelete, setPlanToDelete] = useState(null);

  const fetchPlans = useCallback(async () => {
    try {
      const [pRes, sRes] = await Promise.all([
        api.get('/api/plans'),
        api.get('/api/plans/stats/summary').catch(() => ({ data: null })),
      ]);
      setPlans(pRes.data);
      setStats(sRes.data);
    } catch (err) {
      toast.error('Error al cargar planes');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchPlans(); }, [fetchPlans]);

  const openNew = () => {
    setEditing(null);
    setForm(emptyForm);
    setDialogOpen(true);
  };

  const openEdit = (plan) => {
    setEditing(plan);
    setForm({
      name: plan.name, price: plan.price,
      max_branches: plan.max_branches, max_patients: plan.max_patients,
      modules: plan.modules || []
    });
    setDialogOpen(true);
  };

  const toggleModule = (mod) => {
    setForm(prev => ({
      ...prev,
      modules: prev.modules.includes(mod)
        ? prev.modules.filter(m => m !== mod)
        : [...prev.modules, mod]
    }));
  };

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error('Nombre requerido'); return; }
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/api/plans/${editing._id}`, form);
        toast.success('Plan actualizado');
      } else {
        await api.post('/api/plans', form);
        toast.success('Plan creado');
      }
      setDialogOpen(false);
      fetchPlans();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!planToDelete) return;
    try {
      await api.delete(`/api/plans/${planToDelete._id}`);
      toast.success('Plan eliminado');
      setDeleteDialogOpen(false);
      setPlanToDelete(null);
      fetchPlans();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="plans-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Planes</h1>
          <p className="text-slate-500 mt-1">Administra los planes de suscripcion para opticas</p>
        </div>
        <Button onClick={openNew} className="bg-pine-900 hover:bg-pine-800" data-testid="new-plan-btn">
          <Plus className="w-4 h-4 mr-2" /> Nuevo Plan
        </Button>
      </div>

      {/* Analytics Panel */}
      {stats && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" data-testid="plans-stats-panel">
            <StatCard label="MRR proyectado" value={stats.mrr_projected} icon={TrendingUp} color="from-emerald-500 to-teal-500" currency />
            <StatCard label="ARR proyectado" value={stats.arr_projected} icon={Crown} color="from-indigo-500 to-purple-500" currency />
            <StatCard label="Empresas activas" value={stats.total_companies_active} icon={Building2} color="from-blue-500 to-blue-600" />
            <StatCard label="Ingresos 30d" value={stats.revenue_paid_last_30d} icon={DollarSign} color="from-amber-500 to-orange-500" currency subtitle={`${stats.payments_count_last_30d} pagos`} />
          </div>

          {/* Distribucion por plan */}
          {stats.per_plan?.length > 0 && (
            <Card className="border-slate-200/80" data-testid="plans-distribution-card">
              <CardHeader>
                <CardTitle className="font-heading text-lg flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-slate-600" /> Distribucion por plan
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {stats.per_plan.map((row) => {
                    const pct = stats.total_companies_active > 0
                      ? (row.total_companies / stats.total_companies_active) * 100
                      : 0;
                    return (
                      <div key={row.plan_id} className="space-y-1" data-testid={`plan-row-${row.plan_id}`}>
                        <div className="flex items-center justify-between text-sm">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-800">{row.plan_name}</span>
                            <Badge variant="outline" className="text-xs">
                              {row.total_companies} empresa{row.total_companies !== 1 ? 's' : ''}
                            </Badge>
                            {row.companies_yearly > 0 && (
                              <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200 text-xs" variant="outline">
                                <Zap className="w-3 h-3 mr-0.5" /> {row.companies_yearly} anual{row.companies_yearly !== 1 ? 'es' : ''}
                              </Badge>
                            )}
                          </div>
                          <div className="text-right">
                            <p className="font-heading font-bold text-emerald-700">
                              {curSymbol(row.currency)} {row.mrr.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              <span className="text-xs font-normal text-slate-500 ml-1">/mes</span>
                            </p>
                          </div>
                        </div>
                        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-pine-600 to-pine-500 transition-all" style={{ width: `${pct}%` }} />
                        </div>
                        <p className="text-xs text-slate-500">{pct.toFixed(1)}% del total · ARR proyectado {curSymbol(row.currency)} {row.arr.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                      </div>
                    );
                  })}
                </div>
                {stats.plan_changes_last_30d > 0 && (
                  <div className="mt-4 pt-4 border-t border-slate-100 flex items-center gap-2 text-sm text-slate-600">
                    <Activity className="w-4 h-4 text-slate-500" />
                    {stats.plan_changes_last_30d} cambio{stats.plan_changes_last_30d !== 1 ? 's' : ''} de plan en los ultimos 30 dias
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Plan Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {plans.map(plan => {
          const gradient = PLAN_COLORS[plan.name] || 'from-pine-500 to-pine-600';
          return (
            <Card key={plan._id} className="overflow-hidden border-slate-200/80 hover:shadow-lg transition-shadow" data-testid={`plan-card-${plan._id}`}>
              <div className={`bg-gradient-to-r ${gradient} p-5 text-white`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Crown className="w-5 h-5" />
                    <h3 className="font-heading text-lg font-bold">{plan.name}</h3>
                  </div>
                  <div className="flex gap-1">
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-white/80 hover:text-white hover:bg-white/20"
                      onClick={() => openEdit(plan)} data-testid={`edit-plan-${plan._id}`}>
                      <Edit className="w-4 h-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-white/80 hover:text-white hover:bg-white/20"
                      onClick={() => { setPlanToDelete(plan); setDeleteDialogOpen(true); }} data-testid={`delete-plan-${plan._id}`}>
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
                <div className="mt-3">
                  <span className="text-3xl font-bold">{curSymbol(plan.currency)}{plan.price}</span>
                  <span className="text-white/70 text-sm">/mes</span>
                </div>
              </div>
              <CardContent className="p-5 space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2 text-slate-600"><Building2 className="w-4 h-4" /> Sucursales</span>
                    <span className="font-semibold">{plan.max_branches === 0 ? 'Ilimitadas' : plan.max_branches}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2 text-slate-600"><Users className="w-4 h-4" /> Pacientes</span>
                    <span className="font-semibold">{plan.max_patients === 0 ? 'Ilimitados' : plan.max_patients}</span>
                  </div>
                </div>
                <div className="border-t pt-3">
                  <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Modulos incluidos</p>
                  <div className="flex flex-wrap gap-1.5">
                    {['Dashboard', 'Pacientes', 'Consultas', 'Agenda', 'Recetas', 'Cotizaciones'].map(m => (
                      <Badge key={m} variant="secondary" className="text-xs bg-green-50 text-green-700 border-green-200">{m}</Badge>
                    ))}
                    {ALL_MODULES.map(mod => {
                      const included = (plan.modules || []).includes(mod.key);
                      return (
                        <Badge key={mod.key} variant={included ? "secondary" : "outline"}
                          className={`text-xs ${included ? 'bg-blue-50 text-blue-700 border-blue-200' : 'text-slate-400 border-slate-200'}`}>
                          {mod.label}
                        </Badge>
                      );
                    })}
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-heading">{editing ? 'Editar Plan' : 'Nuevo Plan'}</DialogTitle>
            <DialogDescription>{editing ? 'Modifica los parametros del plan' : 'Crea un nuevo plan de suscripcion'}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label>Nombre del Plan *</Label>
              <Input value={form.name} onChange={(e) => setForm({...form, name: e.target.value})}
                placeholder="Ej: Pro" data-testid="plan-name-input" />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label>Precio (USD/mes)</Label>
                <Input type="number" min="0" step="1" value={form.price}
                  onChange={(e) => setForm({...form, price: parseFloat(e.target.value) || 0})}
                  data-testid="plan-price-input" />
              </div>
              <div className="space-y-1.5">
                <Label>Max Sucursales</Label>
                <Input type="number" min="0" value={form.max_branches}
                  onChange={(e) => setForm({...form, max_branches: parseInt(e.target.value) || 0})}
                  data-testid="plan-branches-input" />
                <p className="text-[10px] text-slate-400">0 = ilimitado</p>
              </div>
              <div className="space-y-1.5">
                <Label>Max Pacientes</Label>
                <Input type="number" min="0" value={form.max_patients}
                  onChange={(e) => setForm({...form, max_patients: parseInt(e.target.value) || 0})}
                  data-testid="plan-patients-input" />
                <p className="text-[10px] text-slate-400">0 = ilimitado</p>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Modulos opcionales incluidos</Label>
              <div className="space-y-2">
                {ALL_MODULES.map(mod => (
                  <div key={mod.key} className="flex items-center justify-between p-2.5 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors">
                    <div className="flex items-center gap-2">
                      <mod.icon className="w-4 h-4 text-slate-500" />
                      <span className="text-sm font-medium">{mod.label}</span>
                    </div>
                    <Switch
                      checked={form.modules.includes(mod.key)}
                      onCheckedChange={() => toggleModule(mod.key)}
                      data-testid={`plan-module-${mod.key}`}
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={handleSave} disabled={saving} className="bg-pine-900 hover:bg-pine-800" data-testid="plan-save-btn">
              {saving ? 'Guardando...' : editing ? 'Actualizar' : 'Crear Plan'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Eliminar Plan</DialogTitle>
            <DialogDescription>
              Eliminar el plan <strong>{planToDelete?.name}</strong>? No se puede eliminar si hay empresas asignadas.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>Cancelar</Button>
            <Button variant="destructive" onClick={handleDelete} data-testid="plan-delete-confirm-btn">Eliminar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, color, currency, subtitle }) {
  const formatted = currency
    ? `$ ${(Number(value) || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : (Number(value) || 0).toLocaleString();
  return (
    <div className="bg-white border border-slate-200/80 rounded-xl p-4 hover:shadow-sm transition-shadow" data-testid={`stat-${label.toLowerCase().replace(/\s+/g,'-')}`}>
      <div className="flex items-center gap-2.5 mb-1.5">
        <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${color} flex items-center justify-center`}>
          <Icon className="w-4 h-4 text-white" />
        </div>
        <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">{label}</p>
      </div>
      <p className="font-heading text-2xl font-bold text-slate-900 leading-tight">{formatted}</p>
      {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
    </div>
  );
}
