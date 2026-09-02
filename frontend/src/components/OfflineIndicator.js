import React, { useEffect, useRef } from 'react';
import { useOffline } from '../context/OfflineContext';
import { Button } from './ui/button';
import { toast } from 'sonner';
import { WifiOff, RefreshCw, CloudUpload, AlertTriangle } from 'lucide-react';

// Umbrales del aviso de seguridad (registros pendientes sin sincronizar).
const WARN_THRESHOLD = 50;
const URGENT_THRESHOLD = 150;

export function OfflineIndicator() {
  const { online, pending, failed, syncing, syncNow } = useOffline();
  const prevOnline = useRef(online);
  const prevPending = useRef(pending);
  const lastWarnBucketRef = useRef(0);

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

  // Aviso de seguridad: recuerda buscar senal cuando se acumulan muchos pendientes.
  // Avisa al cruzar cada bloque del umbral (50, 100, 150...) y escala el mensaje.
  useEffect(() => {
    const bucket = Math.floor(pending / WARN_THRESHOLD);
    if (bucket > lastWarnBucketRef.current && pending >= WARN_THRESHOLD) {
      const urgent = pending >= URGENT_THRESHOLD;
      toast.warning(`Tienes ${pending} registros sin sincronizar`, {
        description: urgent
          ? 'Son muchos. Busca conexion a internet cuanto antes para respaldarlos en el servidor. Mientras tanto se guardan cifrados en este dispositivo.'
          : 'Busca conexion a internet pronto para respaldarlos en el servidor. Se guardan cifrados en este dispositivo mientras tanto.',
        duration: 9000,
      });
    }
    lastWarnBucketRef.current = bucket;
  }, [pending]);

  // Nada que mostrar cuando esta en linea y todo sincronizado.
  if (online && pending === 0 && !syncing && failed === 0) return null;

  const urgent = pending >= WARN_THRESHOLD;
  let cls = '';
  let content = null;
  if (!online) {
    cls = urgent ? 'bg-red-50 text-red-700 border-red-200' : 'bg-amber-50 text-amber-700 border-amber-200';
    content = (<>{urgent ? <AlertTriangle className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}<span>Sin conexion{pending > 0 ? ` · ${pending} sin sincronizar${urgent ? ' · busca senal' : ''}` : ''}</span></>);
  } else if (syncing) {
    cls = 'bg-blue-50 text-blue-700 border-blue-200';
    content = (<><RefreshCw className="w-3.5 h-3.5 animate-spin" /><span>Sincronizando… {pending}</span></>);
  } else if (pending > 0) {
    cls = urgent ? 'bg-red-50 text-red-700 border-red-200' : 'bg-blue-50 text-blue-700 border-blue-200';
    content = (<>{urgent ? <AlertTriangle className="w-3.5 h-3.5" /> : <CloudUpload className="w-3.5 h-3.5" />}<span>{pending} por sincronizar{urgent ? ' · busca senal' : ''}{failed > 0 ? ` · ${failed} con error` : ''}</span></>);
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
