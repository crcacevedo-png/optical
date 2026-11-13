import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Stethoscope, Search, X } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../../context/AuthContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Field, TextIn, AreaIn, NativeSelect } from './EvalFields';
import { apiError } from './examShared';

export const EXAM_TYPES = [{ v: 'primera_vez', l: 'Primera vez' }, { v: 'control', l: 'Control' }, { v: 'urgencia', l: 'Urgencia' }];
const today = () => new Date().toISOString().slice(0, 10);
const nowTime = () => new Date().toTimeString().slice(0, 5);
const fullName = (p) => p?.name || `${p?.first_name || ''} ${p?.last_name || ''}`.trim();

function PatientPicker({ value, onChange }) {
  const [q, setQ] = useState('');
  const [list, setList] = useState([]);
  useEffect(() => {
    if (value) return undefined;
    const t = setTimeout(async () => {
      try { const { data } = await api.get('/api/patients', { params: { limit: 8, search: q || undefined } }); setList(data.patients || []); }
      catch { setList([]); }
    }, 250);
    return () => clearTimeout(t);
  }, [q, value]);
  if (value) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-teal-200 bg-teal-50 px-3 h-10 text-sm" data-testid="new-exam-patient-selected">
        <span className="flex-1 font-medium text-teal-900 truncate">{fullName(value)}</span>
        <button type="button" onClick={() => onChange(null)} className="text-teal-700 hover:text-teal-900" data-testid="new-exam-patient-clear"><X className="w-4 h-4" /></button>
      </div>
    );
  }
  return (
    <div className="space-y-1.5">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nombre, teléfono o DPI…" className="pl-9" data-testid="new-exam-patient-search" />
      </div>
      <ul className="max-h-48 overflow-y-auto rounded-md border border-slate-200 divide-y divide-slate-100">
        {list.length === 0 && <li className="px-3 py-2 text-xs text-slate-400">Sin resultados</li>}
        {list.map((p) => (
          <li key={p._id}>
            <button type="button" onClick={() => onChange(p)} className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50" data-testid={`new-exam-patient-opt-${p._id}`}>
              <span className="font-medium text-slate-800">{fullName(p)}</span> <span className="text-xs text-slate-400">{p.phone}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Inicia un examen (consulta) y abre el espacio de trabajo de 4 pasos.
export function NewExamDialog({ open, onOpenChange, patient = null, appointmentId = null }) {
  const navigate = useNavigate();
  const [p, setP] = useState(patient);
  const [f, setF] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!open) return;
    setP(patient);
    setF({ consultation_date: today(), consultation_time: nowTime(), consultation_type: 'primera_vez', chief_complaint: '' });
  }, [open, patient?._id]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));

  const submit = async () => {
    if (!p?._id) { toast.error('Selecciona un paciente'); return; }
    if (!f.chief_complaint?.trim()) { toast.error('Indica el motivo de consulta'); return; }
    setBusy(true);
    try {
      const { data } = await api.post('/api/consultations', { ...f, patient_id: p._id, appointment_id: appointmentId || undefined });
      toast.success(`Examen ${data.exam_code} iniciado`);
      onOpenChange(false);
      navigate(`/exams/${data._id}`);
    } catch (err) { toast.error(apiError(err, 'No se pudo iniciar el examen')); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="new-exam-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Stethoscope className="w-5 h-5 text-teal-600" /> Nuevo examen</DialogTitle>
          <DialogDescription>Evaluación → Refracción final → Preparar recetas → Imprimir.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Field label="Paciente *"><PatientPicker value={p} onChange={setP} /></Field>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Fecha"><TextIn type="date" value={f.consultation_date} onChange={(v) => set('consultation_date', v)} testId="new-exam-date" /></Field>
            <Field label="Hora"><TextIn type="time" value={f.consultation_time} onChange={(v) => set('consultation_time', v)} testId="new-exam-time" /></Field>
            <Field label="Tipo"><NativeSelect value={f.consultation_type} onChange={(v) => set('consultation_type', v)} options={EXAM_TYPES} testId="new-exam-type" /></Field>
          </div>
          <Field label="Motivo de consulta *"><AreaIn value={f.chief_complaint} onChange={(v) => set('chief_complaint', v)} placeholder="Motivo principal referido por el paciente" testId="new-exam-chief-complaint" /></Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="new-exam-cancel">Cancelar</Button>
          <Button className="bg-pine-700 hover:bg-pine-800" onClick={submit} disabled={busy} data-testid="new-exam-submit">
            {busy && <Loader2 className="w-4 h-4 mr-2 animate-spin" />} Iniciar examen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
