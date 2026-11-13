import React, { useEffect, useState } from 'react';
import { Plus, Save, BadgeCheck, Unlock, Loader2, Info } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../../context/AuthContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Field, TextIn, AreaIn } from './EvalFields';
import { EyeGrid } from './EyeGrid';
import { AdaptationTrial } from './AdaptationTrial';
import { ConfirmDialog, ReasonDialog } from './ExamDialogs';
import { apiError } from './examShared';

const OPTICAL = [
  { key: 'power', label: 'Potencia', unit: 'D' }, { key: 'cylinder', label: 'Cil', unit: 'D' }, { key: 'axis', label: 'Eje', unit: '°' },
  { key: 'addition', label: 'ADD', unit: 'D' }, { key: 'bc', label: 'C.B.', unit: 'mm' }, { key: 'dia', label: 'Diám', unit: 'mm' },
];
const SCLERAL_OPT = [
  { key: 'power', label: 'Potencia', unit: 'D' }, { key: 'cylinder', label: 'Cil', unit: 'D' }, { key: 'axis', label: 'Eje', unit: '°' },
  { key: 'addition', label: 'ADD', unit: 'D' }, { key: 'dia', label: 'Diám', unit: 'mm' }, { key: 'sag', label: 'Sagita', unit: 'µm' }, { key: 'ref_dia', label: 'Diám ref', unit: 'mm' },
];
const SCLERAL_FIT = [{ key: 'limbal_zone', label: 'Zona limbal' }, { key: 'haptic_sup', label: 'Háptica S' }, { key: 'haptic_inf', label: 'Háptica I' }, { key: 'haptic_nas', label: 'Háptica N' }, { key: 'haptic_tem', label: 'Háptica T' }];
const IDENTITY = [{ key: 'brand', label: 'Marca / lab.' }, { key: 'design', label: 'Diseño' }, { key: 'material', label: 'Material' }, { key: 'extra', label: 'Otros parámetros' }];
const TEXTS = ['title', 'care_habits', 'keratometry_od', 'keratometry_os', 'surface_notes', 'decision', 'follow_up', 'params_requested', 'params_received'];
const uid = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + Math.random()));

export function AdaptationDialog({ open, onOpenChange, adaptation, kind, patientId, examId, canClinical, onSaved }) {
  const [ad, setAd] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [confirmAccept, setConfirmAccept] = useState(false);
  const [askReopen, setAskReopen] = useState(false);

  useEffect(() => {
    if (!open) return;
    setAd(adaptation ? JSON.parse(JSON.stringify(adaptation)) : { kind, trials: [], accepted_params: { od: {}, oi: {} } });
    setDirty(false);
  }, [open, adaptation, kind]);
  if (!ad) return null;
  const scleral = ad.kind === 'escleral';
  const accepted = ad.status === 'aceptada';
  const ro = accepted;
  const set = (k, v) => { setAd((a) => ({ ...a, [k]: v })); setDirty(true); };
  const param = (eye) => (eye === 'os' ? 'oi' : 'od');
  const pget = (eye, k) => ad.accepted_params?.[param(eye)]?.[k] ?? '';
  const pset = (eye, k, v) => set('accepted_params', { ...ad.accepted_params, [param(eye)]: { ...(ad.accepted_params?.[param(eye)] || {}), [k]: v } });
  const addTrial = (eye) => set('trials', [...(ad.trials || []), { id: uid(), eye, visit_label: '', visit_date: new Date().toISOString().slice(0, 10), lens: {}, fit: {} }]);

  const persist = async () => {
    const body = { ...Object.fromEntries(TEXTS.map((k) => [k, ad[k] ?? ''])), trials: ad.trials || [], accepted_params: ad.accepted_params || {} };
    if (ad._id) return (await api.put(`/api/clinical/adaptations/${ad._id}`, body)).data;
    return (await api.post('/api/clinical/adaptations', { ...body, kind: ad.kind, patient_id: patientId, consultation_id: examId })).data;
  };
  const run = async (fn, msg) => {
    setBusy(true);
    try { const saved = await fn(); setAd(saved); setDirty(false); toast.success(msg); onSaved(saved); }
    catch (err) { toast.error(apiError(err)); } finally { setBusy(false); }
  };
  const save = () => run(persist, 'Adaptación guardada');
  const accept = () => run(async () => {
    const saved = dirty || !ad._id ? await persist() : ad;
    setConfirmAccept(false);
    return (await api.post(`/api/clinical/adaptations/${saved._id}/accept`)).data;
  }, 'Adaptación aceptada');
  const reopen = (reason) => run(async () => { setAskReopen(false); return (await api.post(`/api/clinical/adaptations/${ad._id}/reopen`, { reason })).data; }, 'Adaptación reabierta');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto" data-testid="adaptation-dialog">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            {scleral ? 'Adaptación de lentes esclerales' : 'Adaptación de lentes de contacto'}
            <span className={`text-xs rounded-full border px-2 py-0.5 ${accepted ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-amber-50 border-amber-200 text-amber-800'}`} data-testid="adaptation-status">
              {accepted ? 'Aceptada' : 'En proceso'}
            </span>
          </DialogTitle>
          <DialogDescription>Registro clínico del proceso de adaptación, separado de la receta. La receta se prepara a partir de una adaptación aceptada.</DialogDescription>
        </DialogHeader>
        <fieldset disabled={ro} className="space-y-5 min-w-0">
          <div className="grid md:grid-cols-2 gap-3">
            <Field label="Título"><TextIn value={ad.title} onChange={(v) => set('title', v)} testId="adaptation-title" /></Field>
            <Field label="Hábitos y cuidados"><TextIn value={ad.care_habits} onChange={(v) => set('care_habits', v)} testId="adaptation-habits" /></Field>
            <Field label="Queratometría / superficie OD"><TextIn value={ad.keratometry_od} onChange={(v) => set('keratometry_od', v)} testId="adaptation-k-od" /></Field>
            <Field label="Queratometría / superficie OS"><TextIn value={ad.keratometry_os} onChange={(v) => set('keratometry_os', v)} testId="adaptation-k-os" /></Field>
          </div>
          <Field label="Notas de superficie ocular"><AreaIn value={ad.surface_notes} onChange={(v) => set('surface_notes', v)} testId="adaptation-surface" /></Field>

          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-xs font-semibold uppercase tracking-[0.08em] text-pine-700">Pruebas ({(ad.trials || []).length})</h4>
              {!ro && (
                <div className="flex gap-2">
                  <Button type="button" variant="outline" size="sm" onClick={() => addTrial('od')} data-testid="adaptation-add-trial-od"><Plus className="w-3.5 h-3.5 mr-1" /> Prueba OD</Button>
                  <Button type="button" variant="outline" size="sm" onClick={() => addTrial('oi')} data-testid="adaptation-add-trial-os"><Plus className="w-3.5 h-3.5 mr-1" /> Prueba OS</Button>
                </div>
              )}
            </div>
            {(ad.trials || []).length === 0 && <p className="text-xs text-slate-400">Sin pruebas registradas. Puedes registrar varias por ojo y por consulta.</p>}
            {(ad.trials || []).map((t, i) => (
              <AdaptationTrial key={t.id} trial={t} index={i} scleral={scleral} readOnly={ro}
                onChange={(nt) => set('trials', ad.trials.map((x) => (x.id === t.id ? nt : x)))}
                onRemove={() => set('trials', ad.trials.filter((x) => x.id !== t.id))} />
            ))}
          </div>

          <div className="grid md:grid-cols-2 gap-3">
            <Field label="Decisión clínica *"><AreaIn value={ad.decision} onChange={(v) => set('decision', v)} testId="adaptation-decision" /></Field>
            <Field label="Seguimiento"><AreaIn value={ad.follow_up} onChange={(v) => set('follow_up', v)} testId="adaptation-follow-up" /></Field>
            {scleral && <Field label="Parámetros solicitados al laboratorio"><AreaIn value={ad.params_requested} onChange={(v) => set('params_requested', v)} testId="adaptation-params-requested" /></Field>}
            {scleral && <Field label="Parámetros recibidos"><AreaIn value={ad.params_received} onChange={(v) => set('params_received', v)} testId="adaptation-params-received" /></Field>}
          </div>

          <div className="rounded-xl border border-teal-200 bg-teal-50/40 p-4 space-y-3" data-testid="adaptation-accepted-params">
            <h4 className="text-xs font-semibold uppercase tracking-[0.08em] text-teal-800">Parámetros aceptados por ojo</h4>
            <EyeGrid columns={scleral ? SCLERAL_OPT : OPTICAL} get={pget} set={pset} readOnly={ro} testId="adaptation-params-optical" cylKey="cylinder" />
            {scleral && <EyeGrid columns={SCLERAL_FIT} get={pget} set={pset} readOnly={ro} testId="adaptation-params-fit" />}
            <EyeGrid columns={IDENTITY} get={pget} set={pset} readOnly={ro} testId="adaptation-params-identity" />
          </div>
        </fieldset>
        <p className="flex items-start gap-1.5 text-[11px] text-slate-500"><Info className="w-3.5 h-3.5 mt-0.5 shrink-0" /> No se aprueba ningún lente por umbrales automáticos ni se calcula potencia a partir de la sobrerrefracción: la decisión es del profesional.</p>
        <div className="flex flex-wrap justify-end gap-2 pt-2 border-t border-slate-100">
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="adaptation-close-btn">Cerrar</Button>
          {accepted ? (
            <Button variant="outline" onClick={() => setAskReopen(true)} disabled={!canClinical || busy} data-testid="adaptation-reopen-btn"><Unlock className="w-4 h-4 mr-1.5" /> Reabrir</Button>
          ) : (
            <>
              <Button variant="outline" onClick={save} disabled={busy || (!dirty && !!ad._id)} data-testid="adaptation-save-btn">
                {busy ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Save className="w-4 h-4 mr-1.5" />} Guardar
              </Button>
              <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => setConfirmAccept(true)} disabled={busy || !canClinical} data-testid="adaptation-accept-btn">
                <BadgeCheck className="w-4 h-4 mr-1.5" /> Marcar como aceptada
              </Button>
            </>
          )}
        </div>
        <ConfirmDialog open={confirmAccept} onOpenChange={setConfirmAccept} title="Aceptar adaptación" testId="adaptation-accept-dialog"
          description="Confirmas la decisión clínica con los parámetros aceptados. A partir de esta adaptación podrás emitir la receta." confirmLabel="Aceptar adaptación" onConfirm={accept} />
        <ReasonDialog open={askReopen} onOpenChange={setAskReopen} title="Reabrir adaptación" danger={false} testId="adaptation-reopen-dialog"
          description="Las recetas ya emitidas desde esta adaptación no cambian." confirmLabel="Reabrir" onConfirm={reopen} />
      </DialogContent>
    </Dialog>
  );
}
