import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail, useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Textarea } from '../components/ui/textarea';
import { Checkbox } from '../components/ui/checkbox';
import { BranchFilter } from '../components/BranchFilter';
import {
  Plus, Trash2, Search, Eye, Pencil, Stethoscope, FileText, Pill,
  Clock, User, CalendarIcon, ChevronRight, Save, ArrowLeft
} from 'lucide-react';
import { toast } from 'sonner';
import { EyeglassRxDialog, ContactRxDialog, MedicalRxDialog } from '../components/patients/PatientDialogs';
import { NextAppointmentDialog } from '../components/appointments/NextAppointmentDialog';

const CONSULTATION_TYPES = [
  { value: 'control', label: 'Control' },
  { value: 'urgencia', label: 'Urgencia' },
  { value: 'primera_vez', label: 'Primera Vez' },
];
// Incluye tipos retirados del menu para etiquetar correctamente consultas antiguas
const CONSULTATION_TYPE_LABELS = {
  general: 'Consulta General', control: 'Control', urgencia: 'Urgencia',
  primera_vez: 'Primera Vez', seguimiento: 'Seguimiento',
};

const formatDate = (d) => {
  if (!d) return '';
  const parts = d.slice(0, 10).split('-');
  return `${parts[2]}/${parts[1]}/${parts[0]}`;
};

export default function ConsultationsPage() {
  const { user } = useAuth();
  const [consultations, setConsultations] = useState([]);
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [branchId, setBranchId] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  // Views: 'list' | 'form' | 'detail'
  const [view, setView] = useState('list');
  const [selectedConsultation, setSelectedConsultation] = useState(null);
  const [isEditing, setIsEditing] = useState(false);

  // Form state
  const defaultClinical = {
    wears_glasses: false, glasses_since: '', glasses_type: '',
    lensometry_od: '', lensometry_oi: '',
    lensometry_od_sphere: '', lensometry_od_cyl: '', lensometry_od_axis: '', lensometry_od_add: '',
    lensometry_oi_sphere: '', lensometry_oi_cyl: '', lensometry_oi_axis: '', lensometry_oi_add: '',
    ocular_surgeries: '', ocular_trauma: '', ocular_diseases: '',
    diabetes: false, hypertension: false, autoimmune_disease: false, autoimmune_details: '',
    current_medications: '', allergies: '',
    family_glaucoma: false, family_glaucoma_relationship: '',
    family_macular_degeneration: false, family_macular_relationship: '',
    family_high_myopia: false, family_high_myopia_relationship: '',
    family_other_history: '',
    va_distance_without_rx_od: '', va_distance_without_rx_oi: '',
    va_distance_with_rx_od: '', va_distance_with_rx_oi: '',
    va_near_without_rx_od: '', va_near_without_rx_oi: '',
    va_near_with_rx_od: '', va_near_with_rx_oi: '',
    va_pinhole_od: '', va_pinhole_oi: '',
    visual_acuity_method: 'Snellen'
  };
  const [form, setForm] = useState({
    patient_id: '', consultation_date: new Date().toISOString().slice(0, 10),
    consultation_time: new Date().toTimeString().slice(0, 5),
    consultation_type: 'primera_vez', chief_complaint: '', anamnesis: '',
    findings: '', diagnosis: '', treatment_plan: '', recommendations: '', notes: '',
    refractions: [],
    ...defaultClinical
  });
  const [patientSearch, setPatientSearch] = useState('');

  // Eyeglass Rx from consultation
  const [showEyeglassRx, setShowEyeglassRx] = useState(false);
  const [eyeglassForm, setEyeglassForm] = useState({
    od_sphere: '', od_cylinder: '', od_axis: '', od_addition: '', od_dp: '',
    oi_sphere: '', oi_cylinder: '', oi_axis: '', oi_addition: '', oi_dp: '',
    lens_type: '', frame_type: '', observations: ''
  });

  // Contact lens Rx from consultation
  const emptyContactForm = { od_power: '', od_bc: '', od_dia: '', od_cylinder: '', od_axis: '', od_addition: '', oi_power: '', oi_bc: '', oi_dia: '', oi_cylinder: '', oi_axis: '', oi_addition: '', brand: '', lens_type: '', replacement: '', observations: '' };
  const [showContactRx, setShowContactRx] = useState(false);
  const [contactForm, setContactForm] = useState(emptyContactForm);

  // Medical Rx from consultation
  const [showMedicalRx, setShowMedicalRx] = useState(false);
  const [medicalForm, setMedicalForm] = useState({
    diagnosis: '', medications: [{ _uid: crypto.randomUUID(), name: '', dosage: '', frequency: '', duration: '' }], instructions: ''
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      if (branchId) params.branch_id = branchId;
      const [cRes, pRes] = await Promise.all([
        api.get('/api/consultations', { params }),
        api.get('/api/patients', { params: { limit: 200 } }),
      ]);
      setConsultations(cRes.data || []);
      setPatients(pRes.data.patients || []);
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, [branchId]);

  useEffect(() => { loadData(); }, [loadData]);

  const resetForm = () => {
    setForm({
      patient_id: '', consultation_date: new Date().toISOString().slice(0, 10),
      consultation_time: new Date().toTimeString().slice(0, 5),
      consultation_type: 'primera_vez', chief_complaint: '', anamnesis: '',
      findings: '', diagnosis: '', treatment_plan: '', recommendations: '', notes: '',
      refractions: [],
      ...defaultClinical
    });
    setPatientSearch('');
  };

  const openNewConsultation = (patientId = '') => {
    resetForm();
    if (patientId) {
      const p = patients.find(pt => pt._id === patientId);
      if (p) {
        setForm(f => ({ ...f, patient_id: patientId }));
        setPatientSearch(`${p.first_name} ${p.last_name}`);
      }
    }
    setIsEditing(false);
    setView('form');
  };

  const openEditConsultation = (c) => {
    setForm({
      patient_id: c.patient_id, consultation_date: c.consultation_date,
      consultation_time: c.consultation_time || '',
      consultation_type: c.consultation_type || 'primera_vez',
      chief_complaint: c.chief_complaint || '', anamnesis: c.anamnesis || '',
      findings: c.findings || '', diagnosis: c.diagnosis || '',
      treatment_plan: c.treatment_plan || '', recommendations: c.recommendations || '',
      notes: c.notes || '',
      refractions: c.refractions || [],
      wears_glasses: c.wears_glasses || false, glasses_since: c.glasses_since || '',
      glasses_type: c.glasses_type || '', lensometry_od: c.lensometry_od || '', lensometry_oi: c.lensometry_oi || '', ocular_surgeries: c.ocular_surgeries || '',
      lensometry_od_sphere: c.lensometry_od_sphere || '', lensometry_od_cyl: c.lensometry_od_cyl || '', lensometry_od_axis: c.lensometry_od_axis || '', lensometry_od_add: c.lensometry_od_add || '',
      lensometry_oi_sphere: c.lensometry_oi_sphere || '', lensometry_oi_cyl: c.lensometry_oi_cyl || '', lensometry_oi_axis: c.lensometry_oi_axis || '', lensometry_oi_add: c.lensometry_oi_add || '',
      ocular_trauma: c.ocular_trauma || '', ocular_diseases: c.ocular_diseases || '',
      diabetes: c.diabetes || false, hypertension: c.hypertension || false,
      autoimmune_disease: c.autoimmune_disease || false, autoimmune_details: c.autoimmune_details || '',
      current_medications: c.current_medications || '', allergies: c.allergies || '',
      family_glaucoma: c.family_glaucoma || false, family_glaucoma_relationship: c.family_glaucoma_relationship || '',
      family_macular_degeneration: c.family_macular_degeneration || false, family_macular_relationship: c.family_macular_relationship || '',
      family_high_myopia: c.family_high_myopia || false, family_high_myopia_relationship: c.family_high_myopia_relationship || '',
      family_other_history: c.family_other_history || '',
      va_distance_without_rx_od: c.va_distance_without_rx_od || '', va_distance_without_rx_oi: c.va_distance_without_rx_oi || '',
      va_distance_with_rx_od: c.va_distance_with_rx_od || '', va_distance_with_rx_oi: c.va_distance_with_rx_oi || '',
      va_near_without_rx_od: c.va_near_without_rx_od || '', va_near_without_rx_oi: c.va_near_without_rx_oi || '',
      va_near_with_rx_od: c.va_near_with_rx_od || '', va_near_with_rx_oi: c.va_near_with_rx_oi || '',
      va_pinhole_od: c.va_pinhole_od || '', va_pinhole_oi: c.va_pinhole_oi || '',
      visual_acuity_method: c.visual_acuity_method || 'Snellen'
    });
    setPatientSearch(c.patient_name || '');
    setSelectedConsultation(c);
    setIsEditing(true);
    setView('form');
  };

  // Iter Agenda mejorada - agendar proxima cita al terminar consulta
  const [showNextApptDialog, setShowNextApptDialog] = useState(false);
  const [nextApptCtx, setNextApptCtx] = useState({ patient_id: null, professional_id: null, professional_name: null });

  const handleSave = async () => {
    if (!form.patient_id) return toast.error('Seleccione un paciente');
    if (!form.chief_complaint) return toast.error('Ingrese el motivo de consulta');

    try {
      if (isEditing && selectedConsultation) {
        await api.put(`/api/consultations/${selectedConsultation._id}`, {
          consultation_type: form.consultation_type,
          chief_complaint: form.chief_complaint, anamnesis: form.anamnesis,
          findings: form.findings, diagnosis: form.diagnosis,
          treatment_plan: form.treatment_plan, recommendations: form.recommendations,
          notes: form.notes,
          lensometry_od_sphere: form.lensometry_od_sphere, lensometry_od_cyl: form.lensometry_od_cyl, lensometry_od_axis: form.lensometry_od_axis, lensometry_od_add: form.lensometry_od_add,
          lensometry_oi_sphere: form.lensometry_oi_sphere, lensometry_oi_cyl: form.lensometry_oi_cyl, lensometry_oi_axis: form.lensometry_oi_axis, lensometry_oi_add: form.lensometry_oi_add,
          refractions: form.refractions
        });
        toast.success('Consulta actualizada');
        openDetail(selectedConsultation._id);
      } else {
        const res = await api.post('/api/consultations', form);
        toast.success('Consulta registrada');
        await openDetail(res.data._id);
        // Auto-abrir modal para agendar proxima cita
        setNextApptCtx({
          patient_id: res.data.patient_id || form.patient_id,
          professional_id: res.data.professional_id || null,
          professional_name: res.data.professional_name || user?.name || null,
        });
        setTimeout(() => setShowNextApptDialog(true), 300);
      }
      loadData();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  const openDetail = async (id) => {
    try {
      const { data } = await api.get(`/api/consultations/${id}`);
      setSelectedConsultation(data);
      setView('detail');
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  const handleCreateEyeglassRx = async () => {
    if (!selectedConsultation) return;
    try {
      await api.post('/api/prescriptions/eyeglass', {
        patient_id: selectedConsultation.patient_id,
        consultation_id: selectedConsultation._id,
        professional_name: selectedConsultation.professional_name || user?.name,
        ...eyeglassForm
      });
      toast.success('Receta de anteojos creada');
      setShowEyeglassRx(false);
      setEyeglassForm({ od_sphere: '', od_cylinder: '', od_axis: '', od_addition: '', od_dp: '', oi_sphere: '', oi_cylinder: '', oi_axis: '', oi_addition: '', oi_dp: '', lens_type: '', frame_type: '', observations: '' });
      openDetail(selectedConsultation._id);
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  const refractionToEyeglass = (r) => ({
    od_sphere: r?.od_sphere || '', od_cylinder: r?.od_cylinder || '', od_axis: r?.od_axis || '', od_addition: r?.od_addition || '', od_dp: '',
    oi_sphere: r?.os_sphere || '', oi_cylinder: r?.os_cylinder || '', oi_axis: r?.os_axis || '', oi_addition: r?.os_addition || '', oi_dp: '',
    lens_type: '', frame_type: '', observations: '',
  });
  const refractionToContact = (r) => ({
    od_power: r?.od_sphere || '', od_cylinder: r?.od_cylinder || '', od_axis: r?.od_axis || '', od_addition: r?.od_addition || '', od_dia: '', od_bc: '',
    oi_power: r?.os_sphere || '', oi_cylinder: r?.os_cylinder || '', oi_axis: r?.os_axis || '', oi_addition: r?.os_addition || '', oi_dia: '', oi_bc: '',
    brand: '', lens_type: '', replacement: '', observations: '',
  });
  const openEyeglassRxFromConsultation = () => {
    const refs = selectedConsultation?.refractions || [];
    setEyeglassForm(refractionToEyeglass(refs[0]));
    setShowEyeglassRx(true);
  };
  const openContactRxFromConsultation = () => {
    const refs = selectedConsultation?.refractions || [];
    setContactForm(refractionToContact(refs[0]));
    setShowContactRx(true);
  };
  const handleCreateContactRx = async () => {
    if (!selectedConsultation) return;
    try {
      await api.post('/api/prescriptions/contact', {
        patient_id: selectedConsultation.patient_id,
        consultation_id: selectedConsultation._id,
        professional_name: selectedConsultation.professional_name || user?.name,
        ...contactForm
      });
      toast.success('Receta de lentes de contacto creada');
      setShowContactRx(false);
      setContactForm(emptyContactForm);
      openDetail(selectedConsultation._id);
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };
  const addRefraction = () => setForm(f => ({ ...f, refractions: [...(f.refractions || []), { od_sphere: '', od_cylinder: '', od_axis: '', od_addition: '', os_sphere: '', os_cylinder: '', os_axis: '', os_addition: '', observations: '' }] }));
  const updateRefraction = (idx, field, value) => setForm(f => { const arr = [...(f.refractions || [])]; arr[idx] = { ...arr[idx], [field]: value }; return { ...f, refractions: arr }; });
  const removeRefraction = (idx) => setForm(f => ({ ...f, refractions: (f.refractions || []).filter((_, i) => i !== idx) }));

  const handleCreateMedicalRx = async () => {
    if (!selectedConsultation) return;
    try {
      await api.post('/api/prescriptions/medical', {
        patient_id: selectedConsultation.patient_id,
        consultation_id: selectedConsultation._id,
        professional_name: selectedConsultation.professional_name || user?.name,
        ...medicalForm
      });
      toast.success('Receta medica creada');
      setShowMedicalRx(false);
      setMedicalForm({ diagnosis: '', medications: [{ name: '', dosage: '', frequency: '', duration: '' }], instructions: '' });
      openDetail(selectedConsultation._id);
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  const addMedication = () => {
    setMedicalForm(f => ({ ...f, medications: [...f.medications, { _uid: crypto.randomUUID(), name: '', dosage: '', frequency: '', duration: '' }] }));
  };

  const updateMedication = (idx, field, value) => {
    const meds = [...medicalForm.medications];
    meds[idx][field] = value;
    setMedicalForm(f => ({ ...f, medications: meds }));
  };

  const removeMedication = (idx) => {
    setMedicalForm(f => ({ ...f, medications: f.medications.filter((_, i) => i !== idx) }));
  };

  const filteredConsultations = consultations.filter(c => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (c.patient_name || '').toLowerCase().includes(term) ||
           (c.chief_complaint || '').toLowerCase().includes(term) ||
           (c.diagnosis || '').toLowerCase().includes(term);
  });

  const filteredPatients = patients.filter(p =>
    `${p.first_name} ${p.last_name}`.toLowerCase().includes(patientSearch.toLowerCase()) ||
    (p.phone || '').includes(patientSearch)
  );
  const selectedPatient = patients.find(p => p._id === form.patient_id);

  // ===== LIST VIEW =====
  const ListView = () => (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Consultas</h1>
          <p className="text-slate-500 text-sm mt-1">Historial de consultas opticas</p>
        </div>
        <div className="flex items-center gap-3">
          <BranchFilter value={branchId} onChange={setBranchId} />
          <Button className="bg-pine-700 hover:bg-pine-800" onClick={() => openNewConsultation()} data-testid="new-consultation-btn">
            <Plus className="w-4 h-4 mr-2" /> Nueva Consulta
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="pt-4 pb-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input placeholder="Buscar por paciente, motivo o diagnostico..." value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)} className="pl-9" data-testid="consultation-search" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-8 text-center text-slate-500">Cargando...</div>
          ) : filteredConsultations.length === 0 ? (
            <div className="p-12 text-center">
              <Stethoscope className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500 font-medium">No hay consultas registradas</p>
              <p className="text-slate-400 text-sm mt-1">Crea tu primera consulta para empezar</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Fecha</TableHead>
                  <TableHead>Paciente</TableHead>
                  <TableHead>Tipo</TableHead>
                  <TableHead>Motivo</TableHead>
                  <TableHead>Diagnostico</TableHead>
                  <TableHead>Profesional</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredConsultations.map((c) => (
                  <TableRow key={c._id} className="hover:bg-slate-50" data-testid={`consultation-row-${c._id}`}>
                    <TableCell className="text-sm font-medium">{formatDate(c.consultation_date)}</TableCell>
                    <TableCell className="font-medium text-sm">{c.patient_name || '-'}</TableCell>
                    <TableCell>
                      <span className="px-2 py-0.5 bg-pine-50 text-pine-700 text-xs rounded-full font-medium">
                        {CONSULTATION_TYPE_LABELS[c.consultation_type] || c.consultation_type}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm text-slate-600 max-w-[200px] truncate">{c.chief_complaint}</TableCell>
                    <TableCell className="text-sm text-slate-600 max-w-[200px] truncate">{c.diagnosis || '-'}</TableCell>
                    <TableCell className="text-sm text-slate-500">{c.professional_name || '-'}</TableCell>
                    <TableCell>
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => openDetail(c._id)} data-testid={`view-consultation-${c._id}`}>
                          <Eye className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => openEditConsultation(c)} data-testid={`edit-consultation-${c._id}`}>
                          <Pencil className="w-4 h-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );

  // ===== FORM VIEW =====
  const FormView = () => (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => { setView('list'); resetForm(); }} data-testid="back-to-list">
          <ArrowLeft className="w-4 h-4 mr-1" /> Volver
        </Button>
        <h1 className="text-xl font-bold text-slate-900">{isEditing ? 'Editar Consulta' : 'Nueva Consulta'}</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left - Patient & General */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-sm text-slate-500">Datos Generales</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {!isEditing && (
                <div className="space-y-2">
                  <Label>Paciente *</Label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <Input placeholder="Buscar paciente..." value={patientSearch}
                      onChange={(e) => { setPatientSearch(e.target.value); if(form.patient_id) setForm(f => ({...f, patient_id: ''})); }}
                      className="pl-9" data-testid="form-patient-search" />
                  </div>
                  {patientSearch && !form.patient_id && (
                    <div className="border rounded-lg max-h-32 overflow-y-auto">
                      {filteredPatients.slice(0, 5).map(p => (
                        <button key={p._id} className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50 flex justify-between"
                          onClick={() => { setForm(f => ({ ...f, patient_id: p._id })); setPatientSearch(`${p.first_name} ${p.last_name}`); }}>
                          <span className="font-medium">{p.first_name} {p.last_name}</span>
                          <span className="text-slate-400">{p.phone}</span>
                        </button>
                      ))}
                    </div>
                  )}
                  {selectedPatient && form.patient_id && (
                    <div className="p-2 bg-pine-50 rounded-lg text-sm text-pine-800 font-medium">
                      {selectedPatient.first_name} {selectedPatient.last_name}
                    </div>
                  )}
                </div>
              )}
              {isEditing && (
                <div className="p-2 bg-slate-50 rounded-lg text-sm font-medium">{patientSearch}</div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">Fecha *</Label>
                  <Input type="date" value={form.consultation_date}
                    onChange={(e) => setForm(f => ({ ...f, consultation_date: e.target.value }))}
                    data-testid="form-date" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Hora</Label>
                  <Input type="time" value={form.consultation_time}
                    onChange={(e) => setForm(f => ({ ...f, consultation_time: e.target.value }))}
                    data-testid="form-time" />
                </div>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Tipo de Consulta</Label>
                <Select value={form.consultation_type} onValueChange={(v) => setForm(f => ({ ...f, consultation_type: v }))}>
                  <SelectTrigger data-testid="form-type"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {CONSULTATION_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Center & Right - Clinical Data */}
        <div className="lg:col-span-2 space-y-4">
          {/* I. Motivo de Consulta */}
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-sm text-slate-500">I. Motivo de Consulta</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Motivo de Consulta *</Label>
                <Textarea value={form.chief_complaint} rows={2}
                  onChange={(e) => setForm(f => ({ ...f, chief_complaint: e.target.value }))}
                  placeholder="Describir sintomas principales, duracion y factores asociados" data-testid="form-chief-complaint" />
              </div>
            </CardContent>
          </Card>

          {/* II. Historia Clinica */}
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-sm text-slate-500">II. Historia Clinica</CardTitle></CardHeader>
            <CardContent className="space-y-5">
              {/* A. Antecedentes Oculares */}
              <div>
                <p className="text-xs font-semibold text-pine-700 uppercase tracking-wide mb-3">A. Antecedentes Oculares Personales</p>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Checkbox id="wears_glasses" checked={form.wears_glasses}
                        onCheckedChange={(v) => setForm(f => ({ ...f, wears_glasses: !!v }))} data-testid="form-wears-glasses" />
                      <Label htmlFor="wears_glasses" className="text-sm cursor-pointer">Usa lentes</Label>
                    </div>
                    {form.wears_glasses && (
                      <div className="space-y-2 pl-6">
                        <Input placeholder="Desde cuando" value={form.glasses_since}
                          onChange={(e) => setForm(f => ({ ...f, glasses_since: e.target.value }))} className="h-8 text-sm" />
                        <Input placeholder="Tipo de lentes" value={form.glasses_type}
                          onChange={(e) => setForm(f => ({ ...f, glasses_type: e.target.value }))} className="h-8 text-sm" />
                      </div>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Cirugias oculares</Label>
                    <Input value={form.ocular_surgeries} placeholder="Ninguna"
                      onChange={(e) => setForm(f => ({ ...f, ocular_surgeries: e.target.value }))} className="h-8 text-sm" />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Traumatismos</Label>
                    <Input value={form.ocular_trauma} placeholder="Ninguno"
                      onChange={(e) => setForm(f => ({ ...f, ocular_trauma: e.target.value }))} className="h-8 text-sm" />
                  </div>
                </div>
                <div className="mt-3">
                  <Label className="text-xs">Enfermedades oculares</Label>
                  <Input value={form.ocular_diseases} placeholder="Ninguna"
                    onChange={(e) => setForm(f => ({ ...f, ocular_diseases: e.target.value }))} className="h-8 text-sm mt-1" />
                </div>
              </div>

              {/* B. Antecedentes Sistemicos */}
              <div className="pt-3 border-t">
                <p className="text-xs font-semibold text-pine-700 uppercase tracking-wide mb-3">B. Antecedentes Sistemicos</p>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-3">
                  <div className="flex items-center gap-2">
                    <Checkbox id="diabetes" checked={form.diabetes}
                      onCheckedChange={(v) => setForm(f => ({ ...f, diabetes: !!v }))} data-testid="form-diabetes" />
                    <Label htmlFor="diabetes" className="text-sm cursor-pointer">Diabetes</Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox id="hypertension" checked={form.hypertension}
                      onCheckedChange={(v) => setForm(f => ({ ...f, hypertension: !!v }))} data-testid="form-hypertension" />
                    <Label htmlFor="hypertension" className="text-sm cursor-pointer">Hipertension</Label>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Checkbox id="autoimmune" checked={form.autoimmune_disease}
                        onCheckedChange={(v) => setForm(f => ({ ...f, autoimmune_disease: !!v }))} />
                      <Label htmlFor="autoimmune" className="text-sm cursor-pointer">Enfermedad autoinmune</Label>
                    </div>
                    {form.autoimmune_disease && (
                      <Input placeholder="Cual" value={form.autoimmune_details} className="h-8 text-sm pl-6"
                        onChange={(e) => setForm(f => ({ ...f, autoimmune_details: e.target.value }))} />
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 mt-3">
                  <div className="space-y-1">
                    <Label className="text-xs">Medicamentos actuales</Label>
                    <Input value={form.current_medications} placeholder="Ninguno"
                      onChange={(e) => setForm(f => ({ ...f, current_medications: e.target.value }))} className="h-8 text-sm" />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Alergias</Label>
                    <Input value={form.allergies} placeholder="Ninguna"
                      onChange={(e) => setForm(f => ({ ...f, allergies: e.target.value }))} className="h-8 text-sm" />
                  </div>
                </div>
              </div>

              {/* C. Antecedentes Familiares */}
              <div className="pt-3 border-t">
                <p className="text-xs font-semibold text-pine-700 uppercase tracking-wide mb-3">C. Antecedentes Familiares Oculares</p>
                <div className="space-y-3">
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                      <Checkbox id="fam_glaucoma" checked={form.family_glaucoma}
                        onCheckedChange={(v) => setForm(f => ({ ...f, family_glaucoma: !!v }))} />
                      <Label htmlFor="fam_glaucoma" className="text-sm cursor-pointer">Glaucoma</Label>
                    </div>
                    {form.family_glaucoma && (
                      <Input placeholder="Parentesco" value={form.family_glaucoma_relationship} className="h-8 text-sm w-40"
                        onChange={(e) => setForm(f => ({ ...f, family_glaucoma_relationship: e.target.value }))} />
                    )}
                  </div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                      <Checkbox id="fam_macular" checked={form.family_macular_degeneration}
                        onCheckedChange={(v) => setForm(f => ({ ...f, family_macular_degeneration: !!v }))} />
                      <Label htmlFor="fam_macular" className="text-sm cursor-pointer">Degeneracion macular</Label>
                    </div>
                    {form.family_macular_degeneration && (
                      <Input placeholder="Parentesco" value={form.family_macular_relationship} className="h-8 text-sm w-40"
                        onChange={(e) => setForm(f => ({ ...f, family_macular_relationship: e.target.value }))} />
                    )}
                  </div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                      <Checkbox id="fam_myopia" checked={form.family_high_myopia}
                        onCheckedChange={(v) => setForm(f => ({ ...f, family_high_myopia: !!v }))} />
                      <Label htmlFor="fam_myopia" className="text-sm cursor-pointer">Miopia alta</Label>
                    </div>
                    {form.family_high_myopia && (
                      <Input placeholder="Parentesco" value={form.family_high_myopia_relationship} className="h-8 text-sm w-40"
                        onChange={(e) => setForm(f => ({ ...f, family_high_myopia_relationship: e.target.value }))} />
                    )}
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Otros antecedentes familiares</Label>
                    <Input value={form.family_other_history} placeholder="Ninguno"
                      onChange={(e) => setForm(f => ({ ...f, family_other_history: e.target.value }))} className="h-8 text-sm" />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* III. Agudeza Visual */}
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-sm text-slate-500">III. Agudeza Visual</CardTitle></CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="va-table">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 pr-4 text-xs font-semibold text-slate-500 uppercase w-1/2">Agudeza Visual</th>
                      <th className="text-center py-2 px-2 text-xs font-semibold text-blue-700 uppercase w-1/4">OD</th>
                      <th className="text-center py-2 px-2 text-xs font-semibold text-green-700 uppercase w-1/4">OS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { label: 'AV Lejos sin Rx', od: 'va_distance_without_rx_od', oi: 'va_distance_without_rx_oi' },
                      { label: 'AV Lejos con Rx', od: 'va_distance_with_rx_od', oi: 'va_distance_with_rx_oi' },
                      { label: 'AV Cerca sin Rx', od: 'va_near_without_rx_od', oi: 'va_near_without_rx_oi' },
                      { label: 'AV Cerca con Rx', od: 'va_near_with_rx_od', oi: 'va_near_with_rx_oi' },
                      { label: 'AV con Estenopeico', od: 'va_pinhole_od', oi: 'va_pinhole_oi' },
                    ].map((row) => (
                      <tr key={row.od} className="border-b last:border-0">
                        <td className="py-2 pr-4 text-slate-700 font-medium">{row.label}</td>
                        <td className="py-2 px-1">
                          <Input className="h-8 text-sm text-center" value={form[row.od]}
                            onChange={(e) => setForm(f => ({ ...f, [row.od]: e.target.value }))}
                            placeholder="20/20" data-testid={`form-${row.od}`} />
                        </td>
                        <td className="py-2 px-1">
                          <Input className="h-8 text-sm text-center" value={form[row.oi]}
                            onChange={(e) => setForm(f => ({ ...f, [row.oi]: e.target.value }))}
                            placeholder="20/20" data-testid={`form-${row.oi}`} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-3 space-y-1">
                <Label className="text-xs">Metodo utilizado</Label>
                <Select value={form.visual_acuity_method} onValueChange={(v) => setForm(f => ({ ...f, visual_acuity_method: v }))}>
                  <SelectTrigger className="w-48" data-testid="form-va-method"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Snellen">Snellen</SelectItem>
                    <SelectItem value="logMAR">logMAR</SelectItem>
                    <SelectItem value="ETDRS">ETDRS</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* IV. Lensometria */}
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-sm text-slate-500">IV. Lensometria</CardTitle></CardHeader>
            <CardContent>
              <p className="text-xs text-slate-400 mb-3">Graduacion actual de los lentes del paciente (opcional).</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="lensometry-table">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 pr-4 text-xs font-semibold text-slate-500 uppercase">Ojo</th>
                      <th className="text-center py-2 px-2 text-xs font-semibold text-slate-500 uppercase">Esfera</th>
                      <th className="text-center py-2 px-2 text-xs font-semibold text-slate-500 uppercase">Cilindro</th>
                      <th className="text-center py-2 px-2 text-xs font-semibold text-slate-500 uppercase">Eje</th>
                      <th className="text-center py-2 px-2 text-xs font-semibold text-slate-500 uppercase">ADD</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { eye: 'OD', color: 'text-blue-700', sphere: 'lensometry_od_sphere', cyl: 'lensometry_od_cyl', axis: 'lensometry_od_axis', add: 'lensometry_od_add' },
                      { eye: 'OS', color: 'text-green-700', sphere: 'lensometry_oi_sphere', cyl: 'lensometry_oi_cyl', axis: 'lensometry_oi_axis', add: 'lensometry_oi_add' },
                    ].map((row) => (
                      <tr key={row.eye} className="border-b last:border-0">
                        <td className={`py-2 pr-4 font-bold ${row.color}`}>{row.eye}</td>
                        {['sphere', 'cyl', 'axis', 'add'].map((col) => (
                          <td key={col} className="py-2 px-1">
                            <Input className="h-8 text-sm text-center" value={form[row[col]]}
                              onChange={(e) => setForm(f => ({ ...f, [row[col]]: e.target.value }))}
                              placeholder={col === 'axis' ? '0' : (col === 'add' ? '+0.00' : '0.00')}
                              data-testid={`form-${row[col]}`} />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* V. Hallazgos, Diagnostico, Plan */}
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-sm text-slate-500">V. Hallazgos y Plan</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Historia / Anamnesis</Label>
                <Textarea value={form.anamnesis} rows={2}
                  onChange={(e) => setForm(f => ({ ...f, anamnesis: e.target.value }))}
                  placeholder="Antecedentes, sintomas previos, uso actual de lentes..." data-testid="form-anamnesis" />
              </div>
              <div className="space-y-2">
                <Label>Hallazgos</Label>
                <Textarea value={form.findings} rows={2}
                  onChange={(e) => setForm(f => ({ ...f, findings: e.target.value }))}
                  placeholder="Resultados del examen visual, agudeza visual, biomicroscopia..." data-testid="form-findings" />
              </div>
              <div className="space-y-2 border-t border-slate-100 pt-4">
                <div className="flex items-center justify-between">
                  <Label>Refraccion Actual</Label>
                  <Button type="button" variant="outline" size="sm" onClick={addRefraction} data-testid="add-refraction-btn">
                    <Plus className="w-3.5 h-3.5 mr-1" /> Agregar refraccion
                  </Button>
                </div>
                {(form.refractions || []).length === 0 && (
                  <p className="text-xs text-slate-400 italic">Sin refracciones. Agrega una para registrar la graduacion del paciente.</p>
                )}
                {(form.refractions || []).map((r, idx) => (
                  <div key={idx} className="border border-slate-200 rounded-lg p-3 space-y-2" data-testid={`refraction-${idx}`}>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-slate-500">Refraccion {idx + 1}</span>
                      <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-red-600 hover:bg-red-50" onClick={() => removeRefraction(idx)} data-testid={`remove-refraction-${idx}`}>
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                    <div className="grid grid-cols-5 gap-2 text-[10px] uppercase text-slate-400">
                      <span></span><span>Esfera</span><span>Cilindro</span><span>Eje</span><span>Adicion</span>
                    </div>
                    <div className="grid grid-cols-5 gap-2 items-center">
                      <span className="text-xs font-bold text-blue-700">OD</span>
                      <Input className="h-8 text-sm" value={r.od_sphere} onChange={(e) => updateRefraction(idx, 'od_sphere', e.target.value)} data-testid={`refraction-${idx}-od-sphere`} />
                      <Input className="h-8 text-sm" value={r.od_cylinder} onChange={(e) => updateRefraction(idx, 'od_cylinder', e.target.value)} />
                      <Input className="h-8 text-sm" value={r.od_axis} onChange={(e) => updateRefraction(idx, 'od_axis', e.target.value)} />
                      <Input className="h-8 text-sm" value={r.od_addition} onChange={(e) => updateRefraction(idx, 'od_addition', e.target.value)} />
                    </div>
                    <div className="grid grid-cols-5 gap-2 items-center">
                      <span className="text-xs font-bold text-green-700">OS</span>
                      <Input className="h-8 text-sm" value={r.os_sphere} onChange={(e) => updateRefraction(idx, 'os_sphere', e.target.value)} data-testid={`refraction-${idx}-os-sphere`} />
                      <Input className="h-8 text-sm" value={r.os_cylinder} onChange={(e) => updateRefraction(idx, 'os_cylinder', e.target.value)} />
                      <Input className="h-8 text-sm" value={r.os_axis} onChange={(e) => updateRefraction(idx, 'os_axis', e.target.value)} />
                      <Input className="h-8 text-sm" value={r.os_addition} onChange={(e) => updateRefraction(idx, 'os_addition', e.target.value)} />
                    </div>
                    <Textarea value={r.observations} rows={1} onChange={(e) => updateRefraction(idx, 'observations', e.target.value)} placeholder="Observaciones de esta refraccion..." data-testid={`refraction-${idx}-observations`} />
                  </div>
                ))}
              </div>
              <div className="space-y-2">
                <Label>Diagnostico / Impresion Clinica</Label>
                <Textarea value={form.diagnosis} rows={2}
                  onChange={(e) => setForm(f => ({ ...f, diagnosis: e.target.value }))}
                  placeholder="Diagnostico o impresion clinica..." data-testid="form-diagnosis" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Plan / Tratamiento</Label>
                  <Textarea value={form.treatment_plan} rows={2}
                    onChange={(e) => setForm(f => ({ ...f, treatment_plan: e.target.value }))}
                    placeholder="Plan de tratamiento, prescripcion optica..." data-testid="form-treatment-plan" />
                </div>
                <div className="space-y-2">
                  <Label>Recomendaciones</Label>
                  <Textarea value={form.recommendations} rows={2}
                    onChange={(e) => setForm(f => ({ ...f, recommendations: e.target.value }))}
                    placeholder="Recomendaciones al paciente..." data-testid="form-recommendations" />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Observaciones</Label>
                <Textarea value={form.notes} rows={2}
                  onChange={(e) => setForm(f => ({ ...f, notes: e.target.value }))}
                  placeholder="Notas adicionales..." data-testid="form-notes" />
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setView('list'); resetForm(); }}>Cancelar</Button>
            <Button className="bg-pine-700 hover:bg-pine-800" onClick={handleSave}
              disabled={!form.patient_id || !form.chief_complaint} data-testid="save-consultation-btn">
              <Save className="w-4 h-4 mr-2" /> {isEditing ? 'Actualizar' : 'Guardar Consulta'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );

  // ===== DETAIL VIEW =====
  const DetailView = () => {
    if (!selectedConsultation) return null;
    const c = selectedConsultation;
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => setView('list')} data-testid="detail-back">
              <ArrowLeft className="w-4 h-4 mr-1" /> Volver
            </Button>
            <h1 className="text-xl font-bold text-slate-900">Consulta del {formatDate(c.consultation_date)}</h1>
            <span className="px-2 py-0.5 bg-pine-50 text-pine-700 text-xs rounded-full font-medium">
              {CONSULTATION_TYPE_LABELS[c.consultation_type] || c.consultation_type}
            </span>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => openEditConsultation(c)} data-testid="detail-edit-btn">
              <Pencil className="w-4 h-4 mr-1" /> Editar
            </Button>
            <Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={openEyeglassRxFromConsultation} data-testid="gen-eyeglass-rx-btn">
              <FileText className="w-4 h-4 mr-1" /> Receta Anteojos
            </Button>
            <Button size="sm" className="bg-teal-600 hover:bg-teal-700" onClick={openContactRxFromConsultation} data-testid="gen-contact-rx-btn">
              <Eye className="w-4 h-4 mr-1" /> Receta Lentes de Contacto
            </Button>
            <Button size="sm" className="bg-purple-600 hover:bg-purple-700" onClick={() => {
              setMedicalForm({ diagnosis: c.diagnosis || '', medications: [{ name: '', dosage: '', frequency: '', duration: '' }], instructions: '' });
              setShowMedicalRx(true);
            }} data-testid="gen-medical-rx-btn">
              <Pill className="w-4 h-4 mr-1" /> Receta Medica
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Patient summary */}
          <Card>
            <CardContent className="pt-4 space-y-3">
              <div className="flex items-center gap-3 pb-3 border-b">
                <div className="w-10 h-10 rounded-full bg-pine-100 flex items-center justify-center text-pine-700 font-bold">
                  {c.patient_name?.split(' ').map(n => n[0]).join('').slice(0, 2)}
                </div>
                <div>
                  <p className="font-semibold text-sm">{c.patient_name}</p>
                  <p className="text-xs text-slate-400">{c.patient_phone}</p>
                </div>
              </div>
              <div className="text-sm space-y-2">
                <div className="flex items-center gap-2 text-slate-500"><CalendarIcon className="w-3.5 h-3.5" /> {formatDate(c.consultation_date)} {c.consultation_time}</div>
                <div className="flex items-center gap-2 text-slate-500"><User className="w-3.5 h-3.5" /> {c.professional_name || 'Sin profesional'}</div>
              </div>
              {/* Linked prescriptions */}
              {((c.eyeglass_prescriptions?.length || 0) + (c.medical_prescriptions?.length || 0) + (c.contact_prescriptions?.length || 0)) > 0 && (
                <div className="pt-3 border-t">
                  <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Recetas Generadas</p>
                  {(c.eyeglass_prescriptions || []).map((rx) => (
                    <div key={rx._id} className="flex items-center gap-2 text-sm py-1">
                      <FileText className="w-3.5 h-3.5 text-blue-500" />
                      <span>Anteojos ({formatDate(rx.created_at)})</span>
                    </div>
                  ))}
                  {(c.contact_prescriptions || []).map((rx) => (
                    <div key={rx._id} className="flex items-center gap-2 text-sm py-1">
                      <FileText className="w-3.5 h-3.5 text-teal-500" />
                      <span>Lentes de contacto ({formatDate(rx.created_at)})</span>
                    </div>
                  ))}
                  {(c.medical_prescriptions || []).map((rx) => (
                    <div key={rx._id} className="flex items-center gap-2 text-sm py-1">
                      <Pill className="w-3.5 h-3.5 text-purple-500" />
                      <span>Medica ({formatDate(rx.created_at)})</span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Clinical data */}
          <div className="lg:col-span-2 space-y-4">
            {/* I. Motivo */}
            {c.chief_complaint && (
              <Card>
                <CardContent className="pt-4">
                  <Section title="I. Motivo de Consulta" text={c.chief_complaint} />
                </CardContent>
              </Card>
            )}

            {/* II. Historia Clinica */}
            {(c.wears_glasses || c.diabetes || c.hypertension || c.autoimmune_disease || c.ocular_surgeries || c.ocular_diseases || c.family_glaucoma || c.family_macular_degeneration || c.family_high_myopia || c.current_medications || c.allergies) && (
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm text-slate-500">II. Historia Clinica</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                  {/* Oculares */}
                  {(c.wears_glasses || c.ocular_surgeries || c.ocular_trauma || c.ocular_diseases) && (
                    <div>
                      <p className="text-xs font-semibold text-pine-700 uppercase tracking-wide mb-2">A. Antecedentes Oculares</p>
                      <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
                        {c.wears_glasses && <div><span className="text-slate-500">Usa lentes:</span> <span className="font-medium">Si{c.glasses_since ? `, desde ${c.glasses_since}` : ''}{c.glasses_type ? ` (${c.glasses_type})` : ''}</span></div>}
                        {c.wears_glasses && (c.lensometry_od || c.lensometry_oi) && <div><span className="text-slate-500">Lensometria:</span> <span className="text-blue-700 font-medium">OD {c.lensometry_od || '-'}</span> · <span className="text-green-700 font-medium">OS {c.lensometry_oi || '-'}</span></div>}
                        {c.ocular_surgeries && <div><span className="text-slate-500">Cirugias:</span> <span className="font-medium">{c.ocular_surgeries}</span></div>}
                        {c.ocular_trauma && <div><span className="text-slate-500">Traumatismos:</span> <span className="font-medium">{c.ocular_trauma}</span></div>}
                        {c.ocular_diseases && <div><span className="text-slate-500">Enfermedades:</span> <span className="font-medium">{c.ocular_diseases}</span></div>}
                      </div>
                    </div>
                  )}
                  {/* Sistemicos */}
                  {(c.diabetes || c.hypertension || c.autoimmune_disease || c.current_medications || c.allergies) && (
                    <div className="pt-3 border-t">
                      <p className="text-xs font-semibold text-pine-700 uppercase tracking-wide mb-2">B. Antecedentes Sistemicos</p>
                      <div className="flex flex-wrap gap-2 mb-2">
                        {c.diabetes && <span className="px-2 py-0.5 bg-amber-50 text-amber-800 rounded text-xs font-medium">Diabetes</span>}
                        {c.hypertension && <span className="px-2 py-0.5 bg-red-50 text-red-800 rounded text-xs font-medium">Hipertension</span>}
                        {c.autoimmune_disease && <span className="px-2 py-0.5 bg-purple-50 text-purple-800 rounded text-xs font-medium">Autoinmune: {c.autoimmune_details || 'Si'}</span>}
                      </div>
                      <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
                        {c.current_medications && <div><span className="text-slate-500">Medicamentos:</span> <span className="font-medium">{c.current_medications}</span></div>}
                        {c.allergies && <div><span className="text-slate-500">Alergias:</span> <span className="font-medium">{c.allergies}</span></div>}
                      </div>
                    </div>
                  )}
                  {/* Familiares */}
                  {(c.family_glaucoma || c.family_macular_degeneration || c.family_high_myopia || c.family_other_history) && (
                    <div className="pt-3 border-t">
                      <p className="text-xs font-semibold text-pine-700 uppercase tracking-wide mb-2">C. Antecedentes Familiares</p>
                      <div className="flex flex-wrap gap-2">
                        {c.family_glaucoma && <span className="px-2 py-0.5 bg-blue-50 text-blue-800 rounded text-xs font-medium">Glaucoma{c.family_glaucoma_relationship ? ` (${c.family_glaucoma_relationship})` : ''}</span>}
                        {c.family_macular_degeneration && <span className="px-2 py-0.5 bg-blue-50 text-blue-800 rounded text-xs font-medium">Deg. Macular{c.family_macular_relationship ? ` (${c.family_macular_relationship})` : ''}</span>}
                        {c.family_high_myopia && <span className="px-2 py-0.5 bg-blue-50 text-blue-800 rounded text-xs font-medium">Miopia Alta{c.family_high_myopia_relationship ? ` (${c.family_high_myopia_relationship})` : ''}</span>}
                      </div>
                      {c.family_other_history && <p className="text-sm text-slate-600 mt-2">Otros: {c.family_other_history}</p>}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* III. Agudeza Visual */}
            {(c.va_distance_without_rx_od || c.va_distance_without_rx_oi || c.va_distance_with_rx_od || c.va_near_without_rx_od || c.va_pinhole_od) && (
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm text-slate-500">III. Agudeza Visual {c.visual_acuity_method ? `(${c.visual_acuity_method})` : ''}</CardTitle></CardHeader>
                <CardContent>
                  <table className="w-full text-sm" data-testid="detail-va-table">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-2 pr-4 text-xs font-semibold text-slate-500 uppercase">Medicion</th>
                        <th className="text-center py-2 px-4 text-xs font-semibold text-blue-700 uppercase">OD</th>
                        <th className="text-center py-2 px-4 text-xs font-semibold text-green-700 uppercase">OS</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { label: 'AV Lejos sin Rx', od: c.va_distance_without_rx_od, oi: c.va_distance_without_rx_oi },
                        { label: 'AV Lejos con Rx', od: c.va_distance_with_rx_od, oi: c.va_distance_with_rx_oi },
                        { label: 'AV Cerca sin Rx', od: c.va_near_without_rx_od, oi: c.va_near_without_rx_oi },
                        { label: 'AV Cerca con Rx', od: c.va_near_with_rx_od, oi: c.va_near_with_rx_oi },
                        { label: 'AV con Estenopeico', od: c.va_pinhole_od, oi: c.va_pinhole_oi },
                      ].filter(r => r.od || r.oi).map((r) => (
                        <tr key={r.label} className="border-b last:border-0">
                          <td className="py-2 pr-4 text-slate-700 font-medium">{r.label}</td>
                          <td className="py-2 px-4 text-center font-mono">{r.od || '-'}</td>
                          <td className="py-2 px-4 text-center font-mono">{r.oi || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            )}

            {/* IV. Lensometria */}
            {(c.lensometry_od_sphere || c.lensometry_od_cyl || c.lensometry_od_axis || c.lensometry_od_add || c.lensometry_oi_sphere || c.lensometry_oi_cyl || c.lensometry_oi_axis || c.lensometry_oi_add) && (
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm text-slate-500">IV. Lensometria</CardTitle></CardHeader>
                <CardContent>
                  <table className="w-full text-sm" data-testid="detail-lensometry-table">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-2 pr-4 text-xs font-semibold text-slate-500 uppercase">Ojo</th>
                        <th className="text-center py-2 px-4 text-xs font-semibold text-slate-500 uppercase">Esfera</th>
                        <th className="text-center py-2 px-4 text-xs font-semibold text-slate-500 uppercase">Cilindro</th>
                        <th className="text-center py-2 px-4 text-xs font-semibold text-slate-500 uppercase">Eje</th>
                        <th className="text-center py-2 px-4 text-xs font-semibold text-slate-500 uppercase">ADD</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { eye: 'OD', color: 'text-blue-700', s: c.lensometry_od_sphere, cy: c.lensometry_od_cyl, ax: c.lensometry_od_axis, ad: c.lensometry_od_add },
                        { eye: 'OS', color: 'text-green-700', s: c.lensometry_oi_sphere, cy: c.lensometry_oi_cyl, ax: c.lensometry_oi_axis, ad: c.lensometry_oi_add },
                      ].map((r) => (
                        <tr key={r.eye} className="border-b last:border-0">
                          <td className={`py-2 pr-4 font-bold ${r.color}`}>{r.eye}</td>
                          <td className="py-2 px-4 text-center font-mono">{r.s || '-'}</td>
                          <td className="py-2 px-4 text-center font-mono">{r.cy || '-'}</td>
                          <td className="py-2 px-4 text-center font-mono">{r.ax || '-'}</td>
                          <td className="py-2 px-4 text-center font-mono">{r.ad || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            )}

            {/* V. Hallazgos y Plan */}
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-sm text-slate-500">V. Hallazgos y Plan</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                {c.anamnesis && <Section title="Historia / Anamnesis" text={c.anamnesis} />}
                {c.findings && <Section title="Hallazgos" text={c.findings} />}
                {Array.isArray(c.refractions) && c.refractions.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase mb-1">Refraccion Actual</p>
                    <div className="space-y-2">
                      {c.refractions.map((r, i) => (
                        <div key={i} className="border border-slate-200 rounded-lg p-2 text-sm">
                          <p className="text-[11px] text-slate-400 mb-1">Refraccion {i + 1}</p>
                          <p className="text-blue-700"><span className="font-bold">OD</span> · Esf {r.od_sphere || '-'} · Cil {r.od_cylinder || '-'} · Eje {r.od_axis || '-'} · Add {r.od_addition || '-'}</p>
                          <p className="text-green-700"><span className="font-bold">OS</span> · Esf {r.os_sphere || '-'} · Cil {r.os_cylinder || '-'} · Eje {r.os_axis || '-'} · Add {r.os_addition || '-'}</p>
                          {r.observations && <p className="text-slate-500 text-xs mt-1">Obs: {r.observations}</p>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {c.diagnosis && <Section title="Diagnostico / Impresion Clinica" text={c.diagnosis} highlight />}
                {c.treatment_plan && <Section title="Plan / Tratamiento" text={c.treatment_plan} />}
                {c.recommendations && <Section title="Recomendaciones" text={c.recommendations} />}
                {c.notes && <Section title="Observaciones" text={c.notes} />}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  };

  const Section = ({ title, text, highlight = false }) => (
    <div>
      <p className="text-xs font-semibold text-slate-400 uppercase mb-1">{title}</p>
      <p className={`text-sm whitespace-pre-wrap ${highlight ? 'font-medium text-pine-800 bg-pine-50/50 p-2 rounded' : 'text-slate-700'}`}>{text}</p>
    </div>
  );

  return (
    <div data-testid="consultations-page">
      {view === 'list' && ListView()}
      {view === 'form' && FormView()}
      {view === 'detail' && DetailView()}

      {/* ===== EYEGLASS RX DIALOG ===== */}
      <EyeglassRxDialog
        open={showEyeglassRx}
        onOpenChange={setShowEyeglassRx}
        form={eyeglassForm}
        setForm={setEyeglassForm}
        onSubmit={handleCreateEyeglassRx}
        testIdPrefix=""
        refractions={selectedConsultation?.refractions || []}
      />
      <ContactRxDialog
        open={showContactRx}
        onOpenChange={setShowContactRx}
        form={contactForm}
        setForm={setContactForm}
        onSubmit={handleCreateContactRx}
        refractions={selectedConsultation?.refractions || []}
      />
      <MedicalRxDialog
        open={showMedicalRx}
        onOpenChange={setShowMedicalRx}
        form={medicalForm}
        setForm={setMedicalForm}
        onSubmit={handleCreateMedicalRx}
        addMedication={addMedication}
        updateMedication={updateMedication}
        removeMedication={removeMedication}
        testIdPrefix=""
      />

      {/* Modal: Agendar proxima cita al terminar consulta */}
      <NextAppointmentDialog
        open={showNextApptDialog}
        onOpenChange={setShowNextApptDialog}
        patientId={nextApptCtx.patient_id}
        professionalId={nextApptCtx.professional_id}
        professionalName={nextApptCtx.professional_name}
      />
    </div>
  );
}
