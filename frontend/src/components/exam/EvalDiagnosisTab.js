import React from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '../ui/button';
import { Field, TextIn, AreaIn, NativeSelect, ClinicalSection } from './EvalFields';

const LATERALITY = [{ v: '', l: 'Lateralidad…' }, { v: 'OD', l: 'OD' }, { v: 'OS', l: 'OS' }, { v: 'AO', l: 'Ambos ojos (AO)' }, { v: 'NA', l: 'No aplica' }];

export function EvalDiagnosisTab({ f, setF, ev, setEv, readOnly }) {
  const list = Array.isArray(ev('diagnoses')) ? ev('diagnoses') : [];
  const setList = (next) => setEv('diagnoses', next);
  return (
    <div className="space-y-4">
      <ClinicalSection title="Diagnósticos y lateralidad" testId="eval-diagnoses">
        <div className="space-y-2">
          {list.map((d, i) => (
            <div key={i} className="flex gap-2 items-start" data-testid={`eval-diagnosis-row-${i}`}>
              <TextIn value={d.text} onChange={(v) => setList(list.map((x, j) => (j === i ? { ...x, text: v } : x)))} placeholder="Diagnóstico" testId={`eval-diagnosis-text-${i}`} className="flex-1" />
              <NativeSelect value={d.laterality} onChange={(v) => setList(list.map((x, j) => (j === i ? { ...x, laterality: v } : x)))} options={LATERALITY} className="w-40" testId={`eval-diagnosis-lat-${i}`} />
              {!readOnly && <Button type="button" variant="ghost" size="sm" className="h-9 text-red-600" onClick={() => setList(list.filter((_, j) => j !== i))} data-testid={`eval-diagnosis-remove-${i}`}><Trash2 className="w-4 h-4" /></Button>}
            </div>
          ))}
          {!readOnly && (
            <Button type="button" variant="outline" size="sm" onClick={() => setList([...list, { text: '', laterality: '' }])} data-testid="eval-diagnosis-add">
              <Plus className="w-3.5 h-3.5 mr-1" /> Agregar diagnóstico
            </Button>
          )}
        </div>
        <Field label="Impresión clínica (resumen)"><AreaIn value={f.diagnosis} onChange={(v) => setF('diagnosis', v)} testId="eval-diagnosis-summary" /></Field>
      </ClinicalSection>
      <ClinicalSection title="Interpretación y plan" testId="eval-plan">
        <Field label="Interpretación"><AreaIn value={ev('interpretation')} onChange={(v) => setEv('interpretation', v)} testId="eval-interpretation" /></Field>
        <div className="grid md:grid-cols-2 gap-3">
          <Field label="Conducta / tratamiento"><AreaIn value={f.treatment_plan} onChange={(v) => setF('treatment_plan', v)} testId="eval-treatment" /></Field>
          <Field label="Indicaciones al paciente"><AreaIn value={f.recommendations} onChange={(v) => setF('recommendations', v)} testId="eval-recommendations" /></Field>
        </div>
        <div className="grid md:grid-cols-2 gap-3">
          <Field label="Referencia / interconsulta"><TextIn value={ev('referral')} onChange={(v) => setEv('referral', v)} placeholder="Especialidad y motivo" testId="eval-referral" /></Field>
          <Field label="Próximo control"><TextIn type="date" value={ev('next_control')} onChange={(v) => setEv('next_control', v)} testId="eval-next-control" /></Field>
        </div>
        <Field label="Observaciones"><AreaIn value={f.notes} onChange={(v) => setF('notes', v)} testId="eval-notes" /></Field>
      </ClinicalSection>
    </div>
  );
}
