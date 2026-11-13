import React, { useEffect, useState } from 'react';
import { ChevronDown, Save, Loader2, ClipboardList } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { EvalGeneralTab } from './EvalGeneralTab';
import { EvalRefractionTab } from './EvalRefractionTab';
import { EvalDiagnosisTab } from './EvalDiagnosisTab';
import { apiError } from './examShared';

const BOOL_KEYS = ['wears_glasses', 'diabetes', 'hypertension', 'autoimmune_disease', 'family_glaucoma', 'family_macular_degeneration', 'family_high_myopia'];
const TEXT_KEYS = [
  'consultation_type', 'chief_complaint', 'anamnesis', 'findings', 'diagnosis', 'treatment_plan', 'recommendations', 'notes',
  'glasses_since', 'glasses_type', 'ocular_surgeries', 'ocular_trauma', 'ocular_diseases', 'autoimmune_details', 'current_medications',
  'allergies', 'family_glaucoma_relationship', 'family_macular_relationship', 'family_high_myopia_relationship', 'family_other_history',
  'visual_acuity_method',
  ...['va_distance_without_rx', 'va_distance_with_rx', 'va_near_without_rx', 'va_near_with_rx', 'va_pinhole'].flatMap((k) => [`${k}_od`, `${k}_oi`]),
  ...['od', 'oi'].flatMap((e) => ['sphere', 'cyl', 'axis', 'add'].map((k) => `lensometry_${e}_${k}`)),
];

const fromExam = (exam) => ({
  ...Object.fromEntries(TEXT_KEYS.map((k) => [k, exam[k] ?? ''])),
  ...Object.fromEntries(BOOL_KEYS.map((k) => [k, !!exam[k]])),
  visual_acuity_method: exam.visual_acuity_method || 'Snellen',
  evaluation: exam.evaluation || {},
});

export function EvaluationPanel({ exam, onExamChange, readOnly }) {
  const [form, setForm] = useState(() => fromExam(exam));
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [open, setOpen] = useState(true);

  useEffect(() => { setForm(fromExam(exam)); setDirty(false); }, [exam._id]); // eslint-disable-line react-hooks/exhaustive-deps

  const setF = (k, v) => { if (readOnly) return; setForm((f) => ({ ...f, [k]: v })); setDirty(true); };
  const ev = (path) => path.split('.').reduce((o, k) => (o && typeof o === 'object' ? o[k] : undefined), form.evaluation) ?? '';
  const setEv = (path, v) => {
    if (readOnly) return;
    setForm((f) => {
      const next = JSON.parse(JSON.stringify(f.evaluation || {}));
      const keys = path.split('.');
      let o = next;
      keys.slice(0, -1).forEach((k) => { if (!o[k] || typeof o[k] !== 'object' || Array.isArray(o[k])) o[k] = {}; o = o[k]; });
      o[keys[keys.length - 1]] = v;
      return { ...f, evaluation: next };
    });
    setDirty(true);
  };

  const save = async () => {
    if (!form.chief_complaint.trim()) { toast.error('El motivo de consulta es obligatorio'); return; }
    setSaving(true);
    try {
      await api.put(`/api/consultations/${exam._id}`, form);
      toast.success('Evaluación guardada');
      setDirty(false);
      onExamChange();
    } catch (err) { toast.error(apiError(err, 'No se pudo guardar la evaluación')); }
    finally { setSaving(false); }
  };

  const props = { f: form, setF, ev, setEv, readOnly };
  return (
    <section className="rounded-2xl border border-slate-200 bg-white shadow-sm" data-testid="evaluation-panel">
      <button type="button" onClick={() => setOpen((o) => !o)} className="w-full flex items-center justify-between gap-3 px-5 py-4 text-left" data-testid="evaluation-toggle">
        <span className="flex items-center gap-3">
          <span className="w-9 h-9 rounded-xl bg-teal-50 text-teal-700 flex items-center justify-center"><ClipboardList className="w-5 h-5" /></span>
          <span>
            <span className="block font-heading text-base font-semibold text-slate-900">Evaluación clínica</span>
            <span className="block text-xs text-slate-500">General · Refracción · Diagnóstico y plan</span>
          </span>
        </span>
        <span className="flex items-center gap-2">
          {dirty && <span className="text-[11px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5" data-testid="evaluation-dirty">Cambios sin guardar</span>}
          <ChevronDown className={`w-5 h-5 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
        </span>
      </button>
      {open && (
        <div className="px-5 pb-5">
          <Tabs defaultValue="general">
            <TabsList className="mb-4 w-full sm:w-auto" data-testid="evaluation-tabs">
              <TabsTrigger value="general" data-testid="eval-tab-general">General</TabsTrigger>
              <TabsTrigger value="refraction" data-testid="eval-tab-refraction">Refracción</TabsTrigger>
              <TabsTrigger value="diagnosis" data-testid="eval-tab-diagnosis">Diagnóstico y plan</TabsTrigger>
            </TabsList>
            <fieldset disabled={readOnly} className="min-w-0">
              <TabsContent value="general"><EvalGeneralTab {...props} exam={exam} onExamChange={onExamChange} /></TabsContent>
              <TabsContent value="refraction"><EvalRefractionTab {...props} legacyRefractions={exam.refractions || []} /></TabsContent>
              <TabsContent value="diagnosis"><EvalDiagnosisTab {...props} /></TabsContent>
            </fieldset>
          </Tabs>
          {!readOnly && (
            <div className="flex flex-wrap items-center justify-end gap-3 pt-4 mt-4 border-t border-slate-100">
              <p className="text-xs text-slate-400 mr-auto">Guardar la evaluación no emite recetas.</p>
              <Button onClick={save} disabled={saving || !dirty} className="bg-pine-700 hover:bg-pine-800" data-testid="save-evaluation-btn">
                {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />} Guardar evaluación
              </Button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
