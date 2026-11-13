import { hasVal, effectiveRx } from './examShared';

// Espejo de clinical_rules.py (OS se guarda con prefijo interno `oi_`).
const EYE_FIELDS = {
  eyeglass: ['sphere', 'cylinder', 'axis', 'addition', 'prism_h', 'base_h', 'prism_v', 'base_v', 'dp', 'height'],
  contact: ['power', 'cylinder', 'axis', 'addition', 'bc', 'dia', 'extra'],
  scleral: ['power', 'cylinder', 'axis', 'addition', 'dia', 'sag', 'ref_dia', 'limbal_zone', 'haptic_sup', 'haptic_inf', 'haptic_nas', 'haptic_tem', 'extra'],
};
const COMMON = ['name', 'usage', 'indications', 'control', 'valid_until', 'observations'];
const KIND = {
  eyeglass: ['rx_mode', 'working_distance', 'lens_type', 'frame_type', 'cyl_convention'],
  contact: ['manufacturer', 'brand', 'model', 'material', 'design', 'modality', 'replacement', 'care_system', 'lens_type'],
  scleral: ['lab', 'design', 'lab_code', 'material', 'thickness', 'surface_treatment', 'special_mods', 'manufacturer_params', 'sag_unit', 'usage_instructions', 'filling_solution', 'cleaning'],
};
const POWERS = new Set(['sphere', 'cylinder', 'addition', 'power']);
const PAIRS = [['od', 'od'], ['os', 'oi']];
export const ADAPT_KIND = { contact: 'contacto', scleral: 'escleral' };

export const rxKeys = (kind) => [...COMMON, ...KIND[kind], ...['od', 'oi'].flatMap((e) => EYE_FIELDS[kind].map((f) => `${e}_${f}`))];

const toText = (key, v) => {
  if (!hasVal(v)) return '';
  const base = key.slice(3);
  if (typeof v === 'number' && POWERS.has(base)) return `${v > 0 ? '+' : ''}${v.toFixed(2)}`;
  return String(v);
};

export const rxValues = (kind, rx) => {
  const src = effectiveRx(rx) || {};
  return Object.fromEntries(rxKeys(kind).map((k) => [k, toText(k, src[k])]));
};

export const latestValidatedFR = (exam) => {
  const fr = exam?.final_refraction;
  if (fr?.status === 'validada') return fr;
  const hist = (exam?.final_refraction_history || []).filter((h) => h.status === 'validada');
  return hist.length ? hist[hist.length - 1] : null;
};

const FR_MAP = { sphere: 'sphere', cyl: 'cylinder', axis: 'axis', add: 'addition', prism_h: 'prism_h', base_h: 'base_h', prism_v: 'prism_v', base_v: 'base_v' };
export const eyeglassFromFR = (fr) => {
  const out = { working_distance: fr.working_distance || '', cyl_convention: fr.cyl_convention || 'negativo' };
  PAIRS.forEach(([e, p]) => Object.entries(FR_MAP).forEach(([src, dst]) => { out[`${p}_${dst}`] = fr[e]?.[src] ?? ''; }));
  if (hasVal(out.od_addition) || hasVal(out.oi_addition)) out.rx_mode = 'lejos_add';
  return out;
};

const designOption = (d) => {
  const s = String(d || '').toLowerCase();
  if (!s) return '';
  if (s.includes('tor')) return 'torico';
  if (s.includes('multi')) return 'multifocal';
  if (s.includes('esf')) return 'esferico';
  return 'otro';
};

export const fieldsFromAdaptation = (kind, ad) => {
  const p = ad?.accepted_params || {};
  const first = (k) => p.od?.[k] || p.oi?.[k] || '';
  const out = {};
  ['od', 'oi'].forEach((e) => EYE_FIELDS[kind].forEach((f) => { if (hasVal(p[e]?.[f])) out[`${e}_${f}`] = p[e][f]; }));
  if (kind === 'contact') Object.assign(out, { brand: first('brand'), material: first('material'), design: designOption(first('design')) });
  else Object.assign(out, { lab: first('brand'), design: first('design'), material: first('material'), sag_unit: first('sag_unit') || 'µm' });
  return out;
};

export const acceptedOf = (adaptations, kind) => (adaptations || []).filter((a) => a.kind === ADAPT_KIND[kind] && a.status === 'aceptada');

export const rxTitle = (rx) => rx.name || { eyeglass: 'Receta de anteojos', contact: 'Receta de lentes de contacto', scleral: 'Receta de lentes esclerales', medical: 'Receta médica' }[rx.kind];
