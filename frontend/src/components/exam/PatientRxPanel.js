import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, FileText } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../../context/AuthContext';
import { RxCard } from './RxCard';
import { RxEditorDialog } from './RxEditorDialog';
import { PrintPanel } from './PrintPanel';
import { useRxActions } from './useRxActions';
import { apiError, KIND_META, RX_STATUS } from './examShared';

const STATUS_FILTERS = ['todas', 'borrador', 'emitida', 'sustituida', 'anulada'];
const KIND_FILTERS = ['todas', 'eyeglass', 'contact', 'scleral'];
const Chip = ({ active, onClick, children, testId }) => (
  <button type="button" onClick={onClick} data-testid={testId}
    className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${active ? 'border-pine-700 bg-pine-700 text-white' : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'}`}>
    {children}
  </button>
);

// Panel de recetas del paciente (solo flujo nuevo): estados, acciones e impresión múltiple.
export function PatientRxPanel({ patient }) {
  const navigate = useNavigate();
  const [items, setItems] = useState(null);
  const [adaptations, setAdaptations] = useState([]);
  const [status, setStatus] = useState('todas');
  const [kind, setKind] = useState('todas');
  const [editor, setEditor] = useState(null);

  const load = useCallback(async () => {
    try {
      const [r, a] = await Promise.all([
        api.get('/api/clinical/prescriptions', { params: { patient_id: patient._id } }),
        api.get('/api/clinical/adaptations', { params: { patient_id: patient._id } }),
      ]);
      setItems((r.data.items || []).filter((x) => !x.is_historic));
      setAdaptations(a.data || []);
    } catch (err) { toast.error(apiError(err, 'No se pudieron cargar las recetas')); setItems([]); }
  }, [patient._id]);
  useEffect(() => { setItems(null); load(); }, [load]);

  const { actions, dialogs } = useRxActions({ patient, reload: load, onDraft: (rx) => setEditor({ kind: rx.kind, rx }) });
  const shown = useMemo(() => (items || []).filter((r) => (status === 'todas' || r.status === status) && (kind === 'todas' || r.kind === kind)), [items, status, kind]);
  const printable = useMemo(() => (items || []).filter((r) => r.status === 'emitida'), [items]);
  const counts = useMemo(() => Object.fromEntries(STATUS_FILTERS.map((s) => [s, (items || []).filter((r) => s === 'todas' || r.status === s).length])), [items]);

  if (items === null) return <div className="flex justify-center py-10"><Loader2 className="w-6 h-6 animate-spin text-teal-600" /></div>;
  return (
    <div className="space-y-4" data-testid="patient-rx-panel">
      <div className="flex flex-wrap gap-1.5" data-testid="patient-rx-status-filters">
        {STATUS_FILTERS.map((s) => (
          <Chip key={s} active={status === s} onClick={() => setStatus(s)} testId={`patient-rx-filter-${s}`}>
            {s === 'todas' ? 'Todas' : RX_STATUS[s].label} ({counts[s]})
          </Chip>
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5" data-testid="patient-rx-kind-filters">
        {KIND_FILTERS.map((k) => (
          <Chip key={k} active={kind === k} onClick={() => setKind(k)} testId={`patient-rx-kind-${k}`}>{k === 'todas' ? 'Todos los tipos' : KIND_META[k].label}</Chip>
        ))}
      </div>
      {shown.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 py-10 text-center" data-testid="patient-rx-empty">
          <FileText className="w-8 h-8 text-slate-300 mx-auto mb-2" />
          <p className="text-sm text-slate-500">{items.length === 0 ? 'Este paciente aún no tiene recetas del nuevo flujo clínico.' : 'No hay recetas con este filtro.'}</p>
          {items.length === 0 && <p className="text-xs text-slate-400 mt-1">Inicia un examen para preparar recetas. Las recetas anteriores siguen en la página Recetas.</p>}
        </div>
      ) : (
        <div className="space-y-2.5" data-testid="patient-rx-list">
          {shown.map((rx) => (
            <RxCard key={`${rx.kind}-${rx._id}`} rx={rx} actions={actions} canIssue
              onEdit={(r) => setEditor({ kind: r.kind, rx: r })} onView={(r) => setEditor({ kind: r.kind, rx: r })}
              onOpenExam={(r) => navigate(`/exams/${r.consultation_id}`)} />
          ))}
        </div>
      )}
      <PrintPanel items={printable} title="Impresión múltiple" testId="patient-print-panel"
        subtitle="Selecciona varias recetas emitidas del paciente y genera un PDF conjunto o archivos separados." />
      <RxEditorDialog open={!!editor} onOpenChange={(o) => !o && setEditor(null)} kind={editor?.kind} rx={editor?.rx || null}
        ctx={{ patientId: patient._id, examId: editor?.rx?.consultation_id, adaptations, canIssue: true }} onSaved={async (rx, { issue }) => { await load(); if (issue) actions.issue(rx); }} />
      {dialogs}
    </div>
  );
}
