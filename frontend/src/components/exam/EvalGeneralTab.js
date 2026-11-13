import React from 'react';
import { Field, TextIn, AreaIn, NativeSelect, CheckLine, ClinicalSection } from './EvalFields';
import { ExamAttachments } from './ExamAttachments';

const FAMILY = [
  { k: 'family_glaucoma', rel: 'family_glaucoma_relationship', label: 'Glaucoma' },
  { k: 'family_macular_degeneration', rel: 'family_macular_relationship', label: 'Degeneración macular' },
  { k: 'family_high_myopia', rel: 'family_high_myopia_relationship', label: 'Miopía alta' },
];
const FUNDUS_METHODS = [
  { v: '', l: 'Método…' }, { v: 'oftalmoscopia_directa', l: 'Oftalmoscopía directa' }, { v: 'oftalmoscopia_indirecta', l: 'Oftalmoscopía indirecta' },
  { v: 'biomicroscopia', l: 'Biomicroscopía con lente' }, { v: 'retinografia', l: 'Retinografía' },
];
const IOP_METHODS = [
  { v: '', l: 'Método…' }, { v: 'aplanacion_goldmann', l: 'Aplanación (Goldmann)' }, { v: 'no_contacto', l: 'No contacto (aire)' },
  { v: 'rebote', l: 'Rebote' }, { v: 'otro', l: 'Otro' },
];

const OdOsText = ({ base, ev, setEv, testId, rows = 2, placeholder = 'Describir hallazgos…' }) => (
  <div className="grid sm:grid-cols-2 gap-3">
    <Field label="OD (ojo derecho)"><AreaIn rows={rows} value={ev(`${base}.od`)} onChange={(v) => setEv(`${base}.od`, v)} placeholder={placeholder} testId={`${testId}-od`} /></Field>
    <Field label="OS (ojo izquierdo)"><AreaIn rows={rows} value={ev(`${base}.os`)} onChange={(v) => setEv(`${base}.os`, v)} placeholder={placeholder} testId={`${testId}-os`} /></Field>
  </div>
);

export function EvalGeneralTab({ f, setF, ev, setEv, exam, onExamChange, readOnly }) {
  return (
    <div className="space-y-4">
      <ClinicalSection title="Motivo y síntomas" testId="eval-motive">
        <Field label="Motivo de consulta *"><AreaIn value={f.chief_complaint} onChange={(v) => setF('chief_complaint', v)} testId="eval-chief-complaint" placeholder="Motivo principal referido por el paciente" /></Field>
        <div className="grid md:grid-cols-2 gap-3">
          <Field label="Síntomas"><AreaIn value={ev('symptoms')} onChange={(v) => setEv('symptoms', v)} testId="eval-symptoms" placeholder="Síntomas, duración, factores asociados" /></Field>
          <Field label="Historia / anamnesis"><AreaIn value={f.anamnesis} onChange={(v) => setF('anamnesis', v)} testId="eval-anamnesis" placeholder="Evolución y contexto" /></Field>
        </div>
      </ClinicalSection>

      <ClinicalSection title="Antecedentes oculares, generales y familiares" testId="eval-history" note="Deja vacío lo que no se haya interrogado; no se asume “ninguno”.">
        <div className="grid md:grid-cols-3 gap-3">
          <Field label="Cirugías oculares"><TextIn value={f.ocular_surgeries} onChange={(v) => setF('ocular_surgeries', v)} testId="eval-ocular-surgeries" /></Field>
          <Field label="Traumatismos"><TextIn value={f.ocular_trauma} onChange={(v) => setF('ocular_trauma', v)} testId="eval-ocular-trauma" /></Field>
          <Field label="Enfermedades oculares"><TextIn value={f.ocular_diseases} onChange={(v) => setF('ocular_diseases', v)} testId="eval-ocular-diseases" /></Field>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-2 pt-1">
          <CheckLine id="ev-dm" checked={f.diabetes} onChange={(v) => setF('diabetes', v)} label="Diabetes" testId="eval-diabetes" />
          <CheckLine id="ev-hta" checked={f.hypertension} onChange={(v) => setF('hypertension', v)} label="Hipertensión" testId="eval-hypertension" />
          <CheckLine id="ev-ai" checked={f.autoimmune_disease} onChange={(v) => setF('autoimmune_disease', v)} label="Enfermedad autoinmune" testId="eval-autoimmune" />
        </div>
        {f.autoimmune_disease && <TextIn value={f.autoimmune_details} onChange={(v) => setF('autoimmune_details', v)} placeholder="¿Cuál?" testId="eval-autoimmune-details" />}
        <div className="grid md:grid-cols-3 gap-3">
          <Field label="Otros antecedentes generales"><TextIn value={ev('general_history')} onChange={(v) => setEv('general_history', v)} testId="eval-general-history" /></Field>
          <Field label="Medicamentos"><TextIn value={f.current_medications} onChange={(v) => setF('current_medications', v)} testId="eval-medications" /></Field>
          <Field label="Alergias"><TextIn value={f.allergies} onChange={(v) => setF('allergies', v)} testId="eval-allergies" /></Field>
        </div>
        <div className="grid md:grid-cols-3 gap-3 pt-1">
          {FAMILY.map((x) => (
            <div key={x.k} className="space-y-1.5">
              <CheckLine id={`ev-${x.k}`} checked={f[x.k]} onChange={(v) => setF(x.k, v)} label={`Familiar con ${x.label.toLowerCase()}`} testId={`eval-${x.k}`} />
              {f[x.k] && <TextIn value={f[x.rel]} onChange={(v) => setF(x.rel, v)} placeholder="Parentesco" testId={`eval-${x.rel}`} />}
            </div>
          ))}
        </div>
        <Field label="Otros antecedentes familiares"><TextIn value={f.family_other_history} onChange={(v) => setF('family_other_history', v)} testId="eval-family-other" /></Field>
      </ClinicalSection>

      <ClinicalSection title="Corrección habitual y necesidades visuales" testId="eval-habitual">
        <div className="grid md:grid-cols-2 gap-3">
          <Field label="Corrección habitual"><AreaIn value={ev('habitual_correction')} onChange={(v) => setEv('habitual_correction', v)} testId="eval-habitual-correction" placeholder="Anteojos / lentes de contacto actuales, antigüedad, satisfacción" /></Field>
          <Field label="Necesidades visuales"><AreaIn value={ev('visual_needs')} onChange={(v) => setEv('visual_needs', v)} testId="eval-visual-needs" placeholder="Ocupación, pantallas, conducción, deportes" /></Field>
        </div>
        <CheckLine id="ev-wg" checked={f.wears_glasses} onChange={(v) => setF('wears_glasses', v)} label="Usa corrección actualmente" testId="eval-wears-glasses" />
      </ClinicalSection>

      <ClinicalSection title="Biomicroscopía y superficie ocular" testId="eval-biomicroscopy" status={ev('biomicroscopy.status')} onStatus={(v) => setEv('biomicroscopy.status', v)}>
        <OdOsText base="biomicroscopy" ev={ev} setEv={setEv} testId="eval-biomicroscopy" />
        <Field label="Película lagrimal / superficie"><TextIn value={ev('biomicroscopy.surface')} onChange={(v) => setEv('biomicroscopy.surface', v)} testId="eval-surface" /></Field>
      </ClinicalSection>

      <ClinicalSection title="Presión intraocular (PIO)" testId="eval-iop" status={ev('iop.status')} onStatus={(v) => setEv('iop.status', v)}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Field label="OD (mmHg)"><TextIn value={ev('iop.od')} onChange={(v) => setEv('iop.od', v)} testId="eval-iop-od" inputMode="decimal" /></Field>
          <Field label="OS (mmHg)"><TextIn value={ev('iop.os')} onChange={(v) => setEv('iop.os', v)} testId="eval-iop-os" inputMode="decimal" /></Field>
          <Field label="Método"><NativeSelect value={ev('iop.method')} onChange={(v) => setEv('iop.method', v)} options={IOP_METHODS} testId="eval-iop-method" /></Field>
          <Field label="Hora"><TextIn type="time" value={ev('iop.time')} onChange={(v) => setEv('iop.time', v)} testId="eval-iop-time" /></Field>
        </div>
      </ClinicalSection>

      <ClinicalSection title="Fondo de ojo" testId="eval-fundus" status={ev('fundus.status')} onStatus={(v) => setEv('fundus.status', v)}>
        <div className="grid md:grid-cols-3 gap-3">
          <Field label="Método"><NativeSelect value={ev('fundus.method')} onChange={(v) => setEv('fundus.method', v)} options={FUNDUS_METHODS} testId="eval-fundus-method" /></Field>
          <Field label="Pupila"><NativeSelect value={ev('fundus.pupil')} onChange={(v) => setEv('fundus.pupil', v)} testId="eval-fundus-pupil"
            options={[{ v: '', l: 'Sin especificar' }, { v: 'sin_dilatar', l: 'Sin dilatar' }, { v: 'dilatada', l: 'Dilatada' }]} /></Field>
        </div>
        <OdOsText base="fundus" ev={ev} setEv={setEv} testId="eval-fundus" />
      </ClinicalSection>

      <div className="grid lg:grid-cols-2 gap-4">
        <ClinicalSection title="Evaluación binocular" testId="eval-binocular" status={ev('binocular.status')} onStatus={(v) => setEv('binocular.status', v)}>
          <AreaIn rows={3} value={ev('binocular.notes')} onChange={(v) => setEv('binocular.notes', v)} testId="eval-binocular-notes" placeholder="Cover test, PPC, vergencias, estereopsis…" />
        </ClinicalSection>
        <ClinicalSection title="Evaluación acomodativa" testId="eval-accommodative" status={ev('accommodative.status')} onStatus={(v) => setEv('accommodative.status', v)}>
          <AreaIn rows={3} value={ev('accommodative.notes')} onChange={(v) => setEv('accommodative.notes', v)} testId="eval-accommodative-notes" placeholder="Amplitud, flexibilidad, retraso acomodativo…" />
        </ClinicalSection>
      </div>

      <ClinicalSection title="Estudios y archivos adjuntos" testId="eval-studies" status={ev('studies.status')} onStatus={(v) => setEv('studies.status', v)}>
        <AreaIn value={ev('studies.notes')} onChange={(v) => setEv('studies.notes', v)} testId="eval-studies-notes" placeholder="Topografía, OCT, campimetría, paquimetría…" />
        <ExamAttachments exam={exam} onChange={onExamChange} readOnly={readOnly} />
      </ClinicalSection>
    </div>
  );
}
