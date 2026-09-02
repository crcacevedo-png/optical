import React, { useEffect, useRef } from 'react';
import { useOffline } from '../context/OfflineContext';
import { Button } from './ui/button';
import { toast } from 'sonner';
import { WifiOff, RefreshCw, CloudUpload, AlertTriangle } from 'lucide-react';

export function OfflineIndicator() {
  const { online, pending, failed, syncing, syncNow } = useOffline();
  const prevOnline = useRef(online);
  const prevPending = useRef(pending);

  useEffect(() => {
    if (prevOnline.current && !online) {
      toast.warning('Sin conexion a internet', {
        description: 'Tus cambios se guardan en este dispositivo y se sincronizaran al volver la senal.',
      });
    } else if (!prevOnline.current && online) {
      toast.success('Conexion restablecida', { description: 'Sincronizando cambios pendientes...' });
    }
    prevOnline.current = online;
  }, [online]);

  useEffect(() => {
    if (online && prevPending.current > 0 && pending === 0 && !syncing && failed === 0) {
      toast.success('Todo sincronizado', { description: 'No hay cambios pendientes en este dispositivo.' });
    }
    prevPending.current = pending;
  }, [pending, online, syncing, failed]);

  // Nada que mostrar cuando esta en linea y todo sincronizado.
  if (online && pending === 0 && !syncing && failed === 0) return null;

  let cls = '';
  let content = null;
  if (!online) {
    cls = 'bg-amber-50 text-amber-700 border-amber-200';
    content = (<><WifiOff className="w-3.5 h-3.5" /><span>Sin conexion{pending > 0 ? ` · ${pending} sin sincronizar` : ''}</span></>);
  } else if (syncing) {
    cls = 'bg-blue-50 text-blue-700 border-blue-200';
    content = (<><RefreshCw className="w-3.5 h-3.5 animate-spin" /><span>Sincronizando… {pending}</span></>);
  } else if (pending > 0) {
    cls = 'bg-blue-50 text-blue-700 border-blue-200';
    content = (<><CloudUpload className="w-3.5 h-3.5" /><span>{pending} por sincronizar{failed > 0 ? ` · ${failed} con error` : ''}</span></>);
  } else {
    cls = 'bg-red-50 text-red-700 border-red-200';
    content = (<><AlertTriangle className="w-3.5 h-3.5" /><span>{failed} con error</span></>);
  }

  return (
    <div className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border ${cls}`} data-testid="offline-indicator">
      {content}
      {online && pending > 0 && !syncing && (
        <Button variant="ghost" size="sm" className="h-5 px-1.5 text-xs hover:bg-white/60" onClick={syncNow} data-testid="offline-sync-now-btn">
          Sincronizar
        </Button>
      )}
    </div>
  );
}
