import React from 'react';
import { Field, TextIn, AreaIn, NativeSelect, ClinicalSection } from './EvalFields';
import { EyeGrid } from './EyeGrid';
import { EYES, PRISM_BASES_H, PRISM_BASES_V } from './examShared';

const VA_ROWS = [
  { label: 'Lejos sin corrección', key: 'va_distance_without_rx' },
  { label: 'Lejos con corrección', key: 'va_distance_with_rx' },
  { label: 'Cerca sin corrección', key: 'va_near_without_rx' },
  { label: 'Cerca con corrección', key: 'va_near_with_rx' },
  { label: 'Con estenopeico', key: 'va_pinhole' },
];
const VA_SCALES = [
  { v: 'Snellen', l: 'Snellen (pies, 20/20)' }, { v: 'Snellen_m', l: 'Snellen (metros, 6/6)' }, { v: 'decimal', l: 'Decimal' },
  { v: 'logMAR', l: 'logMAR' }, { v: 'ETDRS', l: 'ETDRS (letras)' },
];
const BASIC = [
  { key: 'sphere', label: 'Esfera', unit: 'D', placeholder: '±0.00' },
  { key: 'cyl', label: 'Cilindro', unit: 'D', placeholder: '±0.00' },
  { key: 'axis', label: 'Eje', unit: '°', placeholder: '0-180' },
];
const VA_COL = { key: 'va', label: 'AV', placeholder: '20/20' };
const SUBJ = [
  ...BASIC,
  { key: 'add', label: 'ADD', unit: 'D', placeholder: '+0.00' },
  { key: 'prism_h', label: 'Prisma H', unit: 'Δ' }, { key: 'base_h', label: 'Base H', options: PRISM_BASES_H },
  { key: 'prism_v', label: 'Prisma V', unit: 'Δ' }, { key: 'base_v', label: 'Base V', options: PRISM_BASES_V },
  VA_COL,
];
const LENSO_MAP = { sphere: 'sphere', cyl: 'cyl', axis: 'axis', add: 'add' };

const RefSection = ({ title, base, columns, ev, setEv, readOnly, extra, testId }) => (
  <ClinicalSection title={title} testId={testId} status={ev(`${base}.status`)} onStatus={(v) => setEv(`${base}.status`, v)}>
    {extra}
    <EyeGrid columns={columns} readOnly={readOnly} testId={`${testId}-grid`}
      get={(eye, k) => ev(`${base}.${eye}.${k}`)} set={(eye, k, v) => setEv(`${base}.${eye}.${k}`, v)} />
    <AreaIn value={ev(`${base}.notes`)} onChange={(v) => setEv(`${base}.notes`, v)} placeholder="Observaciones" testId={`${testId}-notes`} />
  </ClinicalSection>
);

export function EvalRefractionTab({ f, setF, ev, setEv, legacyRefractions = [], readOnly }) {
  const lensoKey = (eye, k) => `lensometry_${eye === 'os' ? 'oi' : 'od'}_${LENSO_MAP[k]}`;
  return (
    <div className="space-y-4">
      <ClinicalSection title="Lensometría (corrección habitual)" testId="eval-lensometry">
        <EyeGrid columns={[...BASIC, { key: 'add', label: 'ADD', unit: 'D' }]} readOnly={readOnly} testId="eval-lensometry-grid"
          get={(eye, k) => f[lensoKey(eye, k)]} set={(eye, k, v) => setF(lensoKey(eye, k), v)} />
        <TextIn value={ev('lensometry_notes')} onChange={(v) => setEv('lensometry_notes', v)} placeholder="Prisma, tipo de lente, estado de los lentes…" testId="eval-lensometry-notes" />
      </ClinicalSection>

      <ClinicalSection title="Agudeza visual" testId="eval-va">
        <div className="grid sm:grid-cols-3 gap-3">
          <Field label="Escala"><NativeSelect value={f.visual_acuity_method} onChange={(v) => setF('visual_acuity_method', v)} options={VA_SCALES} testId="eval-va-scale" /></Field>
          <Field label="Distancia de prueba"><TextIn value={ev('va_distance')} onChange={(v) => setEv('va_distance', v)} placeholder="6 m / 40 cm" testId="eval-va-distance" /></Field>
          <Field label="Condiciones"><TextIn value={ev('va_conditions')} onChange={(v) => setEv('va_conditions', v)} placeholder="Iluminación, monocular/binocular" testId="eval-va-conditions" /></Field>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="eval-va-table">
            <thead><tr className="text-[11px] uppercase tracking-wide text-slate-500">
              <th className="text-left py-1.5">Medición</th>{EYES.map((e) => <th key={e.key} className={`text-left py-1.5 px-1 ${e.cls}`}>{e.label}</th>)}
            </tr></thead>
            <tbody>
              {VA_ROWS.map((r) => (
                <tr key={r.key} className="border-t border-slate-100">
                  <td className="py-1.5 pr-3 text-slate-700">{r.label}</td>
                  {EYES.map((e) => (
                    <td key={e.key} className="py-1.5 px-1">
                      <TextIn value={f[`${r.key}_${e.rxKey}`]} onChange={(v) => setF(`${r.key}_${e.rxKey}`, v)} readOnly={readOnly} testId={`eval-${r.key}-${e.key}`} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </ClinicalSection>

      <RefSection title="Refracción objetiva" base="objective_refraction" columns={[...BASIC, VA_COL]} ev={ev} setEv={setEv} readOnly={readOnly} testId="eval-objective"
        extra={<Field label="Método" className="max-w-xs"><NativeSelect value={ev('objective_refraction.method')} onChange={(v) => setEv('objective_refraction.method', v)} testId="eval-objective-method"
          options={[{ v: '', l: 'Sin especificar' }, { v: 'autorrefractometro', l: 'Autorrefractómetro' }, { v: 'retinoscopia', l: 'Retinoscopía' }, { v: 'otro', l: 'Otro' }]} /></Field>} />
      <RefSection title="Refracción subjetiva" base="subjective_refraction" columns={SUBJ} ev={ev} setEv={setEv} readOnly={readOnly} testId="eval-subjective" />
      <RefSection title="Refracción bajo cicloplejia" base="cycloplegic_refraction" columns={[...BASIC, VA_COL]} ev={ev} setEv={setEv} readOnly={readOnly} testId="eval-cycloplegic"
        extra={<Field label="Agente / dosis" className="max-w-sm"><TextIn value={ev('cycloplegic_refraction.agent')} onChange={(v) => setEv('cycloplegic_refraction.agent', v)} testId="eval-cycloplegic-agent" /></Field>} />

      {legacyRefractions.length > 0 && (
        <section className="rounded-xl border border-dashed border-slate-300 bg-slate-50/60 p-4" data-testid="eval-legacy-refractions">
          <h4 className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500 mb-2">Refracciones registradas (formato anterior)</h4>
          <div className="space-y-1.5 text-sm">
            {legacyRefractions.map((r, i) => (
              <p key={i} className="font-mono text-slate-700">
                #{i + 1}{r.is_final ? ' (marcada final)' : ''} · <span className="text-blue-700">OD</span> {r.od_sphere || '—'} / {r.od_cylinder || '—'} x {r.od_axis || '—'} ADD {r.od_addition || '—'} · <span className="text-emerald-700">OS</span> {r.os_sphere || '—'} / {r.os_cylinder || '—'} x {r.os_axis || '—'} ADD {r.os_addition || '—'}
              </p>
            ))}
          </div>
        </section>
      )}
      <p className="text-xs text-slate-500">La <strong>refracción final</strong> se registra y valida en el bloque destacado de abajo; no se copia automáticamente a las recetas.</p>
    </div>
  );
}
