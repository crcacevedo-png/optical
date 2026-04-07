import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail, useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Textarea } from '../components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { BranchFilter } from '../components/BranchFilter';
import {
  Plus, Search, Eye, Pencil, Stethoscope, FileText, Pill,
  Clock, User, CalendarIcon, ChevronRight, Save, ArrowLeft
} from 'lucide-react';
import { toast } from 'sonner';

const CONSULTATION_TYPES = [
  { value: 'general', label: 'Consulta General' },
  { value: 'control', label: 'Control' },
  { value: 'urgencia', label: 'Urgencia' },
  { value: 'primera_vez', label: 'Primera Vez' },
  { value: 'seguimiento', label: 'Seguimiento' },
];

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
  const [form, setForm] = useState({
    patient_id: '', consultation_date: new Date().toISOString().slice(0, 10),
    consultation_time: new Date().toTimeString().slice(0, 5),
    consultation_type: 'general', chief_complaint: '', anamnesis: '',
    findings: '', diagnosis: '', treatment_plan: '', recommendations: '', notes: ''
  });
  const [patientSearch, setPatientSearch] = useState('');

  // Eyeglass Rx from consultation
  const [showEyeglassRx, setShowEyeglassRx] = useState(false);
  const [eyeglassForm, setEyeglassForm] = useState({
    od_sphere: '', od_cylinder: '', od_axis: '', od_addition: '', od_dp: '',
    oi_sphere: '', oi_cylinder: '', oi_axis: '', oi_addition: '', oi_dp: '',
    lens_type: '', frame_type: '', observations: ''
  });

  // Medical Rx from consultation
  const [showMedicalRx, setShowMedicalRx] = useState(false);
  const [medicalForm, setMedicalForm] = useState({
    diagnosis: '', medications: [{ name: '', dosage: '', frequency: '', duration: '' }], instructions: ''
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
      consultation_type: 'general', chief_complaint: '', anamnesis: '',
      findings: '', diagnosis: '', treatment_plan: '', recommendations: '', notes: ''
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
      consultation_type: c.consultation_type || 'general',
      chief_complaint: c.chief_complaint || '', anamnesis: c.anamnesis || '',
      findings: c.findings || '', diagnosis: c.diagnosis || '',
      treatment_plan: c.treatment_plan || '', recommendations: c.recommendations || '',
      notes: c.notes || ''
    });
    setPatientSearch(c.patient_name || '');
    setSelectedConsultation(c);
    setIsEditing(true);
    setView('form');
  };

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
          notes: form.notes
        });
        toast.success('Consulta actualizada');
        openDetail(selectedConsultation._id);
      } else {
        const res = await api.post('/api/consultations', form);
        toast.success('Consulta registrada');
        openDetail(res.data._id);
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
    setMedicalForm(f => ({ ...f, medications: [...f.medications, { name: '', dosage: '', frequency: '', duration: '' }] }));
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
                        {CONSULTATION_TYPES.find(t => t.value === c.consultation_type)?.label || c.consultation_type}
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
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-sm text-slate-500">Ficha Clinica</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Motivo de Consulta *</Label>
                <Textarea value={form.chief_complaint} rows={2}
                  onChange={(e) => setForm(f => ({ ...f, chief_complaint: e.target.value }))}
                  placeholder="Motivo principal de la visita..." data-testid="form-chief-complaint" />
              </div>
              <div className="space-y-2">
                <Label>Historia / Anamnesis</Label>
                <Textarea value={form.anamnesis} rows={3}
                  onChange={(e) => setForm(f => ({ ...f, anamnesis: e.target.value }))}
                  placeholder="Antecedentes, sintomas previos, uso actual de lentes..." data-testid="form-anamnesis" />
              </div>
              <div className="space-y-2">
                <Label>Hallazgos</Label>
                <Textarea value={form.findings} rows={3}
                  onChange={(e) => setForm(f => ({ ...f, findings: e.target.value }))}
                  placeholder="Resultados del examen visual, agudeza visual, biomicroscopia..." data-testid="form-findings" />
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
                  <Textarea value={form.treatment_plan} rows={3}
                    onChange={(e) => setForm(f => ({ ...f, treatment_plan: e.target.value }))}
                    placeholder="Plan de tratamiento, prescripcion optica..." data-testid="form-treatment-plan" />
                </div>
                <div className="space-y-2">
                  <Label>Recomendaciones</Label>
                  <Textarea value={form.recommendations} rows={3}
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
              {CONSULTATION_TYPES.find(t => t.value === c.consultation_type)?.label || c.consultation_type}
            </span>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => openEditConsultation(c)} data-testid="detail-edit-btn">
              <Pencil className="w-4 h-4 mr-1" /> Editar
            </Button>
            <Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={() => {
              setEyeglassForm({ od_sphere: '', od_cylinder: '', od_axis: '', od_addition: '', od_dp: '', oi_sphere: '', oi_cylinder: '', oi_axis: '', oi_addition: '', oi_dp: '', lens_type: '', frame_type: '', observations: '' });
              setShowEyeglassRx(true);
            }} data-testid="gen-eyeglass-rx-btn">
              <FileText className="w-4 h-4 mr-1" /> Receta Anteojos
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
                  {(c.eyeglass_prescriptions || []).map((rx, i) => (
                    <div key={rx._id} className="flex items-center gap-2 text-sm py-1">
                      <FileText className="w-3.5 h-3.5 text-blue-500" />
                      <span>Anteojos ({formatDate(rx.created_at)})</span>
                    </div>
                  ))}
                  {(c.contact_prescriptions || []).map((rx, i) => (
                    <div key={rx._id} className="flex items-center gap-2 text-sm py-1">
                      <FileText className="w-3.5 h-3.5 text-teal-500" />
                      <span>Lentes de contacto ({formatDate(rx.created_at)})</span>
                    </div>
                  ))}
                  {(c.medical_prescriptions || []).map((rx, i) => (
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
          <div className="lg:col-span-2">
            <Card>
              <CardContent className="pt-4 space-y-5">
                {c.chief_complaint && (
                  <Section title="Motivo de Consulta" text={c.chief_complaint} />
                )}
                {c.anamnesis && (
                  <Section title="Historia / Anamnesis" text={c.anamnesis} />
                )}
                {c.findings && (
                  <Section title="Hallazgos" text={c.findings} />
                )}
                {c.diagnosis && (
                  <Section title="Diagnostico / Impresion Clinica" text={c.diagnosis} highlight />
                )}
                {c.treatment_plan && (
                  <Section title="Plan / Tratamiento" text={c.treatment_plan} />
                )}
                {c.recommendations && (
                  <Section title="Recomendaciones" text={c.recommendations} />
                )}
                {c.notes && (
                  <Section title="Observaciones" text={c.notes} />
                )}
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
      {view === 'list' && <ListView />}
      {view === 'form' && <FormView />}
      {view === 'detail' && <DetailView />}

      {/* ===== EYEGLASS RX DIALOG ===== */}
      <Dialog open={showEyeglassRx} onOpenChange={setShowEyeglassRx}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><FileText className="w-5 h-5 text-blue-600" /> Receta de Anteojos</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              {/* OD */}
              <div className="p-3 bg-blue-50 rounded-lg">
                <p className="text-xs font-bold text-blue-700 mb-2">OJO DERECHO (OD)</p>
                <div className="grid grid-cols-5 gap-2">
                  {['sphere', 'cylinder', 'axis', 'addition', 'dp'].map(f => (
                    <div key={f} className="space-y-1">
                      <Label className="text-[10px] uppercase">{f === 'dp' ? 'DP' : f === 'sphere' ? 'Esfera' : f === 'cylinder' ? 'Cilindro' : f === 'axis' ? 'Eje' : 'Adicion'}</Label>
                      <Input className="h-8 text-sm" value={eyeglassForm[`od_${f}`]}
                        onChange={(e) => setEyeglassForm(p => ({ ...p, [`od_${f}`]: e.target.value }))} data-testid={`rx-od-${f}`} />
                    </div>
                  ))}
                </div>
              </div>
              {/* OI */}
              <div className="p-3 bg-green-50 rounded-lg">
                <p className="text-xs font-bold text-green-700 mb-2">OJO IZQUIERDO (OI)</p>
                <div className="grid grid-cols-5 gap-2">
                  {['sphere', 'cylinder', 'axis', 'addition', 'dp'].map(f => (
                    <div key={f} className="space-y-1">
                      <Label className="text-[10px] uppercase">{f === 'dp' ? 'DP' : f === 'sphere' ? 'Esfera' : f === 'cylinder' ? 'Cilindro' : f === 'axis' ? 'Eje' : 'Adicion'}</Label>
                      <Input className="h-8 text-sm" value={eyeglassForm[`oi_${f}`]}
                        onChange={(e) => setEyeglassForm(p => ({ ...p, [`oi_${f}`]: e.target.value }))} data-testid={`rx-oi-${f}`} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">Tipo de Lente</Label>
                <Input value={eyeglassForm.lens_type} onChange={(e) => setEyeglassForm(p => ({ ...p, lens_type: e.target.value }))} placeholder="Monofocal, bifocal, progresivo..." />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Tipo de Armazon</Label>
                <Input value={eyeglassForm.frame_type} onChange={(e) => setEyeglassForm(p => ({ ...p, frame_type: e.target.value }))} />
              </div>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Observaciones</Label>
              <Textarea value={eyeglassForm.observations} onChange={(e) => setEyeglassForm(p => ({ ...p, observations: e.target.value }))} rows={2} />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowEyeglassRx(false)}>Cancelar</Button>
              <Button className="bg-blue-600 hover:bg-blue-700" onClick={handleCreateEyeglassRx} data-testid="save-eyeglass-rx-btn">
                <Save className="w-4 h-4 mr-2" /> Guardar Receta
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ===== MEDICAL RX DIALOG ===== */}
      <Dialog open={showMedicalRx} onOpenChange={setShowMedicalRx}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Pill className="w-5 h-5 text-purple-600" /> Receta Medica</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1">
              <Label>Diagnostico</Label>
              <Input value={medicalForm.diagnosis} onChange={(e) => setMedicalForm(f => ({ ...f, diagnosis: e.target.value }))} data-testid="med-rx-diagnosis" />
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <Label>Medicamentos</Label>
                <Button type="button" variant="outline" size="sm" onClick={addMedication} data-testid="add-medication-btn">
                  <Plus className="w-3 h-3 mr-1" /> Agregar
                </Button>
              </div>
              {medicalForm.medications.map((med, idx) => (
                <div key={idx} className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-2 mb-2 items-end">
                  <div className="space-y-1">
                    <Label className="text-[10px]">Medicamento</Label>
                    <Input className="h-8 text-sm" value={med.name} onChange={(e) => updateMedication(idx, 'name', e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-[10px]">Dosis</Label>
                    <Input className="h-8 text-sm w-20" value={med.dosage} onChange={(e) => updateMedication(idx, 'dosage', e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-[10px]">Frecuencia</Label>
                    <Input className="h-8 text-sm w-24" value={med.frequency} onChange={(e) => updateMedication(idx, 'frequency', e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-[10px]">Duracion</Label>
                    <Input className="h-8 text-sm w-20" value={med.duration} onChange={(e) => updateMedication(idx, 'duration', e.target.value)} />
                  </div>
                  {medicalForm.medications.length > 1 && (
                    <Button variant="ghost" size="sm" className="text-red-500 h-8 w-8 p-0" onClick={() => removeMedication(idx)}>X</Button>
                  )}
                </div>
              ))}
            </div>
            <div className="space-y-1">
              <Label>Instrucciones</Label>
              <Textarea value={medicalForm.instructions} onChange={(e) => setMedicalForm(f => ({ ...f, instructions: e.target.value }))} rows={2} data-testid="med-rx-instructions" />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowMedicalRx(false)}>Cancelar</Button>
              <Button className="bg-purple-600 hover:bg-purple-700" onClick={handleCreateMedicalRx} data-testid="save-medical-rx-btn">
                <Save className="w-4 h-4 mr-2" /> Guardar Receta
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
