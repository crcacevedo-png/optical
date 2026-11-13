import React from 'react';
import { EyeGrid } from './EyeGrid';
import { Field, TextIn, AreaIn, NativeSelect } from './EvalFields';
import { PRISM_BASES_H, PRISM_BASES_V } from './examShared';

const rk = (eye, k) => `${eye === 'os' ? 'oi' : 'od'}_${k}`;
const grid = (v, set) => ({ get: (eye, k) => v[rk(eye, k)], set: (eye, k, val) => set(rk(eye, k), val) });
const Sub = ({ children }) => <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">{children}</p>;

const EYEGLASS_COLS = [
  { key: 'sphere', label: 'Esfera', unit: 'D', placeholder: '±0.00' }, { key: 'cylinder', label: 'Cilindro', unit: 'D', placeholder: '±0.00' },
  { key: 'axis', label: 'Eje', unit: '°', placeholder: '0-180' }, { key: 'addition', label: 'ADD', unit: 'D', placeholder: '+0.00' },
  { key: 'prism_h', label: 'Prisma H', unit: 'Δ' }, { key: 'base_h', label: 'Base H', options: PRISM_BASES_H },
  { key: 'prism_v', label: 'Prisma V', unit: 'Δ' }, { key: 'base_v', label: 'Base V', options: PRISM_BASES_V },
];
const RX_MODES = [
  { v: '', l: 'Sin especificar' }, { v: 'lejos_add', l: 'Receta de lejos con ADD (multifocal / progresivo)' },
  { v: 'cerca_final', l: 'Potencia final de cerca (monofocal de cerca)' }, { v: 'monofocal', l: 'Monofocal' },
];

export function EyeglassFields({ v, set, readOnly }) {
  return (
    <div className="space-y-4">
      <EyeGrid columns={EYEGLASS_COLS} {...grid(v, set)} readOnly={readOnly} testId="rx-eyeglass-grid" cylKey="cylinder" />
      <div className="grid sm:grid-cols-3 gap-3">
        <Field label="Diseño de la prescripción" className="sm:col-span-2" hint="Diferencia la receta de lejos con ADD de la potencia final de cerca.">
          <NativeSelect value={v.rx_mode} onChange={(x) => set('rx_mode', x)} options={RX_MODES} disabled={readOnly} testId="rx-mode" />
        </Field>
        <Field label="Distancia de trabajo (cm)"><TextIn value={v.working_distance} onChange={(x) => set('working_distance', x)} readOnly={readOnly} inputMode="decimal" testId="rx-working-distance" /></Field>
      </div>
      <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/50 p-3 space-y-2" data-testid="rx-dispensing">
        <Sub>Dispensación · no forma parte del resultado refractivo</Sub>
        <EyeGrid columns={[{ key: 'dp', label: 'DP', unit: 'mm' }, { key: 'height', label: 'Altura', unit: 'mm' }]} {...grid(v, set)} readOnly={readOnly} testId="rx-dispensing-grid" />
        <div className="grid sm:grid-cols-2 gap-3">
          <Field label="Tipo de lente"><TextIn value={v.lens_type} onChange={(x) => set('lens_type', x)} readOnly={readOnly} placeholder="Monofocal, progresivo, ocupacional…" testId="rx-lens-type" /></Field>
          <Field label="Armazón"><TextIn value={v.frame_type} onChange={(x) => set('frame_type', x)} readOnly={readOnly} testId="rx-frame-type" /></Field>
        </div>
      </div>
    </div>
  );
}

const CONTACT_COLS = [
  { key: 'power', label: 'Potencia', unit: 'D', placeholder: '±0.00' }, { key: 'cylinder', label: 'Cil', unit: 'D' }, { key: 'axis', label: 'Eje', unit: '°' },
  { key: 'addition', label: 'ADD', unit: 'D' }, { key: 'bc', label: 'C.B.', unit: 'mm' }, { key: 'dia', label: 'Diám', unit: 'mm' },
  { key: 'extra', label: 'Parámetros propios del ojo' },
];
const DESIGNS = [{ v: '', l: 'Diseño…' }, { v: 'esferico', l: 'Esférico' }, { v: 'torico', l: 'Tórico' }, { v: 'multifocal', l: 'Multifocal' }, { v: 'otro', l: 'Otro' }];
const MODALITY = [{ v: '', l: 'Modalidad…' }, { v: 'uso diario', l: 'Uso diario (se retira al dormir)' }, { v: 'uso flexible', l: 'Uso flexible' }, { v: 'uso prolongado', l: 'Uso prolongado / continuo' }];
const REPLACEMENT = [{ v: '', l: 'Reemplazo…' }, { v: 'diario', l: 'Diario' }, { v: 'quincenal', l: 'Quincenal' }, { v: 'mensual', l: 'Mensual' }, { v: 'trimestral', l: 'Trimestral' }, { v: 'anual', l: 'Anual' }];

export function ContactFields({ v, set, readOnly }) {
  return (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <Field label="Fabricante"><TextIn value={v.manufacturer} onChange={(x) => set('manufacturer', x)} readOnly={readOnly} testId="rx-manufacturer" /></Field>
        <Field label="Marca"><TextIn value={v.brand} onChange={(x) => set('brand', x)} readOnly={readOnly} testId="rx-brand" /></Field>
        <Field label="Modelo"><TextIn value={v.model} onChange={(x) => set('model', x)} readOnly={readOnly} testId="rx-model" /></Field>
        <Field label="Material"><TextIn value={v.material} onChange={(x) => set('material', x)} readOnly={readOnly} testId="rx-material" /></Field>
        <Field label="Diseño"><NativeSelect value={v.design} onChange={(x) => set('design', x)} options={DESIGNS} disabled={readOnly} testId="rx-design" /></Field>
        <Field label="Modalidad de uso"><NativeSelect value={v.modality} onChange={(x) => set('modality', x)} options={MODALITY} disabled={readOnly} testId="rx-modality" /></Field>
        <Field label="Frecuencia de reemplazo"><NativeSelect value={v.replacement} onChange={(x) => set('replacement', x)} options={REPLACEMENT} disabled={readOnly} testId="rx-replacement" /></Field>
        <Field label="Sistema de cuidado"><TextIn value={v.care_system} onChange={(x) => set('care_system', x)} readOnly={readOnly} testId="rx-care" /></Field>
      </div>
      <EyeGrid columns={CONTACT_COLS} {...grid(v, set)} readOnly={readOnly} testId="rx-contact-grid" cylKey="cylinder" />
    </div>
  );
}

const SCLERAL_COLS = [
  { key: 'power', label: 'Potencia', unit: 'D' }, { key: 'cylinder', label: 'Cil', unit: 'D' }, { key: 'axis', label: 'Eje', unit: '°' },
  { key: 'addition', label: 'ADD', unit: 'D' }, { key: 'dia', label: 'Diám', unit: 'mm' }, { key: 'sag', label: 'Sagita' }, { key: 'ref_dia', label: 'Diám ref.', unit: 'mm' },
];
const SCLERAL_FIT = [
  { key: 'limbal_zone', label: 'Zona limbal' }, { key: 'haptic_sup', label: 'Háptica S' }, { key: 'haptic_inf', label: 'Háptica I' },
  { key: 'haptic_nas', label: 'Háptica N' }, { key: 'haptic_tem', label: 'Háptica T' }, { key: 'extra', label: 'Parámetros propios' },
];

export function ScleralFields({ v, set, readOnly }) {
  return (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <Field label="Laboratorio"><TextIn value={v.lab} onChange={(x) => set('lab', x)} readOnly={readOnly} testId="rx-lab" /></Field>
        <Field label="Diseño"><TextIn value={v.design} onChange={(x) => set('design', x)} readOnly={readOnly} testId="rx-scleral-design" /></Field>
        <Field label="Código del lente"><TextIn value={v.lab_code} onChange={(x) => set('lab_code', x)} readOnly={readOnly} testId="rx-lab-code" /></Field>
        <Field label="Material"><TextIn value={v.material} onChange={(x) => set('material', x)} readOnly={readOnly} testId="rx-scleral-material" /></Field>
        <Field label="Espesor"><TextIn value={v.thickness} onChange={(x) => set('thickness', x)} readOnly={readOnly} testId="rx-thickness" /></Field>
        <Field label="Tratamiento superficial"><TextIn value={v.surface_treatment} onChange={(x) => set('surface_treatment', x)} readOnly={readOnly} testId="rx-surface" /></Field>
      </div>
      <div className="flex items-end gap-3">
        <Field label="Unidad de sagita" className="w-40"><NativeSelect value={v.sag_unit || 'µm'} onChange={(x) => set('sag_unit', x)} disabled={readOnly} testId="rx-sag-unit"
          options={[{ v: 'µm', l: 'µm' }, { v: 'mm', l: 'mm' }]} /></Field>
        <p className="text-[11px] text-slate-400 pb-2">Indica la sagita junto con su diámetro de referencia.</p>
      </div>
      <EyeGrid columns={SCLERAL_COLS} {...grid(v, set)} readOnly={readOnly} testId="rx-scleral-grid" cylKey="cylinder" />
      <EyeGrid columns={SCLERAL_FIT} {...grid(v, set)} readOnly={readOnly} testId="rx-scleral-fit-grid" />
      <div className="grid md:grid-cols-2 gap-3">
        <Field label="Modificaciones especiales"><AreaIn value={v.special_mods} onChange={(x) => set('special_mods', x)} readOnly={readOnly} testId="rx-special-mods" /></Field>
        <Field label="Parámetros propios del fabricante"><AreaIn value={v.manufacturer_params} onChange={(x) => set('manufacturer_params', x)} readOnly={readOnly} testId="rx-manufacturer-params" /></Field>
        <Field label="Uso"><TextIn value={v.usage_instructions} onChange={(x) => set('usage_instructions', x)} readOnly={readOnly} placeholder="Horas de uso, esquema" testId="rx-usage-instructions" /></Field>
        <Field label="Solución de llenado"><TextIn value={v.filling_solution} onChange={(x) => set('filling_solution', x)} readOnly={readOnly} testId="rx-filling" /></Field>
        <Field label="Limpieza y desinfección" className="md:col-span-2"><TextIn value={v.cleaning} onChange={(x) => set('cleaning', x)} readOnly={readOnly} testId="rx-cleaning" /></Field>
      </div>
    </div>
  );
}

export const KIND_FIELD_COMPONENTS = { eyeglass: EyeglassFields, contact: ContactFields, scleral: ScleralFields };
