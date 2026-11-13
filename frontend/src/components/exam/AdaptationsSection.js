import React, { useState } from 'react';
import { Plus, Eye, CircleDot, ChevronRight, Layers } from 'lucide-react';
import { Button } from '../ui/button';
import { AdaptationDialog } from './AdaptationDialog';
import { fmtDate } from './examShared';

export function AdaptationsSection({ adaptations, patientId, examId, canClinical, onChange }) {
  const [dialog, setDialog] = useState(null);
  return (
    <section className="rounded-2xl border border-slate-200 bg-white shadow-sm p-5 space-y-3" data-testid="adaptations-section">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="w-9 h-9 rounded-xl bg-violet-50 text-violet-700 flex items-center justify-center"><Layers className="w-5 h-5" /></span>
          <div>
            <h3 className="font-heading text-base font-semibold text-slate-900">Adaptaciones de contacto y esclerales</h3>
            <p className="text-xs text-slate-500">Registro clínico del paciente. Las recetas de contacto y esclerales se emiten desde una adaptación aceptada.</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => setDialog({ kind: 'contacto' })} data-testid="new-adaptation-contact-btn"><Eye className="w-3.5 h-3.5 mr-1.5" /> Nueva de contacto</Button>
          <Button variant="outline" size="sm" onClick={() => setDialog({ kind: 'escleral' })} data-testid="new-adaptation-scleral-btn"><CircleDot className="w-3.5 h-3.5 mr-1.5" /> Nueva escleral</Button>
        </div>
      </div>
      {adaptations.length === 0 ? (
        <p className="text-sm text-slate-400" data-testid="adaptations-empty">Este paciente no tiene adaptaciones registradas.</p>
      ) : (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200">
          {adaptations.map((a) => (
            <li key={a._id}>
              <button type="button" onClick={() => setDialog({ adaptation: a, kind: a.kind })} className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-50 transition-colors" data-testid={`adaptation-row-${a._id}`}>
                {a.kind === 'escleral' ? <CircleDot className="w-4 h-4 text-violet-600" /> : <Eye className="w-4 h-4 text-teal-600" />}
                <span className="flex-1 min-w-0">
                  <span className="block text-sm font-medium text-slate-800 truncate">{a.title}</span>
                  <span className="block text-xs text-slate-500">{(a.trials || []).length} prueba(s) · creada {fmtDate(a.created_at)}{a.accepted_at ? ` · aceptada ${fmtDate(a.accepted_at)}` : ''}</span>
                </span>
                <span className={`text-[11px] font-semibold rounded-full border px-2 py-0.5 ${a.status === 'aceptada' ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-amber-50 border-amber-200 text-amber-800'}`}>
                  {a.status === 'aceptada' ? 'Aceptada' : 'En proceso'}
                </span>
                <ChevronRight className="w-4 h-4 text-slate-300" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <AdaptationDialog open={!!dialog} onOpenChange={(o) => !o && setDialog(null)} adaptation={dialog?.adaptation || null} kind={dialog?.kind}
        patientId={patientId} examId={examId} canClinical={canClinical} onSaved={() => onChange()} />
    </section>
  );
}
