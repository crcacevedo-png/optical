import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail, useAuth } from '../../context/AuthContext';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../ui/alert-dialog';
import { Monitor, Smartphone, Tablet, Globe, Clock, ShieldOff, RefreshCw, LogOut, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

/** Detecta un icono basico segun el user-agent raw. Sin parsing pesado. */
function detectDeviceIcon(ua) {
  const u = (ua || '').toLowerCase();
  if (u.includes('iphone') || u.includes('android') && u.includes('mobile')) return Smartphone;
  if (u.includes('ipad') || (u.includes('tablet') && !u.includes('mobile'))) return Tablet;
  if (u.includes('chrome') || u.includes('firefox') || u.includes('safari') || u.includes('edge')) return Monitor;
  return Globe;
}

function humanTimeAgo(iso) {
  if (!iso) return '-';
  try {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return 'hace segundos';
    if (diff < 3600) return `hace ${Math.floor(diff / 60)} min`;
    if (diff < 86400) return `hace ${Math.floor(diff / 3600)} h`;
    return `hace ${Math.floor(diff / 86400)} d`;
  } catch { return iso; }
}

export default function SessionsPanel() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [revokeTarget, setRevokeTarget] = useState(null);
  const [revoking, setRevoking] = useState(false);
  const [revokeAllOpen, setRevokeAllOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await api.get('/api/sessions');
      setData(data);
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail) || 'Error al cargar sesiones');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const doRevoke = async () => {
    if (!revokeTarget) return;
    setRevoking(true);
    try {
      await api.post(`/api/sessions/${revokeTarget.session_id}/revoke`);
      toast.success('Sesion revocada');
      setRevokeTarget(null);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail) || 'Error al revocar');
    } finally {
      setRevoking(false);
    }
  };

  const doRevokeAllMine = async () => {
    setRevoking(true);
    try {
      const { data } = await api.post('/api/sessions/revoke-all-mine');
      toast.success(`Se cerraron ${data.revoked_count} sesiones`);
      setRevokeAllOpen(false);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail) || 'Error');
    } finally {
      setRevoking(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-pine-900"></div>
      </div>
    );
  }
  if (!data) return null;

  const isAdmin = user?.role === 'admin' || user?.role === 'superadmin';
  const items = data.items || [];
  const myOtherSessions = items.filter((s) => s.user_id === user?._id && !s.is_current);

  return (
    <div className="space-y-6" data-testid="sessions-panel">
      {/* Header + acciones */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">
            {isAdmin ? 'Sesiones activas del equipo' : 'Mis sesiones activas'}
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {isAdmin
              ? 'Dispositivos con acceso a tu optica. Revoca sesiones sospechosas con un click.'
              : 'Dispositivos donde tu cuenta esta activa. Cierra sesiones antiguas por seguridad.'}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load} data-testid="sessions-refresh">
            <RefreshCw className="w-4 h-4 mr-1.5" /> Actualizar
          </Button>
          {myOtherSessions.length > 0 && (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setRevokeAllOpen(true)}
              data-testid="sessions-revoke-all-mine"
            >
              <LogOut className="w-4 h-4 mr-1.5" />
              Cerrar mis otras sesiones ({myOtherSessions.length})
            </Button>
          )}
        </div>
      </div>

      {/* Warning si hay muchas sesiones */}
      {items.length > 10 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-amber-800">
            Tienes <strong>{items.length}</strong> sesiones activas.
            Revisa que todas sean de dispositivos conocidos.
          </p>
        </div>
      )}

      {/* Grid de sesiones */}
      {items.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-slate-500">
            <Monitor className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No hay sesiones activas registradas.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {items.map((s) => {
            const Icon = detectDeviceIcon(s.user_agent);
            return (
              <Card
                key={s.session_id}
                className={s.is_current ? 'border-emerald-300 bg-emerald-50/40' : ''}
                data-testid={`session-${s.session_id}`}
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <div className={`p-2.5 rounded-lg ${s.is_current ? 'bg-emerald-100' : 'bg-slate-100'}`}>
                      <Icon className={`w-5 h-5 ${s.is_current ? 'text-emerald-700' : 'text-slate-600'}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-sm text-slate-900 truncate">
                          {isAdmin ? s.user_name : 'Mi sesion'}
                        </span>
                        {s.is_current && (
                          <Badge className="bg-emerald-600 text-white text-[10px] px-1.5 py-0">
                            Esta sesion
                          </Badge>
                        )}
                        {isAdmin && (
                          <Badge variant="outline" className="text-[10px]">
                            {s.user_role}
                          </Badge>
                        )}
                      </div>
                      {isAdmin && (
                        <p className="text-xs text-slate-500 truncate">{s.user_email}</p>
                      )}
                      <div className="mt-2 text-xs text-slate-600 space-y-0.5">
                        <div className="truncate" title={s.user_agent}>
                          <span className="text-slate-400">Dispositivo:</span>{' '}
                          {s.user_agent?.slice(0, 60) || 'Desconocido'}
                        </div>
                        <div>
                          <span className="text-slate-400">IP:</span> {s.ip || '-'}
                        </div>
                        <div className="flex items-center gap-1 text-slate-500">
                          <Clock className="w-3 h-3" />
                          Ultima actividad: {humanTimeAgo(s.last_activity_at)}
                        </div>
                      </div>
                    </div>
                    {!s.is_current && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        onClick={() => setRevokeTarget(s)}
                        data-testid={`revoke-${s.session_id}`}
                      >
                        <ShieldOff className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Revoke single confirmation */}
      <AlertDialog open={!!revokeTarget} onOpenChange={(o) => { if (!o) setRevokeTarget(null); }}>
        <AlertDialogContent data-testid="revoke-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Cerrar sesion?</AlertDialogTitle>
            <AlertDialogDescription>
              {isAdmin && revokeTarget?.user_id !== user?._id
                ? `La sesion de ${revokeTarget?.user_name} en ${revokeTarget?.user_agent?.slice(0, 60)} se cerrara inmediatamente. El usuario debera volver a iniciar sesion.`
                : 'Esta sesion se cerrara. Necesitaras iniciar sesion de nuevo en ese dispositivo.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="revoke-cancel">Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={doRevoke}
              disabled={revoking}
              className="bg-red-600 hover:bg-red-700"
              data-testid="revoke-confirm"
            >
              {revoking ? 'Cerrando...' : 'Cerrar sesion'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Revoke all mine confirmation */}
      <AlertDialog open={revokeAllOpen} onOpenChange={setRevokeAllOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cerrar todas mis otras sesiones?</AlertDialogTitle>
            <AlertDialogDescription>
              Se cerraran <strong>{myOtherSessions.length}</strong> sesiones en otros dispositivos.
              Solo permanecera activa esta sesion.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={doRevokeAllMine}
              disabled={revoking}
              className="bg-red-600 hover:bg-red-700"
              data-testid="revoke-all-mine-confirm"
            >
              {revoking ? 'Cerrando...' : 'Si, cerrar todas'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
