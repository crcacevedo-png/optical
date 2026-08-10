import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { toast } from 'sonner';
import { ArrowLeft, ChevronRight, ChevronLeft, Tent, Wallet, Package, Users } from 'lucide-react';

const STEPS = [
  { key: 'general', label: 'Datos generales', icon: Tent },
  { key: 'cash', label: 'Configuracion de caja', icon: Wallet },
  { key: 'inventory', label: 'Fuentes de inventario', icon: Package },
  { key: 'team', label: 'Equipo y meta', icon: Users },
];

const emptyForm = {
  name: '',
  start_date: '',
  end_date: '',
  responsible_branch_id: '',
  location: '',
  address: '',
  municipality: '',
  department: '',
  partner_entity: '',
  manager_user_id: '',
  team_user_ids: [],
  description: '',
  cash_config: { mode: 'own', initial_fund: 0 },
  inventory_config: { use_branch_stock: true, use_consignment: false, prioritize_consignment: true },
  price_list_discount_percent: '',
  goal_amount: '',
  goal_patients: '',
};

export default function JornadaFormPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const isEdit = Boolean(id);
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(emptyForm);
  const [branches, setBranches] = useState([]);
  const [users, setUsers] = useState([]);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(isEdit);

  const load = useCallback(async () => {
    try {
      const [bRes, uRes] = await Promise.all([
        api.get('/api/branches'),
        api.get('/api/users').catch(() => ({ data: [] })),
      ]);
      setBranches(bRes.data || []);
      setUsers(uRes.data || []);
      if (isEdit) {
        const jRes = await api.get(`/api/jornadas/${id}`);
        const j = jRes.data;
        setForm({
          ...emptyForm,
          ...j,
          cash_config: j.cash_config || emptyForm.cash_config,
          inventory_config: j.inventory_config || emptyForm.inventory_config,
          team_user_ids: j.team_user_ids || [],
          price_list_discount_percent: j.price_list_discount_percent ?? '',
          goal_amount: j.goal_amount ?? '',
          goal_patients: j.goal_patients ?? '',
          manager_user_id: j.manager_user_id || '',
        });
      }
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, [id, isEdit]);

  useEffect(() => { load(); }, [load]);

  const canNext = () => {
    if (step === 0) {
      return form.name.trim() && form.start_date && form.end_date && form.responsible_branch_id;
    }
    if (step === 2) {
      return form.inventory_config.use_branch_stock || form.inventory_config.use_consignment;
    }
    return true;
  };

  const handleSubmit = async () => {
    // Validaciones finales
    if (!form.name.trim() || !form.start_date || !form.end_date || !form.responsible_branch_id) {
      setStep(0);
      toast.error('Completa los datos generales');
      return;
    }
    if (form.end_date < form.start_date) {
      setStep(0);
      toast.error('La fecha de fin no puede ser anterior a la de inicio');
      return;
    }
    if (!form.inventory_config.use_branch_stock && !form.inventory_config.use_consignment) {
      setStep(2);
      toast.error('Selecciona al menos una fuente de inventario');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        ...form,
        price_list_discount_percent: form.price_list_discount_percent === '' ? null : parseFloat(form.price_list_discount_percent),
        goal_amount: form.goal_amount === '' ? null : parseFloat(form.goal_amount),
        goal_patients: form.goal_patients === '' ? null : parseInt(form.goal_patients, 10),
        manager_user_id: form.manager_user_id || null,
        cash_config: {
          ...form.cash_config,
          initial_fund: parseFloat(form.cash_config.initial_fund) || 0,
        },
      };
      if (isEdit) {
        await api.put(`/api/jornadas/${id}`, payload);
        toast.success('Jornada actualizada');
        navigate(`/jornadas/${id}`);
      } else {
        const res = await api.post('/api/jornadas', payload);
        toast.success('Jornada creada');
        navigate(`/jornadas/${res.data._id}`);
      }
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSaving(false);
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
    <div className="space-y-6 max-w-3xl mx-auto" data-testid="jornada-form-page">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/jornadas')} data-testid="back-btn">
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">
            {isEdit ? 'Editar Jornada' : 'Nueva Jornada'}
          </h1>
          <p className="text-sm text-slate-500">Paso {step + 1} de {STEPS.length} · {STEPS[step].label}</p>
        </div>
      </div>

      {/* Stepper */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2" data-testid="jornada-stepper">
        {STEPS.map((s, idx) => {
          const done = idx < step;
          const active = idx === step;
          const Icon = s.icon;
          return (
            <div key={s.key} className="flex items-center gap-2 flex-shrink-0">
              <button
                type="button"
                onClick={() => idx <= step && setStep(idx)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  active ? 'bg-pine-900 text-white' :
                  done ? 'bg-emerald-100 text-emerald-700' :
                  'bg-slate-100 text-slate-500'
                }`}
                data-testid={`step-${s.key}`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">{s.label}</span>
                <span className="sm:hidden">{idx + 1}</span>
              </button>
              {idx < STEPS.length - 1 && <ChevronRight className="w-4 h-4 text-slate-300" />}
            </div>
          );
        })}
      </div>

      <Card className="border-slate-200/80">
        <CardContent className="pt-6 space-y-4">
          {step === 0 && (
            <>
              <div className="space-y-1.5">
                <Label>Nombre de la jornada *</Label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Jornada Visual Municipalidad de Mixco — Marzo"
                  data-testid="input-name"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Fecha de inicio *</Label>
                  <Input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} data-testid="input-start" />
                </div>
                <div className="space-y-1.5">
                  <Label>Fecha de fin *</Label>
                  <Input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} data-testid="input-end" />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label>Sucursal responsable *</Label>
                <Select value={form.responsible_branch_id} onValueChange={(v) => setForm({ ...form, responsible_branch_id: v })}>
                  <SelectTrigger data-testid="input-branch"><SelectValue placeholder="Selecciona sucursal" /></SelectTrigger>
                  <SelectContent>
                    {branches.map((b) => <SelectItem key={b._id} value={b._id}>{b.name}</SelectItem>)}
                  </SelectContent>
                </Select>
                <p className="text-[11px] text-slate-400">La jornada se consolida en los reportes de esta sucursal.</p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Lugar / Ubicacion</Label>
                  <Input value={form.location || ''} onChange={(e) => setForm({ ...form, location: e.target.value })} placeholder="Ej. Salon Municipal" data-testid="input-location" />
                </div>
                <div className="space-y-1.5">
                  <Label>Entidad aliada</Label>
                  <Input value={form.partner_entity || ''} onChange={(e) => setForm({ ...form, partner_entity: e.target.value })} placeholder="Municipalidad, ONG, empresa..." data-testid="input-partner" />
                </div>
                <div className="space-y-1.5">
                  <Label>Direccion</Label>
                  <Input value={form.address || ''} onChange={(e) => setForm({ ...form, address: e.target.value })} data-testid="input-address" />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1.5">
                    <Label>Municipio</Label>
                    <Input value={form.municipality || ''} onChange={(e) => setForm({ ...form, municipality: e.target.value })} data-testid="input-municipality" />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Depto.</Label>
                    <Input value={form.department || ''} onChange={(e) => setForm({ ...form, department: e.target.value })} data-testid="input-department" />
                  </div>
                </div>
              </div>
              <div className="space-y-1.5">
                <Label>Descripcion / notas internas</Label>
                <Textarea rows={2} value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="input-description" />
              </div>
            </>
          )}

          {step === 1 && (
            <>
              <div className="space-y-3">
                <Label className="text-sm font-semibold">Modalidad de caja</Label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setForm({ ...form, cash_config: { ...form.cash_config, mode: 'own' } })}
                    className={`text-left p-3 rounded-lg border-2 transition-colors ${form.cash_config.mode === 'own' ? 'border-pine-900 bg-pine-50' : 'border-slate-200 hover:border-slate-300'}`}
                    data-testid="cash-mode-own"
                  >
                    <p className="font-semibold text-sm text-slate-900">Caja propia (recomendado)</p>
                    <p className="text-xs text-slate-500 mt-1">Exclusiva del evento, con fondo, movimientos y arqueo independientes.</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => setForm({ ...form, cash_config: { ...form.cash_config, mode: 'branch' } })}
                    className={`text-left p-3 rounded-lg border-2 transition-colors ${form.cash_config.mode === 'branch' ? 'border-pine-900 bg-pine-50' : 'border-slate-200 hover:border-slate-300'}`}
                    data-testid="cash-mode-branch"
                  >
                    <p className="font-semibold text-sm text-slate-900">Caja de la sucursal</p>
                    <p className="text-xs text-slate-500 mt-1">Los movimientos se registran en la caja de la sucursal responsable.</p>
                  </button>
                </div>
              </div>
              {form.cash_config.mode === 'own' && (
                <div className="space-y-1.5">
                  <Label>Fondo inicial de efectivo (Q)</Label>
                  <Input
                    type="number" min="0" step="1"
                    value={form.cash_config.initial_fund}
                    onChange={(e) => setForm({ ...form, cash_config: { ...form.cash_config, initial_fund: e.target.value } })}
                    data-testid="input-initial-fund"
                  />
                  <p className="text-[11px] text-slate-400">Se confirmara al momento de aperturar la caja.</p>
                </div>
              )}
            </>
          )}

          {step === 2 && (
            <>
              <p className="text-sm text-slate-500">Elige de donde saldra el inventario. Puedes usar una o ambas fuentes.</p>
              <div className="space-y-3">
                <ModuleSwitch
                  checked={form.inventory_config.use_branch_stock}
                  onChange={(v) => setForm({ ...form, inventory_config: { ...form.inventory_config, use_branch_stock: v } })}
                  label="Traslado desde sucursal"
                  desc="Selecciona productos de una sucursal para trasladarlos temporalmente a la jornada. El remanente vuelve al cerrar."
                  testId="inv-branch"
                />
                <ModuleSwitch
                  checked={form.inventory_config.use_consignment}
                  onChange={(v) => setForm({ ...form, inventory_config: { ...form.inventory_config, use_consignment: v } })}
                  label="Consignacion (carga por Excel)"
                  desc="Inventario aportado por un proveedor / aliado solo para este evento. No afecta el stock de sucursales."
                  testId="inv-consignment"
                  soon="Disponible en la siguiente iteracion"
                />
              </div>
              {form.inventory_config.use_branch_stock && form.inventory_config.use_consignment && (
                <div className="pt-2 border-t border-slate-100 space-y-2">
                  <Label className="text-sm">Modo mixto — al vender, priorizar</Label>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setForm({ ...form, inventory_config: { ...form.inventory_config, prioritize_consignment: true } })}
                      className={`flex-1 p-2 rounded-md border text-xs ${form.inventory_config.prioritize_consignment ? 'border-pine-900 bg-pine-50 text-pine-900' : 'border-slate-200'}`}
                      data-testid="prioritize-consignment"
                    >
                      Consignacion primero
                    </button>
                    <button
                      type="button"
                      onClick={() => setForm({ ...form, inventory_config: { ...form.inventory_config, prioritize_consignment: false } })}
                      className={`flex-1 p-2 rounded-md border text-xs ${!form.inventory_config.prioritize_consignment ? 'border-pine-900 bg-pine-50 text-pine-900' : 'border-slate-200'}`}
                      data-testid="prioritize-branch"
                    >
                      Sucursal primero
                    </button>
                  </div>
                </div>
              )}
              <div className="pt-3 border-t border-slate-100 space-y-1.5">
                <Label>Descuento global de la jornada (%)</Label>
                <Input
                  type="number" min="0" max="100" step="0.5"
                  value={form.price_list_discount_percent}
                  onChange={(e) => setForm({ ...form, price_list_discount_percent: e.target.value })}
                  placeholder="Opcional"
                  data-testid="input-discount"
                />
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <div className="space-y-1.5">
                <Label>Responsable de la jornada</Label>
                <Select value={form.manager_user_id || 'none'} onValueChange={(v) => setForm({ ...form, manager_user_id: v === 'none' ? '' : v })}>
                  <SelectTrigger data-testid="input-manager"><SelectValue placeholder="Selecciona un usuario" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Sin asignar</SelectItem>
                    {users.map((u) => <SelectItem key={u._id} value={u._id}>{u.name} · {u.role}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Equipo asignado</Label>
                <div className="border rounded-md p-2 max-h-48 overflow-y-auto space-y-1" data-testid="team-list">
                  {users.length === 0 && <p className="text-xs text-slate-400 py-2 text-center">No hay usuarios disponibles</p>}
                  {users.map((u) => {
                    const selected = form.team_user_ids.includes(u._id);
                    return (
                      <label key={u._id} className="flex items-center gap-2 p-1.5 rounded hover:bg-slate-50 cursor-pointer text-sm">
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={(e) => {
                            const set = new Set(form.team_user_ids);
                            e.target.checked ? set.add(u._id) : set.delete(u._id);
                            setForm({ ...form, team_user_ids: Array.from(set) });
                          }}
                          data-testid={`team-user-${u._id}`}
                        />
                        <span className="flex-1 truncate">{u.name}</span>
                        <Badge variant="secondary" className="text-[10px]">{u.role}</Badge>
                      </label>
                    );
                  })}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 pt-3 border-t border-slate-100">
                <div className="space-y-1.5">
                  <Label>Meta de venta (Q)</Label>
                  <Input
                    type="number" min="0" step="1"
                    value={form.goal_amount}
                    onChange={(e) => setForm({ ...form, goal_amount: e.target.value })}
                    placeholder="Opcional"
                    data-testid="input-goal-amount"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Meta de pacientes</Label>
                  <Input
                    type="number" min="0" step="1"
                    value={form.goal_patients}
                    onChange={(e) => setForm({ ...form, goal_patients: e.target.value })}
                    placeholder="Opcional"
                    data-testid="input-goal-patients"
                  />
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between gap-2">
        <Button
          variant="outline"
          disabled={step === 0}
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          data-testid="prev-step-btn"
        >
          <ChevronLeft className="w-4 h-4 mr-1" /> Anterior
        </Button>
        {step < STEPS.length - 1 ? (
          <Button
            disabled={!canNext()}
            onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
            className="bg-pine-900 hover:bg-pine-800"
            data-testid="next-step-btn"
          >
            Siguiente <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        ) : (
          <Button
            disabled={saving}
            onClick={handleSubmit}
            className="bg-pine-900 hover:bg-pine-800"
            data-testid="submit-btn"
          >
            {saving ? 'Guardando...' : isEdit ? 'Actualizar Jornada' : 'Crear Jornada'}
          </Button>
        )}
      </div>
    </div>
  );
}

function ModuleSwitch({ checked, onChange, label, desc, testId, soon }) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors">
      <Switch checked={checked} onCheckedChange={onChange} data-testid={testId} />
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold text-slate-800">{label}</p>
          {soon && <Badge variant="secondary" className="text-[10px] bg-amber-50 text-amber-700 border-amber-200">Proximamente</Badge>}
        </div>
        <p className="text-xs text-slate-500 mt-0.5">{desc}</p>
      </div>
    </div>
  );
}
