import React, { useState, useEffect } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { 
  Search, Plus, User, Phone, Mail, Calendar, 
  FileText, Eye, ShoppingBag, ChevronRight
} from 'lucide-react';
import { toast } from 'sonner';

export default function PatientsPage() {
  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
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

  useEffect(() => {
    fetchPatients();
  }, []);

  const fetchPatients = async (searchTerm = '') => {
    try {
      const params = searchTerm ? { search: searchTerm } : {};
      const { data } = await api.get('/api/patients', { params });
      setPatients(data.patients || []);
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
    if (value.length >= 2 || value.length === 0) {
      fetchPatients(value);
    }
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
        <CardContent className="p-0">
          <ScrollArea className="h-[calc(100vh-16rem)]">
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
                  <CardTitle className="font-heading text-xl">
                    {selectedPatient.first_name} {selectedPatient.last_name}
                  </CardTitle>
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
                      <span className="flex items-center gap-1">
                        <Calendar className="w-4 h-4" /> {selectedPatient.birth_date}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <Tabs defaultValue="prescriptions" className="h-full">
                <TabsList className="w-full justify-start rounded-none border-b border-slate-100 h-12 p-0 bg-transparent">
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
                            <span className={`px-3 py-1 rounded-full text-xs font-medium status-${apt.status}`}>
                              {apt.status === 'scheduled' ? 'Programada' : apt.status === 'completed' ? 'Completada' : 'Cancelada'}
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
                              <span className={`px-3 py-1 rounded-full text-xs font-medium status-${sale.status}`}>
                                {sale.status === 'completed' ? 'Pagado' : 'Pendiente'}
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
    </div>
  );
}
