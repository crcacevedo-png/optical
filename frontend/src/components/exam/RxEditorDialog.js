import React, { useEffect, useState } from 'react';
import { Save, Loader2, Target, Layers, AlertTriangle, RefreshCw, Send } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../../context/AuthContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Field, TextIn, AreaIn, NativeSelect } from './EvalFields';
import { KIND_FIELD_COMPONENTS } from './RxKindFields';
import { KIND_META, RX_STATUS, USAGE_OPTIONS, apiError, fmtDate, rxStatusKey } from './examShared';
import { rxValues, eyeglassFromFR, fieldsFromAdaptation, acceptedOf } from './rxUtils';

function CommonFields({ kind, v, set, readOnly }) {
  return (
    <div className="grid sm:grid-cols-2 gap-3" data-testid="rx-common-fields">
      <Field label="Nombre de la receta" hint="Ej.: Anteojos para lejos, Lentes de lectura, LC mensuales">
        <TextIn value={v.name} onChange={(x) => set('name', x)} readOnly={readOnly} testId="rx-name" />
      </Field>
      <Field label="Uso indicado">
        <TextIn value={v.usage} onChange={(x) => set('usage', x)} readOnly={readOnly} list={`usage-${kind}`} testId="rx-usage" />
        <datalist id={`usage-${kind}`}>{USAGE_OPTIONS[kind].map((u) => <option key={u} value={u} />)}</datalist>
      </Field>
      <Field label="Indicaciones" className="sm:col-span-2"><AreaIn value={v.indications} onChange={(x) => set('indications', x)} readOnly={readOnly} testId="rx-indications" /></Field>
      <Field label="Control recomendado"><TextIn value={v.control} onChange={(x) => set('control', x)} readOnly={readOnly} placeholder="Ej.: 12 meses" testId="rx-control" /></Field>
      <Field label="Vigencia hasta"><TextIn type="date" value={v.valid_until} onChange={(x) => set('valid_until', x)} readOnly={readOnly} testId="rx-valid-until" /></Field>
      <Field label="Observaciones" className="sm:col-span-2"><AreaIn value={v.observations} onChange={(x) => set('observations', x)} readOnly={readOnly} testId="rx-observations" /></Field>
    </div>
  );
}

function SourceBanner({ kind, rx, fr, adaptations, adaptationId, setAdaptationId, onReload, readOnly }) {
  if (kind === 'eyeglass') {
    const ver = rx?.snapshot?.fr_version || rx?.source_ref?.fr_version || fr?.version;
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-teal-200 bg-teal-50/60 px-3 py-2 text-sm text-teal-900" data-testid="rx-source-fr">
        <Target className="w-4 h-4 shrink-0" />
        <span className="flex-1 min-w-[200px]">{ver ? <>Origen: <strong>refracción final v{ver}</strong> validada. Ajusta solo lo que corresponda a esta receta.</> : 'Sin refracción final validada vinculada.'}</span>
        {rx?.from_previous_fr && <span className="inline-flex items-center gap-1 text-amber-800 text-xs font-semibold"><AlertTriangle className="w-3.5 h-3.5" /> Basada en una versión anterior</span>}
        {!readOnly && fr && <Button type="button" size="sm" variant="outline" className="h-8 bg-white" onClick={onReload} data-testid="rx-reload-fr-btn"><RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Recargar v{fr.version}</Button>}
      </div>
    );
  }
  const options = acceptedOf(adaptations, kind);
  return (
    <div className="flex flex-wrap items-end gap-2 rounded-xl border border-violet-200 bg-violet-50/50 px-3 py-2" data-testid="rx-source-adaptation">
      <Layers className="w-4 h-4 text-violet-700 mb-2.5" />
      <Field label="Adaptación aceptada de origen" className="flex-1 min-w-[220px]">
        <NativeSelect value={adaptationId} onChange={setAdaptationId} disabled={readOnly} testId="rx-adaptation-select"
          options={[{ v: '', l: options.length ? 'Selecciona una adaptación…' : 'No hay adaptaciones aceptadas' }, ...options.map((a) => ({ v: a._id, l: `${a.title} · aceptada ${fmtDate(a.accepted_at)}` }))]} />
      </Field>
      {!readOnly && adaptationId && <Button type="button" size="sm" variant="outline" className="h-9 bg-white" onClick={onReload} data-testid="rx-reload-adaptation-btn"><RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Copiar parámetros</Button>}
    </div>
  );
}

// Editor de receta: crea/edita borradores; las emitidas se muestran en solo lectura (instantánea).
export function RxEditorDialog({ open, onOpenChange, kind, rx, initial, ctx, onSaved }) {
  const [v, setV] = useState({});
  const [adaptationId, setAdaptationId] = useState('');
  const [busy, setBusy] = useState(false);
  const readOnly = !!rx && rx.status !== 'borrador';
  const fr = ctx?.fr || null;

  useEffect(() => {
    if (!open || !kind) return;
    setV(rx ? rxValues(kind, rx) : { ...rxValues(kind, {}), ...(initial?.fields || {}) });
    setAdaptationId(rx?.adaptation_id || initial?.adaptation_id || '');
  }, [open, kind, rx, initial]);

  if (!kind) return null;
  const meta = KIND_META[kind];
  const KindFields = KIND_FIELD_COMPONENTS[kind];
  const set = (k, x) => setV((s) => ({ ...s, [k]: x }));
  const reload = () => {
    if (kind === 'eyeglass') { setV((s) => ({ ...s, ...eyeglassFromFR(fr) })); toast.info(`Valores de la refracción final v${fr.version} cargados`); return; }
    const ad = (ctx?.adaptations || []).find((a) => a._id === adaptationId);
    if (ad) { setV((s) => ({ ...s, ...fieldsFromAdaptation(kind, ad) })); toast.info('Parámetros de la adaptación copiados'); }
  };

  const save = async (issueAfter) => {
    setBusy(true);
    try {
      const body = { fields: v, adaptation_id: kind === 'eyeglass' ? undefined : (adaptationId || ''), fr_version: kind === 'eyeglass' && fr && !rx ? fr.version : undefined };
      const { data } = rx?._id
        ? await api.put(`/api/clinical/prescriptions/${kind}/${rx._id}`, body)
        : await api.post('/api/clinical/prescriptions', { ...body, kind, patient_id: ctx.patientId, consultation_id: ctx.examId || undefined });
      toast.success(rx?._id ? 'Borrador actualizado' : `Borrador ${data.code_display} creado`);
      onSaved(data, { issue: issueAfter });
      onOpenChange(false);
    } catch (err) { toast.error(apiError(err, 'No se pudo guardar la receta')); }
    finally { setBusy(false); }
  };

  const st = RX_STATUS[rxStatusKey(rx)] || RX_STATUS.borrador;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[92vh] overflow-y-auto" data-testid="rx-editor-dialog">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            <span className={`w-8 h-8 rounded-lg flex items-center justify-center ${meta.cls}`}><meta.icon className="w-4 h-4" /></span>
            {rx ? `${meta.label} · ${rx.code_display} v${rx.version || 1}` : `Nueva receta de ${meta.label.toLowerCase()}`}
            <span className={`text-xs rounded-full border px-2 py-0.5 ${rx ? st.cls : RX_STATUS.borrador.cls}`} data-testid="rx-editor-status">{rx ? st.label : 'Borrador'}</span>
          </DialogTitle>
          <DialogDescription>
            {readOnly ? 'Receta emitida: se muestran los valores congelados al momento de la emisión.' : 'Los cambios se guardan como borrador. La receta solo tiene validez al emitirla.'}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-5">
          <SourceBanner kind={kind} rx={rx} fr={fr} adaptations={ctx?.adaptations} adaptationId={adaptationId} setAdaptationId={setAdaptationId} onReload={reload} readOnly={readOnly} />
          <KindFields v={v} set={set} readOnly={readOnly} />
          <CommonFields kind={kind} v={v} set={set} readOnly={readOnly} />
        </div>
        <div className="flex flex-wrap justify-end gap-2 pt-3 border-t border-slate-100">
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="rx-editor-close">{readOnly ? 'Cerrar' : 'Cancelar'}</Button>
          {!readOnly && (
            <>
              <Button variant="outline" onClick={() => save(false)} disabled={busy} data-testid="rx-save-draft-btn">
                {busy ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Save className="w-4 h-4 mr-1.5" />} Guardar borrador
              </Button>
              {ctx?.canIssue && (
                <Button className="bg-pine-700 hover:bg-pine-800" onClick={() => save(true)} disabled={busy} data-testid="rx-save-issue-btn">
                  <Send className="w-4 h-4 mr-1.5" /> Guardar y emitir
                </Button>
              )}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
