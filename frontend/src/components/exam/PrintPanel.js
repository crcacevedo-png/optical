import React, { useEffect, useMemo, useState } from 'react';
import { Printer, Files, FileStack, Loader2, CheckSquare } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { KIND_META, apiError, fetchRxPdf, openPdfBlob, fmtDate } from './examShared';
import { rxTitle } from './rxUtils';

const MED_META = { label: 'Receta médica' };
const keyOf = (rx) => `${rx.kind}-${rx._id}`;
const codeOf = (rx) => rx.code_display || `RM-${String(rx._id).slice(-6).toUpperCase()}`;

// Impresión múltiple: solo recetas entregables (emitidas, históricas o médicas).
export function PrintPanel({ items, title = 'Imprimir recetas', subtitle, onPrinted, testId = 'print-panel' }) {
  const [sel, setSel] = useState({});
  const [busy, setBusy] = useState(null);
  const ids = useMemo(() => items.map(keyOf).join('|'), [items]);
  useEffect(() => { setSel({}); }, [ids]);

  const chosen = items.filter((rx) => sel[keyOf(rx)]);
  const toggle = (rx, on) => setSel((s) => ({ ...s, [keyOf(rx)]: on ? (s[keyOf(rx)] || 1) : 0 }));
  const setCopies = (rx, n) => setSel((s) => ({ ...s, [keyOf(rx)]: Math.max(1, Math.min(10, Number(n) || 1)) }));
  const allOn = items.length > 0 && chosen.length === items.length;

  const joint = async () => {
    setBusy('joint');
    try {
      const res = await api.post('/api/clinical/prescriptions/print', { items: chosen.map((rx) => ({ kind: rx.kind, id: rx._id, copies: sel[keyOf(rx)] })) }, { responseType: 'blob' });
      openPdfBlob(res.data);
      toast.success(`PDF conjunto con ${chosen.length} receta(s)`);
      onPrinted?.();
    } catch (err) {
      let msg = 'No se pudo generar el PDF';
      try { msg = JSON.parse(await err.response.data.text()).detail || msg; } catch (e) { /* respuesta no JSON */ }
      toast.error(msg);
    } finally { setBusy(null); }
  };
  const separate = async () => {
    setBusy('separate');
    try {
      for (const rx of chosen) {
        const res = await fetchRxPdf(rx.kind, rx._id, sel[keyOf(rx)]);
        openPdfBlob(res.data, `${codeOf(rx)}.pdf`);
      }
      toast.success(`${chosen.length} PDF descargado(s)`);
      onPrinted?.();
    } catch (err) { toast.error(apiError(err, 'No se pudo generar alguno de los PDF')); }
    finally { setBusy(null); }
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white shadow-sm p-5 space-y-4" data-testid={testId}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="w-9 h-9 rounded-xl bg-slate-900 text-white flex items-center justify-center"><Printer className="w-5 h-5" /></span>
          <div>
            <h3 className="font-heading text-base font-semibold text-slate-900">{title}</h3>
            <p className="text-xs text-slate-500">{subtitle || 'Selecciona recetas emitidas y genera un PDF conjunto (una receta por página) o archivos separados.'}</p>
          </div>
        </div>
        {items.length > 0 && (
          <Button size="sm" variant="ghost" onClick={() => setSel(allOn ? {} : Object.fromEntries(items.map((rx) => [keyOf(rx), sel[keyOf(rx)] || 1])))} data-testid={`${testId}-select-all`}>
            <CheckSquare className="w-4 h-4 mr-1.5" /> {allOn ? 'Quitar selección' : 'Seleccionar todas'}
          </Button>
        )}
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-slate-400" data-testid={`${testId}-empty`}>Aún no hay recetas emitidas para imprimir. Los borradores, sustituidas y anuladas no entran en la impresión de entrega.</p>
      ) : (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200">
          {items.map((rx) => {
            const k = keyOf(rx);
            const meta = KIND_META[rx.kind] || MED_META;
            return (
              <li key={k} className={`flex flex-wrap items-center gap-3 px-4 py-2.5 transition-colors ${sel[k] ? 'bg-teal-50/50' : ''}`} data-testid={`${testId}-row-${k}`}>
                <Checkbox checked={!!sel[k]} onCheckedChange={(v) => toggle(rx, !!v)} data-testid={`${testId}-check-${k}`} />
                <span className="flex-1 min-w-[160px] text-sm">
                  <span className="font-medium text-slate-800">{rxTitle(rx)}</span>
                  <span className="block text-xs text-slate-500"><span className="font-mono">{codeOf(rx)}</span> · {meta.label} · {fmtDate(rx.issued_at || rx.created_at)}</span>
                </span>
                <label className="flex items-center gap-1.5 text-xs text-slate-500">
                  Copias
                  <input type="number" min={1} max={10} value={sel[k] || 1} disabled={!sel[k]} onChange={(e) => setCopies(rx, e.target.value)}
                    className="h-8 w-14 rounded-md border border-slate-200 px-2 text-sm disabled:bg-slate-50" data-testid={`${testId}-copies-${k}`} />
                </label>
              </li>
            );
          })}
        </ul>
      )}
      <div className="flex flex-wrap items-center justify-end gap-2">
        <span className="mr-auto text-xs text-slate-500" data-testid={`${testId}-count`}>{chosen.length} seleccionada(s)</span>
        <Button variant="outline" onClick={separate} disabled={!chosen.length || !!busy} data-testid={`${testId}-separate-btn`}>
          {busy === 'separate' ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Files className="w-4 h-4 mr-1.5" />} PDF por separado
        </Button>
        <Button className="bg-slate-900 hover:bg-slate-800" onClick={joint} disabled={!chosen.length || !!busy} data-testid={`${testId}-joint-btn`}>
          {busy === 'joint' ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <FileStack className="w-4 h-4 mr-1.5" />} PDF conjunto
        </Button>
      </div>
    </section>
  );
}
