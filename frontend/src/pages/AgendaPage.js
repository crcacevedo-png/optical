import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import { Calendar } from '../components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { Tabs, TabsList, TabsTrigger } from '../components/ui/tabs';
import { BranchFilter } from '../components/BranchFilter';
import {
  Plus, CalendarIcon, ChevronLeft, ChevronRight,
  Check, X, MoreHorizontal, Clock, MessageCircle, Phone, CircleDot, AlertTriangle
} from 'lucide-react';
import {
  format, addDays, addWeeks, addMonths, subDays, subWeeks, subMonths,
  startOfWeek, endOfWeek, startOfMonth, endOfMonth,
  isSameDay, isSameMonth, parseISO, eachDayOfInterval, getDay
} from 'date-fns';
import { es } from 'date-fns/locale';
import { toast } from 'sonner';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../components/ui/dropdown-menu';

const HOURS = [
  '08:00','08:30','09:00','09:30','10:00','10:30','11:00','11:30',
  '12:00','12:30','14:00','14:30','15:00','15:30','16:00','16:30','17:00','17:30'
];

const TYPE_LABELS = { consulta: 'Consulta', examen: 'Examen Visual', control: 'Control', entrega: 'Entrega' };

const STATUS_STYLES = {
  pendiente:  { bg: 'bg-amber-50 border-amber-200', dot: 'bg-amber-400', text: 'text-amber-700' },
  confirmada: { bg: 'bg-blue-50 border-blue-200', dot: 'bg-blue-400', text: 'text-blue-700' },
  completada: { bg: 'bg-green-50 border-green-200', dot: 'bg-green-400', text: 'text-green-700' },
  cancelada:  { bg: 'bg-red-50 border-red-200', dot: 'bg-red-400', text: 'text-red-700' },
};

export default function AgendaPage() {
  const [appointments, setAppointments] = useState([]);
  const [patients, setPatients] = useState([]);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [viewMode, setViewMode] = useState('daily');
  const [branchId, setBranchId] = useState('');
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [formData, setFormData] = useState({
    patient_id: '', date: '', time: '', duration: 30, type: 'consulta', notes: ''
  });

  const dateRange = useMemo(() => {
    if (viewMode === 'daily') {
      const d = format(selectedDate, 'yyyy-MM-dd');
      return { from: d, to: d };
    }
    if (viewMode === 'weekly') {
      const start = startOfWeek(selectedDate, { weekStartsOn: 1 });
      const end = endOfWeek(selectedDate, { weekStartsOn: 1 });
      return { from: format(start, 'yyyy-MM-dd'), to: format(end, 'yyyy-MM-dd') };
    }
    const start = startOfMonth(selectedDate);
    const end = endOfMonth(selectedDate);
    return { from: format(start, 'yyyy-MM-dd'), to: format(end, 'yyyy-MM-dd') };
  }, [selectedDate, viewMode]);

  const fetchAppointments = useCallback(async () => {
    try {
      setLoading(true);
      const params = viewMode === 'daily'
        ? { date: dateRange.from }
        : { date_from: dateRange.from, date_to: dateRange.to };
      if (branchId) params.branch_id = branchId;
      const { data } = await api.get('/api/appointments', { params });
      setAppointments(data || []);
    } catch (error) {
      console.error('Error fetching appointments:', error);
    } finally {
      setLoading(false);
    }
  }, [dateRange, viewMode, branchId]);

  const fetchPatients = useCallback(async () => {
    try {
      const { data } = await api.get('/api/patients', { params: { limit: 200 } });
      setPatients(data.patients || []);
    } catch (error) {
      console.error('Error fetching patients:', error);
    }
  }, []);

  useEffect(() => { fetchAppointments(); }, [fetchAppointments]);
  useEffect(() => { fetchPatients(); }, [fetchPatients]);

  // Recordatorios de manana via WhatsApp
  const [reminders, setReminders] = useState({ date: '', items: [] });
  const [remindersOpen, setRemindersOpen] = useState(false);
  const fetchReminders = useCallback(async () => {
    try {
      const { data } = await api.get('/api/appointments/reminders', { params: { days_ahead: 1 } });
      setReminders(data);
    } catch (err) { /* silent */ }
  }, []);
  useEffect(() => { fetchReminders(); }, [fetchReminders]);

  // Recordatorios de reposicion de lentes de contacto via WhatsApp
  const [replReminders, setReplReminders] = useState({ count: 0, items: [] });
  const [replOpen, setReplOpen] = useState(false);
  const fetchReplReminders = useCallback(async () => {
    try {
      const { data } = await api.get('/api/prescriptions/contact/replacement-reminders', { params: { days_ahead: 5 } });
      setReplReminders(data);
    } catch (err) { /* silent */ }
  }, []);
  useEffect(() => { fetchReplReminders(); }, [fetchReplReminders]);

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

  const updateStatus = async (id, status) => {
    try {
      await api.put(`/api/appointments/${id}`, { status });
      toast.success('Estado actualizado');
      fetchAppointments();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const cancelAppointment = async (id) => {
    try {
      await api.delete(`/api/appointments/${id}`);
      toast.success('Cita cancelada');
      fetchAppointments();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const navigate = (dir) => {
    const fn = dir === 'prev'
      ? { daily: () => subDays(selectedDate, 1), weekly: () => subWeeks(selectedDate, 1), monthly: () => subMonths(selectedDate, 1) }
      : { daily: () => addDays(selectedDate, 1), weekly: () => addWeeks(selectedDate, 1), monthly: () => addMonths(selectedDate, 1) };
    setSelectedDate(fn[viewMode]());
  };

  const headerLabel = useMemo(() => {
    if (viewMode === 'daily') return format(selectedDate, "EEEE d 'de' MMMM, yyyy", { locale: es });
    if (viewMode === 'weekly') {
      const start = startOfWeek(selectedDate, { weekStartsOn: 1 });
      const end = endOfWeek(selectedDate, { weekStartsOn: 1 });
      return `${format(start, 'd MMM', { locale: es })} - ${format(end, "d MMM yyyy", { locale: es })}`;
    }
    return format(selectedDate, "MMMM yyyy", { locale: es });
  }, [selectedDate, viewMode]);

  const getAptsForDate = (dateStr) => appointments.filter(a => a.date === dateStr);
  const getAptsForDateTime = (dateStr, time) => appointments.filter(a => a.date === dateStr && a.time === time);

  // ===== APPOINTMENT CARD (reusable) =====
  const AppointmentCard = ({ apt, compact = false }) => {
    const st = STATUS_STYLES[apt.status] || STATUS_STYLES.pendiente;
    if (compact) {
      return (
        <div
          className={`px-2 py-1 rounded text-xs border ${st.bg} cursor-default`}
          title={`${apt.patient_name || 'Paciente'} - ${apt.time} - ${TYPE_LABELS[apt.type] || apt.type}`}
          data-testid={`appointment-${apt._id}`}
        >
          <div className="flex items-center gap-1">
            <span className={`w-1.5 h-1.5 rounded-full ${st.dot} flex-shrink-0`}></span>
            <span className="font-medium truncate">{apt.time} {apt.patient_name?.split(' ')[0] || ''}</span>
          </div>
        </div>
      );
    }
    return (
      <div
        className={`p-3 rounded-lg flex items-center justify-between border ${st.bg}`}
        data-testid={`appointment-${apt._id}`}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center text-sm font-medium flex-shrink-0">
            {apt.patient_name?.split(' ').map(n => n[0]).join('').slice(0, 2) || 'P'}
          </div>
          <div className="min-w-0">
            <p className="font-medium text-sm text-slate-900 truncate">{apt.patient_name || 'Paciente'}</p>
            <p className="text-xs text-slate-500">{TYPE_LABELS[apt.type] || apt.type} &middot; {apt.duration} min</p>
          </div>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8 flex-shrink-0">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => updateStatus(apt._id, 'confirmada')}>
              <Check className="w-4 h-4 mr-2" /> Confirmar
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => updateStatus(apt._id, 'completada')}>
              <Check className="w-4 h-4 mr-2" /> Completar
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => cancelAppointment(apt._id)} className="text-red-600">
              <X className="w-4 h-4 mr-2" /> Cancelar
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    );
  };

  // ===== DAILY VIEW =====
  const DailyView = () => (
    <div className="space-y-1">
      {HOURS.map((time) => {
        const timeApts = getAptsForDateTime(format(selectedDate, 'yyyy-MM-dd'), time);
        return (
          <div key={time} className="flex gap-4 py-2 border-b border-slate-100 last:border-0">
            <div className="w-14 flex-shrink-0 text-sm font-medium text-slate-400 pt-2">{time}</div>
            <div className="flex-1 min-h-[44px]">
              {timeApts.length > 0 ? (
                <div className="space-y-2">
                  {timeApts.map((apt) => <AppointmentCard key={apt._id} apt={apt} />)}
                </div>
              ) : (
                <div className="h-full flex items-center">
                  <span className="text-sm text-slate-200">--</span>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );

  // ===== WEEKLY VIEW =====
  const WeeklyView = () => {
    const weekStart = startOfWeek(selectedDate, { weekStartsOn: 1 });
    const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

    return (
      <div className="overflow-x-auto">
        <div className="min-w-[700px]">
          {/* Day headers */}
          <div className="grid grid-cols-[60px_repeat(7,1fr)] border-b border-slate-200">
            <div className="p-2"></div>
            {days.map((day) => (
              <div
                key={day.toISOString()}
                className={`p-2 text-center border-l border-slate-100 cursor-pointer hover:bg-slate-50 ${
                  isSameDay(day, new Date()) ? 'bg-pine-50' : ''
                } ${isSameDay(day, selectedDate) ? 'border-b-2 border-b-pine-700' : ''}`}
                onClick={() => { setSelectedDate(day); setViewMode('daily'); }}
              >
                <p className="text-xs font-medium text-slate-400 uppercase">{format(day, 'EEE', { locale: es })}</p>
                <p className={`text-lg font-semibold ${isSameDay(day, new Date()) ? 'text-pine-700' : 'text-slate-800'}`}>
                  {format(day, 'd')}
                </p>
              </div>
            ))}
          </div>

          {/* Time rows */}
          {HOURS.map((time) => (
            <div key={time} className="grid grid-cols-[60px_repeat(7,1fr)] border-b border-slate-50">
              <div className="p-1.5 text-xs font-medium text-slate-400 text-right pr-3">{time}</div>
              {days.map((day) => {
                const dateStr = format(day, 'yyyy-MM-dd');
                const apts = getAptsForDateTime(dateStr, time);
                return (
                  <div key={dateStr + time} className="border-l border-slate-50 p-0.5 min-h-[36px]">
                    {apts.map((apt) => <AppointmentCard key={apt._id} apt={apt} compact />)}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    );
  };

  // ===== MONTHLY VIEW =====
  const MonthlyView = () => {
    const monthStart = startOfMonth(selectedDate);
    const monthEnd = endOfMonth(selectedDate);
    const calStart = startOfWeek(monthStart, { weekStartsOn: 1 });
    const calEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });
    const allDays = eachDayOfInterval({ start: calStart, end: calEnd });
    const dayNames = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'];

    return (
      <div>
        {/* Day headers */}
        <div className="grid grid-cols-7 border-b border-slate-200">
          {dayNames.map((d) => (
            <div key={d} className="p-2 text-center text-xs font-semibold text-slate-500 uppercase">{d}</div>
          ))}
        </div>

        {/* Calendar grid */}
        <div className="grid grid-cols-7">
          {allDays.map((day) => {
            const dateStr = format(day, 'yyyy-MM-dd');
            const dayApts = getAptsForDate(dateStr);
            const isCurrentMonth = isSameMonth(day, selectedDate);
            const isToday = isSameDay(day, new Date());
            const isSelected = isSameDay(day, selectedDate);

            return (
              <div
                key={dateStr}
                className={`border border-slate-100 min-h-[100px] p-1.5 cursor-pointer transition-colors ${
                  !isCurrentMonth ? 'bg-slate-50/50' : 'bg-white hover:bg-slate-50'
                } ${isSelected ? 'ring-2 ring-pine-500 ring-inset' : ''}`}
                onClick={() => { setSelectedDate(day); setViewMode('daily'); }}
                data-testid={`month-day-${dateStr}`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-sm font-medium w-7 h-7 flex items-center justify-center rounded-full ${
                    isToday ? 'bg-pine-700 text-white' : isCurrentMonth ? 'text-slate-700' : 'text-slate-300'
                  }`}>
                    {format(day, 'd')}
                  </span>
                  {dayApts.length > 0 && (
                    <span className="text-xs font-medium text-pine-600 bg-pine-50 px-1.5 py-0.5 rounded-full">
                      {dayApts.length}
                    </span>
                  )}
                </div>
                <div className="space-y-0.5">
                  {dayApts.slice(0, 3).map((apt) => {
                    const st = STATUS_STYLES[apt.status] || STATUS_STYLES.pendiente;
                    return (
                      <div key={apt._id} className={`text-[10px] px-1.5 py-0.5 rounded truncate ${st.bg} border`}>
                        <span className="font-medium">{apt.time}</span> {apt.patient_name?.split(' ')[0] || ''}
                      </div>
                    );
                  })}
                  {dayApts.length > 3 && (
                    <div className="text-[10px] text-slate-400 px-1.5">+{dayApts.length - 3} mas</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6" data-testid="agenda-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Agenda</h1>
          <p className="text-slate-500 mt-1">Gestiona las citas de tus pacientes</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            onClick={() => setRemindersOpen(true)}
            className="border-emerald-200 text-emerald-700 hover:bg-emerald-50"
            data-testid="reminders-open-btn"
          >
            <MessageCircle className="w-4 h-4 mr-2" />
            Recordatorios manana
            {reminders.count > 0 && (
              <span className="ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-emerald-600 text-white text-[10px] font-bold">
                {reminders.count}
              </span>
            )}
          </Button>
          <Button
            variant="outline"
            onClick={() => setReplOpen(true)}
            className="border-cyan-200 text-cyan-700 hover:bg-cyan-50"
            data-testid="repl-reminders-open-btn"
          >
            <CircleDot className="w-4 h-4 mr-2" />
            Reposicion de lentes
            {replReminders.count > 0 && (
              <span className="ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-cyan-600 text-white text-[10px] font-bold">
                {replReminders.count}
              </span>
            )}
          </Button>
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
                      <SelectItem key={p._id} value={p._id}>{p.first_name} {p.last_name}</SelectItem>
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
                      {HOURS.map((h) => (<SelectItem key={h} value={h}>{h}</SelectItem>))}
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
                  <Label>Duracion</Label>
                  <Select value={String(formData.duration)} onValueChange={(v) => setFormData({...formData, duration: parseInt(v)})}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
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
                <Textarea value={formData.notes} onChange={(e) => setFormData({...formData, notes: e.target.value})} rows={2} />
              </div>
              <div className="flex justify-end gap-2 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowAddDialog(false)}>Cancelar</Button>
                <Button type="submit" className="bg-pine-900 hover:bg-pine-700" data-testid="save-appointment-btn">Agendar Cita</Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      {/* Modal: Recordatorios de manana */}
      <Dialog open={remindersOpen} onOpenChange={setRemindersOpen}>
        <DialogContent className="sm:max-w-lg" data-testid="reminders-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading">Recordatorios para manana</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <p className="text-xs text-slate-500">
              {reminders.date ? `Citas del ${reminders.date} — ${reminders.count || 0} paciente(s)` : 'Cargando...'}
            </p>
            {(reminders.items || []).length === 0 ? (
              <div className="py-6 text-center text-sm text-slate-400 italic">No hay citas para manana</div>
            ) : (
              <div className="divide-y divide-slate-100 max-h-96 overflow-y-auto -mx-2">
                {(reminders.items || []).map((a) => (
                  <div key={a._id} className="flex items-center gap-3 py-2.5 px-2" data-testid={`reminder-${a._id}`}>
                    <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
                      <Clock className="w-4 h-4 text-emerald-700" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-slate-800 text-sm truncate">{a.patient_name}</p>
                      <p className="text-xs text-slate-500">
                        {a.time} · {a.patient_phone || 'sin telefono'}
                      </p>
                    </div>
                    {a.whatsapp_url ? (
                      <a
                        href={a.whatsapp_url}
                        target="_blank" rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 bg-[#25D366] hover:bg-[#20b859] text-white text-xs font-medium px-3 py-1.5 rounded-md"
                        data-testid={`reminder-wa-${a._id}`}
                      >
                        <MessageCircle className="w-3.5 h-3.5" /> Enviar
                      </a>
                    ) : (
                      <span className="text-[10px] text-slate-400 italic">sin WhatsApp</span>
                    )}
                  </div>
                ))}
              </div>
            )}
            <p className="text-[11px] text-slate-400 pt-2 border-t border-slate-100">
              Al hacer click en &quot;Enviar&quot; se abre WhatsApp Web con el mensaje pre-armado. Confirma y envia desde WhatsApp.
            </p>
          </div>
        </DialogContent>
      </Dialog>

      {/* Modal: Recordatorios de reposicion de lentes de contacto */}
      <Dialog open={replOpen} onOpenChange={setReplOpen}>
        <DialogContent className="sm:max-w-lg" data-testid="repl-reminders-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading">Reposicion de lentes de contacto</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <p className="text-xs text-slate-500">
              Lentes por vencer (proximos 5 dias) o vencidos — {replReminders.count || 0} paciente(s)
            </p>
            {(replReminders.items || []).length === 0 ? (
              <div className="py-6 text-center text-sm text-slate-400 italic">No hay reposiciones pendientes</div>
            ) : (
              <div className="divide-y divide-slate-100 max-h-96 overflow-y-auto -mx-2">
                {(replReminders.items || []).map((r) => {
                  const overdue = r.status === 'vencida';
                  return (
                    <div key={r._id} className="flex items-center gap-3 py-2.5 px-2" data-testid={`repl-reminder-${r._id}`}>
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${overdue ? 'bg-red-100' : 'bg-cyan-100'}`}>
                        {overdue ? <AlertTriangle className="w-4 h-4 text-red-600" /> : <CircleDot className="w-4 h-4 text-cyan-700" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-slate-800 text-sm truncate">{r.patient_name}</p>
                        <p className="text-xs text-slate-500 truncate">
                          {r.replacement}{r.brand ? ` · ${r.brand}` : ''} · {r.patient_phone || 'sin telefono'}
                        </p>
                        <p className={`text-[11px] font-medium ${overdue ? 'text-red-600' : 'text-cyan-700'}`}>
                          {overdue
                            ? `Vencio el ${r.due_date} (hace ${Math.abs(r.days_remaining)} dias)`
                            : (r.days_remaining === 0 ? `Vence hoy (${r.due_date})` : `Vence en ${r.days_remaining} dias (${r.due_date})`)}
                        </p>
                      </div>
                      {r.whatsapp_url ? (
                        <a
                          href={r.whatsapp_url}
                          target="_blank" rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 bg-[#25D366] hover:bg-[#20b859] text-white text-xs font-medium px-3 py-1.5 rounded-md flex-shrink-0"
                          data-testid={`repl-reminder-wa-${r._id}`}
                        >
                          <MessageCircle className="w-3.5 h-3.5" /> Enviar
                        </a>
                      ) : (
                        <span className="text-[10px] text-slate-400 italic flex-shrink-0">sin WhatsApp</span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            <p className="text-[11px] text-slate-400 pt-2 border-t border-slate-100">
              El vencimiento se calcula desde la fecha de la receta segun el tipo de reemplazo. Al hacer click en &quot;Enviar&quot; se abre WhatsApp con el mensaje pre-armado; confirma y envia desde WhatsApp.
            </p>
          </div>
        </DialogContent>
      </Dialog>

      {/* Controls Bar */}
      <Card className="border-slate-200/80">
        <CardHeader className="pb-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            {/* Navigation */}
            <div className="flex items-center gap-3">
              <Button variant="outline" size="icon" onClick={() => navigate('prev')} data-testid="nav-prev">
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <h2 className="font-heading text-base sm:text-lg font-semibold capitalize min-w-[180px] text-center" data-testid="agenda-header-label">
                {headerLabel}
              </h2>
              <Button variant="outline" size="icon" onClick={() => navigate('next')} data-testid="nav-next">
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Button variant="outline" size="sm" onClick={() => setSelectedDate(new Date())} data-testid="today-btn">
                Hoy
              </Button>
            </div>

            {/* View Switcher */}
            <div className="flex items-center gap-3">
              <BranchFilter value={branchId} onChange={setBranchId} />
              <Tabs value={viewMode} onValueChange={setViewMode}>
              <TabsList>
                <TabsTrigger value="daily" data-testid="view-daily">Dia</TabsTrigger>
                <TabsTrigger value="weekly" data-testid="view-weekly">Semana</TabsTrigger>
                <TabsTrigger value="monthly" data-testid="view-monthly">Mes</TabsTrigger>
              </TabsList>
            </Tabs>
            </div>
          </div>
        </CardHeader>

        <CardContent className="pt-0">
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-pine-900"></div>
            </div>
          ) : (
            <>
              {viewMode === 'daily' && <DailyView />}
              {viewMode === 'weekly' && <WeeklyView />}
              {viewMode === 'monthly' && <MonthlyView />}
            </>
          )}

          {/* Legend */}
          <div className="flex flex-wrap gap-4 mt-4 pt-4 border-t border-slate-100">
            {Object.entries(STATUS_STYLES).map(([key, st]) => (
              <div key={key} className="flex items-center gap-1.5 text-xs text-slate-500">
                <span className={`w-2.5 h-2.5 rounded-full ${st.dot}`}></span>
                <span className="capitalize">{key}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
