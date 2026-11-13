import React from 'react';
import { EYES, axisMissing, notNumeric } from './examShared';

const NUMERIC = new Set(['sphere', 'cyl', 'cylinder', 'add', 'addition', 'power', 'prism_h', 'prism_v', 'dp', 'height', 'bc', 'dia', 'sag', 'ref_dia']);

// Grilla OD/OS reutilizable. columns: [{ key, label, unit, placeholder, options }]
// get(eye, key) / set(eye, key, value) con eye = 'od' | 'os'.
export function EyeGrid({ columns, get, set, readOnly = false, testId = 'eye-grid', cylKey = 'cyl' }) {
  return (
    <div className="overflow-x-auto -mx-1 px-1">
      <table className="w-full text-sm border-separate border-spacing-y-1" data-testid={testId}>
        <thead>
          <tr>
            <th className="w-12 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-400">Ojo</th>
            {columns.map((c) => (
              <th key={c.key} className="px-1 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-500 whitespace-nowrap">
                {c.label}{c.unit && <span className="ml-0.5 normal-case font-normal text-slate-400">({c.unit})</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {EYES.map((eye) => (
            <tr key={eye.key}>
              <td className={`pr-2 font-bold ${eye.cls}`} title={eye.name}>{eye.label}</td>
              {columns.map((c) => {
                const val = get(eye.key, c.key) ?? '';
                const missAxis = c.key === 'axis' && axisMissing(get(eye.key, cylKey), val);
                const bad = (NUMERIC.has(c.key) && notNumeric(val)) || missAxis;
                const tid = `${testId}-${eye.key}-${c.key}`;
                if (c.options) {
                  return (
                    <td key={c.key} className="px-1">
                      <select value={val} disabled={readOnly} onChange={(e) => set(eye.key, c.key, e.target.value)} data-testid={tid}
                        className="h-9 w-full min-w-[84px] rounded-md border border-slate-200 bg-white px-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 disabled:bg-slate-50 disabled:text-slate-500">
                        {c.options.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
                      </select>
                    </td>
                  );
                }
                return (
                  <td key={c.key} className="px-1">
                    <input value={val} readOnly={readOnly} placeholder={c.placeholder || ''} onChange={(e) => set(eye.key, c.key, e.target.value)}
                      aria-label={`${eye.label} ${c.label}`} title={missAxis ? 'El eje es obligatorio cuando el cilindro no es cero' : undefined}
                      className={`h-9 w-full min-w-[64px] rounded-md border px-2 text-sm font-mono tabular-nums focus:outline-none focus:ring-2 focus:ring-teal-500 ${readOnly ? 'bg-slate-50 text-slate-600' : 'bg-white'} ${bad ? 'border-red-400 bg-red-50/40' : 'border-slate-200'}`}
                      data-testid={tid} />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
