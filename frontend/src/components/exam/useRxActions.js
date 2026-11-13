import React, { useState } from 'react';
import { toast } from 'sonner';
import { api } from '../../context/AuthContext';
import { IssueDialog, ReasonDialog } from './ExamDialogs';
import { apiError, eyeSummary, fetchRxPdf, openPdfBlob, waDigits, KIND_META } from './examShared';
import { rxTitle } from './rxUtils';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const IssueSummary = ({ rx }) => (
  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm space-y-1" data-testid="issue-summary">
    <p className="font-semibold text-slate-800">{rxTitle(rx)} · {KIND_META[rx.kind]?.label}</p>
    <p className="font-mono text-xs"><span className="font-bold text-blue-700">OD</span> {eyeSummary(rx.kind, rx, 'od')}</p>
    <p className="font-mono text-xs"><span className="font-bold text-emerald-700">OS</span> {eyeSummary(rx.kind, rx, 'oi')}</p>
    {rx.usage && <p className="text-xs text-slate-500">Uso: {rx.usage}</p>}
  </div>
);

// Acciones compartidas de receta (examen y ficha del paciente).
export function useRxActions({ patient, reload, onDraft }) {
  const [issuing, setIssuing] = useState(null);
  const [voiding, setVoiding] = useState(null);
  const base = (rx) => `/api/clinical/prescriptions/${rx.kind}/${rx._id}`;
  const wrap = async (fn, fallback) => { try { return await fn(); } catch (err) { toast.error(apiError(err, fallback)); return null; } };

  const actions = {
    issue: (rx) => setIssuing(rx),
    void: (rx) => setVoiding(rx),
    duplicate: (rx) => wrap(async () => {
      const { data } = await api.post(`${base(rx)}/duplicate`);
      toast.success(`Copia creada como borrador ${data.code_display}`);
      await reload(); onDraft?.(data);
    }, 'No se pudo duplicar'),
    newVersion: (rx) => wrap(async () => {
      const { data } = await api.post(`${base(rx)}/new-version`);
      toast.success(`Versión v${data.version} creada como borrador`);
      await reload(); onDraft?.(data);
    }, 'No se pudo crear la nueva versión'),
    pdf: (rx) => wrap(async () => { const res = await fetchRxPdf(rx.kind, rx._id); openPdfBlob(res.data); }, 'No se pudo generar el PDF'),
    whatsapp: (rx) => wrap(async () => {
      const phone = waDigits(patient);
      if (!phone) { toast.error('El paciente no tiene teléfono registrado'); return; }
      const { data } = await api.post(`/api/prescriptions/${rx.kind}/${rx._id}/share-link`);
      const name = patient?.name || `${patient?.first_name || ''} ${patient?.last_name || ''}`.trim();
      const msg = `Hola ${name}, aquí tienes tu receta (${rxTitle(rx)}). Puedes descargarla o imprimirla desde este enlace: ${API_URL}/api/prescriptions/public/${data.token}`;
      window.open(`https://wa.me/${phone}?text=${encodeURIComponent(msg)}`, '_blank');
    }, 'No se pudo generar el enlace'),
    email: (rx) => wrap(async () => {
      const { data } = await api.post(`/api/prescriptions/${rx.kind}/${rx._id}/email`);
      toast.success(`Receta enviada a ${data.email}`);
    }, 'No se pudo enviar el correo'),
  };

  const confirmIssue = async (checked) => {
    const rx = issuing;
    const ok = await wrap(async () => {
      await api.post(`${base(rx)}/issue`, { confirm_reviewed: checked });
      toast.success(`Receta ${rx.code_display} emitida`);
      return true;
    }, 'No se pudo emitir la receta');
    if (ok) { setIssuing(null); reload(); }
  };
  const confirmVoid = async (reason) => {
    const rx = voiding;
    const ok = await wrap(async () => {
      await api.post(`${base(rx)}/void`, { reason });
      toast.success(`Receta ${rx.code_display} anulada`);
      return true;
    }, 'No se pudo anular la receta');
    if (ok) { setVoiding(null); reload(); }
  };

  const dialogs = (
    <>
      <IssueDialog open={!!issuing} onOpenChange={(o) => !o && setIssuing(null)} summary={issuing && <IssueSummary rx={issuing} />} onConfirm={confirmIssue} />
      <ReasonDialog open={!!voiding} onOpenChange={(o) => !o && setVoiding(null)} title="Anular receta" testId="void-rx-dialog" confirmLabel="Anular receta"
        description={voiding ? `${rxTitle(voiding)} · ${voiding.code_display}. La receta anulada queda en el historial y no podrá imprimirse para entrega.` : ''}
        onConfirm={confirmVoid} />
    </>
  );
  return { actions, dialogs };
}
