import React, { useState, useEffect } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Plus, Eye, Pill, Download, Trash2, CircleDot, MessageCircle } from 'lucide-react';
import { toast } from 'sonner';

// Nombre corto empresa para el mensaje
const OPTICA_NAME = 'Cortexia Optical';

const fmtEye = (sph, cyl, axis) => {
  const s = (v) => (v === '' || v == null ? '-' : v);
  return `Esf ${s(sph)} · Cil ${s(cyl)} · Eje ${s(axis)}`;
};

const buildWhatsAppMessage = (type, rx) => {
  const name = rx.patient_name || 'Estimado(a) paciente';
  const date = (rx.created_at || '').slice(0, 10);
  if (type === 'eyeglass') {
    const od = fmtEye(rx.od_sphere, rx.od_cylinder, rx.od_axis);
    const oi = fmtEye(rx.oi_sphere, rx.oi_cylinder, rx.oi_axis);
    const add = rx.od_addition || rx.oi_addition ? `\n  ADD OD: ${rx.od_addition || '-'} · OS: ${rx.oi_addition || '-'}` : '';
    const lens = rx.lens_type ? `\nTipo de lente: ${rx.lens_type}` : '';
    return `Hola ${name}, adjunto tu receta de anteojos del ${date}:\n\n  OD (derecho): ${od}\n  OS (izquierdo): ${oi}${add}${lens}\n\nGracias por confiar en ${OPTICA_NAME}.`;
  }
  if (type === 'contact') {
    const od = `Esf ${rx.od_power ?? '-'} · Cil ${rx.od_cylinder ?? '-'} · Eje ${rx.od_axis ?? '-'} · Add ${rx.od_addition ?? '-'} · Diam ${rx.od_dia ?? '-'} · CB ${rx.od_bc ?? '-'}`;
    const oi = `Esf ${rx.oi_power ?? '-'} · Cil ${rx.oi_cylinder ?? '-'} · Eje ${rx.oi_axis ?? '-'} · Add ${rx.oi_addition ?? '-'} · Diam ${rx.oi_dia ?? '-'} · CB ${rx.oi_bc ?? '-'}`;
    const brand = rx.brand ? `\nMarca: ${rx.brand}` : '';
    const repl = rx.replacement ? `\nReemplazo: ${rx.replacement}` : '';
    return `Hola ${name}, adjunto tu receta de lentes de contacto del ${date}:\n\n  OD: ${od}\n  OS: ${oi}${brand}${repl}\n\nGracias por confiar en ${OPTICA_NAME}.`;
  }
  if (type === 'medical') {
    const meds = (rx.medications || [])
      .map((m, i) => `  ${i + 1}. ${m.name || ''} - ${m.dosage || ''}${m.duration ? ` (${m.duration})` : ''}`)
      .join('\n');
    const dx = rx.diagnosis ? `\nDiagnostico: ${rx.diagnosis}` : '';
    const inst = rx.instructions ? `\nIndicaciones: ${rx.instructions}` : '';
    return `Hola ${name}, adjunto tu receta medica del ${date}:${dx}\n\nMedicamentos:\n${meds || '  (sin medicamentos)'}${inst}\n\nGracias por confiar en ${OPTICA_NAME}.`;
  }
  return `Hola ${name}, adjunto tu receta del ${date}.`;
};

const openWhatsAppFor = (type, rx) => {
  const raw = (rx.patient_whatsapp || rx.patient_phone || '').replace(/\D/g, '');
  if (!raw) {
    toast.error('Este paciente no tiene telefono ni WhatsApp registrado');
    return;
  }
  const msg = buildWhatsAppMessage(type, rx);
  window.open(`https://wa.me/${raw}?text=${encodeURIComponent(msg)}`, '_blank');
};

export default function PrescriptionsPage() {
  const [eyeglassPrescriptions, setEyeglassPrescriptions] = useState([]);
  const [medicalPrescriptions, setMedicalPrescriptions] = useState([]);
  const [contactPrescriptions, setContactPrescriptions] = useState([]);
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showEyeglassDialog, setShowEyeglassDialog] = useState(false);
  const [showMedicalDialog, setShowMedicalDialog] = useState(false);
  const [showContactDialog, setShowContactDialog] = useState(false);

  const [eyeglassForm, setEyeglassForm] = useState({
    patient_id: '',
    od_sphere: '', od_cylinder: '', od_axis: '', od_addition: '', od_dp: '',
    oi_sphere: '', oi_cylinder: '', oi_axis: '', oi_addition: '', oi_dp: '',
    observations: '', lens_type: '', frame_type: ''
  });

  const [medicalForm, setMedicalForm] = useState({
    patient_id: '',
    diagnosis: '',
    medications: [{ _uid: crypto.randomUUID(), name: '', dosage: '', duration: '' }],
    instructions: ''
  });

  const [contactForm, setContactForm] = useState({
    patient_id: '',
    od_power: '', od_bc: '', od_dia: '', od_cylinder: '', od_axis: '', od_addition: '',
    oi_power: '', oi_bc: '', oi_dia: '', oi_cylinder: '', oi_axis: '', oi_addition: '',
    brand: '', lens_type: '', replacement: '', observations: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [eyeglassRes, medicalRes, contactRes, patientsRes] = await Promise.all([
        api.get('/api/prescriptions/eyeglass'),
        api.get('/api/prescriptions/medical'),
        api.get('/api/prescriptions/contact'),
        api.get('/api/patients', { params: { limit: 200 } })
      ]);
      setEyeglassPrescriptions(eyeglassRes.data || []);
      setMedicalPrescriptions(medicalRes.data || []);
      setContactPrescriptions(contactRes.data || []);
      setPatients(patientsRes.data.patients || []);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleEyeglassSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...eyeglassForm,
        od_sphere: eyeglassForm.od_sphere ? parseFloat(eyeglassForm.od_sphere) : null,
        od_cylinder: eyeglassForm.od_cylinder ? parseFloat(eyeglassForm.od_cylinder) : null,
        od_axis: eyeglassForm.od_axis ? parseInt(eyeglassForm.od_axis) : null,
        od_addition: eyeglassForm.od_addition ? parseFloat(eyeglassForm.od_addition) : null,
        od_dp: eyeglassForm.od_dp ? parseFloat(eyeglassForm.od_dp) : null,
        oi_sphere: eyeglassForm.oi_sphere ? parseFloat(eyeglassForm.oi_sphere) : null,
        oi_cylinder: eyeglassForm.oi_cylinder ? parseFloat(eyeglassForm.oi_cylinder) : null,
        oi_axis: eyeglassForm.oi_axis ? parseInt(eyeglassForm.oi_axis) : null,
        oi_addition: eyeglassForm.oi_addition ? parseFloat(eyeglassForm.oi_addition) : null,
        oi_dp: eyeglassForm.oi_dp ? parseFloat(eyeglassForm.oi_dp) : null,
      };
      await api.post('/api/prescriptions/eyeglass', payload);
      toast.success('Receta creada exitosamente');
      setShowEyeglassDialog(false);
      setEyeglassForm({
        patient_id: '', od_sphere: '', od_cylinder: '', od_axis: '', od_addition: '', od_dp: '',
        oi_sphere: '', oi_cylinder: '', oi_axis: '', oi_addition: '', oi_dp: '',
        observations: '', lens_type: '', frame_type: ''
      });
      fetchData();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const handleMedicalSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/api/prescriptions/medical', medicalForm);
      toast.success('Receta médica creada');
      setShowMedicalDialog(false);
      setMedicalForm({
        patient_id: '', diagnosis: '',
        medications: [{ _uid: crypto.randomUUID(), name: '', dosage: '', duration: '' }],
        instructions: ''
      });
      fetchData();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const handleContactSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...contactForm,
        od_power: contactForm.od_power ? parseFloat(contactForm.od_power) : null,
        od_bc: contactForm.od_bc ? parseFloat(contactForm.od_bc) : null,
        od_dia: contactForm.od_dia ? parseFloat(contactForm.od_dia) : null,
        od_cylinder: contactForm.od_cylinder ? parseFloat(contactForm.od_cylinder) : null,
        od_axis: contactForm.od_axis ? parseInt(contactForm.od_axis) : null,
        od_addition: contactForm.od_addition ? parseFloat(contactForm.od_addition) : null,
        oi_power: contactForm.oi_power ? parseFloat(contactForm.oi_power) : null,
        oi_bc: contactForm.oi_bc ? parseFloat(contactForm.oi_bc) : null,
        oi_dia: contactForm.oi_dia ? parseFloat(contactForm.oi_dia) : null,
        oi_cylinder: contactForm.oi_cylinder ? parseFloat(contactForm.oi_cylinder) : null,
        oi_axis: contactForm.oi_axis ? parseInt(contactForm.oi_axis) : null,
        oi_addition: contactForm.oi_addition ? parseFloat(contactForm.oi_addition) : null,
      };
      await api.post('/api/prescriptions/contact', payload);
      toast.success('Receta de lentes de contacto creada');
      setShowContactDialog(false);
      setContactForm({
        patient_id: '',
        od_power: '', od_bc: '', od_dia: '', od_cylinder: '', od_axis: '', od_addition: '',
        oi_power: '', oi_bc: '', oi_dia: '', oi_cylinder: '', oi_axis: '', oi_addition: '',
        brand: '', lens_type: '', replacement: '', observations: ''
      });
      fetchData();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const addMedication = () => {
    setMedicalForm({
      ...medicalForm,
      medications: [...medicalForm.medications, { _uid: crypto.randomUUID(), name: '', dosage: '', duration: '' }]
    });
  };

  const removeMedication = (index) => {
    setMedicalForm({
      ...medicalForm,
      medications: medicalForm.medications.filter((_, i) => i !== index)
    });
  };

  const updateMedication = (index, field, value) => {
    const newMeds = [...medicalForm.medications];
    newMeds[index][field] = value;
    setMedicalForm({ ...medicalForm, medications: newMeds });
  };

  const downloadPdf = async (type, id) => {
    try {
      const response = await api.get(`/api/prescriptions/${type}/${id}/pdf`, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      window.open(url, '_blank');
    } catch (err) {
      toast.error('Error al generar PDF');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="prescriptions-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Recetas</h1>
          <p className="text-slate-500 mt-1">Gestiona recetas de anteojos, lentes de contacto y médicas</p>
        </div>
      </div>

      <Tabs defaultValue="eyeglass">
        <TabsList className="mb-4">
          <TabsTrigger value="eyeglass">
            <Eye className="w-4 h-4 mr-2" /> Anteojos
          </TabsTrigger>
          <TabsTrigger value="contact">
            <CircleDot className="w-4 h-4 mr-2" /> Lentes de Contacto
          </TabsTrigger>
          <TabsTrigger value="medical">
            <Pill className="w-4 h-4 mr-2" /> Médicas
          </TabsTrigger>
        </TabsList>

        {/* Eyeglass Prescriptions */}
        <TabsContent value="eyeglass">
          <Card className="border-slate-200/80">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="font-heading text-lg">Recetas de Anteojos</CardTitle>
              <Dialog open={showEyeglassDialog} onOpenChange={setShowEyeglassDialog}>
                <DialogTrigger asChild>
                  <Button className="bg-pine-900 hover:bg-pine-700" data-testid="add-eyeglass-rx-btn">
                    <Plus className="w-4 h-4 mr-2" /> Nueva Receta
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle className="font-heading">Nueva Receta de Anteojos</DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleEyeglassSubmit} className="space-y-6">
                    <div className="space-y-2">
                      <Label>Paciente *</Label>
                      <Select value={eyeglassForm.patient_id} onValueChange={(v) => setEyeglassForm({...eyeglassForm, patient_id: v})}>
                        <SelectTrigger data-testid="rx-patient">
                          <SelectValue placeholder="Seleccionar paciente" />
                        </SelectTrigger>
                        <SelectContent>
                          {patients.map((p) => (
                            <SelectItem key={p._id} value={p._id}>
                              {p.first_name} {p.last_name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    {/* OD - Ojo Derecho */}
                    <div className="p-4 rounded-lg bg-blue-50 border border-blue-200">
                      <h3 className="font-semibold text-blue-900 mb-3">Ojo Derecho (OD)</h3>
                      <div className="grid grid-cols-5 gap-3">
                        <div className="space-y-1">
                          <Label className="text-xs">Esfera</Label>
                          <Input type="number" step="0.25" value={eyeglassForm.od_sphere} onChange={(e) => setEyeglassForm({...eyeglassForm, od_sphere: e.target.value})} placeholder="-2.50" className="h-9" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Cilindro</Label>
                          <Input type="number" step="0.25" value={eyeglassForm.od_cylinder} onChange={(e) => setEyeglassForm({...eyeglassForm, od_cylinder: e.target.value})} placeholder="-0.75" className="h-9" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Eje</Label>
                          <Input type="number" value={eyeglassForm.od_axis} onChange={(e) => setEyeglassForm({...eyeglassForm, od_axis: e.target.value})} placeholder="90" className="h-9" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Adición</Label>
                          <Input type="number" step="0.25" value={eyeglassForm.od_addition} onChange={(e) => setEyeglassForm({...eyeglassForm, od_addition: e.target.value})} placeholder="+1.50" className="h-9" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">D.P.</Label>
                          <Input type="number" step="0.5" value={eyeglassForm.od_dp} onChange={(e) => setEyeglassForm({...eyeglassForm, od_dp: e.target.value})} placeholder="32" className="h-9" />
                        </div>
                      </div>
                    </div>

                    {/* OS - Ojo Izquierdo */}
                    <div className="p-4 rounded-lg bg-green-50 border border-green-200">
                      <h3 className="font-semibold text-green-900 mb-3">Ojo Izquierdo (OS)</h3>
                      <div className="grid grid-cols-5 gap-3">
                        <div className="space-y-1">
                          <Label className="text-xs">Esfera</Label>
                          <Input type="number" step="0.25" value={eyeglassForm.oi_sphere} onChange={(e) => setEyeglassForm({...eyeglassForm, oi_sphere: e.target.value})} placeholder="-2.25" className="h-9" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Cilindro</Label>
                          <Input type="number" step="0.25" value={eyeglassForm.oi_cylinder} onChange={(e) => setEyeglassForm({...eyeglassForm, oi_cylinder: e.target.value})} placeholder="-0.50" className="h-9" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Eje</Label>
                          <Input type="number" value={eyeglassForm.oi_axis} onChange={(e) => setEyeglassForm({...eyeglassForm, oi_axis: e.target.value})} placeholder="85" className="h-9" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Adición</Label>
                          <Input type="number" step="0.25" value={eyeglassForm.oi_addition} onChange={(e) => setEyeglassForm({...eyeglassForm, oi_addition: e.target.value})} placeholder="+1.50" className="h-9" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">D.P.</Label>
                          <Input type="number" step="0.5" value={eyeglassForm.oi_dp} onChange={(e) => setEyeglassForm({...eyeglassForm, oi_dp: e.target.value})} placeholder="32" className="h-9" />
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Tipo de Lente</Label>
                        <Select value={eyeglassForm.lens_type} onValueChange={(v) => setEyeglassForm({...eyeglassForm, lens_type: v})}>
                          <SelectTrigger><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Monofocal">Monofocal</SelectItem>
                            <SelectItem value="Bifocal">Bifocal</SelectItem>
                            <SelectItem value="Progresivo">Progresivo</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>Tipo de Armazón</Label>
                        <Input value={eyeglassForm.frame_type} onChange={(e) => setEyeglassForm({...eyeglassForm, frame_type: e.target.value})} placeholder="Ej: Metálico, Pasta" />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label>Observaciones</Label>
                      <Textarea value={eyeglassForm.observations} onChange={(e) => setEyeglassForm({...eyeglassForm, observations: e.target.value})} rows={2} />
                    </div>

                    <div className="flex justify-end gap-2 pt-4">
                      <Button type="button" variant="outline" onClick={() => setShowEyeglassDialog(false)}>Cancelar</Button>
                      <Button type="submit" className="bg-pine-900 hover:bg-pine-700">Guardar Receta</Button>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow className="data-table-header">
                    <TableHead>Fecha</TableHead>
                    <TableHead>Paciente</TableHead>
                    <TableHead className="text-blue-700">OD</TableHead>
                    <TableHead className="text-green-700">OS</TableHead>
                    <TableHead>Tipo</TableHead>
                    <TableHead className="text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {eyeglassPrescriptions.map((rx) => (
                    <TableRow key={rx._id} className="data-table-row">
                      <TableCell>{rx.created_at?.slice(0, 10)}</TableCell>
                      <TableCell className="font-medium">{rx.patient_name || 'Paciente'}</TableCell>
                      <TableCell className="text-sm text-blue-700 font-medium">{rx.od_sphere || '-'} / {rx.od_cylinder || '-'} x {rx.od_axis || '-'}</TableCell>
                      <TableCell className="text-sm text-green-700 font-medium">{rx.oi_sphere || '-'} / {rx.oi_cylinder || '-'} x {rx.oi_axis || '-'}</TableCell>
                      <TableCell>{rx.lens_type || '-'}</TableCell>
                      <TableCell className="text-right space-x-1">
                        <Button size="sm" variant="outline" onClick={() => openWhatsAppFor('eyeglass', rx)} className="border-green-300 text-green-700 hover:bg-green-50" data-testid={`send-rx-eyeglass-wa-${rx._id}`}>
                          <MessageCircle className="w-4 h-4 mr-1" /> WhatsApp
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => downloadPdf('eyeglass', rx._id)} data-testid={`download-rx-eyeglass-${rx._id}`}><Download className="w-4 h-4 mr-1" /> PDF</Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {eyeglassPrescriptions.length === 0 && (
                    <TableRow><TableCell colSpan={6} className="text-center py-8 text-slate-500">No hay recetas de anteojos</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Contact Lens Prescriptions */}
        <TabsContent value="contact">
          <Card className="border-slate-200/80">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="font-heading text-lg">Recetas de Lentes de Contacto</CardTitle>
              <Dialog open={showContactDialog} onOpenChange={setShowContactDialog}>
                <DialogTrigger asChild>
                  <Button className="bg-pine-900 hover:bg-pine-700" data-testid="add-contact-rx-btn">
                    <Plus className="w-4 h-4 mr-2" /> Nueva Receta
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle className="font-heading">Nueva Receta de Lentes de Contacto</DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleContactSubmit} className="space-y-6">
                    <div className="space-y-2">
                      <Label>Paciente *</Label>
                      <Select value={contactForm.patient_id} onValueChange={(v) => setContactForm({...contactForm, patient_id: v})}>
                        <SelectTrigger data-testid="contact-rx-patient">
                          <SelectValue placeholder="Seleccionar paciente" />
                        </SelectTrigger>
                        <SelectContent>
                          {patients.map((p) => (
                            <SelectItem key={p._id} value={p._id}>
                              {p.first_name} {p.last_name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    {/* OD - Ojo Derecho */}
                    <div className="p-4 rounded-lg bg-blue-50 border border-blue-200">
                      <h3 className="font-semibold text-blue-900 mb-3">Ojo Derecho (OD)</h3>
                      <div className="grid grid-cols-6 gap-3">
                        <div className="space-y-1">
                          <Label className="text-xs">Esfera</Label>
                          <Input type="number" step="0.25" value={contactForm.od_power} onChange={(e) => setContactForm({...contactForm, od_power: e.target.value})} placeholder="-2.50" className="h-9" data-testid="od-esfera" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Cilindro</Label>
                          <Input type="number" step="0.25" value={contactForm.od_cylinder} onChange={(e) => setContactForm({...contactForm, od_cylinder: e.target.value})} placeholder="-0.75" className="h-9" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Eje</Label>
                          <Input type="number" value={contactForm.od_axis} onChange={(e) => setContactForm({...contactForm, od_axis: e.target.value})} placeholder="180" className="h-9" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Adición</Label>
                          <Input type="number" step="0.25" value={contactForm.od_addition} onChange={(e) => setContactForm({...contactForm, od_addition: e.target.value})} placeholder="+1.50" className="h-9" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Diametro</Label>
                          <Input type="number" step="0.1" value={contactForm.od_dia} onChange={(e) => setContactForm({...contactForm, od_dia: e.target.value})} placeholder="14.2" className="h-9" data-testid="od-dia" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Curva Base</Label>
                          <Input type="number" step="0.1" value={contactForm.od_bc} onChange={(e) => setContactForm({...contactForm, od_bc: e.target.value})} placeholder="8.6" className="h-9" data-testid="od-bc" />
                        </div>
                      </div>
                    </div>

                    {/* OS - Ojo Izquierdo */}
                    <div className="p-4 rounded-lg bg-green-50 border border-green-200">
                      <h3 className="font-semibold text-green-900 mb-3">Ojo Izquierdo (OS)</h3>
                      <div className="grid grid-cols-6 gap-3">
                        <div className="space-y-1">
                          <Label className="text-xs">Esfera</Label>
                          <Input type="number" step="0.25" value={contactForm.oi_power} onChange={(e) => setContactForm({...contactForm, oi_power: e.target.value})} placeholder="-2.25" className="h-9" data-testid="oi-esfera" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Cilindro</Label>
                          <Input type="number" step="0.25" value={contactForm.oi_cylinder} onChange={(e) => setContactForm({...contactForm, oi_cylinder: e.target.value})} placeholder="-0.50" className="h-9" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Eje</Label>
                          <Input type="number" value={contactForm.oi_axis} onChange={(e) => setContactForm({...contactForm, oi_axis: e.target.value})} placeholder="180" className="h-9" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Adición</Label>
                          <Input type="number" step="0.25" value={contactForm.oi_addition} onChange={(e) => setContactForm({...contactForm, oi_addition: e.target.value})} placeholder="+1.50" className="h-9" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Diametro</Label>
                          <Input type="number" step="0.1" value={contactForm.oi_dia} onChange={(e) => setContactForm({...contactForm, oi_dia: e.target.value})} placeholder="14.2" className="h-9" data-testid="oi-dia" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Curva Base</Label>
                          <Input type="number" step="0.1" value={contactForm.oi_bc} onChange={(e) => setContactForm({...contactForm, oi_bc: e.target.value})} placeholder="8.6" className="h-9" data-testid="oi-bc" />
                        </div>
                      </div>
                    </div>

                    {/* Product Info */}
                    <div className="grid grid-cols-3 gap-4">
                      <div className="space-y-2">
                        <Label>Marca</Label>
                        <Input value={contactForm.brand} onChange={(e) => setContactForm({...contactForm, brand: e.target.value})} placeholder="Ej: Acuvue, Air Optix" data-testid="contact-brand" />
                      </div>
                      <div className="space-y-2">
                        <Label>Tipo de Lente</Label>
                        <Select value={contactForm.lens_type} onValueChange={(v) => setContactForm({...contactForm, lens_type: v})}>
                          <SelectTrigger data-testid="contact-lens-type"><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Blando Esférico">Blando Esférico</SelectItem>
                            <SelectItem value="Blando Tórico">Blando Tórico</SelectItem>
                            <SelectItem value="Blando Multifocal">Blando Multifocal</SelectItem>
                            <SelectItem value="Rígido Gas Permeable">Rígido Gas Permeable</SelectItem>
                            <SelectItem value="Híbrido">Híbrido</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>Reemplazo</Label>
                        <Select value={contactForm.replacement} onValueChange={(v) => setContactForm({...contactForm, replacement: v})}>
                          <SelectTrigger data-testid="contact-replacement"><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Diario">Diario</SelectItem>
                            <SelectItem value="Quincenal">Quincenal</SelectItem>
                            <SelectItem value="Mensual">Mensual</SelectItem>
                            <SelectItem value="Trimestral">Trimestral</SelectItem>
                            <SelectItem value="Anual">Anual</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label>Observaciones</Label>
                      <Textarea value={contactForm.observations} onChange={(e) => setContactForm({...contactForm, observations: e.target.value})} rows={2} placeholder="Instrucciones de uso, cuidados, etc." />
                    </div>

                    <div className="flex justify-end gap-2 pt-4">
                      <Button type="button" variant="outline" onClick={() => setShowContactDialog(false)}>Cancelar</Button>
                      <Button type="submit" className="bg-pine-900 hover:bg-pine-700" data-testid="save-contact-rx">Guardar Receta</Button>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow className="data-table-header">
                    <TableHead>Fecha</TableHead>
                    <TableHead>Paciente</TableHead>
                    <TableHead className="text-blue-700">OD (Esf/Cil/Eje/Add/Diam/CB)</TableHead>
                    <TableHead className="text-green-700">OS (Esf/Cil/Eje/Add/Diam/CB)</TableHead>
                    <TableHead>Marca</TableHead>
                    <TableHead>Reemplazo</TableHead>
                    <TableHead className="text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {contactPrescriptions.map((rx) => (
                    <TableRow key={rx._id} className="data-table-row">
                      <TableCell>{rx.created_at?.slice(0, 10)}</TableCell>
                      <TableCell className="font-medium">{rx.patient_name || 'Paciente'}</TableCell>
                      <TableCell className="text-sm text-blue-700 font-medium">{rx.od_power || '-'} / {rx.od_cylinder || '-'} x {rx.od_axis || '-'} · Add {rx.od_addition || '-'} · Diam {rx.od_dia || '-'} · CB {rx.od_bc || '-'}</TableCell>
                      <TableCell className="text-sm text-green-700 font-medium">{rx.oi_power || '-'} / {rx.oi_cylinder || '-'} x {rx.oi_axis || '-'} · Add {rx.oi_addition || '-'} · Diam {rx.oi_dia || '-'} · CB {rx.oi_bc || '-'}</TableCell>
                      <TableCell>{rx.brand || '-'}</TableCell>
                      <TableCell>{rx.replacement || '-'}</TableCell>
                      <TableCell className="text-right space-x-1">
                        <Button size="sm" variant="outline" onClick={() => openWhatsAppFor('contact', rx)} className="border-green-300 text-green-700 hover:bg-green-50" data-testid={`send-rx-contact-wa-${rx._id}`}>
                          <MessageCircle className="w-4 h-4 mr-1" /> WhatsApp
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => downloadPdf('contact', rx._id)} data-testid={`download-rx-contact-${rx._id}`}><Download className="w-4 h-4 mr-1" /> PDF</Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {contactPrescriptions.length === 0 && (
                    <TableRow><TableCell colSpan={7} className="text-center py-8 text-slate-500">No hay recetas de lentes de contacto</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Medical Prescriptions */}
        <TabsContent value="medical">
          <Card className="border-slate-200/80">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="font-heading text-lg">Recetas Médicas</CardTitle>
              <Dialog open={showMedicalDialog} onOpenChange={setShowMedicalDialog}>
                <DialogTrigger asChild>
                  <Button className="bg-pine-900 hover:bg-pine-700" data-testid="add-medical-rx-btn">
                    <Plus className="w-4 h-4 mr-2" /> Nueva Receta
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle className="font-heading">Nueva Receta Médica</DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleMedicalSubmit} className="space-y-4">
                    <div className="space-y-2">
                      <Label>Paciente *</Label>
                      <Select value={medicalForm.patient_id} onValueChange={(v) => setMedicalForm({...medicalForm, patient_id: v})}>
                        <SelectTrigger data-testid="medical-rx-patient"><SelectValue placeholder="Seleccionar paciente" /></SelectTrigger>
                        <SelectContent>
                          {patients.map((p) => (
                            <SelectItem key={p._id} value={p._id}>{p.first_name} {p.last_name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2">
                      <Label>Diagnóstico</Label>
                      <Textarea value={medicalForm.diagnosis} onChange={(e) => setMedicalForm({...medicalForm, diagnosis: e.target.value})} rows={2} />
                    </div>

                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Label>Medicamentos</Label>
                        <Button type="button" size="sm" variant="outline" onClick={addMedication}><Plus className="w-4 h-4 mr-1" /> Agregar</Button>
                      </div>
                      {medicalForm.medications.map((med, idx) => (
                        <div key={med._uid || idx} className="flex gap-2 items-start">
                          <Input placeholder="Medicamento" value={med.name} onChange={(e) => updateMedication(idx, 'name', e.target.value)} className="flex-1" />
                          <Input placeholder="Dosis" value={med.dosage} onChange={(e) => updateMedication(idx, 'dosage', e.target.value)} className="w-28" />
                          <Input placeholder="Duración" value={med.duration} onChange={(e) => updateMedication(idx, 'duration', e.target.value)} className="w-28" />
                          {medicalForm.medications.length > 1 && (
                            <Button type="button" size="icon" variant="ghost" onClick={() => removeMedication(idx)}><Trash2 className="w-4 h-4 text-red-500" /></Button>
                          )}
                        </div>
                      ))}
                    </div>

                    <div className="space-y-2">
                      <Label>Instrucciones</Label>
                      <Textarea value={medicalForm.instructions} onChange={(e) => setMedicalForm({...medicalForm, instructions: e.target.value})} rows={2} />
                    </div>

                    <div className="flex justify-end gap-2 pt-4">
                      <Button type="button" variant="outline" onClick={() => setShowMedicalDialog(false)}>Cancelar</Button>
                      <Button type="submit" className="bg-pine-900 hover:bg-pine-700">Guardar Receta</Button>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow className="data-table-header">
                    <TableHead>Fecha</TableHead>
                    <TableHead>Paciente</TableHead>
                    <TableHead>Diagnóstico</TableHead>
                    <TableHead>Medicamentos</TableHead>
                    <TableHead className="text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {medicalPrescriptions.map((rx) => (
                    <TableRow key={rx._id} className="data-table-row">
                      <TableCell>{rx.created_at?.slice(0, 10)}</TableCell>
                      <TableCell className="font-medium">{rx.patient_name || 'Paciente'}</TableCell>
                      <TableCell className="max-w-[200px] truncate">{rx.diagnosis || '-'}</TableCell>
                      <TableCell>{rx.medications?.length || 0} medicamento(s)</TableCell>
                      <TableCell className="text-right space-x-1">
                        <Button size="sm" variant="outline" onClick={() => openWhatsAppFor('medical', rx)} className="border-green-300 text-green-700 hover:bg-green-50" data-testid={`send-rx-medical-wa-${rx._id}`}>
                          <MessageCircle className="w-4 h-4 mr-1" /> WhatsApp
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => downloadPdf('medical', rx._id)} data-testid={`download-rx-medical-${rx._id}`}><Download className="w-4 h-4 mr-1" /> PDF</Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {medicalPrescriptions.length === 0 && (
                    <TableRow><TableCell colSpan={5} className="text-center py-8 text-slate-500">No hay recetas médicas</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
