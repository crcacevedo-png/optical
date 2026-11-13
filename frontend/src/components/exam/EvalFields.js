import React from 'react';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { SECTION_STATUS } from './examShared';

export const Field = ({ label, hint, children, className = '' }) => (
  <div className={`space-y-1 ${className}`}>
    <Label className="text-xs font-medium text-slate-600">{label}</Label>
    {children}
    {hint && <p className="text-[11px] leading-snug text-slate-400">{hint}</p>}
  </div>
);

export const TextIn = ({ value, onChange, testId, className = '', ...rest }) => (
  <Input value={value ?? ''} onChange={(e) => onChange(e.target.value)} data-testid={testId} className={`h-9 text-sm ${className}`} {...rest} />
);

export const AreaIn = ({ value, onChange, testId, rows = 2, ...rest }) => (
  <Textarea value={value ?? ''} rows={rows} onChange={(e) => onChange(e.target.value)} data-testid={testId} className="text-sm" {...rest} />
);

export const NativeSelect = ({ value, onChange, options, testId, className = '', disabled }) => (
  <select value={value ?? ''} onChange={(e) => onChange(e.target.value)} disabled={disabled} data-testid={testId}
    className={`h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 disabled:bg-slate-50 ${className}`}>
    {options.map((o) => <option key={o.v ?? o.value} value={o.v ?? o.value}>{o.l ?? o.label}</option>)}
  </select>
);

export const CheckLine = ({ id, checked, onChange, label, testId }) => (
  <label htmlFor={id} className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
    <input id={id} type="checkbox" checked={!!checked} onChange={(e) => onChange(e.target.checked)} data-testid={testId}
      className="h-4 w-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500" />
    {label}
  </label>
);

const HIDE = new Set(['no_realizado', 'no_indicado']);

// Seccion clinica con estado explicito: no se asume "normal" por defecto.
export const ClinicalSection = ({ title, status, onStatus, testId, children, note }) => (
  <section className="rounded-xl border border-slate-200 bg-white p-4 space-y-3" data-testid={testId}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-[0.08em] text-pine-700">{title}</h4>
        {note && <p className="text-[11px] text-slate-400 mt-0.5">{note}</p>}
      </div>
      {onStatus && (
        <NativeSelect value={status || ''} onChange={onStatus} testId={`${testId}-status`} className="w-auto min-w-[170px] h-8 text-xs"
          options={SECTION_STATUS.map((s) => ({ v: s.value, l: s.label }))} />
      )}
    </div>
    {HIDE.has(status) ? (
      <p className="text-xs italic text-slate-400">Registrado como “{SECTION_STATUS.find((s) => s.value === status)?.label}”.</p>
    ) : children}
  </section>
);
