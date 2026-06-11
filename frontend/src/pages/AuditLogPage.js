import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { ShieldAlert, RefreshCw, Search } from 'lucide-react';
import { toast } from 'sonner';

const ACTION_STYLES = {
  LOGIN_SUCCESS: 'bg-emerald-100 text-emerald-800',
  LOGIN_FAILED: 'bg-red-100 text-red-800',
  LOGOUT: 'bg-slate-100 text-slate-700',
  PASSWORD_CHANGED: 'bg-blue-100 text-blue-800',
  PASSWORD_RESET: 'bg-amber-100 text-amber-800',
  USER_CREATED: 'bg-emerald-100 text-emerald-800',
  USER_DEACTIVATED: 'bg-orange-100 text-orange-800',
  USER_DELETED: 'bg-red-100 text-red-800',
  USER_ACTIVATED: 'bg-emerald-100 text-emerald-800',
  USER_ROLE_CHANGED: 'bg-purple-100 text-purple-800',
  DATABASE_EXPORTED: 'bg-blue-100 text-blue-800',
};

const PAGE_SIZE = 50;

export default function AuditLogPage() {
  const [logs, setLogs] = useState([]);
  const [actions, setActions] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filterAction, setFilterAction] = useState('all');
  const [filterEmail, setFilterEmail] = useState('');
  const [skip, setSkip] = useState(0);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append('limit', PAGE_SIZE);
      params.append('skip', skip);
      if (filterAction && filterAction !== 'all') params.append('action', filterAction);
      if (filterEmail.trim()) params.append('actor_email', filterEmail.trim());
      const { data } = await api.get(`/api/audit/logs?${params.toString()}`);
      setLogs(data.logs || []);
      setTotal(data.total || 0);
    } catch (err) {
      toast.error('Error cargando audit log');
    } finally {
      setLoading(false);
    }
  }, [filterAction, filterEmail, skip]);

  const fetchActions = useCallback(async () => {
    try {
      const { data } = await api.get('/api/audit/actions');
      setActions(data.actions || []);
    } catch (err) {
      // silent
    }
  }, []);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);
  useEffect(() => { fetchActions(); }, [fetchActions]);

  const handleSearch = (e) => {
    e.preventDefault();
    setSkip(0);
    fetchLogs();
  };

  const formatDate = (iso) => {
    if (!iso) return '-';
    try {
      const d = new Date(iso);
      return d.toLocaleString('es-GT', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return iso;
    }
  };

  const formatMetadata = (meta) => {
    if (!meta || Object.keys(meta).length === 0) return '-';
    return Object.entries(meta).map(([k, v]) => `${k}: ${v}`).join(', ');
  };

  const nextPage = () => setSkip(skip + PAGE_SIZE);
  const prevPage = () => setSkip(Math.max(0, skip - PAGE_SIZE));

  return (
    <div className="space-y-6" data-testid="audit-log-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900 flex items-center gap-2">
            <ShieldAlert className="w-7 h-7 text-amber-600" />
            Auditoría del Sistema
          </h1>
          <p className="text-slate-500 mt-1">Registro de acciones críticas (logins, cambios de contraseña, gestión de usuarios, exportaciones)</p>
        </div>
        <Button onClick={fetchLogs} variant="outline" data-testid="refresh-audit">
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} /> Actualizar
        </Button>
      </div>

      {/* Filtros */}
      <Card className="border-slate-200/80">
        <CardContent className="pt-5">
          <form onSubmit={handleSearch} className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-500 uppercase">Tipo de evento</Label>
              <Select value={filterAction} onValueChange={(v) => { setFilterAction(v); setSkip(0); }}>
                <SelectTrigger data-testid="filter-action"><SelectValue placeholder="Todos" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos los eventos</SelectItem>
                  {actions.map(a => <SelectItem key={a} value={a}>{a}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-500 uppercase">Email del usuario</Label>
              <Input
                placeholder="ej: admin@cortexia.gt"
                value={filterEmail}
                onChange={(e) => setFilterEmail(e.target.value)}
                data-testid="filter-email"
              />
            </div>
            <Button type="submit" className="bg-pine-900 hover:bg-pine-700" data-testid="search-audit-btn">
              <Search className="w-4 h-4 mr-2" /> Buscar
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Tabla */}
      <Card className="border-slate-200/80">
        <CardHeader>
          <CardTitle className="font-heading text-lg">
            Eventos registrados ({total})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-slate-500">Cargando...</div>
          ) : logs.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <ShieldAlert className="w-12 h-12 mx-auto mb-2 opacity-30" />
              <p>No hay eventos que coincidan con el filtro</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="data-table-header">
                      <TableHead>Fecha</TableHead>
                      <TableHead>Acción</TableHead>
                      <TableHead>Usuario</TableHead>
                      <TableHead>Rol</TableHead>
                      <TableHead>IP</TableHead>
                      <TableHead>Detalles</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {logs.map((log) => (
                      <TableRow key={log._id} className="data-table-row" data-testid={`audit-row-${log._id}`}>
                        <TableCell className="whitespace-nowrap text-xs font-mono text-slate-600">{formatDate(log.created_at)}</TableCell>
                        <TableCell>
                          <Badge className={ACTION_STYLES[log.action] || 'bg-slate-100 text-slate-700'}>
                            {log.action}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm">{log.actor_email || '-'}</TableCell>
                        <TableCell className="text-sm text-slate-600">{log.actor_role || '-'}</TableCell>
                        <TableCell className="text-xs font-mono text-slate-500">{log.ip || '-'}</TableCell>
                        <TableCell className="text-xs text-slate-600 max-w-md truncate" title={formatMetadata(log.metadata)}>
                          {formatMetadata(log.metadata)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              {/* Paginacion */}
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-100">
                <p className="text-xs text-slate-500">
                  Mostrando {skip + 1} - {Math.min(skip + PAGE_SIZE, total)} de {total}
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={prevPage} disabled={skip === 0} data-testid="prev-page">
                    Anterior
                  </Button>
                  <Button variant="outline" size="sm" onClick={nextPage} disabled={skip + PAGE_SIZE >= total} data-testid="next-page">
                    Siguiente
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
