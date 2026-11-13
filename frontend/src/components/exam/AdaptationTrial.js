import React from 'react';
import { Trash2 } from 'lucide-react';
import { Button } from '../ui/button';
import { Field, TextIn, AreaIn } from './EvalFields';

const LENS = [
  { k: 'brand', l: 'Marca / laboratorio' }, { k: 'design', l: 'Diseño' }, { k: 'material', l: 'Material' },
  { k: 'power', l: 'Potencia (D)' }, { k: 'cylinder', l: 'Cil (D)' }, { k: 'axis', l: 'Eje (°)' }, { k: 'addition', l: 'ADD (D)' },
  { k: 'bc', l: 'C.B. (mm)' }, { k: 'dia', l: 'Diám (mm)' },
];
const FIT = [{ k: 'centration', l: 'Centrado' }, { k: 'coverage', l: 'Cobertura' }, { k: 'movement', l: 'Movimiento' }, { k: 'rotation', l: 'Rotación' }];
const SECTORS = [{ k: 'sup', l: 'Superior' }, { k: 'inf', l: 'Inferior' }, { k: 'nas', l: 'Nasal' }, { k: 'tem', l: 'Temporal' }];

const Grid = ({ items, get, set, prefix, cols = 'grid-cols-2 md:grid-cols-3 lg:grid-cols-5' }) => (
  <div className={`grid ${cols} gap-2`}>
    {items.map((x) => <Field key={x.k} label={x.l}><TextIn value={get(x.k)} onChange={(v) => set(x.k, v)} testId={`${prefix}-${x.k}`} /></Field>)}
  </div>
);

export function AdaptationTrial({ trial, index, scleral, onChange, onRemove, readOnly }) {
  const sub = (group) => ({ get: (k) => trial[group]?.[k] ?? '', set: (k, v) => onChange({ ...trial, [group]: { ...(trial[group] || {}), [k]: v } }) });
  const top = (k, v) => onChange({ ...trial, [k]: v });
  const eyeLbl = trial.eye === 'oi' ? 'OS' : 'OD';
  const t = `trial-${index}`;
  const lens = scleral ? [...LENS, { k: 'sag', l: 'Sagita (µm)' }] : LENS;
  return (
    <div className="rounded-xl border border-slate-200 p-4 space-y-3 bg-slate-50/40" data-testid={t}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`text-xs font-bold rounded-md px-2 py-0.5 ${trial.eye === 'oi' ? 'bg-emerald-100 text-emerald-800' : 'bg-blue-100 text-blue-800'}`}>Prueba {index + 1} · {eyeLbl}</span>
        <TextIn value={trial.visit_label} onChange={(v) => top('visit_label', v)} placeholder="Consulta (ej. 1ª visita)" className="w-44" testId={`${t}-visit`} />
        <TextIn type="date" value={trial.visit_date} onChange={(v) => top('visit_date', v)} className="w-40" testId={`${t}-date`} />
        {!readOnly && <Button type="button" variant="ghost" size="sm" className="ml-auto text-red-600" onClick={onRemove} data-testid={`${t}-remove`}><Trash2 className="w-4 h-4" /></Button>}
      </div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Lente de prueba</p>
      <Grid items={lens} {...sub('lens')} prefix={`${t}-lens`} />
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Evaluación del ajuste</p>
      <Grid items={FIT} {...sub('fit')} prefix={`${t}-fit`} cols="grid-cols-2 md:grid-cols-4" />
      {scleral && (
        <>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Clearance</p>
          <Grid items={[{ k: 'clearance_central', l: 'Central (µm)' }, { k: 'clearance_min', l: 'Mínimo (µm)' }, { k: 'clearance_limbal', l: 'Limbal' },
            { k: 'clearance_location', l: 'Ubicación' }, { k: 'clearance_method', l: 'Método (OCT/LH)' }]} {...sub('scleral')} prefix={`${t}-clr`} />
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Zona de apoyo por sector (apoyo, compresión, blanqueamiento, borde)</p>
          <Grid items={SECTORS.map((s) => ({ k: `landing_${s.k}`, l: s.l }))} {...sub('scleral')} prefix={`${t}-land`} cols="grid-cols-2 md:grid-cols-4" />
          <Grid items={[{ k: 'bubbles', l: 'Burbujas' }, { k: 'debris', l: 'Residuos' }, { k: 'fogging', l: 'Empañamiento' }]} {...sub('scleral')} prefix={`${t}-misc`} cols="grid-cols-1 md:grid-cols-3" />
        </>
      )}
      <div className="grid md:grid-cols-3 gap-2">
        <Field label="Sobrerrefracción"><TextIn value={trial.over_refraction} onChange={(v) => top('over_refraction', v)} testId={`${t}-overrx`} /></Field>
        <Field label="AV con el lente"><TextIn value={trial.va} onChange={(v) => top('va', v)} testId={`${t}-va`} /></Field>
        <Field label="Comodidad"><TextIn value={trial.comfort} onChange={(v) => top('comfort', v)} testId={`${t}-comfort`} /></Field>
      </div>
      <div className="grid md:grid-cols-2 gap-2">
        <Field label="Hallazgos tras retiro"><AreaIn value={trial.post_removal} onChange={(v) => top('post_removal', v)} testId={`${t}-post`} /></Field>
        <Field label="Notas"><AreaIn value={trial.notes} onChange={(v) => top('notes', v)} testId={`${t}-notes`} /></Field>
      </div>
    </div>
  );
}
