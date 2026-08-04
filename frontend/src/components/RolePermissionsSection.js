import React, { useState, useEffect } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Checkbox } from './ui/checkbox';
import { Badge } from './ui/badge';
import { Users, ShieldCheck, Info } from 'lucide-react';
import { toast } from 'sonner';

// Modulos con label + descripcion (mismo orden que sidebar)
const MODULE_META = {
  dashboard: { label: 'Dashboard', hint: 'Resumen general con metricas', locked: true },
  patients: { label: 'Pacientes', hint: 'Ficha, historial clinico y gestion' },
  consultations: { label: 'Consultas', hint: 'Registro de consultas oftalmicas' },
  agenda: { label: 'Agenda', hint: 'Citas y calendario' },
  prescriptions: { label: 'Recetas', hint: 'Emision de recetas y PDF' },
  quotations: { label: 'Cotizaciones', hint: 'Cotizaciones para pacientes' },
  inventory: { label: 'Inventario', hint: 'Productos, stock y movimientos', planKey: 'inventario' },
  sales: { label: 'Ventas', hint: 'Registro y gestion de ventas', planKey: 'ventas' },
  'cash-register': { label: 'Caja', hint: 'Abrir/cerrar caja diaria', planKey: 'ventas' },
  receivables: { label: 'Cuentas por Cobrar', hint: 'Ventas con saldo pendiente', planKey: 'ventas' },
  suppliers: { label: 'Proveedores', hint: 'Gestion de proveedores', planKey: 'proveedores' },
  finance: { label: 'Finanzas', hint: 'Ingresos y gastos', planKey: 'finanzas' },
  reports: { label: 'Reportes', hint: 'Reportes generales' },
};

const ROLES = [
  { key: 'user', label: 'Atencion al Cliente', desc: 'Personal de piso, cajeros, vendedores' },
];

export function RolePermissionsSection() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [permissions, setPermissions] = useState({ user: [] });
  const [available, setAvailable] = useState([]);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/api/settings/role-permissions');
        setPermissions(data.permissions || { user: [] });
        setAvailable(data.available_modules || []);
      } catch (err) {
        toast.error(formatApiErrorDetail(err.response?.data?.detail));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const toggle = (role, moduleKey) => {
    setPermissions((prev) => {
      const current = prev[role] || [];
      const next = current.includes(moduleKey)
        ? current.filter((k) => k !== moduleKey)
        : [...current, moduleKey];
      return { ...prev, [role]: next };
    });
  };

  const setAll = (role, on) => {
    setPermissions((prev) => ({
      ...prev,
      [role]: on ? [...available] : ['dashboard'],  // dashboard siempre queda
    }));
  };

  const save = async () => {
    try {
      setSaving(true);
      await api.put('/api/settings/role-permissions', { permissions });
      toast.success('Permisos actualizados. Los usuarios veran los cambios al proximo login.');
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card className="border-slate-200/80" data-testid="role-permissions-loading">
        <CardContent className="p-6">
          <div className="animate-pulse text-slate-400">Cargando permisos...</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-slate-200/80" data-testid="role-permissions-card">
      <CardHeader>
        <CardTitle className="font-heading text-lg flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-violet-700" />
          Permisos por Rol
        </CardTitle>
        <p className="text-sm text-slate-500 mt-1">
          Configura que modulos del sistema puede ver cada rol de usuario en su menu lateral.
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="p-3 rounded-lg bg-blue-50 border border-blue-100 flex items-start gap-2 text-sm text-blue-800">
          <Info className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <p><strong>Administradores</strong> siempre tienen acceso a todos los modulos habilitados en el plan.</p>
            <p className="text-xs mt-1">Los cambios se aplican al proximo inicio de sesion del usuario.</p>
          </div>
        </div>

        {ROLES.map((role) => {
          const active = permissions[role.key] || [];
          return (
            <div key={role.key} className="border border-slate-200 rounded-lg overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 bg-slate-50 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-slate-500" />
                  <div>
                    <p className="font-semibold text-slate-900 text-sm">{role.label}</p>
                    <p className="text-xs text-slate-500">{role.desc}</p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <Badge variant="outline" className="text-xs">{active.length} / {available.length}</Badge>
                  <Button
                    size="sm" variant="ghost" className="h-7 text-xs"
                    onClick={() => setAll(role.key, true)}
                    data-testid={`select-all-${role.key}`}
                  >
                    Todo
                  </Button>
                  <Button
                    size="sm" variant="ghost" className="h-7 text-xs"
                    onClick={() => setAll(role.key, false)}
                    data-testid={`select-none-${role.key}`}
                  >
                    Solo Dashboard
                  </Button>
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 p-4">
                {available.map((mod) => {
                  const meta = MODULE_META[mod] || { label: mod, hint: '' };
                  const checked = active.includes(mod);
                  const locked = meta.locked; // dashboard siempre visible
                  return (
                    <label
                      key={mod}
                      className={`flex items-start gap-2.5 p-2.5 rounded-lg border transition-colors cursor-pointer ${
                        checked ? 'border-violet-300 bg-violet-50/40' : 'border-slate-200 hover:border-slate-300'
                      } ${locked ? 'opacity-70 cursor-not-allowed' : ''}`}
                      data-testid={`perm-${role.key}-${mod}`}
                    >
                      <Checkbox
                        checked={checked || locked}
                        disabled={locked}
                        onCheckedChange={() => !locked && toggle(role.key, mod)}
                        className="mt-0.5"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-800">{meta.label}</p>
                        {meta.hint && <p className="text-[11px] text-slate-500 leading-tight mt-0.5">{meta.hint}</p>}
                        {meta.planKey && (
                          <Badge variant="secondary" className="text-[10px] mt-1 h-4 px-1.5">
                            Modulo de plan
                          </Badge>
                        )}
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>
          );
        })}

        <div className="flex justify-end pt-2 border-t border-slate-100">
          <Button
            onClick={save}
            disabled={saving}
            className="bg-violet-600 hover:bg-violet-700"
            data-testid="save-role-permissions"
          >
            {saving ? 'Guardando...' : 'Guardar cambios'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
