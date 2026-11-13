import React, { useState } from 'react';
import { toast } from 'sonner';
import { api, useAuth } from '../../context/AuthContext';
import { MedicalRxDialog } from '../patients/PatientDialogs';
import { apiError } from './examShared';

const newMed = () => ({ _uid: crypto.randomUUID(), name: '', dosage: '', frequency: '', duration: '' });

// Receta médica asociada al examen (formato existente).
export function useMedicalRx(exam, onCreated) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ diagnosis: '', medications: [newMed()], instructions: '' });
  const start = () => { setForm({ diagnosis: exam?.diagnosis || '', medications: [newMed()], instructions: '' }); setOpen(true); };
  const submit = async () => {
    try {
      await api.post('/api/prescriptions/medical', {
        patient_id: exam.patient_id, consultation_id: exam._id, professional_name: exam.professional_name || user?.name,
        ...form, medications: form.medications.map(({ _uid, ...m }) => m),
      });
      toast.success('Receta médica creada');
      setOpen(false);
      onCreated();
    } catch (err) { toast.error(apiError(err, 'No se pudo crear la receta médica')); }
  };
  const dialog = (
    <MedicalRxDialog open={open} onOpenChange={setOpen} form={form} setForm={setForm} onSubmit={submit} testIdPrefix="exam-"
      addMedication={() => setForm((f) => ({ ...f, medications: [...f.medications, newMed()] }))}
      updateMedication={(i, k, v) => setForm((f) => ({ ...f, medications: f.medications.map((m, j) => (j === i ? { ...m, [k]: v } : m)) }))}
      removeMedication={(i) => setForm((f) => ({ ...f, medications: f.medications.filter((_, j) => j !== i) }))} />
  );
  return { start, dialog };
}
