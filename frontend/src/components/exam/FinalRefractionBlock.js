import React, { useEffect, useState } from 'react';
import { Target, Copy, Save, ShieldCheck, Clock, History, Undo2, Loader2, ChevronDown } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { EyeGrid } from './EyeGrid';
import { Field, TextIn, AreaIn, NativeSelect } from './EvalFields';
import { ConfirmDialog } from './ExamDialogs';
import { PRISM_BASES_H, PRISM_BASES_V, apiError, fmtDate, hasVal, fmtPow } from './examShared';

const COLS = [
  { key: 'sphere', label: 'Esfera', unit: 'D', placeholder: '±0.00' },
  { key: 'cyl', label: 'Cilindro', unit: 'D', placeholder: '±0.00' },
  { key: 'axis', label: 'Eje', unit: '°', placeholder: '0-180' },
  { key: 'add', label: 'ADD', unit: 'D', placeholder: '+0.00' },
  { key: 'prism_h', label: 'Prisma H', unit: 'Δ' }, { key: 'base_h', label: 'Base H', options: PRISM_BASES_H },
  { key: 'prism_v', label: 'Prisma V', unit: 'Δ' }, { key: 'base_v', label: 'Base V', options: PRISM_BASES_V },
  { key: 'va', label: 'AV mejor corr.', placeholder: '20/20' },
];
const EYE_KEYS = COLS.map((c) => c.key);
const clone = (o) => JSON.parse(JSON.stringify(o || {}));
const blank = (exam) => ({ od: {}, os: {}, working_distance: '', cyl_convention: 'negativo', observations: '', professional_name: exam.professional_name || '' });
const anyValue = (d) => ['od', 'os'].some((e) => EYE_KEYS.some((k) => hasVal(d[e]?.[k])));
const pickEye = (src) => Object.fromEntries(EYE_KEYS.map((k) => [k, src?.[k] ?? '']));
const legacyEye = (r, p) => ({ sphere: r[`${p}_sphere`] || '', cyl: r[`${p}_cylinder`] || '', axis: r[`${p}_axis`] || '', add: r[`${p}_addition`] || '' });
const frLine = (fr) => ['od', 'os'].map((e) => `${e === 'od' ? 'OD' : 'OS'} ${fmtPow(fr[e]?.sphere, true)} / ${fmtPow(fr[e]?.cyl)} x ${fr[e]?.axis || '—'} ADD ${fmtPow(fr[e]?.add)}`).join(' · ');

export function FinalRefractionBlock({ exam, onSaved, readOnly, canValidate }) {
  const fr = exam.final_refraction || null;
  const history = exam.final_refraction_history || [];
  const [draft, setDraft] = useState(() => (fr ? clone(fr) : blank(exam)));
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(null);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => { setDraft(fr ? clone(fr) : blank(exam)); setDirty(false); }, [exam._id, fr?.version, fr?.status, fr?.updated_at]); // eslint-disable-line react-hooks/exhaustive-deps

  const setEye = (eye, k, v) => { setDraft((d) => ({ ...d, [eye]: { ...(d[eye] || {}), [k]: v } })); setDirty(true); };
  const setTop = (k, v) => { setDraft((d) => ({ ...d, [k]: v })); setDirty(true); };
  const subj = exam.evaluation?.subjective_refraction;
  const legacy = (exam.refractions || []).find((r) => r.is_final) || (exam.refractions || [])[0];

  const applyCopy = (od, os, source) => { setDraft((d) => ({ ...d, od, os, source })); setDirty(true); setConfirm(null); toast.info('Valores copiados. Revísalos antes de validar.'); };
  const askCopy = (od, os, source, label) => {
    if (anyValue(draft)) setConfirm({ title: `Copiar ${label}`, desc: 'Se reemplazarán los valores actuales de la refracción final. Deberás revisarlos y validarlos.', run: () => applyCopy(od, os, source) });
    else applyCopy(od, os, source);
  };
  const copySubjective = () => {
    if (!subj || (!anyValue({ od: subj.od || {}, os: subj.os || {} }))) { toast.error('No hay refracción subjetiva guardada en la evaluación'); return; }
    askCopy(pickEye(subj.od), pickEye(subj.os), 'subjetiva', 'refracción subjetiva');
  };

  const save = async (quiet = false) => {
    const { data } = await api.put(`/api/clinical/exams/${exam._id}/final-refraction`, {
      od: pickEye(draft.od), os: pickEye(draft.os), working_distance: draft.working_distance || '', cyl_convention: draft.cyl_convention || 'negativo',
      observations: draft.observations || '', professional_name: draft.professional_name || '', source: draft.source || 'manual',
    });
    if (!quiet) toast.success(data.unchanged ? 'Sin cambios' : (fr?.status === 'validada' ? `Revisión v${data.final_refraction.version} creada (pendiente de validar)` : 'Refracción final guardada'));
    return data;
  };
  const run = async (fn) => { setBusy(true); try { await fn(); setDirty(false); onSaved(); } catch (err) { toast.error(apiError(err)); } finally { setBusy(false); } };
  const doSave = () => run(() => save());
  const doValidate = () => run(async () => {
    if (dirty || !fr) await save(true);
    await api.post(`/api/clinical/exams/${exam._id}/final-refraction/validate`);
    toast.success('Refracción final validada');
    setConfirm(null);
  });
  const doDiscard = () => run(async () => { await api.post(`/api/clinical/exams/${exam._id}/final-refraction/discard-revision`); toast.success('Revisión descartada'); setConfirm(null); });

  const status = fr?.status || 'none';
  const badge = status === 'validada'
    ? <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-800" data-testid="fr-status"><ShieldCheck className="w-3.5 h-3.5" /> Validada · v{fr.version}</span>
    : status === 'borrador'
      ? <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800" data-testid="fr-status"><Clock className="w-3.5 h-3.5" /> Pendiente de validación · v{fr.version}</span>
      : <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-600" data-testid="fr-status">Sin registrar</span>;

  return (
    <section className="relative rounded-2xl border-2 border-teal-500/70 bg-white shadow-sm overflow-hidden" data-testid="final-refraction-block">
      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-teal-500 to-pine-700" />
      <div className="p-5 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="w-9 h-9 rounded-xl bg-teal-600 text-white flex items-center justify-center"><Target className="w-5 h-5" /></span>
            <div>
              <h3 className="font-heading text-base font-semibold text-slate-900">Refracción final</h3>
              <p className="text-xs text-slate-500">Resultado clínico de referencia. No equivale automáticamente a las recetas que se emitan.</p>
            </div>
          </div>
          {badge}
        </div>

        {status === 'validada' && !readOnly && (
          <p className="text-xs rounded-lg bg-sky-50 border border-sky-200 text-sky-900 px-3 py-2" data-testid="fr-revision-note">
            Validada el {fmtDate(fr.validated_at)} por {fr.validated_by_name || 'el profesional'}. Si modificas y guardas, se crea la versión v{fr.version + 1}; las recetas ya emitidas no cambian.
          </p>
        )}
        {status === 'borrador' && history.length > 0 && (
          <p className="text-xs rounded-lg bg-amber-50 border border-amber-200 text-amber-900 px-3 py-2">Revisión en curso de la versión validada v{history[history.length - 1].version}.</p>
        )}

        <EyeGrid columns={COLS} readOnly={readOnly} testId="fr-grid" get={(e, k) => draft[e]?.[k]} set={setEye} />

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <Field label="Distancia de trabajo para ADD (cm)"><TextIn value={draft.working_distance} onChange={(v) => setTop('working_distance', v)} readOnly={readOnly} inputMode="decimal" testId="fr-working-distance" /></Field>
          <Field label="Convención de cilindro"><NativeSelect value={draft.cyl_convention || 'negativo'} onChange={(v) => setTop('cyl_convention', v)} disabled={readOnly} testId="fr-cyl-convention"
            options={[{ v: 'negativo', l: 'Cilindro negativo (−)' }, { v: 'positivo', l: 'Cilindro positivo (+)' }]} /></Field>
          <Field label="Profesional responsable" className="lg:col-span-2"><TextIn value={draft.professional_name} onChange={(v) => setTop('professional_name', v)} readOnly={readOnly} testId="fr-professional" /></Field>
        </div>
        <Field label="Observaciones clínicas"><AreaIn value={draft.observations} onChange={(v) => setTop('observations', v)} readOnly={readOnly} testId="fr-observations" /></Field>

        {!readOnly && (
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Button type="button" variant="outline" size="sm" onClick={copySubjective} data-testid="fr-copy-subjective-btn"><Copy className="w-3.5 h-3.5 mr-1.5" /> Copiar refracción subjetiva</Button>
            {legacy && (
              <Button type="button" variant="outline" size="sm" onClick={() => askCopy(legacyEye(legacy, 'od'), legacyEye(legacy, 'os'), 'refraccion_previa', 'refracción previa')} data-testid="fr-copy-legacy-btn">
                <Copy className="w-3.5 h-3.5 mr-1.5" /> Copiar refracción previa
              </Button>
            )}
            {status === 'borrador' && history.length > 0 && (
              <Button type="button" variant="ghost" size="sm" onClick={() => setConfirm({ title: 'Descartar revisión', desc: `Se restaurará la versión validada v${history[history.length - 1].version}.`, run: doDiscard })} data-testid="fr-discard-btn">
                <Undo2 className="w-3.5 h-3.5 mr-1.5" /> Descartar revisión
              </Button>
            )}
            <div className="ml-auto flex gap-2">
              <Button type="button" variant="outline" onClick={doSave} disabled={busy || !dirty} data-testid="fr-save-btn"><Save className="w-4 h-4 mr-1.5" /> Guardar</Button>
              <Button type="button" className="bg-teal-600 hover:bg-teal-700" disabled={busy || !canValidate || (status === 'validada' && !dirty) || (!fr && !anyValue(draft))}
                title={!canValidate ? 'Solo el profesional responsable o un perfil clínico puede validar' : undefined}
                onClick={() => setConfirm({ title: 'Validar refracción final', desc: 'Esta versión quedará como referencia clínica para emitir recetas de anteojos. Revisa OD y OS antes de continuar.', run: doValidate })}
                data-testid="fr-validate-btn">
                {busy ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <ShieldCheck className="w-4 h-4 mr-1.5" />} Validar refracción
              </Button>
            </div>
          </div>
        )}

        {history.length > 0 && (
          <div className="border-t border-slate-100 pt-3">
            <button type="button" onClick={() => setShowHistory((s) => !s)} className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-700" data-testid="fr-history-toggle">
              <History className="w-3.5 h-3.5" /> Versiones anteriores ({history.length}) <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showHistory ? 'rotate-180' : ''}`} />
            </button>
            {showHistory && (
              <ul className="mt-2 space-y-1.5" data-testid="fr-history-list">
                {[...history].reverse().map((h) => (
                  <li key={h.version} className="text-xs font-mono text-slate-600 rounded-lg bg-slate-50 px-3 py-2">
                    <span className="font-sans font-semibold text-slate-800">v{h.version}</span> · validada {fmtDate(h.validated_at)} · {frLine(h)}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
      <ConfirmDialog open={!!confirm} onOpenChange={(o) => !o && setConfirm(null)} title={confirm?.title} description={confirm?.desc}
        onConfirm={() => confirm?.run()} testId="fr-confirm-dialog" />
    </section>
  );
}
