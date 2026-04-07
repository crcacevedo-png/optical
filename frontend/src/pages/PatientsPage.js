import React, { useState, useEffect } from 'react';
import { api, formatApiErrorDetail, useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Checkbox } from '../components/ui/checkbox';
import { 
  Search, Plus, User, Phone, Mail, Calendar, 
  FileText, Eye, ShoppingBag, ChevronRight,
  ChevronLeft, Save, Pill, Glasses
} from 'lucide-react';
import { toast } from 'sonner';

const VA_METHODS = ['Snellen', 'logMAR', 'ETDRS'];

const defaultClinicalFields = {
  wears_glasses: false, glasses_since: '', glasses_type: '',
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

const CONSULTATION_TYPES = [
  { value: 'general', label: 'Consulta General' },
  { value: 'control', label: 'Control' },
  { value: 'urgencia', label: 'Urgencia' },
  { value: 'primera_vez', label: 'Primera Vez' },
  { value: 'seguimiento', label: 'Seguimiento' },
];

export default function PatientsPage() {
  const { user } = useAuth();
  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [page, setPage] = useState(0);
  const [totalPatients, setTotalPatients] = useState(0);
  const PAGE_SIZE = 30;
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    dpi: '',
    birth_date: '',
    gender: '',
    phone: '',
    email: '',
    address: '',
    emergency_contact: '',
    emergency_phone: '',
    notes: ''
  });

  // Consultation form state
  const [showConsultationDialog, setShowConsultationDialog] = useState(false);
  const [consultationForm, setConsultationForm] = useState({
    consultation_date: new Date().toISOString().slice(0, 10),
    consultation_time: new Date().toTimeString().slice(0, 5),
    consultation_type: 'general',
    chief_complaint: '',
    anamnesis: '',
    findings: '',
    diagnosis: '',
    treatment_plan: '',
    recommendations: '',
    notes: '',
    ...defaultClinicalFields
  });
  const [savingConsultation, setSavingConsultation] = useState(false);
  const [savedConsultationId, setSavedConsultationId] = useState(null);
  const [viewConsultation, setViewConsultation] = useState(null);
  const [showViewConsultation, setShowViewConsultation] = useState(false);
  const [loadingConsultation, setLoadingConsultation] = useState(false);

  // Prescription states
  const [showEyeglassRx, setShowEyeglassRx] = useState(false);
  const [eyeglassForm, setEyeglassForm] = useState({
    od_sphere: '', od_cylinder: '', od_axis: '', od_addition: '', od_dp: '',
    oi_sphere: '', oi_cylinder: '', oi_axis: '', oi_addition: '', oi_dp: '',
    lens_type: '', frame_type: '', observations: ''
  });
  const [showContactRx, setShowContactRx] = useState(false);
  const [contactForm, setContactForm] = useState({
    od_power: '', od_bc: '', od_dia: '', od_cylinder: '', od_axis: '', od_addition: '',
    oi_power: '', oi_bc: '', oi_dia: '', oi_cylinder: '', oi_axis: '', oi_addition: '',
    brand: '', lens_type: '', replacement: '', observations: ''
  });
  const [showMedicalRx, setShowMedicalRx] = useState(false);
  const [medicalForm, setMedicalForm] = useState({
    diagnosis: '', medications: [{ name: '', dosage: '', frequency: '', duration: '' }], instructions: ''
  });

  useEffect(() => {
    fetchPatients();
  }, [page]);

  const fetchPatients = async (searchTerm = '') => {
    try {
      setLoading(true);
      const params = { limit: PAGE_SIZE, skip: page * PAGE_SIZE };
      if (searchTerm) params.search = searchTerm;
      const { data } = await api.get('/api/patients', { params });
      setPatients(data.patients || []);
      setTotalPatients(data.total || 0);
    } catch (error) {
      console.error('Error fetching patients:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchPatientDetails = async (patientId) => {
    try {
      const { data } = await api.get(`/api/patients/${patientId}`);
      setSelectedPatient(data);
    } catch (error) {
      console.error('Error fetching patient details:', error);
    }
  };

  const handleSearch = (e) => {
    const value = e.target.value;
    setSearch(value);
    setPage(0);
    if (value.length >= 2 || value.length === 0) {
      fetchPatients(value);
    }
  };

  const totalPages = Math.ceil(totalPatients / PAGE_SIZE);

  const resetConsultationForm = () => {
    setConsultationForm({
      consultation_date: new Date().toISOString().slice(0, 10),
      consultation_time: new Date().toTimeString().slice(0, 5),
      consultation_type: 'general',
      chief_complaint: '',
      anamnesis: '',
      findings: '',
      diagnosis: '',
      treatment_plan: '',
      recommendations: '',
      notes: '',
      ...defaultClinicalFields
    });
  };

  const handleCreateConsultation = async () => {
    if (!consultationForm.chief_complaint) {
      return toast.error('Ingrese el motivo de consulta');
    }
    setSavingConsultation(true);
    try {
      const { data } = await api.post('/api/consultations', {
        patient_id: selectedPatient._id,
        ...consultationForm
      });
      toast.success('Consulta registrada exitosamente');
      const newId = data._id || data.id;
      setSavedConsultationId(newId);
      fetchPatientDetails(selectedPatient._id);
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    } finally {
      setSavingConsultation(false);
    }
  };

  const openConsultationDetail = async (consultationId) => {
    setLoadingConsultation(true);
    setShowViewConsultation(true);
    try {
      const { data } = await api.get(`/api/consultations/${consultationId}`);
      setViewConsultation(data);
    } catch (error) {
      toast.error('Error al cargar la consulta');
      setShowViewConsultation(false);
    } finally {
      setLoadingConsultation(false);
    }
  };

  // Prescription handlers
  const rxConsultationId = savedConsultationId;
  const rxPatientId = selectedPatient?._id;

  const handleCreateEyeglassRx = async () => {
    if (!rxConsultationId) return;
    try {
      await api.post('/api/prescriptions/eyeglass', {
        patient_id: rxPatientId,
        consultation_id: rxConsultationId,
        professional_name: user?.name,
        ...eyeglassForm
      });
      toast.success('Receta de anteojos creada');
      setShowEyeglassRx(false);
      setEyeglassForm({ od_sphere: '', od_cylinder: '', od_axis: '', od_addition: '', od_dp: '', oi_sphere: '', oi_cylinder: '', oi_axis: '', oi_addition: '', oi_dp: '', lens_type: '', frame_type: '', observations: '' });
      fetchPatientDetails(selectedPatient._id);
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  const handleCreateContactRx = async () => {
    if (!rxConsultationId) return;
    try {
      await api.post('/api/prescriptions/contact-lens', {
        patient_id: rxPatientId,
        consultation_id: rxConsultationId,
        professional_name: user?.name,
        ...contactForm
      });
      toast.success('Receta de lentes de contacto creada');
      setShowContactRx(false);
      setContactForm({ od_power: '', od_bc: '', od_dia: '', od_cylinder: '', od_axis: '', od_addition: '', oi_power: '', oi_bc: '', oi_dia: '', oi_cylinder: '', oi_axis: '', oi_addition: '', brand: '', lens_type: '', replacement: '', observations: '' });
      fetchPatientDetails(selectedPatient._id);
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  const handleCreateMedicalRx = async () => {
    if (!rxConsultationId) return;
    try {
      await api.post('/api/prescriptions/medical', {
        patient_id: rxPatientId,
        consultation_id: rxConsultationId,
        professional_name: user?.name,
        ...medicalForm
      });
      toast.success('Receta medica creada');
      setShowMedicalRx(false);
      setMedicalForm({ diagnosis: '', medications: [{ name: '', dosage: '', frequency: '', duration: '' }], instructions: '' });
      fetchPatientDetails(selectedPatient._id);
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/api/patients', formData);
      toast.success('Paciente creado exitosamente');
      setShowAddDialog(false);
      setFormData({
        first_name: '', last_name: '', dpi: '', birth_date: '', gender: '',
        phone: '', email: '', address: '', emergency_contact: '', emergency_phone: '', notes: ''
      });
      fetchPatients();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const formatCurrency = (amount) => {
    return `Q ${(amount || 0).toLocaleString('es-GT', { minimumFractionDigits: 2 })}`;
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-6" data-testid="patients-page">
      {/* Left Panel - Patient List */}
      <Card className="w-full lg:w-[350px] flex-shrink-0 border-slate-200/80">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="font-heading text-lg">Pacientes</CardTitle>
            <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
              <DialogTrigger asChild>
                <Button size="sm" className="bg-pine-900 hover:bg-pine-700" data-testid="add-patient-btn">
                  <Plus className="w-4 h-4 mr-1" /> Nuevo
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle className="font-heading">Nuevo Paciente</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Nombre *</Label>
                      <Input
                        value={formData.first_name}
                        onChange={(e) => setFormData({...formData, first_name: e.target.value})}
                        required
                        data-testid="patient-first-name"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Apellido *</Label>
                      <Input
                        value={formData.last_name}
                        onChange={(e) => setFormData({...formData, last_name: e.target.value})}
                        required
                        data-testid="patient-last-name"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>DPI</Label>
                      <Input
                        value={formData.dpi}
                        onChange={(e) => setFormData({...formData, dpi: e.target.value})}
                        data-testid="patient-dpi"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Teléfono *</Label>
                      <Input
                        value={formData.phone}
                        onChange={(e) => setFormData({...formData, phone: e.target.value})}
                        required
                        data-testid="patient-phone"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Fecha de Nacimiento</Label>
                      <Input
                        type="date"
                        value={formData.birth_date}
                        onChange={(e) => setFormData({...formData, birth_date: e.target.value})}
                        data-testid="patient-birthdate"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Género</Label>
                      <Select value={formData.gender} onValueChange={(v) => setFormData({...formData, gender: v})}>
                        <SelectTrigger data-testid="patient-gender">
                          <SelectValue placeholder="Seleccionar" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="M">Masculino</SelectItem>
                          <SelectItem value="F">Femenino</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>Correo Electrónico</Label>
                    <Input
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({...formData, email: e.target.value})}
                      data-testid="patient-email"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Dirección</Label>
                    <Textarea
                      value={formData.address}
                      onChange={(e) => setFormData({...formData, address: e.target.value})}
                      rows={2}
                      data-testid="patient-address"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Contacto de Emergencia</Label>
                      <Input
                        value={formData.emergency_contact}
                        onChange={(e) => setFormData({...formData, emergency_contact: e.target.value})}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Teléfono de Emergencia</Label>
                      <Input
                        value={formData.emergency_phone}
                        onChange={(e) => setFormData({...formData, emergency_phone: e.target.value})}
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>Notas</Label>
                    <Textarea
                      value={formData.notes}
                      onChange={(e) => setFormData({...formData, notes: e.target.value})}
                      rows={2}
                    />
                  </div>
                  <div className="flex justify-end gap-2 pt-4">
                    <Button type="button" variant="outline" onClick={() => setShowAddDialog(false)}>
                      Cancelar
                    </Button>
                    <Button type="submit" className="bg-pine-900 hover:bg-pine-700" data-testid="save-patient-btn">
                      Guardar Paciente
                    </Button>
                  </div>
                </form>
              </DialogContent>
            </Dialog>
          </div>
          <div className="relative mt-3">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input
              placeholder="Buscar paciente..."
              value={search}
              onChange={handleSearch}
              className="pl-9"
              data-testid="patient-search"
            />
          </div>
        </CardHeader>
        <CardContent className="p-0 flex flex-col" style={{ height: 'calc(100vh - 16rem)' }}>
          <ScrollArea className="flex-1">
            {loading ? (
              <div className="flex justify-center py-8">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-pine-900"></div>
              </div>
            ) : patients.length === 0 ? (
              <div className="text-center py-8 text-slate-500">
                <User className="w-12 h-12 mx-auto mb-2 opacity-30" />
                <p>No se encontraron pacientes</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {patients.map((patient) => (
                  <button
                    key={patient._id}
                    onClick={() => fetchPatientDetails(patient._id)}
                    className={`w-full p-4 text-left hover:bg-slate-50 transition-colors flex items-center gap-3 ${
                      selectedPatient?._id === patient._id ? 'bg-pine-50' : ''
                    }`}
                    data-testid={`patient-item-${patient._id}`}
                  >
                    <div className="w-10 h-10 rounded-full bg-pine-100 flex items-center justify-center text-pine-700 font-medium text-sm flex-shrink-0">
                      {patient.first_name?.[0]}{patient.last_name?.[0]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-slate-900 truncate">
                        {patient.first_name} {patient.last_name}
                      </p>
                      <p className="text-sm text-slate-500 truncate">{patient.phone}</p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-400" />
                  </button>
                ))}
              </div>
            )}
          </ScrollArea>
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-2 border-t border-slate-100" data-testid="patients-pagination">
              <span className="text-xs text-slate-500">{totalPatients} pacientes</span>
              <div className="flex items-center gap-1">
                <Button variant="ghost" size="sm" className="h-7 w-7 p-0" disabled={page === 0}
                  onClick={() => setPage(p => p - 1)} data-testid="prev-page-btn">
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <span className="text-xs text-slate-600 px-2">{page + 1}/{totalPages}</span>
                <Button variant="ghost" size="sm" className="h-7 w-7 p-0" disabled={page >= totalPages - 1}
                  onClick={() => setPage(p => p + 1)} data-testid="next-page-btn">
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Right Panel - Patient Details */}
      <div className="flex-1 hidden lg:block">
        {selectedPatient ? (
          <Card className="h-full border-slate-200/80">
            <CardHeader className="border-b border-slate-100">
              <div className="flex items-start gap-4">
                <div className="w-16 h-16 rounded-full bg-pine-100 flex items-center justify-center text-pine-700 font-semibold text-xl">
                  {selectedPatient.first_name?.[0]}{selectedPatient.last_name?.[0]}
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <CardTitle className="font-heading text-xl">
                      {selectedPatient.first_name} {selectedPatient.last_name}
                    </CardTitle>
                    <Button size="sm" className="bg-pine-700 hover:bg-pine-800" data-testid="header-new-consultation-btn"
                      onClick={() => { resetConsultationForm(); setSavedConsultationId(null); setShowConsultationDialog(true); }}>
                      <Eye className="w-4 h-4 mr-1" /> Nueva Consulta
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-4 mt-2 text-sm text-slate-500">
                    {selectedPatient.phone && (
                      <span className="flex items-center gap-1">
                        <Phone className="w-4 h-4" /> {selectedPatient.phone}
                      </span>
                    )}
                    {selectedPatient.email && (
                      <span className="flex items-center gap-1">
                        <Mail className="w-4 h-4" /> {selectedPatient.email}
                      </span>
                    )}
                    {selectedPatient.birth_date && (
                      <span className="flex items-center gap-1" data-testid="patient-age-display">
                        <Calendar className="w-4 h-4" /> {selectedPatient.birth_date}
                        {selectedPatient.age != null && (
                          <span className="ml-1 px-1.5 py-0.5 bg-pine-50 text-pine-700 rounded text-xs font-medium">
                            {selectedPatient.age} años
                          </span>
                        )}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <Tabs defaultValue="prescriptions" className="h-full">
                <TabsList className="w-full justify-start rounded-none border-b border-slate-100 h-12 p-0 bg-transparent">
                  <TabsTrigger value="consultations" className="rounded-none border-b-2 border-transparent data-[state=active]:border-pine-700 data-[state=active]:bg-transparent">
                    <Eye className="w-4 h-4 mr-2" /> Consultas
                  </TabsTrigger>
                  <TabsTrigger value="prescriptions" className="rounded-none border-b-2 border-transparent data-[state=active]:border-pine-700 data-[state=active]:bg-transparent">
                    <Eye className="w-4 h-4 mr-2" /> Recetas
                  </TabsTrigger>
                  <TabsTrigger value="appointments" className="rounded-none border-b-2 border-transparent data-[state=active]:border-pine-700 data-[state=active]:bg-transparent">
                    <Calendar className="w-4 h-4 mr-2" /> Citas
                  </TabsTrigger>
                  <TabsTrigger value="sales" className="rounded-none border-b-2 border-transparent data-[state=active]:border-pine-700 data-[state=active]:bg-transparent">
                    <ShoppingBag className="w-4 h-4 mr-2" /> Compras
                  </TabsTrigger>
                  <TabsTrigger value="info" className="rounded-none border-b-2 border-transparent data-[state=active]:border-pine-700 data-[state=active]:bg-transparent">
                    <FileText className="w-4 h-4 mr-2" /> Información
                  </TabsTrigger>
                </TabsList>

                <ScrollArea className="h-[calc(100vh-20rem)]">
                  <TabsContent value="consultations" className="p-4 m-0">
                    <h3 className="font-medium text-slate-900 mb-3">Historial de Consultas</h3>
                    {selectedPatient.consultations?.length > 0 ? (
                      <div className="space-y-3">
                        {selectedPatient.consultations.map((con) => (
                          <div key={con._id} className="p-3 bg-slate-50 rounded-lg border cursor-pointer hover:bg-slate-100 hover:border-pine-200 transition-colors"
                            onClick={() => openConsultationDetail(con._id)} data-testid={`consultation-history-${con._id}`}>
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-semibold text-pine-700">{con.consultation_date?.slice(0, 10)}</span>
                                <span className="px-2 py-0.5 bg-pine-50 text-pine-600 text-[10px] rounded-full font-medium">{con.consultation_type}</span>
                              </div>
                              <span className="text-xs text-slate-400">{con.professional_name || ''}</span>
                            </div>
                            <p className="text-sm text-slate-700 font-medium">{con.chief_complaint}</p>
                            {con.diagnosis && <p className="text-xs text-slate-500 mt-1">Dx: {con.diagnosis}</p>}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-slate-400">No hay consultas registradas</p>
                    )}
                  </TabsContent>

                  <TabsContent value="prescriptions" className="p-4 m-0">
                    <h3 className="font-medium text-slate-900 mb-3">Recetas de Anteojos</h3>
                    {selectedPatient.eyeglass_prescriptions?.length > 0 ? (
                      <div className="space-y-3">
                        {selectedPatient.eyeglass_prescriptions.map((rx) => (
                          <div key={rx._id} className="p-4 rounded-lg bg-slate-50 border border-slate-100">
                            <div className="flex justify-between items-start mb-3">
                              <span className="text-sm text-slate-500">{rx.created_at?.slice(0, 10)}</span>
                              <Button size="sm" variant="outline" onClick={() => window.open(`${process.env.REACT_APP_BACKEND_URL}/api/prescriptions/eyeglass/${rx._id}/pdf`, '_blank')}>
                                Imprimir PDF
                              </Button>
                            </div>
                            <div className="grid grid-cols-6 gap-2 text-sm">
                              <div className="font-medium text-slate-500"></div>
                              <div className="font-medium text-slate-500 text-center">Esfera</div>
                              <div className="font-medium text-slate-500 text-center">Cilindro</div>
                              <div className="font-medium text-slate-500 text-center">Eje</div>
                              <div className="font-medium text-slate-500 text-center">Adición</div>
                              <div className="font-medium text-slate-500 text-center">D.P.</div>
                              
                              <div className="font-medium">OD</div>
                              <div className="text-center">{rx.od_sphere || '-'}</div>
                              <div className="text-center">{rx.od_cylinder || '-'}</div>
                              <div className="text-center">{rx.od_axis || '-'}</div>
                              <div className="text-center">{rx.od_addition || '-'}</div>
                              <div className="text-center">{rx.od_dp || '-'}</div>
                              
                              <div className="font-medium">OI</div>
                              <div className="text-center">{rx.oi_sphere || '-'}</div>
                              <div className="text-center">{rx.oi_cylinder || '-'}</div>
                              <div className="text-center">{rx.oi_axis || '-'}</div>
                              <div className="text-center">{rx.oi_addition || '-'}</div>
                              <div className="text-center">{rx.oi_dp || '-'}</div>
                            </div>
                            {rx.observations && (
                              <p className="mt-3 text-sm text-slate-600 border-t pt-2">
                                <span className="font-medium">Observaciones:</span> {rx.observations}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-slate-500 text-center py-4">Sin recetas de anteojos</p>
                    )}

                    <h3 className="font-medium text-slate-900 mb-3 mt-6">Recetas Médicas</h3>
                    {selectedPatient.medical_prescriptions?.length > 0 ? (
                      <div className="space-y-3">
                        {selectedPatient.medical_prescriptions.map((rx) => (
                          <div key={rx._id} className="p-4 rounded-lg bg-slate-50 border border-slate-100">
                            <div className="flex justify-between items-start mb-3">
                              <span className="text-sm text-slate-500">{rx.created_at?.slice(0, 10)}</span>
                              <Button size="sm" variant="outline" onClick={() => window.open(`${process.env.REACT_APP_BACKEND_URL}/api/prescriptions/medical/${rx._id}/pdf`, '_blank')}>
                                Imprimir PDF
                              </Button>
                            </div>
                            {rx.diagnosis && (
                              <p className="text-sm mb-2"><span className="font-medium">Diagnóstico:</span> {rx.diagnosis}</p>
                            )}
                            <div className="space-y-1">
                              {rx.medications?.map((med, idx) => (
                                <p key={idx} className="text-sm">
                                  • {med.name} - {med.dosage} ({med.duration})
                                </p>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-slate-500 text-center py-4">Sin recetas médicas</p>
                    )}
                  </TabsContent>

                  <TabsContent value="appointments" className="p-4 m-0">
                    {selectedPatient.appointments?.length > 0 ? (
                      <div className="space-y-3">
                        {selectedPatient.appointments.map((apt) => (
                          <div key={apt._id} className="p-4 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
                            <div>
                              <p className="font-medium text-slate-900">{apt.type}</p>
                              <p className="text-sm text-slate-500">{apt.date} - {apt.time}</p>
                            </div>
                            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                              apt.status === 'completada' ? 'bg-green-100 text-green-800' : 
                              apt.status === 'cancelada' ? 'bg-red-100 text-red-800' : 
                              apt.status === 'confirmada' ? 'bg-blue-100 text-blue-800' :
                              'bg-amber-100 text-amber-800'
                            }`}>
                              {apt.status === 'pendiente' ? 'Pendiente' : 
                               apt.status === 'confirmada' ? 'Confirmada' :
                               apt.status === 'completada' ? 'Completada' : 
                               apt.status === 'cancelada' ? 'Cancelada' : apt.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-slate-500 text-center py-8">Sin historial de citas</p>
                    )}
                  </TabsContent>

                  <TabsContent value="sales" className="p-4 m-0">
                    {selectedPatient.sales?.length > 0 ? (
                      <div className="space-y-3">
                        {selectedPatient.sales.map((sale) => (
                          <div key={sale._id} className="p-4 rounded-lg bg-slate-50 border border-slate-100">
                            <div className="flex justify-between items-start">
                              <div>
                                <p className="font-medium text-slate-900">{formatCurrency(sale.total)}</p>
                                <p className="text-sm text-slate-500">{sale.created_at?.slice(0, 10)}</p>
                              </div>
                              <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                                sale.status === 'completada' ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'
                              }`}>
                                {sale.status === 'completada' ? 'Pagado' : 'Pendiente'}
                              </span>
                            </div>
                            {sale.balance > 0 && (
                              <p className="text-sm text-amber-600 mt-2">Saldo pendiente: {formatCurrency(sale.balance)}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-slate-500 text-center py-8">Sin historial de compras</p>
                    )}
                  </TabsContent>

                  <TabsContent value="info" className="p-4 m-0">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label className="text-slate-500">DPI</Label>
                        <p className="font-medium">{selectedPatient.dpi || '-'}</p>
                      </div>
                      <div>
                        <Label className="text-slate-500">Género</Label>
                        <p className="font-medium">{selectedPatient.gender === 'M' ? 'Masculino' : selectedPatient.gender === 'F' ? 'Femenino' : '-'}</p>
                      </div>
                      <div className="col-span-2">
                        <Label className="text-slate-500">Dirección</Label>
                        <p className="font-medium">{selectedPatient.address || '-'}</p>
                      </div>
                      <div>
                        <Label className="text-slate-500">Contacto de Emergencia</Label>
                        <p className="font-medium">{selectedPatient.emergency_contact || '-'}</p>
                      </div>
                      <div>
                        <Label className="text-slate-500">Teléfono de Emergencia</Label>
                        <p className="font-medium">{selectedPatient.emergency_phone || '-'}</p>
                      </div>
                      {selectedPatient.notes && (
                        <div className="col-span-2">
                          <Label className="text-slate-500">Notas</Label>
                          <p className="font-medium">{selectedPatient.notes}</p>
                        </div>
                      )}
                    </div>
                  </TabsContent>
                </ScrollArea>
              </Tabs>
            </CardContent>
          </Card>
        ) : (
          <Card className="h-full border-slate-200/80 flex items-center justify-center">
            <div className="text-center text-slate-500">
              <User className="w-16 h-16 mx-auto mb-4 opacity-30" />
              <p className="text-lg font-medium">Seleccione un paciente</p>
              <p className="text-sm">para ver su información detallada</p>
            </div>
          </Card>
        )}
      </div>

      {/* Nueva Consulta Dialog */}
      <Dialog open={showConsultationDialog} onOpenChange={setShowConsultationDialog}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-heading">
              <Eye className="w-5 h-5 text-pine-700" />
              Nueva Consulta - {selectedPatient?.first_name} {selectedPatient?.last_name}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-5">
            {/* Header fields */}
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1">
                <Label className="text-xs">Fecha *</Label>
                <Input type="date" value={consultationForm.consultation_date}
                  onChange={(e) => setConsultationForm(f => ({ ...f, consultation_date: e.target.value }))}
                  data-testid="consultation-date" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Hora</Label>
                <Input type="time" value={consultationForm.consultation_time}
                  onChange={(e) => setConsultationForm(f => ({ ...f, consultation_time: e.target.value }))}
                  data-testid="consultation-time" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Tipo de Consulta</Label>
                <Select value={consultationForm.consultation_type}
                  onValueChange={(v) => setConsultationForm(f => ({ ...f, consultation_type: v }))}>
                  <SelectTrigger data-testid="consultation-type"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {CONSULTATION_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* I. Motivo */}
            <div className="space-y-2">
              <Label className="font-semibold text-pine-700">I. Motivo de Consulta *</Label>
              <Textarea value={consultationForm.chief_complaint} rows={2}
                onChange={(e) => setConsultationForm(f => ({ ...f, chief_complaint: e.target.value }))}
                placeholder="Describir sintomas principales, duracion y factores asociados" data-testid="consultation-chief-complaint" />
            </div>

            {/* II. Historia Clinica */}
            <div className="border rounded-lg p-4 space-y-4">
              <p className="text-sm font-semibold text-pine-700">II. Historia Clinica</p>
              {/* A. Oculares */}
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase mb-2">A. Antecedentes Oculares</p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Checkbox id="p-wears" checked={consultationForm.wears_glasses}
                        onCheckedChange={(v) => setConsultationForm(f => ({ ...f, wears_glasses: !!v }))} />
                      <Label htmlFor="p-wears" className="text-sm cursor-pointer">Usa lentes</Label>
                    </div>
                    {consultationForm.wears_glasses && (
                      <div className="pl-6 space-y-1">
                        <Input placeholder="Desde cuando" value={consultationForm.glasses_since} className="h-7 text-sm"
                          onChange={(e) => setConsultationForm(f => ({ ...f, glasses_since: e.target.value }))} />
                        <Input placeholder="Tipo de lentes" value={consultationForm.glasses_type} className="h-7 text-sm"
                          onChange={(e) => setConsultationForm(f => ({ ...f, glasses_type: e.target.value }))} />
                      </div>
                    )}
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Cirugias oculares</Label>
                    <Input value={consultationForm.ocular_surgeries} placeholder="Ninguna" className="h-7 text-sm"
                      onChange={(e) => setConsultationForm(f => ({ ...f, ocular_surgeries: e.target.value }))} />
                    <Label className="text-xs">Traumatismos</Label>
                    <Input value={consultationForm.ocular_trauma} placeholder="Ninguno" className="h-7 text-sm"
                      onChange={(e) => setConsultationForm(f => ({ ...f, ocular_trauma: e.target.value }))} />
                  </div>
                </div>
                <div className="mt-2">
                  <Label className="text-xs">Enfermedades oculares</Label>
                  <Input value={consultationForm.ocular_diseases} placeholder="Ninguna" className="h-7 text-sm mt-1"
                    onChange={(e) => setConsultationForm(f => ({ ...f, ocular_diseases: e.target.value }))} />
                </div>
              </div>
              {/* B. Sistemicos */}
              <div className="pt-3 border-t">
                <p className="text-xs font-semibold text-slate-500 uppercase mb-2">B. Antecedentes Sistemicos</p>
                <div className="flex flex-wrap gap-4 mb-2">
                  <div className="flex items-center gap-2">
                    <Checkbox id="p-diabetes" checked={consultationForm.diabetes}
                      onCheckedChange={(v) => setConsultationForm(f => ({ ...f, diabetes: !!v }))} />
                    <Label htmlFor="p-diabetes" className="text-sm cursor-pointer">Diabetes</Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox id="p-hyp" checked={consultationForm.hypertension}
                      onCheckedChange={(v) => setConsultationForm(f => ({ ...f, hypertension: !!v }))} />
                    <Label htmlFor="p-hyp" className="text-sm cursor-pointer">Hipertension</Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox id="p-auto" checked={consultationForm.autoimmune_disease}
                      onCheckedChange={(v) => setConsultationForm(f => ({ ...f, autoimmune_disease: !!v }))} />
                    <Label htmlFor="p-auto" className="text-sm cursor-pointer">Autoinmune</Label>
                  </div>
                </div>
                {consultationForm.autoimmune_disease && (
                  <Input placeholder="Cual enfermedad autoinmune" value={consultationForm.autoimmune_details} className="h-7 text-sm mb-2"
                    onChange={(e) => setConsultationForm(f => ({ ...f, autoimmune_details: e.target.value }))} />
                )}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label className="text-xs">Medicamentos</Label>
                    <Input value={consultationForm.current_medications} placeholder="Ninguno" className="h-7 text-sm"
                      onChange={(e) => setConsultationForm(f => ({ ...f, current_medications: e.target.value }))} />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Alergias</Label>
                    <Input value={consultationForm.allergies} placeholder="Ninguna" className="h-7 text-sm"
                      onChange={(e) => setConsultationForm(f => ({ ...f, allergies: e.target.value }))} />
                  </div>
                </div>
              </div>
              {/* C. Familiares */}
              <div className="pt-3 border-t">
                <p className="text-xs font-semibold text-slate-500 uppercase mb-2">C. Antecedentes Familiares</p>
                <div className="space-y-2">
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                      <Checkbox id="p-fglau" checked={consultationForm.family_glaucoma}
                        onCheckedChange={(v) => setConsultationForm(f => ({ ...f, family_glaucoma: !!v }))} />
                      <Label htmlFor="p-fglau" className="text-sm cursor-pointer">Glaucoma</Label>
                    </div>
                    {consultationForm.family_glaucoma && (
                      <Input placeholder="Parentesco" value={consultationForm.family_glaucoma_relationship} className="h-7 text-sm w-32"
                        onChange={(e) => setConsultationForm(f => ({ ...f, family_glaucoma_relationship: e.target.value }))} />
                    )}
                  </div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                      <Checkbox id="p-fmac" checked={consultationForm.family_macular_degeneration}
                        onCheckedChange={(v) => setConsultationForm(f => ({ ...f, family_macular_degeneration: !!v }))} />
                      <Label htmlFor="p-fmac" className="text-sm cursor-pointer">Deg. macular</Label>
                    </div>
                    {consultationForm.family_macular_degeneration && (
                      <Input placeholder="Parentesco" value={consultationForm.family_macular_relationship} className="h-7 text-sm w-32"
                        onChange={(e) => setConsultationForm(f => ({ ...f, family_macular_relationship: e.target.value }))} />
                    )}
                  </div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                      <Checkbox id="p-fmyo" checked={consultationForm.family_high_myopia}
                        onCheckedChange={(v) => setConsultationForm(f => ({ ...f, family_high_myopia: !!v }))} />
                      <Label htmlFor="p-fmyo" className="text-sm cursor-pointer">Miopia alta</Label>
                    </div>
                    {consultationForm.family_high_myopia && (
                      <Input placeholder="Parentesco" value={consultationForm.family_high_myopia_relationship} className="h-7 text-sm w-32"
                        onChange={(e) => setConsultationForm(f => ({ ...f, family_high_myopia_relationship: e.target.value }))} />
                    )}
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Otros</Label>
                    <Input value={consultationForm.family_other_history} placeholder="Ninguno" className="h-7 text-sm"
                      onChange={(e) => setConsultationForm(f => ({ ...f, family_other_history: e.target.value }))} />
                  </div>
                </div>
              </div>
            </div>

            {/* III. Agudeza Visual */}
            <div className="border rounded-lg p-4 space-y-3">
              <p className="text-sm font-semibold text-pine-700">III. Agudeza Visual</p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-1 pr-2 text-xs font-semibold text-slate-500 uppercase">Medicion</th>
                    <th className="text-center py-1 px-1 text-xs font-semibold text-blue-700 uppercase">OD</th>
                    <th className="text-center py-1 px-1 text-xs font-semibold text-green-700 uppercase">OI</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { label: 'AV Lejos sin Rx', od: 'va_distance_without_rx_od', oi: 'va_distance_without_rx_oi' },
                    { label: 'AV Lejos con Rx', od: 'va_distance_with_rx_od', oi: 'va_distance_with_rx_oi' },
                    { label: 'AV Cerca sin Rx', od: 'va_near_without_rx_od', oi: 'va_near_without_rx_oi' },
                    { label: 'AV Cerca con Rx', od: 'va_near_with_rx_od', oi: 'va_near_with_rx_oi' },
                    { label: 'AV Estenopeico', od: 'va_pinhole_od', oi: 'va_pinhole_oi' },
                  ].map((row) => (
                    <tr key={row.od} className="border-b last:border-0">
                      <td className="py-1 pr-2 text-slate-700 text-xs">{row.label}</td>
                      <td className="py-1 px-1">
                        <Input className="h-7 text-sm text-center" value={consultationForm[row.od]} placeholder="20/20"
                          onChange={(e) => setConsultationForm(f => ({ ...f, [row.od]: e.target.value }))} />
                      </td>
                      <td className="py-1 px-1">
                        <Input className="h-7 text-sm text-center" value={consultationForm[row.oi]} placeholder="20/20"
                          onChange={(e) => setConsultationForm(f => ({ ...f, [row.oi]: e.target.value }))} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="flex items-center gap-2">
                <Label className="text-xs">Metodo:</Label>
                <Select value={consultationForm.visual_acuity_method}
                  onValueChange={(v) => setConsultationForm(f => ({ ...f, visual_acuity_method: v }))}>
                  <SelectTrigger className="w-32 h-7 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {VA_METHODS.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* IV. Hallazgos y Plan */}
            <div className="space-y-3">
              <p className="text-sm font-semibold text-pine-700">IV. Hallazgos y Plan</p>
              <div className="space-y-2">
                <Label className="text-xs">Historia / Anamnesis</Label>
                <Textarea value={consultationForm.anamnesis} rows={2}
                  onChange={(e) => setConsultationForm(f => ({ ...f, anamnesis: e.target.value }))}
                  placeholder="Antecedentes, sintomas previos..." data-testid="consultation-anamnesis" />
              </div>
              <div className="space-y-2">
                <Label className="text-xs">Hallazgos</Label>
                <Textarea value={consultationForm.findings} rows={2}
                  onChange={(e) => setConsultationForm(f => ({ ...f, findings: e.target.value }))}
                  placeholder="Resultados del examen visual, agudeza visual..." data-testid="consultation-findings" />
              </div>
              <div className="space-y-2">
                <Label className="text-xs">Diagnostico</Label>
                <Textarea value={consultationForm.diagnosis} rows={2}
                  onChange={(e) => setConsultationForm(f => ({ ...f, diagnosis: e.target.value }))}
                  placeholder="Diagnostico o impresion clinica..." data-testid="consultation-diagnosis" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label className="text-xs">Plan / Tratamiento</Label>
                  <Textarea value={consultationForm.treatment_plan} rows={2}
                    onChange={(e) => setConsultationForm(f => ({ ...f, treatment_plan: e.target.value }))}
                    placeholder="Plan de tratamiento..." data-testid="consultation-treatment" />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs">Recomendaciones</Label>
                  <Textarea value={consultationForm.recommendations} rows={2}
                    onChange={(e) => setConsultationForm(f => ({ ...f, recommendations: e.target.value }))}
                    placeholder="Recomendaciones al paciente..." data-testid="consultation-recommendations" />
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-xs">Observaciones</Label>
                <Textarea value={consultationForm.notes} rows={2}
                  onChange={(e) => setConsultationForm(f => ({ ...f, notes: e.target.value }))}
                  placeholder="Notas adicionales..." data-testid="consultation-notes" />
              </div>
            </div>

            <div className="flex justify-between items-center gap-2 pt-2 border-t">
              {savedConsultationId ? (
                <div className="flex flex-wrap gap-2" data-testid="new-rx-actions">
                  <Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={() => {
                    setEyeglassForm({ od_sphere: '', od_cylinder: '', od_axis: '', od_addition: '', od_dp: '', oi_sphere: '', oi_cylinder: '', oi_axis: '', oi_addition: '', oi_dp: '', lens_type: '', frame_type: '', observations: '' });
                    setShowEyeglassRx(true);
                  }} data-testid="new-gen-eyeglass-rx-btn">
                    <Glasses className="w-4 h-4 mr-1" /> Receta Anteojos
                  </Button>
                  <Button size="sm" className="bg-teal-600 hover:bg-teal-700" onClick={() => {
                    setContactForm({ od_power: '', od_bc: '', od_dia: '', od_cylinder: '', od_axis: '', od_addition: '', oi_power: '', oi_bc: '', oi_dia: '', oi_cylinder: '', oi_axis: '', oi_addition: '', brand: '', lens_type: '', replacement: '', observations: '' });
                    setShowContactRx(true);
                  }} data-testid="new-gen-contact-rx-btn">
                    <Eye className="w-4 h-4 mr-1" /> Lentes de Contacto
                  </Button>
                  <Button size="sm" className="bg-purple-600 hover:bg-purple-700" onClick={() => {
                    setMedicalForm({ diagnosis: consultationForm.diagnosis || '', medications: [{ name: '', dosage: '', frequency: '', duration: '' }], instructions: '' });
                    setShowMedicalRx(true);
                  }} data-testid="new-gen-medical-rx-btn">
                    <Pill className="w-4 h-4 mr-1" /> Receta Medica
                  </Button>
                </div>
              ) : <div />}
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => { setShowConsultationDialog(false); setSavedConsultationId(null); resetConsultationForm(); }}>
                  {savedConsultationId ? 'Cerrar' : 'Cancelar'}
                </Button>
                {!savedConsultationId && (
                  <Button className="bg-pine-700 hover:bg-pine-800" onClick={handleCreateConsultation}
                    disabled={!consultationForm.chief_complaint || savingConsultation} data-testid="save-consultation-from-patient-btn">
                    <Save className="w-4 h-4 mr-2" /> Guardar Consulta
                  </Button>
                )}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Ver Consulta Dialog (solo lectura) */}
      <Dialog open={showViewConsultation} onOpenChange={setShowViewConsultation}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="view-consultation-dialog">
          {loadingConsultation ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
            </div>
          ) : viewConsultation ? (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 font-heading">
                  <Eye className="w-5 h-5 text-pine-700" />
                  Consulta del {viewConsultation.consultation_date?.slice(0, 10)}
                  <span className="px-2 py-0.5 bg-pine-50 text-pine-700 text-xs rounded-full font-medium ml-1">
                    {viewConsultation.consultation_type}
                  </span>
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4 pt-2">
                <div className="flex items-center justify-between text-sm text-slate-500 pb-3 border-b">
                  <span>Hora: {viewConsultation.consultation_time || '-'}</span>
                  <span>Profesional: {viewConsultation.professional_name || '-'}</span>
                </div>

                {/* I. Motivo */}
                {viewConsultation.chief_complaint && (
                  <div>
                    <p className="text-xs font-semibold text-pine-700 uppercase mb-1">I. Motivo de Consulta</p>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap">{viewConsultation.chief_complaint}</p>
                  </div>
                )}

                {/* II. Historia Clinica */}
                {(viewConsultation.wears_glasses || viewConsultation.diabetes || viewConsultation.hypertension || viewConsultation.autoimmune_disease || viewConsultation.ocular_surgeries || viewConsultation.family_glaucoma || viewConsultation.family_macular_degeneration || viewConsultation.family_high_myopia || viewConsultation.current_medications || viewConsultation.allergies) && (
                  <div className="border rounded-lg p-3 space-y-3">
                    <p className="text-xs font-semibold text-pine-700 uppercase">II. Historia Clinica</p>
                    {(viewConsultation.wears_glasses || viewConsultation.ocular_surgeries || viewConsultation.ocular_trauma || viewConsultation.ocular_diseases) && (
                      <div>
                        <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Antecedentes Oculares</p>
                        <div className="text-sm space-y-0.5">
                          {viewConsultation.wears_glasses && <p><span className="text-slate-500">Usa lentes:</span> Si{viewConsultation.glasses_since ? `, desde ${viewConsultation.glasses_since}` : ''}{viewConsultation.glasses_type ? ` (${viewConsultation.glasses_type})` : ''}</p>}
                          {viewConsultation.ocular_surgeries && <p><span className="text-slate-500">Cirugias:</span> {viewConsultation.ocular_surgeries}</p>}
                          {viewConsultation.ocular_trauma && <p><span className="text-slate-500">Traumatismos:</span> {viewConsultation.ocular_trauma}</p>}
                          {viewConsultation.ocular_diseases && <p><span className="text-slate-500">Enfermedades:</span> {viewConsultation.ocular_diseases}</p>}
                        </div>
                      </div>
                    )}
                    {(viewConsultation.diabetes || viewConsultation.hypertension || viewConsultation.autoimmune_disease || viewConsultation.current_medications || viewConsultation.allergies) && (
                      <div className="pt-2 border-t">
                        <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Antecedentes Sistemicos</p>
                        <div className="flex flex-wrap gap-1.5 mb-1">
                          {viewConsultation.diabetes && <span className="px-2 py-0.5 bg-amber-50 text-amber-800 rounded text-xs font-medium">Diabetes</span>}
                          {viewConsultation.hypertension && <span className="px-2 py-0.5 bg-red-50 text-red-800 rounded text-xs font-medium">Hipertension</span>}
                          {viewConsultation.autoimmune_disease && <span className="px-2 py-0.5 bg-purple-50 text-purple-800 rounded text-xs font-medium">Autoinmune: {viewConsultation.autoimmune_details || 'Si'}</span>}
                        </div>
                        <div className="text-sm space-y-0.5">
                          {viewConsultation.current_medications && <p><span className="text-slate-500">Medicamentos:</span> {viewConsultation.current_medications}</p>}
                          {viewConsultation.allergies && <p><span className="text-slate-500">Alergias:</span> {viewConsultation.allergies}</p>}
                        </div>
                      </div>
                    )}
                    {(viewConsultation.family_glaucoma || viewConsultation.family_macular_degeneration || viewConsultation.family_high_myopia || viewConsultation.family_other_history) && (
                      <div className="pt-2 border-t">
                        <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Antecedentes Familiares</p>
                        <div className="flex flex-wrap gap-1.5">
                          {viewConsultation.family_glaucoma && <span className="px-2 py-0.5 bg-blue-50 text-blue-800 rounded text-xs font-medium">Glaucoma{viewConsultation.family_glaucoma_relationship ? ` (${viewConsultation.family_glaucoma_relationship})` : ''}</span>}
                          {viewConsultation.family_macular_degeneration && <span className="px-2 py-0.5 bg-blue-50 text-blue-800 rounded text-xs font-medium">Deg. Macular{viewConsultation.family_macular_relationship ? ` (${viewConsultation.family_macular_relationship})` : ''}</span>}
                          {viewConsultation.family_high_myopia && <span className="px-2 py-0.5 bg-blue-50 text-blue-800 rounded text-xs font-medium">Miopia Alta{viewConsultation.family_high_myopia_relationship ? ` (${viewConsultation.family_high_myopia_relationship})` : ''}</span>}
                        </div>
                        {viewConsultation.family_other_history && <p className="text-sm text-slate-600 mt-1">Otros: {viewConsultation.family_other_history}</p>}
                      </div>
                    )}
                  </div>
                )}

                {/* III. Agudeza Visual */}
                {(viewConsultation.va_distance_without_rx_od || viewConsultation.va_distance_without_rx_oi || viewConsultation.va_distance_with_rx_od || viewConsultation.va_near_without_rx_od || viewConsultation.va_pinhole_od) && (
                  <div className="border rounded-lg p-3">
                    <p className="text-xs font-semibold text-pine-700 uppercase mb-2">III. Agudeza Visual {viewConsultation.visual_acuity_method ? `(${viewConsultation.visual_acuity_method})` : ''}</p>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-1 text-xs text-slate-500 uppercase">Medicion</th>
                          <th className="text-center py-1 text-xs text-blue-700 uppercase">OD</th>
                          <th className="text-center py-1 text-xs text-green-700 uppercase">OI</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          { label: 'AV Lejos sin Rx', od: viewConsultation.va_distance_without_rx_od, oi: viewConsultation.va_distance_without_rx_oi },
                          { label: 'AV Lejos con Rx', od: viewConsultation.va_distance_with_rx_od, oi: viewConsultation.va_distance_with_rx_oi },
                          { label: 'AV Cerca sin Rx', od: viewConsultation.va_near_without_rx_od, oi: viewConsultation.va_near_without_rx_oi },
                          { label: 'AV Cerca con Rx', od: viewConsultation.va_near_with_rx_od, oi: viewConsultation.va_near_with_rx_oi },
                          { label: 'AV Estenopeico', od: viewConsultation.va_pinhole_od, oi: viewConsultation.va_pinhole_oi },
                        ].filter(r => r.od || r.oi).map((r) => (
                          <tr key={r.label} className="border-b last:border-0">
                            <td className="py-1 text-slate-700">{r.label}</td>
                            <td className="py-1 text-center font-mono">{r.od || '-'}</td>
                            <td className="py-1 text-center font-mono">{r.oi || '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* IV. Hallazgos y Plan */}
                {viewConsultation.anamnesis && (
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase mb-1">Historia / Anamnesis</p>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap">{viewConsultation.anamnesis}</p>
                  </div>
                )}
                {viewConsultation.findings && (
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase mb-1">Hallazgos</p>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap">{viewConsultation.findings}</p>
                  </div>
                )}
                {viewConsultation.diagnosis && (
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase mb-1">Diagnostico</p>
                    <p className="text-sm font-medium text-pine-800 bg-pine-50/50 p-2 rounded whitespace-pre-wrap">{viewConsultation.diagnosis}</p>
                  </div>
                )}
                {viewConsultation.treatment_plan && (
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase mb-1">Plan / Tratamiento</p>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap">{viewConsultation.treatment_plan}</p>
                  </div>
                )}
                {viewConsultation.recommendations && (
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase mb-1">Recomendaciones</p>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap">{viewConsultation.recommendations}</p>
                  </div>
                )}
                {viewConsultation.notes && (
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase mb-1">Observaciones</p>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap">{viewConsultation.notes}</p>
                  </div>
                )}

                {/* Recetas */}
                {((viewConsultation.eyeglass_prescriptions?.length || 0) + (viewConsultation.contact_prescriptions?.length || 0) + (viewConsultation.medical_prescriptions?.length || 0)) > 0 && (
                  <div className="pt-3 border-t">
                    <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Recetas Vinculadas</p>
                    {(viewConsultation.eyeglass_prescriptions || []).map((rx) => (
                      <div key={rx._id} className="flex items-center gap-2 text-sm py-1">
                        <Glasses className="w-3.5 h-3.5 text-blue-500" />
                        <span>Receta de Anteojos ({rx.created_at?.slice(0, 10)})</span>
                      </div>
                    ))}
                    {(viewConsultation.contact_prescriptions || []).map((rx) => (
                      <div key={rx._id} className="flex items-center gap-2 text-sm py-1">
                        <Eye className="w-3.5 h-3.5 text-teal-500" />
                        <span>Lentes de Contacto ({rx.created_at?.slice(0, 10)})</span>
                      </div>
                    ))}
                    {(viewConsultation.medical_prescriptions || []).map((rx) => (
                      <div key={rx._id} className="flex items-center gap-2 text-sm py-1">
                        <Pill className="w-3.5 h-3.5 text-purple-500" />
                        <span>Receta Medica ({rx.created_at?.slice(0, 10)})</span>
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex justify-end pt-2">
                  <Button variant="outline" onClick={() => setShowViewConsultation(false)}>Cerrar</Button>
                </div>
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* ===== EYEGLASS RX DIALOG ===== */}
      <Dialog open={showEyeglassRx} onOpenChange={setShowEyeglassRx}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Glasses className="w-5 h-5 text-blue-600" /> Receta de Anteojos</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-3">
              <div className="p-3 bg-blue-50 rounded-lg">
                <p className="text-xs font-bold text-blue-700 mb-2">OJO DERECHO (OD)</p>
                <div className="grid grid-cols-5 gap-2">
                  {['sphere', 'cylinder', 'axis', 'addition', 'dp'].map(f => (
                    <div key={f} className="space-y-1">
                      <Label className="text-[10px] uppercase">{f === 'dp' ? 'DP' : f === 'sphere' ? 'Esfera' : f === 'cylinder' ? 'Cilindro' : f === 'axis' ? 'Eje' : 'Adicion'}</Label>
                      <Input className="h-8 text-sm" value={eyeglassForm[`od_${f}`]}
                        onChange={(e) => setEyeglassForm(p => ({ ...p, [`od_${f}`]: e.target.value }))} data-testid={`p-rx-od-${f}`} />
                    </div>
                  ))}
                </div>
              </div>
              <div className="p-3 bg-green-50 rounded-lg">
                <p className="text-xs font-bold text-green-700 mb-2">OJO IZQUIERDO (OI)</p>
                <div className="grid grid-cols-5 gap-2">
                  {['sphere', 'cylinder', 'axis', 'addition', 'dp'].map(f => (
                    <div key={f} className="space-y-1">
                      <Label className="text-[10px] uppercase">{f === 'dp' ? 'DP' : f === 'sphere' ? 'Esfera' : f === 'cylinder' ? 'Cilindro' : f === 'axis' ? 'Eje' : 'Adicion'}</Label>
                      <Input className="h-8 text-sm" value={eyeglassForm[`oi_${f}`]}
                        onChange={(e) => setEyeglassForm(p => ({ ...p, [`oi_${f}`]: e.target.value }))} data-testid={`p-rx-oi-${f}`} />
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
              <Button className="bg-blue-600 hover:bg-blue-700" onClick={handleCreateEyeglassRx} data-testid="p-save-eyeglass-rx-btn">
                <Save className="w-4 h-4 mr-2" /> Guardar Receta
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ===== CONTACT LENS RX DIALOG ===== */}
      <Dialog open={showContactRx} onOpenChange={setShowContactRx}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Eye className="w-5 h-5 text-teal-600" /> Receta de Lentes de Contacto</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-3">
              <div className="p-3 bg-blue-50 rounded-lg">
                <p className="text-xs font-bold text-blue-700 mb-2">OJO DERECHO (OD)</p>
                <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                  {[{k:'power',l:'Poder'},{k:'bc',l:'CB'},{k:'dia',l:'DIA'},{k:'cylinder',l:'Cilindro'},{k:'axis',l:'Eje'},{k:'addition',l:'Adicion'}].map(({k,l}) => (
                    <div key={k} className="space-y-1">
                      <Label className="text-[10px] uppercase">{l}</Label>
                      <Input className="h-8 text-sm" value={contactForm[`od_${k}`]}
                        onChange={(e) => setContactForm(p => ({ ...p, [`od_${k}`]: e.target.value }))} />
                    </div>
                  ))}
                </div>
              </div>
              <div className="p-3 bg-green-50 rounded-lg">
                <p className="text-xs font-bold text-green-700 mb-2">OJO IZQUIERDO (OI)</p>
                <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                  {[{k:'power',l:'Poder'},{k:'bc',l:'CB'},{k:'dia',l:'DIA'},{k:'cylinder',l:'Cilindro'},{k:'axis',l:'Eje'},{k:'addition',l:'Adicion'}].map(({k,l}) => (
                    <div key={k} className="space-y-1">
                      <Label className="text-[10px] uppercase">{l}</Label>
                      <Input className="h-8 text-sm" value={contactForm[`oi_${k}`]}
                        onChange={(e) => setContactForm(p => ({ ...p, [`oi_${k}`]: e.target.value }))} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1">
                <Label className="text-xs">Marca</Label>
                <Input value={contactForm.brand} onChange={(e) => setContactForm(p => ({ ...p, brand: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Tipo de Lente</Label>
                <Input value={contactForm.lens_type} onChange={(e) => setContactForm(p => ({ ...p, lens_type: e.target.value }))} placeholder="Blanda, rigida..." />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Reemplazo</Label>
                <Input value={contactForm.replacement} onChange={(e) => setContactForm(p => ({ ...p, replacement: e.target.value }))} placeholder="Mensual, quincenal..." />
              </div>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Observaciones</Label>
              <Textarea value={contactForm.observations} onChange={(e) => setContactForm(p => ({ ...p, observations: e.target.value }))} rows={2} />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowContactRx(false)}>Cancelar</Button>
              <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleCreateContactRx} data-testid="p-save-contact-rx-btn">
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
              <Input value={medicalForm.diagnosis} onChange={(e) => setMedicalForm(f => ({ ...f, diagnosis: e.target.value }))} data-testid="p-med-rx-diagnosis" />
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <Label>Medicamentos</Label>
                <Button type="button" variant="outline" size="sm" onClick={addMedication} data-testid="p-add-medication-btn">
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
              <Textarea value={medicalForm.instructions} onChange={(e) => setMedicalForm(f => ({ ...f, instructions: e.target.value }))} rows={2} data-testid="p-med-rx-instructions" />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowMedicalRx(false)}>Cancelar</Button>
              <Button className="bg-purple-600 hover:bg-purple-700" onClick={handleCreateMedicalRx} data-testid="p-save-medical-rx-btn">
                <Save className="w-4 h-4 mr-2" /> Guardar Receta
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
