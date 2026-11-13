import React from 'react';
import { ArrowLeft, CalendarIcon, User, ShieldCheck, PenLine, Unlock, CalendarPlus, Pill, Check } from 'lucide-react';
import { Button } from '../ui/button';
import { fmtDate } from './examShared';

const TYPE_LABELS = { general: 'Consulta general', control: 'Control', urgencia: 'Urgencia', primera_vez: 'Primera vez', seguimiento: 'Seguimiento' };

const ageOf = (b) => {
  if (!b) return null;
  const d = new Date(b);
  if (Number.isNaN(d.getTime())) return null;
  const n = new Date();
  let a = n.getFullYear() - d.getFullYear();
  if (n.getMonth() < d.getMonth() || (n.getMonth() === d.getMonth() && n.getDate() < d.getDate())) a -= 1;
  return a;
};

export function ExamHeader({ exam, onBack, onSign, onReopen, onSchedule, onMedical }) {
  const signed = exam.exam_status === 'firmado';
  const p = exam.patient || {};
  const age = ageOf(p.birth_date);
  return (
    <header className="rounded-2xl border border-slate-200 bg-white shadow-sm p-5" data-testid="exam-header">
      <div className="flex flex-col xl:flex-row xl:items-center gap-4 justify-between">
        <div className="flex items-start gap-3 min-w-0">
          <Button variant="ghost" size="sm" onClick={onBack} className="shrink-0 -ml-2" data-testid="exam-back-btn"><ArrowLeft className="w-4 h-4 mr-1" /> Volver</Button>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-heading text-xl sm:text-2xl font-semibold text-slate-900 truncate" data-testid="exam-patient-name">{p.name || 'Paciente'}</h1>
              <span className="text-xs font-mono text-slate-500 bg-slate-100 rounded px-1.5 py-0.5" data-testid="exam-patient-id">{p.dpi ? `DPI ${p.dpi}` : (p.phone || '—')}</span>
              {age !== null && <span className="text-xs text-slate-500">{age} años</span>}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
              <span className="font-semibold text-slate-700" data-testid="exam-code">Examen {exam.exam_code}</span>
              <span className="inline-flex items-center gap-1"><CalendarIcon className="w-3.5 h-3.5" />{fmtDate(exam.consultation_date)} {exam.consultation_time}</span>
              <span>{TYPE_LABELS[exam.consultation_type] || exam.consultation_type}</span>
              <span className="inline-flex items-center gap-1"><User className="w-3.5 h-3.5" />{exam.professional_name || 'Sin profesional'}</span>
              {signed ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-xs font-semibold text-emerald-800" data-testid="exam-status">
                  <ShieldCheck className="w-3.5 h-3.5" /> Firmado {fmtDate(exam.signed_at)}{exam.signed_by_name ? ` · ${exam.signed_by_name}` : ''}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-xs font-semibold text-amber-800" data-testid="exam-status">En curso</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 xl:justify-end">
          <Button variant="outline" size="sm" onClick={onMedical} data-testid="exam-medical-rx-btn"><Pill className="w-4 h-4 mr-1.5" /> Receta médica</Button>
          <Button variant="outline" size="sm" onClick={onSchedule} data-testid="exam-schedule-btn"><CalendarPlus className="w-4 h-4 mr-1.5" /> Próxima cita</Button>
          {signed ? (
            <Button variant="outline" size="sm" onClick={onReopen} disabled={!exam.permissions?.clinical} data-testid="exam-reopen-btn"><Unlock className="w-4 h-4 mr-1.5" /> Reabrir examen</Button>
          ) : (
            <Button size="sm" className="bg-pine-700 hover:bg-pine-800" onClick={onSign} disabled={!exam.permissions?.clinical} data-testid="exam-sign-btn"><PenLine className="w-4 h-4 mr-1.5" /> Firmar examen</Button>
          )}
        </div>
      </div>
    </header>
  );
}

export function ExamSteps({ steps, onSelect }) {
  const current = steps.findIndex((s) => !s.done);
  return (
    <ol className="grid grid-cols-2 md:grid-cols-4 gap-2" data-testid="exam-steps">
      {steps.map((s, i) => {
        const state = s.done ? 'done' : i === current ? 'active' : 'todo';
        const cls = state === 'done' ? 'border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
          : state === 'active' ? 'border-teal-600 bg-teal-600 text-white shadow-md shadow-teal-600/20 hover:bg-teal-700' : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50';
        return (
          <li key={s.label}>
            <button type="button" onClick={() => onSelect?.(i)} className={`w-full flex items-center gap-2.5 rounded-xl border px-3 py-2.5 text-left transition-colors ${cls}`} data-testid={`exam-step-${i + 1}`} data-state={state}>
              <span className={`w-6 h-6 shrink-0 rounded-full flex items-center justify-center text-xs font-bold ${state === 'active' ? 'bg-white text-teal-700' : state === 'done' ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
                {state === 'done' ? <Check className="w-3.5 h-3.5" /> : i + 1}
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold leading-tight">{s.label}</span>
                {s.hint && <span className={`block text-[11px] leading-tight mt-0.5 truncate ${state === 'active' ? 'text-teal-50' : 'opacity-75'}`}>{s.hint}</span>}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
