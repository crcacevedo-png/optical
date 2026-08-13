import React, { useEffect, useState } from 'react';
import { api, formatApiErrorDetail } from '../../context/AuthContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { toast } from 'sonner';

const QUICK_RANGES = [
  { l: '1 semana', d: 7 },
  { l: '1 mes', d: 30 },
  { l: '3 meses', d: 90 },
  { l: '6 meses', d: 180 },
  { l: '1 ano', d: 365 },
];

export function NextAppointmentDialog({
  open,
  onOpenChange,
  patientId,
  professionalId,
  professionalName,
  onSaved,
}) {
  const [form, setForm] = useState({
    date: '', time: '09:00', duration: 30, type: 'general', notes: 'Control de rutina',
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      const in6mo = new Date();
      in6mo.setMonth(in6mo.getMonth() + 6);
      setForm({
        date: in6mo.toISOString().slice(0, 10),
        time: '09:00',
        duration: 30,
        type: 'general',
        notes: 'Control de rutina',
      });
    }
  }, [open]);

  const save = async () => {
    if (!patientId) {
      toast.error('Paciente no valido');
      return;
    }
    if (!form.date || !form.time) {
      toast.error('Fecha y hora obligatorias');
      return;
    }
    setSaving(true);
    try {
      await api.post('/api/appointments', {
        patient_id: patientId,
        date: form.date,
        time: form.time,
        duration: parseInt(form.duration, 10) || 30,
        type: form.type,
        status: 'pendiente',
        notes: form.notes,
        professional_id: professionalId || null,
        professional_name: professionalName || null,
      });
      toast.success(`Proxima cita agendada para ${form.date} ${form.time}`);
      onOpenChange(false);
      if (onSaved) onSaved();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="next-appt-dialog">
        <DialogHeader>
          <DialogTitle>Agendar proxima cita</DialogTitle>
          <DialogDescription>
            La consulta se guardo correctamente. Reserva la siguiente cita del paciente ahora - o saltalo si no aplica.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1.5">
              <Label>Fecha *</Label>
              <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} data-testid="next-appt-date" />
            </div>
            <div className="space-y-1.5">
              <Label>Hora *</Label>
              <Input type="time" value={form.time} onChange={(e) => setForm({ ...form, time: e.target.value })} data-testid="next-appt-time" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1.5">
              <Label>Duracion (min)</Label>
              <Input type="number" min="15" step="15" value={form.duration} onChange={(e) => setForm({ ...form, duration: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Tipo</Label>
              <Select value={form.type} onValueChange={(v) => setForm({ ...form, type: v })}>
                <SelectTrigger data-testid="next-appt-type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="general">Control</SelectItem>
                  <SelectItem value="revision">Revision</SelectItem>
                  <SelectItem value="postoperatorio">Postoperatorio</SelectItem>
                  <SelectItem value="entrega">Entrega de lentes</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Motivo / Notas</Label>
            <Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Ej. Control de rutina" data-testid="next-appt-notes" />
          </div>
          <div className="flex flex-wrap gap-1.5 pt-1">
            {QUICK_RANGES.map(o => (
              <Button
                key={o.d}
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  const dt = new Date();
                  dt.setDate(dt.getDate() + o.d);
                  setForm({ ...form, date: dt.toISOString().slice(0, 10) });
                }}
                data-testid={`next-appt-quick-${o.d}`}
              >
                {o.l}
              </Button>
            ))}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="next-appt-skip">Ahora no</Button>
          <Button className="bg-pine-900 hover:bg-pine-800" disabled={saving} onClick={save} data-testid="next-appt-save">
            {saving ? 'Agendando...' : 'Agendar cita'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
