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
import { Plus, Eye, Pill, FileText, Download, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

export default function PrescriptionsPage() {
  const [eyeglassPrescriptions, setEyeglassPrescriptions] = useState([]);
  const [medicalPrescriptions, setMedicalPrescriptions] = useState([]);
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showEyeglassDialog, setShowEyeglassDialog] = useState(false);
  const [showMedicalDialog, setShowMedicalDialog] = useState(false);

  const [eyeglassForm, setEyeglassForm] = useState({
    patient_id: '',
    od_sphere: '', od_cylinder: '', od_axis: '', od_addition: '', od_dp: '',
    oi_sphere: '', oi_cylinder: '', oi_axis: '', oi_addition: '', oi_dp: '',
    observations: '', lens_type: '', frame_type: ''
  });

  const [medicalForm, setMedicalForm] = useState({
    patient_id: '',
    diagnosis: '',
    medications: [{ name: '', dosage: '', duration: '' }],
    instructions: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [eyeglassRes, medicalRes, patientsRes] = await Promise.all([
        api.get('/api/prescriptions/eyeglass'),
        api.get('/api/prescriptions/medical'),
        api.get('/api/patients', { params: { limit: 200 } })
      ]);
      setEyeglassPrescriptions(eyeglassRes.data || []);
      setMedicalPrescriptions(medicalRes.data || []);
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
        medications: [{ name: '', dosage: '', duration: '' }],
        instructions: ''
      });
      fetchData();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const addMedication = () => {
    setMedicalForm({
      ...medicalForm,
      medications: [...medicalForm.medications, { name: '', dosage: '', duration: '' }]
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

  const downloadPdf = (type, id) => {
    window.open(`${process.env.REACT_APP_BACKEND_URL}/api/prescriptions/${type}/${id}/pdf`, '_blank');
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
          <p className="text-slate-500 mt-1">Gestiona recetas de anteojos y médicas</p>
        </div>
      </div>

      <Tabs defaultValue="eyeglass">
        <TabsList className="mb-4">
          <TabsTrigger value="eyeglass">
            <Eye className="w-4 h-4 mr-2" /> Recetas de Anteojos
          </TabsTrigger>
          <TabsTrigger value="medical">
            <Pill className="w-4 h-4 mr-2" /> Recetas Médicas
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
                          <Input
                            type="number"
                            step="0.25"
                            value={eyeglassForm.od_sphere}
                            onChange={(e) => setEyeglassForm({...eyeglassForm, od_sphere: e.target.value})}
                            placeholder="-2.50"
                            className="h-9"
                            data-testid="od-sphere"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Cilindro</Label>
                          <Input
                            type="number"
                            step="0.25"
                            value={eyeglassForm.od_cylinder}
                            onChange={(e) => setEyeglassForm({...eyeglassForm, od_cylinder: e.target.value})}
                            placeholder="-0.75"
                            className="h-9"
                            data-testid="od-cylinder"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Eje</Label>
                          <Input
                            type="number"
                            value={eyeglassForm.od_axis}
                            onChange={(e) => setEyeglassForm({...eyeglassForm, od_axis: e.target.value})}
                            placeholder="90"
                            className="h-9"
                            data-testid="od-axis"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Adición</Label>
                          <Input
                            type="number"
                            step="0.25"
                            value={eyeglassForm.od_addition}
                            onChange={(e) => setEyeglassForm({...eyeglassForm, od_addition: e.target.value})}
                            placeholder="+1.50"
                            className="h-9"
                            data-testid="od-addition"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">D.P.</Label>
                          <Input
                            type="number"
                            step="0.5"
                            value={eyeglassForm.od_dp}
                            onChange={(e) => setEyeglassForm({...eyeglassForm, od_dp: e.target.value})}
                            placeholder="32"
                            className="h-9"
                            data-testid="od-dp"
                          />
                        </div>
                      </div>
                    </div>

                    {/* OI - Ojo Izquierdo */}
                    <div className="p-4 rounded-lg bg-green-50 border border-green-200">
                      <h3 className="font-semibold text-green-900 mb-3">Ojo Izquierdo (OI)</h3>
                      <div className="grid grid-cols-5 gap-3">
                        <div className="space-y-1">
                          <Label className="text-xs">Esfera</Label>
                          <Input
                            type="number"
                            step="0.25"
                            value={eyeglassForm.oi_sphere}
                            onChange={(e) => setEyeglassForm({...eyeglassForm, oi_sphere: e.target.value})}
                            placeholder="-2.25"
                            className="h-9"
                            data-testid="oi-sphere"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Cilindro</Label>
                          <Input
                            type="number"
                            step="0.25"
                            value={eyeglassForm.oi_cylinder}
                            onChange={(e) => setEyeglassForm({...eyeglassForm, oi_cylinder: e.target.value})}
                            placeholder="-0.50"
                            className="h-9"
                            data-testid="oi-cylinder"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Eje</Label>
                          <Input
                            type="number"
                            value={eyeglassForm.oi_axis}
                            onChange={(e) => setEyeglassForm({...eyeglassForm, oi_axis: e.target.value})}
                            placeholder="85"
                            className="h-9"
                            data-testid="oi-axis"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Adición</Label>
                          <Input
                            type="number"
                            step="0.25"
                            value={eyeglassForm.oi_addition}
                            onChange={(e) => setEyeglassForm({...eyeglassForm, oi_addition: e.target.value})}
                            placeholder="+1.50"
                            className="h-9"
                            data-testid="oi-addition"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">D.P.</Label>
                          <Input
                            type="number"
                            step="0.5"
                            value={eyeglassForm.oi_dp}
                            onChange={(e) => setEyeglassForm({...eyeglassForm, oi_dp: e.target.value})}
                            placeholder="32"
                            className="h-9"
                            data-testid="oi-dp"
                          />
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Tipo de Lente</Label>
                        <Select value={eyeglassForm.lens_type} onValueChange={(v) => setEyeglassForm({...eyeglassForm, lens_type: v})}>
                          <SelectTrigger>
                            <SelectValue placeholder="Seleccionar" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Monofocal">Monofocal</SelectItem>
                            <SelectItem value="Bifocal">Bifocal</SelectItem>
                            <SelectItem value="Progresivo">Progresivo</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>Tipo de Armazón</Label>
                        <Input
                          value={eyeglassForm.frame_type}
                          onChange={(e) => setEyeglassForm({...eyeglassForm, frame_type: e.target.value})}
                          placeholder="Ej: Metálico, Pasta"
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label>Observaciones</Label>
                      <Textarea
                        value={eyeglassForm.observations}
                        onChange={(e) => setEyeglassForm({...eyeglassForm, observations: e.target.value})}
                        rows={2}
                      />
                    </div>

                    <div className="flex justify-end gap-2 pt-4">
                      <Button type="button" variant="outline" onClick={() => setShowEyeglassDialog(false)}>
                        Cancelar
                      </Button>
                      <Button type="submit" className="bg-pine-900 hover:bg-pine-700" data-testid="save-eyeglass-rx">
                        Guardar Receta
                      </Button>
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
                    <TableHead>OD</TableHead>
                    <TableHead>OI</TableHead>
                    <TableHead>Tipo</TableHead>
                    <TableHead className="text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {eyeglassPrescriptions.map((rx) => (
                    <TableRow key={rx._id} className="data-table-row">
                      <TableCell>{rx.created_at?.slice(0, 10)}</TableCell>
                      <TableCell className="font-medium">{rx.patient_name || 'Paciente'}</TableCell>
                      <TableCell className="text-sm">
                        {rx.od_sphere || '-'} / {rx.od_cylinder || '-'} x {rx.od_axis || '-'}
                      </TableCell>
                      <TableCell className="text-sm">
                        {rx.oi_sphere || '-'} / {rx.oi_cylinder || '-'} x {rx.oi_axis || '-'}
                      </TableCell>
                      <TableCell>{rx.lens_type || '-'}</TableCell>
                      <TableCell className="text-right">
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => downloadPdf('eyeglass', rx._id)}
                          data-testid={`download-eyeglass-${rx._id}`}
                        >
                          <Download className="w-4 h-4 mr-1" /> PDF
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {eyeglassPrescriptions.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-slate-500">
                        No hay recetas de anteojos
                      </TableCell>
                    </TableRow>
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
                        <SelectTrigger data-testid="medical-rx-patient">
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

                    <div className="space-y-2">
                      <Label>Diagnóstico</Label>
                      <Textarea
                        value={medicalForm.diagnosis}
                        onChange={(e) => setMedicalForm({...medicalForm, diagnosis: e.target.value})}
                        rows={2}
                        data-testid="medical-diagnosis"
                      />
                    </div>

                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Label>Medicamentos</Label>
                        <Button type="button" size="sm" variant="outline" onClick={addMedication}>
                          <Plus className="w-4 h-4 mr-1" /> Agregar
                        </Button>
                      </div>
                      {medicalForm.medications.map((med, idx) => (
                        <div key={idx} className="flex gap-2 items-start">
                          <Input
                            placeholder="Medicamento"
                            value={med.name}
                            onChange={(e) => updateMedication(idx, 'name', e.target.value)}
                            className="flex-1"
                            data-testid={`med-name-${idx}`}
                          />
                          <Input
                            placeholder="Dosis"
                            value={med.dosage}
                            onChange={(e) => updateMedication(idx, 'dosage', e.target.value)}
                            className="w-28"
                            data-testid={`med-dosage-${idx}`}
                          />
                          <Input
                            placeholder="Duración"
                            value={med.duration}
                            onChange={(e) => updateMedication(idx, 'duration', e.target.value)}
                            className="w-28"
                            data-testid={`med-duration-${idx}`}
                          />
                          {medicalForm.medications.length > 1 && (
                            <Button type="button" size="icon" variant="ghost" onClick={() => removeMedication(idx)}>
                              <Trash2 className="w-4 h-4 text-red-500" />
                            </Button>
                          )}
                        </div>
                      ))}
                    </div>

                    <div className="space-y-2">
                      <Label>Instrucciones</Label>
                      <Textarea
                        value={medicalForm.instructions}
                        onChange={(e) => setMedicalForm({...medicalForm, instructions: e.target.value})}
                        rows={2}
                      />
                    </div>

                    <div className="flex justify-end gap-2 pt-4">
                      <Button type="button" variant="outline" onClick={() => setShowMedicalDialog(false)}>
                        Cancelar
                      </Button>
                      <Button type="submit" className="bg-pine-900 hover:bg-pine-700" data-testid="save-medical-rx">
                        Guardar Receta
                      </Button>
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
                      <TableCell className="text-right">
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => downloadPdf('medical', rx._id)}
                          data-testid={`download-medical-${rx._id}`}
                        >
                          <Download className="w-4 h-4 mr-1" /> PDF
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {medicalPrescriptions.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-slate-500">
                        No hay recetas médicas
                      </TableCell>
                    </TableRow>
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
