import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { BranchFilter } from '../components/BranchFilter';
import { Plus, Search, Eye, Stethoscope, ArrowRight, ShieldCheck, History } from 'lucide-react';
import { toast } from 'sonner';
import { NewExamDialog } from '../components/exam/NewExamDialog';
import { ConsultationViewDialog } from '../components/patients/ConsultationViewDialog';
import { fetchRxPdf, openPdfBlob, fmtDate } from '../components/exam/examShared';

// Incluye tipos retirados del menu para etiquetar correctamente consultas antiguas
const CONSULTATION_TYPE_LABELS = {
  general: 'Consulta General', control: 'Control', urgencia: 'Urgencia',
  primera_vez: 'Primera Vez', seguimiento: 'Seguimiento',
};
const STATUS_FILTERS = [{ v: 'todos', l: 'Todos' }, { v: 'en_curso', l: 'En curso' }, { v: 'firmado', l: 'Firmados' }, { v: 'historica', l: 'Históricas' }];
const statusOf = (c) => (!c.exam_code ? 'historica' : c.exam_status || 'en_curso');

const StatusBadge = ({ c }) => {
  const s = statusOf(c);
  if (s === 'historica') return <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-slate-100 text-slate-600 font-medium"><History className="w-3 h-3" /> Histórica</span>;
  if (s === 'firmado') return <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 font-medium"><ShieldCheck className="w-3 h-3" /> Firmado</span>;
  return <span className="px-2 py-0.5 text-xs rounded-full bg-amber-50 text-amber-800 border border-amber-200 font-medium">En curso</span>;
};

export default function ConsultationsPage() {
  const navigate = useNavigate();
  const [consultations, setConsultations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [branchId, setBranchId] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('todos');
  const [showNew, setShowNew] = useState(false);
  const [legacy, setLegacy] = useState({ open: false, loading: false, data: null });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await api.get('/api/consultations', { params: branchId ? { branch_id: branchId } : {} });
      setConsultations(data || []);
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, [branchId]);
  useEffect(() => { loadData(); }, [loadData]);

  const openLegacy = async (id) => {
    setLegacy({ open: true, loading: true, data: null });
    try {
      const { data } = await api.get(`/api/consultations/${id}`);
      setLegacy({ open: true, loading: false, data });
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
      setLegacy({ open: false, loading: false, data: null });
    }
  };
  const downloadPdf = async (type, id) => {
    try { openPdfBlob((await fetchRxPdf(type, id)).data); } catch { toast.error('No se pudo generar el PDF'); }
  };

  const term = searchTerm.toLowerCase();
  const filtered = consultations.filter((c) => (statusFilter === 'todos' || statusOf(c) === statusFilter) && (!term
    || [c.patient_name, c.chief_complaint, c.diagnosis, c.exam_code].some((x) => (x || '').toLowerCase().includes(term))));

  return (
    <div className="space-y-6" data-testid="consultations-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Consultas y exámenes</h1>
          <p className="text-slate-500 text-sm mt-1">Evaluación → Refracción final → Recetas → Impresión. Las consultas anteriores se conservan en solo lectura.</p>
        </div>
        <div className="flex items-center gap-3">
          <BranchFilter value={branchId} onChange={setBranchId} />
          <Button className="bg-pine-700 hover:bg-pine-800" onClick={() => setShowNew(true)} data-testid="new-exam-btn">
            <Plus className="w-4 h-4 mr-2" /> Nuevo examen
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="pt-4 pb-4 flex flex-col md:flex-row gap-3 md:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input placeholder="Buscar por paciente, código, motivo o diagnóstico..." value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)} className="pl-9" data-testid="consultation-search" />
          </div>
          <div className="flex flex-wrap gap-1.5" data-testid="consultation-status-filters">
            {STATUS_FILTERS.map((s) => (
              <button key={s.v} type="button" onClick={() => setStatusFilter(s.v)} data-testid={`consultation-filter-${s.v}`}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${statusFilter === s.v ? 'border-pine-700 bg-pine-700 text-white' : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
                {s.l}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-8 text-center text-slate-500">Cargando...</div>
          ) : filtered.length === 0 ? (
            <div className="p-12 text-center" data-testid="consultations-empty">
              <Stethoscope className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500 font-medium">No hay exámenes registrados</p>
              <p className="text-slate-400 text-sm mt-1">Inicia un examen para empezar</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Fecha</TableHead>
                  <TableHead>Paciente</TableHead>
                  <TableHead>Código</TableHead>
                  <TableHead>Tipo</TableHead>
                  <TableHead>Motivo</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Profesional</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((c) => (
                  <TableRow key={c._id} className="hover:bg-slate-50" data-testid={`consultation-row-${c._id}`}>
                    <TableCell className="text-sm font-medium whitespace-nowrap">{fmtDate(c.consultation_date)}</TableCell>
                    <TableCell className="font-medium text-sm">{c.patient_name || '-'}</TableCell>
                    <TableCell className="text-xs font-mono text-slate-500">{c.exam_code || '—'}</TableCell>
                    <TableCell>
                      <span className="px-2 py-0.5 bg-pine-50 text-pine-700 text-xs rounded-full font-medium">
                        {CONSULTATION_TYPE_LABELS[c.consultation_type] || c.consultation_type}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm text-slate-600 max-w-[220px] truncate">{c.chief_complaint}</TableCell>
                    <TableCell><StatusBadge c={c} /></TableCell>
                    <TableCell className="text-sm text-slate-500">{c.professional_name || '-'}</TableCell>
                    <TableCell className="text-right">
                      {c.exam_code ? (
                        <Button variant="outline" size="sm" onClick={() => navigate(`/exams/${c._id}`)} data-testid={`open-exam-${c._id}`}>
                          Abrir examen <ArrowRight className="w-3.5 h-3.5 ml-1" />
                        </Button>
                      ) : (
                        <Button variant="ghost" size="sm" onClick={() => openLegacy(c._id)} data-testid={`view-consultation-${c._id}`}>
                          <Eye className="w-4 h-4 mr-1" /> Ver
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <NewExamDialog open={showNew} onOpenChange={setShowNew} />
      <ConsultationViewDialog open={legacy.open} onOpenChange={(o) => setLegacy((s) => ({ ...s, open: o }))} loading={legacy.loading}
        consultation={legacy.data} downloadPdf={downloadPdf} />
    </div>
  );
}
