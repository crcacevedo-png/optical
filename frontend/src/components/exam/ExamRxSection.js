import React, { useState } from 'react';
import { FilePlus2, Glasses, Eye, CircleDot, Pill, FileDown, Info } from 'lucide-react';
import { Button } from '../ui/button';
import { RxCard } from './RxCard';
import { RxEditorDialog } from './RxEditorDialog';
import { useRxActions } from './useRxActions';
import { fmtDate, fetchRxPdf, openPdfBlob } from './examShared';
import { latestValidatedFR, eyeglassFromFR, acceptedOf, fieldsFromAdaptation } from './rxUtils';

const NEW_BTNS = [
  { kind: 'eyeglass', label: 'Anteojos', icon: Glasses },
  { kind: 'contact', label: 'Lentes de contacto', icon: Eye },
  { kind: 'scleral', label: 'Esclerales', icon: CircleDot },
];

// Paso 3: preparar una o varias recetas del examen.
export function ExamRxSection({ exam, items, medical, adaptations, reload, onMedical }) {
  const [editor, setEditor] = useState(null);
  const fr = latestValidatedFR(exam);
  const canIssue = !!exam.permissions?.issue;
  const ctx = { patientId: exam.patient_id, examId: exam._id, fr, adaptations, canIssue };
  const { actions, dialogs } = useRxActions({ patient: exam.patient, reload, onDraft: (rx) => setEditor({ kind: rx.kind, rx }) });

  const blocked = {
    eyeglass: !fr && 'Valida la refracción final para preparar recetas de anteojos.',
    contact: !acceptedOf(adaptations, 'contact').length && 'Requiere una adaptación de contacto aceptada.',
    scleral: !acceptedOf(adaptations, 'scleral').length && 'Requiere una adaptación escleral aceptada.',
  };
  const startNew = (kind) => {
    if (kind === 'eyeglass') { setEditor({ kind, initial: { fields: eyeglassFromFR(fr) } }); return; }
    const ad = acceptedOf(adaptations, kind)[0];
    setEditor({ kind, initial: { adaptation_id: ad._id, fields: fieldsFromAdaptation(kind, ad) } });
  };
  const onSaved = async (rx, { issue }) => { await reload(); if (issue) actions.issue(rx); };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white shadow-sm p-5 space-y-4" data-testid="exam-rx-section">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="w-9 h-9 rounded-xl bg-pine-700 text-white flex items-center justify-center"><FilePlus2 className="w-5 h-5" /></span>
          <div>
            <h3 className="font-heading text-base font-semibold text-slate-900">Preparar recetas</h3>
            <p className="text-xs text-slate-500">Prepara una o varias recetas por examen. Cada receta se revisa y emite por separado.</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {NEW_BTNS.map((b) => (
            <Button key={b.kind} size="sm" variant="outline" disabled={!!blocked[b.kind]} title={blocked[b.kind] || undefined} onClick={() => startNew(b.kind)} data-testid={`new-rx-${b.kind}-btn`}>
              <b.icon className="w-3.5 h-3.5 mr-1.5" /> {b.label}
            </Button>
          ))}
        </div>
      </div>
      {Object.values(blocked).some(Boolean) && (
        <ul className="space-y-1" data-testid="rx-blocked-hints">
          {NEW_BTNS.filter((b) => blocked[b.kind]).map((b) => (
            <li key={b.kind} className="flex items-center gap-1.5 text-[11px] text-slate-500"><Info className="w-3 h-3" /> <strong className="font-semibold">{b.label}:</strong> {blocked[b.kind]}</li>
          ))}
        </ul>
      )}
      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 py-8 text-center text-sm text-slate-400" data-testid="exam-rx-empty">Este examen todavía no tiene recetas.</div>
      ) : (
        <div className="space-y-2.5" data-testid="exam-rx-list">
          {items.map((rx) => (
            <RxCard key={`${rx.kind}-${rx._id}`} rx={rx} actions={actions} canIssue={canIssue}
              onEdit={(r) => setEditor({ kind: r.kind, rx: r })} onView={(r) => setEditor({ kind: r.kind, rx: r })} />
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
        <Pill className="w-4 h-4 text-purple-600" />
        <span className="text-sm font-medium text-slate-700 mr-auto">Recetas médicas ({medical.length})</span>
        <Button size="sm" variant="ghost" onClick={onMedical} data-testid="exam-rx-medical-btn">Nueva receta médica</Button>
      </div>
      {medical.length > 0 && (
        <ul className="space-y-1" data-testid="exam-medical-list">
          {medical.map((m) => (
            <li key={m._id} className="flex items-center gap-2 text-sm text-slate-600">
              <span className="flex-1 truncate">{m.diagnosis || 'Receta médica'} · {(m.medications || []).length} medicamento(s) · {fmtDate(m.created_at)}</span>
              <Button size="sm" variant="ghost" className="h-7" onClick={async () => openPdfBlob((await fetchRxPdf('medical', m._id)).data)} data-testid={`medical-pdf-${m._id}`}><FileDown className="w-3.5 h-3.5 mr-1" /> PDF</Button>
            </li>
          ))}
        </ul>
      )}
      <RxEditorDialog open={!!editor} onOpenChange={(o) => !o && setEditor(null)} kind={editor?.kind} rx={editor?.rx || null} initial={editor?.initial} ctx={ctx} onSaved={onSaved} />
      {dialogs}
    </section>
  );
}
