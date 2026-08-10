import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { toast } from 'sonner';
import { Plus, Search, Tent, Calendar, Building2, Users, DollarSign, Filter, X } from 'lucide-react';

const STATUS_META = {
  planificada: { label: 'Planificada', cls: 'bg-slate-100 text-slate-700 border-slate-200' },
  activa: { label: 'Activa', cls: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
  en_cierre: { label: 'En cierre', cls: 'bg-amber-100 text-amber-700 border-amber-200' },
  cerrada: { label: 'Cerrada', cls: 'bg-blue-100 text-blue-700 border-blue-200' },
  cancelada: { label: 'Cancelada', cls: 'bg-rose-100 text-rose-700 border-rose-200' },
};

const fmtQ = (n) => `Q ${(Number(n) || 0).toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtDate = (iso) => (iso ? new Date(iso + 'T00:00:00').toLocaleDateString('es-GT', { day: '2-digit', month: 'short', year: 'numeric' }) : '');

export default function JornadasPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [branches, setBranches] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ status: '', branch_id: '', search: '', from_date: '', to_date: '' });
  const [showFilters, setShowFilters] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
      const [jRes, bRes] = await Promise.all([
        api.get('/api/jornadas', { params }),
        api.get('/api/branches').catch(() => ({ data: [] })),
      ]);
      setItems(jRes.data.items || []);
      setTotal(jRes.data.total || 0);
      setBranches(bRes.data || []);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  const activeFiltersCount = useMemo(
    () => Object.values(filters).filter(Boolean).length,
    [filters]
  );

  const clearFilters = () => setFilters({ status: '', branch_id: '', search: '', from_date: '', to_date: '' });

  return (
    <div className="space-y-6" data-testid="jornadas-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-pine-600 to-emerald-500 flex items-center justify-center">
              <Tent className="w-5 h-5 text-white" />
            </div>
            <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Jornadas</h1>
          </div>
          <p className="text-slate-500 text-sm">
            Brigadas, ferias y visitas fuera de la operacion habitual · {total} jornada{total !== 1 ? 's' : ''}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowFilters((v) => !v)}
            data-testid="toggle-filters-btn"
          >
            <Filter className="w-4 h-4 mr-1.5" />
            Filtros {activeFiltersCount > 0 && <Badge variant="secondary" className="ml-1.5">{activeFiltersCount}</Badge>}
          </Button>
          <Button onClick={() => navigate('/jornadas/new')} className="bg-pine-900 hover:bg-pine-800" data-testid="new-jornada-btn">
            <Plus className="w-4 h-4 mr-2" /> Nueva Jornada
          </Button>
        </div>
      </div>

      {showFilters && (
        <Card className="border-slate-200/80" data-testid="jornadas-filters">
          <CardContent className="pt-5 space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
              <div>
                <Label className="text-xs">Buscar por nombre</Label>
                <div className="relative">
                  <Search className="absolute left-2 top-2.5 w-4 h-4 text-slate-400" />
                  <Input
                    value={filters.search}
                    onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                    placeholder="Municipalidad de..."
                    className="pl-8"
                    data-testid="filter-search"
                  />
                </div>
              </div>
              <div>
                <Label className="text-xs">Estado</Label>
                <Select value={filters.status || 'all'} onValueChange={(v) => setFilters({ ...filters, status: v === 'all' ? '' : v })}>
                  <SelectTrigger data-testid="filter-status"><SelectValue placeholder="Todos" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos</SelectItem>
                    {Object.entries(STATUS_META).map(([k, v]) => (
                      <SelectItem key={k} value={k}>{v.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Sucursal</Label>
                <Select value={filters.branch_id || 'all'} onValueChange={(v) => setFilters({ ...filters, branch_id: v === 'all' ? '' : v })}>
                  <SelectTrigger data-testid="filter-branch"><SelectValue placeholder="Todas" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todas</SelectItem>
                    {branches.map((b) => (
                      <SelectItem key={b._id} value={b._id}>{b.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Desde</Label>
                <Input type="date" value={filters.from_date} onChange={(e) => setFilters({ ...filters, from_date: e.target.value })} data-testid="filter-from" />
              </div>
              <div>
                <Label className="text-xs">Hasta</Label>
                <Input type="date" value={filters.to_date} onChange={(e) => setFilters({ ...filters, to_date: e.target.value })} data-testid="filter-to" />
              </div>
            </div>
            {activeFiltersCount > 0 && (
              <Button variant="ghost" size="sm" onClick={clearFilters} data-testid="clear-filters-btn">
                <X className="w-4 h-4 mr-1" /> Limpiar filtros
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
        </div>
      ) : items.length === 0 ? (
        <Card className="border-dashed border-slate-300" data-testid="jornadas-empty">
          <CardContent className="py-16 text-center">
            <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto mb-3">
              <Tent className="w-8 h-8 text-slate-400" />
            </div>
            <h3 className="font-heading text-lg font-semibold text-slate-800 mb-1">
              {activeFiltersCount > 0 ? 'Sin resultados' : 'Aun no hay jornadas'}
            </h3>
            <p className="text-sm text-slate-500 mb-4">
              {activeFiltersCount > 0
                ? 'Ajusta los filtros para ver mas resultados.'
                : 'Crea tu primera jornada para organizar una brigada, feria o visita externa.'}
            </p>
            {activeFiltersCount === 0 && (
              <Button onClick={() => navigate('/jornadas/new')} className="bg-pine-900 hover:bg-pine-800" data-testid="empty-new-btn">
                <Plus className="w-4 h-4 mr-2" /> Crear primera jornada
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {items.map((j) => {
            const meta = STATUS_META[j.status] || STATUS_META.planificada;
            return (
              <Card
                key={j._id}
                className="border-slate-200/80 hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => navigate(`/jornadas/${j._id}`)}
                data-testid={`jornada-card-${j._id}`}
              >
                <CardContent className="pt-5 pb-4 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-heading text-base font-semibold text-slate-900 truncate">{j.name}</h3>
                      <div className="flex items-center gap-1.5 text-xs text-slate-500 mt-0.5">
                        <Calendar className="w-3.5 h-3.5" />
                        <span>{fmtDate(j.start_date)} — {fmtDate(j.end_date)}</span>
                      </div>
                    </div>
                    <Badge variant="outline" className={`${meta.cls} text-xs`}>{meta.label}</Badge>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-slate-600">
                    <Building2 className="w-3.5 h-3.5 text-slate-400" />
                    <span className="truncate">{j.responsible_branch_name || 'Sin sucursal'}</span>
                    {j.location && <span className="text-slate-400">· {j.location}</span>}
                  </div>
                  <div className="grid grid-cols-3 gap-3 pt-2 border-t border-slate-100">
                    <div>
                      <p className="text-[10px] text-slate-400 uppercase tracking-wide">Vendido</p>
                      <p className="text-sm font-semibold text-slate-900">{fmtQ(j.total_sold)}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-slate-400 uppercase tracking-wide flex items-center gap-1"><Users className="w-3 h-3" /> Pacientes</p>
                      <p className="text-sm font-semibold text-slate-900">{j.patients_count || 0}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-slate-400 uppercase tracking-wide flex items-center gap-1"><DollarSign className="w-3 h-3" /> Saldo caja</p>
                      <p className="text-sm font-semibold text-slate-900">{fmtQ(j.cash_balance)}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
