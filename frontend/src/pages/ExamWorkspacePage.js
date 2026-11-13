import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Loader2, Lock, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { ExamHeader, ExamSteps } from '../components/exam/ExamHeader';
import { EvaluationPanel } from '../components/exam/EvaluationPanel';
import { FinalRefractionBlock } from '../components/exam/FinalRefractionBlock';
import { AdaptationsSection } from '../components/exam/AdaptationsSection';
import { ExamRxSection } from '../components/exam/ExamRxSection';
import { PrintPanel } from '../components/exam/PrintPanel';
import { ConfirmDialog, ReasonDialog } from '../components/exam/ExamDialogs';
import { useMedicalRx } from '../components/exam/useMedicalRx';
import { NextAppointmentDialog } from '../components/appointments/NextAppointmentDialog';
import { apiError, isDeliverable } from '../components/exam/examShared';
import { latestValidatedFR } from '../components/exam/rxUtils';

const buildSteps = (exam, items) => {
  const fr = latestValidatedFR(exam);
  const issued = items.filter((r) => r.status === 'emitida');
  const evalDone = Object.keys(exam.evaluation || {}).length > 0 || !!exam.diagnosis;
  return [
    { label: 'Evaluación', done: evalDone, hint: evalDone ? 'Registrada' : 'General · Refracción · Diagnóstico' },
    { label: 'Refracción final', done: !!fr, hint: fr ? `Validada v${fr.version}` : (exam.final_refraction ? 'Pendiente de validar' : 'Sin registrar') },
    { label: 'Preparar recetas', done: issued.length > 0, hint: `${issued.length} emitida(s) · ${items.filter((r) => r.status === 'borrador').length} borrador(es)` },
    { label: 'Imprimir', done: issued.some((r) => (r.print_count || 0) > 0), hint: issued.some((r) => r.print_count) ? 'Entregada' : 'Selección múltiple' },
  ];
};

export default function ExamWorkspacePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [exam, setExam] = useState(null);
  const [error, setError] = useState(null);
  const [rx, setRx] = useState({ items: [], medical: [] });
  const [adaptations, setAdaptations] = useState([]);
  const [dialog, setDialog] = useState(null);
  const refs = [useRef(null), useRef(null), useRef(null), useRef(null)];

  const loadExam = useCallback(async () => {
    try { const { data } = await api.get(`/api/clinical/exams/${id}/workspace`); setExam(data); setError(null); return data; }
    catch (err) { setError(apiError(err, 'No se pudo cargar el examen')); return null; }
  }, [id]);
  const pid = exam?.patient_id;
  const loadRx = useCallback(async () => {
    if (!pid) return;
    try { const { data } = await api.get('/api/clinical/prescriptions', { params: { patient_id: pid, consultation_id: id } }); setRx(data); }
    catch (err) { toast.error(apiError(err, 'No se pudieron cargar las recetas')); }
  }, [pid, id]);
  const loadAdaptations = useCallback(async () => {
    if (!pid) return;
    try { const { data } = await api.get('/api/clinical/adaptations', { params: { patient_id: pid } }); setAdaptations(data); }
    catch (err) { toast.error(apiError(err, 'No se pudieron cargar las adaptaciones')); }
  }, [pid]);

  useEffect(() => { loadExam(); }, [loadExam]);
  useEffect(() => { loadRx(); loadAdaptations(); }, [loadRx, loadAdaptations]);
  const reloadRx = useCallback(async () => { await Promise.all([loadRx(), loadExam()]); }, [loadRx, loadExam]);
  const medical = useMedicalRx(exam, loadRx);

  const printable = useMemo(() => [
    ...rx.items.filter(isDeliverable),
    ...(rx.medical || []).map((m) => ({ ...m, kind: 'medical', name: m.diagnosis ? `Receta médica · ${m.diagnosis}` : 'Receta médica' })),
  ], [rx]);

  if (error) {
    return (
      <div className="max-w-lg mx-auto mt-16 rounded-2xl border border-red-200 bg-red-50 p-6 text-center" data-testid="exam-error">
        <AlertCircle className="w-8 h-8 text-red-500 mx-auto mb-2" />
        <p className="text-red-800 font-medium">{error}</p>
        <Button variant="outline" className="mt-4" onClick={() => navigate('/consultations')}>Ir a consultas</Button>
      </div>
    );
  }
  if (!exam) return <div className="flex justify-center py-24" data-testid="exam-loading"><Loader2 className="w-7 h-7 animate-spin text-teal-600" /></div>;

  const signed = exam.exam_status === 'firmado';
  const back = () => (window.history.length > 1 ? navigate(-1) : navigate('/consultations'));
  const scrollTo = (i) => refs[i].current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  const act = async (fn, msg) => { try { await fn(); toast.success(msg); setDialog(null); loadExam(); } catch (err) { toast.error(apiError(err)); } };

  return (
    <div className="max-w-[1400px] mx-auto space-y-5 pb-16" data-testid="exam-workspace">
      <ExamHeader exam={exam} onBack={back} onSign={() => setDialog('sign')} onReopen={() => setDialog('reopen')}
        onSchedule={() => setDialog('schedule')} onMedical={medical.start} />
      <div className="sticky top-0 z-20 -mx-1 px-1 py-2 bg-slate-50/85 backdrop-blur-md">
        <ExamSteps steps={buildSteps(exam, rx.items)} onSelect={scrollTo} />
      </div>
      {signed && (
        <p className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-900" data-testid="exam-signed-banner">
          <Lock className="w-4 h-4" /> Examen firmado: la evaluación y la refracción final están en solo lectura. Reábrelo para modificarlas; las recetas se gestionan por separado.
        </p>
      )}
      <div ref={refs[0]} className="scroll-mt-28"><EvaluationPanel exam={exam} onExamChange={loadExam} readOnly={signed} /></div>
      <div ref={refs[1]} className="scroll-mt-28">
        <FinalRefractionBlock exam={exam} onSaved={loadExam} readOnly={signed} canValidate={!!exam.permissions?.clinical} />
      </div>
      <AdaptationsSection adaptations={adaptations} patientId={exam.patient_id} examId={exam._id} canClinical={!!exam.permissions?.clinical} onChange={loadAdaptations} />
      <div ref={refs[2]} className="scroll-mt-28">
        <ExamRxSection exam={exam} items={rx.items} medical={rx.medical || []} adaptations={adaptations} reload={reloadRx} onMedical={medical.start} />
      </div>
      <div ref={refs[3]} className="scroll-mt-28">
        <PrintPanel items={printable} title="Imprimir y entregar" testId="exam-print-panel" />
      </div>

      <ConfirmDialog open={dialog === 'sign'} onOpenChange={(o) => !o && setDialog(null)} title="Firmar examen" testId="sign-exam-dialog" confirmLabel="Firmar examen"
        description="La evaluación y la refracción final quedarán en solo lectura. Podrás reabrir el examen indicando un motivo."
        onConfirm={() => act(() => api.post(`/api/clinical/exams/${id}/sign`), 'Examen firmado')} />
      <ReasonDialog open={dialog === 'reopen'} onOpenChange={(o) => !o && setDialog(null)} title="Reabrir examen" danger={false} testId="reopen-exam-dialog" confirmLabel="Reabrir"
        description="Queda registrado quién reabrió el examen y por qué. Las recetas emitidas no cambian."
        onConfirm={(reason) => act(() => api.post(`/api/clinical/exams/${id}/reopen`, { reason }), 'Examen reabierto')} />
      <NextAppointmentDialog open={dialog === 'schedule'} onOpenChange={(o) => !o && setDialog(null)} patientId={exam.patient_id}
        professionalId={exam.professional_user_id} professionalName={exam.professional_name} />
      {medical.dialog}
    </div>
  );
}
