import { Glasses, Eye, CircleDot } from 'lucide-react';
import { api, formatApiErrorDetail } from '../../context/AuthContext';

// OD = ojo derecho, OS = ojo izquierdo. Las recetas guardan el OS con prefijo interno `oi_`.
export const EYES = [
  { key: 'od', rxKey: 'od', label: 'OD', name: 'Ojo derecho', cls: 'text-blue-700' },
  { key: 'os', rxKey: 'oi', label: 'OS', name: 'Ojo izquierdo', cls: 'text-emerald-700' },
];

export const SECTION_STATUS = [
  { value: '', label: 'Sin registrar' },
  { value: 'realizado', label: 'Realizado' },
  { value: 'con_hallazgos', label: 'Con hallazgos' },
  { value: 'sin_hallazgos', label: 'Resultado negativo' },
  { value: 'no_realizado', label: 'No realizado' },
  { value: 'no_indicado', label: 'No indicado' },
];

export const RX_STATUS = {
  borrador: { label: 'Borrador', cls: 'bg-amber-50 text-amber-800 border-amber-200' },
  emitida: { label: 'Emitida', cls: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
  sustituida: { label: 'Sustituida', cls: 'bg-slate-100 text-slate-600 border-slate-200' },
  anulada: { label: 'Anulada', cls: 'bg-red-50 text-red-700 border-red-200' },
  historica: { label: 'Emitida (histórica)', cls: 'bg-sky-50 text-sky-800 border-sky-200' },
};

export const KIND_META = {
  eyeglass: { label: 'Anteojos', icon: Glasses, cls: 'text-blue-700 bg-blue-50' },
  contact: { label: 'Lentes de contacto', icon: Eye, cls: 'text-teal-700 bg-teal-50' },
  scleral: { label: 'Esclerales', icon: CircleDot, cls: 'text-violet-700 bg-violet-50' },
};

export const USAGE_OPTIONS = {
  eyeglass: ['Lejos', 'Cerca / lectura', 'Intermedia / computadora', 'Multifocal (lejos + ADD)', 'Ocupacional', 'Respaldo', 'Sol', 'Deportivo'],
  contact: ['Uso diario', 'Uso ocasional', 'Deportivo', 'Terapéutico', 'Cosmético'],
  scleral: ['Uso diario', 'Terapéutico', 'Rehabilitación visual'],
};

export const PRISM_BASES_H = [{ v: '', l: '—' }, { v: 'BN', l: 'BN (nasal)' }, { v: 'BT', l: 'BT (temporal)' }];
export const PRISM_BASES_V = [{ v: '', l: '—' }, { v: 'BS', l: 'BS (superior)' }, { v: 'BI', l: 'BI (inferior)' }];

export const rxStatusKey = (rx) => rx?.status || 'historica';
export const isDeliverable = (rx) => ['emitida', 'historica'].includes(rxStatusKey(rx));
export const apiError = (err, fallback = 'Ocurrió un error') => formatApiErrorDetail(err?.response?.data?.detail) || fallback;
export const hasVal = (v) => v !== null && v !== undefined && String(v).trim() !== '';

export const fmtDate = (d) => {
  if (!d) return '';
  const p = String(d).slice(0, 10).split('-');
  return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : d;
};

export const fmtPow = (v, plano = false) => {
  if (!hasVal(v)) return '—';
  const n = Number(String(v).replace(',', '.'));
  if (Number.isNaN(n)) return String(v);
  if (n === 0) return plano ? 'PL' : '0.00';
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}`;
};

const parseNum = (v) => {
  if (!hasVal(v)) return null;
  const s = String(v).trim().toLowerCase();
  if (['pl', 'plano', 'neutro'].includes(s)) return 0;
  const n = Number(s.replace(',', '.'));
  return Number.isNaN(n) ? NaN : n;
};

// Eje obligatorio cuando el cilindro no es cero.
export const axisMissing = (cyl, axis) => {
  const c = parseNum(cyl);
  return c !== null && !Number.isNaN(c) && c !== 0 && !hasVal(axis);
};
export const notNumeric = (v) => Number.isNaN(parseNum(v));

export const effectiveRx = (rx) => (['emitida', 'sustituida'].includes(rx?.status) && rx?.snapshot?.values ? { ...rx, ...rx.snapshot.values } : rx);

export const eyeSummary = (kind, rx, prefix) => {
  const r = effectiveRx(rx) || {};
  const sph = kind === 'eyeglass' ? r[`${prefix}_sphere`] : r[`${prefix}_power`];
  if (!hasVal(sph) && !hasVal(r[`${prefix}_cylinder`])) return '—';
  let s = `${fmtPow(sph, true)}`;
  if (hasVal(r[`${prefix}_cylinder`]) && Number(r[`${prefix}_cylinder`]) !== 0) s += ` / ${fmtPow(r[`${prefix}_cylinder`])} x ${r[`${prefix}_axis`] ?? '—'}°`;
  if (hasVal(r[`${prefix}_addition`])) s += ` · ADD ${fmtPow(r[`${prefix}_addition`])}`;
  if (kind !== 'eyeglass' && hasVal(r[`${prefix}_dia`])) s += ` · Ø ${r[`${prefix}_dia`]}`;
  return s;
};

export const openPdfBlob = (data, download = null) => {
  const url = window.URL.createObjectURL(new Blob([data], { type: 'application/pdf' }));
  if (download) {
    const a = document.createElement('a');
    a.href = url; a.download = download;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => window.URL.revokeObjectURL(url), 4000);
    return null;
  }
  return window.open(url, '_blank');
};

export const fetchRxPdf = (kind, id, copies = 1) =>
  api.get(`/api/prescriptions/${kind}/${id}/pdf`, { params: { copies }, responseType: 'blob' });

export const waDigits = (patient) => {
  let d = String(patient?.whatsapp || patient?.phone || '').replace(/\D/g, '');
  if (d.length === 8) d = `502${d}`;
  return d;
};
