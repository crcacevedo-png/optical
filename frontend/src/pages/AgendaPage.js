import React, { useState, useEffect } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import { Calendar } from '../components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { 
  Plus, CalendarIcon, Clock, ChevronLeft, ChevronRight, 
  User, Check, X, MoreHorizontal
} from 'lucide-react';
import { format, addDays, startOfWeek, isSameDay, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';
import { toast } from 'sonner';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../components/ui/dropdown-menu';

export default function AgendaPage() {
  const [appointments, setAppointments] = useState([]);
  const [patients, setPatients] = useState([]);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [formData, setFormData] = useState({
    patient_id: '',
    date: '',
    time: '',
    duration: 30,
    type: 'consulta',
    notes: ''
  });

  const hours = ['08:00', '08:30', '09:00', '09:30', '10:00', '10:30', '11:00', '11:30', 
                 '12:00', '12:30', '14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '17:00', '17:30'];

  useEffect(() => {
    fetchAppointments();
    fetchPatients();
  }, [selectedDate]);

  const fetchAppointments = async () => {
    try {
      const dateStr = format(selectedDate, 'yyyy-MM-dd');
      const { data } = await api.get('/api/appointments', { params: { date: dateStr } });
      setAppointments(data || []);
    } catch (error) {
      console.error('Error fetching appointments:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchPatients = async () => {
    try {
      const { data } = await api.get('/api/patients', { params: { limit: 200 } });
      setPatients(data.patients || []);
    } catch (error) {
      console.error('Error fetching patients:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/api/appointments', formData);
      toast.success('Cita agendada exitosamente');
      setShowAddDialog(false);
      setFormData({ patient_id: '', date: '', time: '', duration: 30, type: 'consulta', notes: '' });
      fetchAppointments();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const updateStatus = async (appointmentId, status) => {
    try {
      await api.put(`/api/appointments/${appointmentId}`, { status });
      toast.success('Estado actualizado');
      fetchAppointments();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const cancelAppointment = async (appointmentId) => {
    try {
      await api.delete(`/api/appointments/${appointmentId}`);
      toast.success('Cita cancelada');
      fetchAppointments();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const getAppointmentsForTime = (time) => {
    return appointments.filter(apt => apt.time === time);
  };

  const weekDays = Array.from({ length: 7 }, (_, i) => addDays(startOfWeek(selectedDate, { locale: es }), i));

  return (
    <div className="space-y-6" data-testid="agenda-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Agenda</h1>
          <p className="text-slate-500 mt-1">Gestiona las citas de tus pacientes</p>
        </div>
        <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
          <DialogTrigger asChild>
            <Button className="bg-pine-900 hover:bg-pine-700" data-testid="add-appointment-btn">
              <Plus className="w-4 h-4 mr-2" /> Nueva Cita
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="font-heading">Nueva Cita</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label>Paciente *</Label>
                <Select value={formData.patient_id} onValueChange={(v) => setFormData({...formData, patient_id: v})}>
                  <SelectTrigger data-testid="appointment-patient">
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
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Fecha *</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" className="w-full justify-start text-left font-normal" data-testid="appointment-date">
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {formData.date ? format(parseISO(formData.date), 'dd/MM/yyyy') : 'Seleccionar'}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                      <Calendar
                        mode="single"
                        selected={formData.date ? parseISO(formData.date) : undefined}
                        onSelect={(date) => setFormData({...formData, date: date ? format(date, 'yyyy-MM-dd') : ''})}
                        locale={es}
                      />
                    </PopoverContent>
                  </Popover>
                </div>
                <div className="space-y-2">
                  <Label>Hora *</Label>
                  <Select value={formData.time} onValueChange={(v) => setFormData({...formData, time: v})}>
                    <SelectTrigger data-testid="appointment-time">
                      <SelectValue placeholder="Hora" />
                    </SelectTrigger>
                    <SelectContent>
                      {hours.map((h) => (
                        <SelectItem key={h} value={h}>{h}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Tipo</Label>
                  <Select value={formData.type} onValueChange={(v) => setFormData({...formData, type: v})}>
                    <SelectTrigger data-testid="appointment-type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="consulta">Consulta</SelectItem>
                      <SelectItem value="examen">Examen Visual</SelectItem>
                      <SelectItem value="control">Control</SelectItem>
                      <SelectItem value="entrega">Entrega</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Duración</Label>
                  <Select value={String(formData.duration)} onValueChange={(v) => setFormData({...formData, duration: parseInt(v)})}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="15">15 min</SelectItem>
                      <SelectItem value="30">30 min</SelectItem>
                      <SelectItem value="45">45 min</SelectItem>
                      <SelectItem value="60">60 min</SelectItem>
                    </SelectContent>
                  </Select>
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
                <Button type="submit" className="bg-pine-900 hover:bg-pine-700" data-testid="save-appointment-btn">
                  Agendar Cita
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Calendar Navigation */}
      <Card className="border-slate-200/80">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="outline" size="icon" onClick={() => setSelectedDate(addDays(selectedDate, -7))}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <h2 className="font-heading text-lg font-semibold">
                {format(selectedDate, "MMMM yyyy", { locale: es })}
              </h2>
              <Button variant="outline" size="icon" onClick={() => setSelectedDate(addDays(selectedDate, 7))}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
            <Button variant="outline" onClick={() => setSelectedDate(new Date())}>
              Hoy
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Week Days */}
          <div className="grid grid-cols-7 gap-2 mb-4">
            {weekDays.map((day, idx) => (
              <button
                key={idx}
                onClick={() => setSelectedDate(day)}
                className={`p-2 rounded-lg text-center transition-colors ${
                  isSameDay(day, selectedDate)
                    ? 'bg-pine-900 text-white'
                    : isSameDay(day, new Date())
                    ? 'bg-pine-50 text-pine-900'
                    : 'hover:bg-slate-100'
                }`}
              >
                <p className="text-xs font-medium uppercase">{format(day, 'EEE', { locale: es })}</p>
                <p className="text-lg font-semibold">{format(day, 'd')}</p>
              </button>
            ))}
          </div>

          {/* Time Slots */}
          <div className="space-y-2">
            {loading ? (
              <div className="flex justify-center py-8">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-pine-900"></div>
              </div>
            ) : (
              hours.map((time) => {
                const timeAppointments = getAppointmentsForTime(time);
                return (
                  <div key={time} className="flex gap-4 py-2 border-b border-slate-100 last:border-0">
                    <div className="w-16 flex-shrink-0 text-sm font-medium text-slate-500 py-2">
                      {time}
                    </div>
                    <div className="flex-1 min-h-[40px]">
                      {timeAppointments.length > 0 ? (
                        <div className="space-y-2">
                          {timeAppointments.map((apt) => (
                            <div
                              key={apt._id}
                              className={`p-3 rounded-lg flex items-center justify-between ${
                                apt.status === 'completed' ? 'bg-green-50 border border-green-200' :
                                apt.status === 'cancelled' ? 'bg-red-50 border border-red-200' :
                                'bg-blue-50 border border-blue-200'
                              }`}
                              data-testid={`appointment-${apt._id}`}
                            >
                              <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center text-sm font-medium">
                                  {apt.patient_name?.split(' ').map(n => n[0]).join('').slice(0, 2) || 'P'}
                                </div>
                                <div>
                                  <p className="font-medium text-sm text-slate-900">{apt.patient_name || 'Paciente'}</p>
                                  <p className="text-xs text-slate-500">{apt.type} • {apt.duration} min</p>
                                </div>
                              </div>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" size="icon" className="h-8 w-8">
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem onClick={() => updateStatus(apt._id, 'completed')}>
                                    <Check className="w-4 h-4 mr-2" /> Completar
                                  </DropdownMenuItem>
                                  <DropdownMenuItem onClick={() => cancelAppointment(apt._id)} className="text-red-600">
                                    <X className="w-4 h-4 mr-2" /> Cancelar
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="h-full flex items-center">
                          <span className="text-sm text-slate-300">Disponible</span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
