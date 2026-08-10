// Tab de Pacientes de la Jornada (registro rapido con deteccion de duplicados)
import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import { Users, UserPlus, Star } from 'lucide-react';

export default function JornadaPatientsTab({ jornada, reload }) {
  const jid = jornada._id;
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(false);
  const [form, setForm] = useState({ first_name: '', last_name: '', dpi: '', phone: '', whatsapp: '', email: '', gender: '', birth_date: '' });
  const [duplicates, setDuplicates] = useState([]);
  const [checking, setChecking] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [dupCheckTimer, setDupCheckTimer] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/api/jornadas/${jid}/patients`);
      setItems(res.data.items || []);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setLoading(false); }
  }, [jid]);
  useEffect(() => { load(); }, [load]);

  // Debounced duplicate check
  useEffect(() => {
    if (!dialog) return;
    if (dupCheckTimer) clearTimeout(dupCheckTimer);
    if (!form.dpi && !form.phone && !(form.first_name && form.last_name)) {
      setDuplicates([]);
      return;
    }
    const t = setTimeout(async () => {
      setChecking(true);
      try {
        const res = await api.post(`/api/jornadas/${jid}/patients/search`, {
          dpi: form.dpi || null, phone: form.phone || null,
          first_name: form.first_name || null, last_name: form.last_name || null,
        });
        setDuplicates(res.data.matches || []);
      } catch { /* ignore */ } finally { setChecking(false); }
    }, 500);
    setDupCheckTimer(t);
    return () => clearTimeout(t);
  }, [form.dpi, form.phone, form.first_name, form.last_name, dialog]);

  const linkExisting = async (patient) => {
    setProcessing(true);
    try {
      await api.post(`/api/jornadas/${jid}/patients`, { ...form, link_to_patient_id: patient._id });
      toast.success(`${patient.first_name} vinculado a la jornada`);
      setDialog(false);
      resetForm();
      load(); reload?.();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setProcessing(false); }
  };

  const createNew = async () => {
    if (!form.first_name.trim() || !form.last_name.trim() || !form.phone.trim()) {
      toast.error('Nombre, apellido y telefono son obligatorios');
      return;
    }
    setProcessing(true);
    try {
      await api.post(`/api/jornadas/${jid}/patients`, form);
      toast.success('Paciente registrado');
      setDialog(false);
      resetForm();
      load(); reload?.();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setProcessing(false); }
  };

  const resetForm = () => {
    setForm({ first_name: '', last_name: '', dpi: '', phone: '', whatsapp: '', email: '', gender: '', birth_date: '' });
    setDuplicates([]);
  };

  const canOperate = jornada.status === 'activa' || jornada.status === 'planificada';

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-500">Total: <strong className="text-slate-800">{items.length}</strong> paciente(s)</p>
        </div>
        {canOperate && (
          <Button size="sm" className="bg-pine-900 hover:bg-pine-800" onClick={() => setDialog(true)} data-testid="jpat-register-btn">
            <UserPlus className="w-4 h-4 mr-1.5" /> Registrar paciente
          </Button>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-pine-900" /></div>
      ) : items.length === 0 ? (
        <Card className="border-dashed border-slate-300"><CardContent className="py-10 text-center">
          <Users className="w-10 h-10 text-slate-400 mx-auto mb-2" />
          <p className="text-sm text-slate-600">Aun no hay pacientes en esta jornada</p>
        </CardContent></Card>
      ) : (
        <Card><CardContent className="p-0">
          <div className="divide-y divide-slate-100 max-h-[500px] overflow-y-auto">
            {items.map(p => (
              <div key={p._id} className="flex items-center gap-3 p-3 hover:bg-slate-50" data-testid={`jpat-row-${p._id}`}>
                <div className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-xs font-semibold text-slate-600 flex-shrink-0">
                  {p.first_name?.[0]}{p.last_name?.[0]}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-slate-800 truncate">{p.first_name} {p.last_name}</p>
                    {p.is_first_capture_here && (
                      <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[10px]">
                        <Star className="w-2.5 h-2.5 mr-0.5" /> Nuevo
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-slate-500">{p.phone} {p.dpi ? `· DPI ${p.dpi}` : ''}</p>
                </div>
                <p className="text-xs text-slate-400 hidden sm:block">{new Date(p.created_at).toLocaleDateString('es-GT')}</p>
              </div>
            ))}
          </div>
        </CardContent></Card>
      )}

      <Dialog open={dialog} onOpenChange={(o) => { if (!o) { setDialog(false); resetForm(); } else setDialog(true); }}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Registrar paciente</DialogTitle>
            <DialogDescription>Registro rapido — el paciente se guarda en la base central marcado con esta jornada.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5"><Label>Nombre *</Label><Input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} data-testid="jpat-first" /></div>
              <div className="space-y-1.5"><Label>Apellido *</Label><Input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} data-testid="jpat-last" /></div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5"><Label>DPI</Label><Input value={form.dpi} onChange={(e) => setForm({ ...form, dpi: e.target.value })} data-testid="jpat-dpi" /></div>
              <div className="space-y-1.5"><Label>Telefono *</Label><Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} data-testid="jpat-phone" /></div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5"><Label>WhatsApp</Label><Input value={form.whatsapp} onChange={(e) => setForm({ ...form, whatsapp: e.target.value })} /></div>
              <div className="space-y-1.5"><Label>Email</Label><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5"><Label>Genero</Label><Input value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })} placeholder="M / F / Otro" /></div>
              <div className="space-y-1.5"><Label>Fecha nacimiento</Label><Input type="date" value={form.birth_date} onChange={(e) => setForm({ ...form, birth_date: e.target.value })} /></div>
            </div>

            {duplicates.length > 0 && (
              <div className="rounded-md border border-amber-200 bg-amber-50 p-3 space-y-2" data-testid="jpat-duplicates">
                <p className="text-xs font-semibold text-amber-800">Pacientes similares encontrados — vincula en vez de duplicar:</p>
                {duplicates.map(d => (
                  <button
                    key={d._id}
                    type="button"
                    onClick={() => linkExisting(d)}
                    disabled={processing}
                    className="w-full text-left p-2 rounded bg-white border border-amber-200 hover:border-amber-400 transition-colors text-sm"
                    data-testid={`jpat-link-${d._id}`}
                  >
                    <p className="font-medium">{d.first_name} {d.last_name}</p>
                    <p className="text-xs text-slate-500">{d.phone} {d.dpi ? `· ${d.dpi}` : ''} · {(d.jornada_ids || []).length} jornada(s)</p>
                  </button>
                ))}
              </div>
            )}
            {checking && <p className="text-[11px] text-slate-400">Verificando duplicados...</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setDialog(false); resetForm(); }}>Cancelar</Button>
            <Button className="bg-pine-900 hover:bg-pine-800" disabled={processing} onClick={createNew} data-testid="jpat-create-confirm">
              {processing ? 'Guardando...' : 'Crear como nuevo'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
