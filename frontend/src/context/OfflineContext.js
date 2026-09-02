import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { api, formatApiErrorDetail } from './AuthContext';
import { getAll, remove, markFailed } from '../lib/offlineQueue';

const OfflineContext = createContext(null);

export function OfflineProvider({ children }) {
  const [online, setOnline] = useState(typeof navigator !== 'undefined' ? navigator.onLine : true);
  const [pending, setPending] = useState(0);
  const [failed, setFailed] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [lastSyncedAt, setLastSyncedAt] = useState(null);
  const pendingRef = useRef(0);
  const syncingRef = useRef(false);

  const refreshCount = useCallback(async () => {
    try {
      const all = await getAll();
      const p = all.filter((i) => i.status !== 'failed').length;
      const f = all.filter((i) => i.status === 'failed').length;
      pendingRef.current = p;
      setPending(p);
      setFailed(f);
    } catch { /* noop */ }
  }, []);

  const syncNow = useCallback(async () => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) return;
    if (syncingRef.current) return;
    syncingRef.current = true;
    setSyncing(true);
    try {
      const items = (await getAll())
        .filter((i) => i.status !== 'failed')
        .sort((a, b) => a.createdAt - b.createdAt);
      for (const item of items) {
        try {
          await api({ method: item.method, url: item.url, data: item.data, skipOfflineQueue: true });
          await remove(item.id);
        } catch (err) {
          if (!err.response) {
            // Sigue sin conexion: se detiene y se reintenta luego.
            break;
          }
          // El servidor rechazo la peticion (validacion / conflicto): se marca como fallida.
          await markFailed(item.id, formatApiErrorDetail(err.response?.data?.detail));
        }
      }
      setLastSyncedAt(Date.now());
      setOnline(true);
    } finally {
      syncingRef.current = false;
      setSyncing(false);
      await refreshCount();
    }
  }, [refreshCount]);

  useEffect(() => {
    const goOnline = () => { setOnline(true); syncNow(); };
    const goOffline = () => setOnline(false);
    const onQueueChanged = () => refreshCount();

    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    window.addEventListener('cortexia:online', goOnline);
    window.addEventListener('cortexia:offline', goOffline);
    window.addEventListener('cortexia:queue-changed', onQueueChanged);

    refreshCount();
    if (typeof navigator === 'undefined' || navigator.onLine) syncNow();

    const iv = setInterval(() => {
      if ((typeof navigator === 'undefined' || navigator.onLine) && pendingRef.current > 0) {
        syncNow();
      }
    }, 30000);

    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
      window.removeEventListener('cortexia:online', goOnline);
      window.removeEventListener('cortexia:offline', goOffline);
      window.removeEventListener('cortexia:queue-changed', onQueueChanged);
      clearInterval(iv);
    };
  }, [syncNow, refreshCount]);

  return (
    <OfflineContext.Provider value={{ online, pending, failed, syncing, lastSyncedAt, syncNow, refreshCount }}>
      {children}
    </OfflineContext.Provider>
  );
}

export function useOffline() {
  const ctx = useContext(OfflineContext);
  if (!ctx) throw new Error('useOffline must be used within an OfflineProvider');
  return ctx;
}
