import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { enqueue as enqueueRequest } from '../lib/offlineQueue';

// In production (custom domain), use relative URL (same-origin).
// In preview/dev, use the env variable.
const isProduction = typeof window !== 'undefined' && 
  window.location.hostname !== 'localhost' && 
  !window.location.hostname.includes('preview.emergentagent.com');

const API_URL = isProduction ? '' : (process.env.REACT_APP_BACKEND_URL || '');

const AuthContext = createContext(null);

// Axios instance with credentials
const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  }
});

// CSRF double-submit: leer csrf_token cookie e injectar en cada request state-changing.
// Se combina con el backend middleware que exige que el header X-CSRF-Token
// coincida con la cookie. Un atacante cross-site NO puede leer la cookie via JS
// (SOP), por eso no puede forjar el header y su request es rechazado 403.
function _getCsrfToken() {
  try {
    const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : null;
  } catch {
    return null;
  }
}

api.interceptors.request.use((config) => {
  const method = (config.method || 'get').toLowerCase();
  if (['post', 'put', 'patch', 'delete'].includes(method)) {
    const token = _getCsrfToken();
    if (token) {
      config.headers = config.headers || {};
      config.headers['X-CSRF-Token'] = token;
    }
  }
  return config;
});

// Auto-refresh interceptor: retry once with refreshed token on 401
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error) => {
  failedQueue.forEach(prom => {
    if (error) prom.reject(error);
    else prom.resolve();
  });
  failedQueue = [];
};

// ---- Cola offline: decide que peticiones se guardan si no hay conexion ----
const _QUEUE_DENYLIST = [/\/auth\//, /\/data-export\//, /\/search/, /receipt\.pdf/, /\.pdf/, /manifesto/, /\/refresh/];
function _isQueueable(config) {
  const method = (config.method || 'get').toLowerCase();
  if (!['post', 'put', 'patch', 'delete'].includes(method)) return false;
  if (config.skipOfflineQueue) return false;
  if (config.responseType === 'blob') return false;
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) return false;
  const url = config.url || '';
  if (_QUEUE_DENYLIST.some((rx) => rx.test(url))) return false;
  return true;
}
function _parseData(d) {
  if (d == null) return undefined;
  if (typeof d === 'string') { try { return JSON.parse(d); } catch { return d; } }
  return d;
}
function _labelFor(config) {
  const url = config.url || '';
  const m = (config.method || '').toUpperCase();
  if (/\/jornadas\/.*\/patients/.test(url)) return 'Registro de paciente (jornada)';
  if (/\/jornadas\/.*\/consultations/.test(url)) return 'Consulta de jornada';
  if (/\/jornadas\/.*\/sales/.test(url)) return 'Venta de jornada';
  if (/\/prescriptions\/eyeglass/.test(url)) return 'Receta de anteojos';
  if (/\/prescriptions\/contact/.test(url)) return 'Receta de lentes de contacto';
  if (/\/consultations/.test(url)) return 'Consulta';
  if (/\/patients/.test(url)) return 'Paciente';
  if (/\/sales/.test(url)) return 'Venta';
  if (/\/appointments/.test(url)) return 'Cita';
  return `${m} ${url}`;
}

api.interceptors.response.use(
  (response) => {
    try { window.dispatchEvent(new Event('cortexia:online')); } catch { /* noop */ }
    return response;
  },
  async (error) => {
    const originalRequest = error.config || {};
    const isAuthRoute = originalRequest.url?.includes('/auth/');

    // Sin respuesta = error de red (offline o servidor inalcanzable)
    if (!error.response) {
      if (!isAuthRoute && _isQueueable(originalRequest)) {
        try {
          await enqueueRequest({
            method: (originalRequest.method || 'post').toLowerCase(),
            url: originalRequest.url,
            data: _parseData(originalRequest.data),
            createdAt: Date.now(),
            label: _labelFor(originalRequest),
          });
          try { window.dispatchEvent(new Event('cortexia:offline')); } catch { /* noop */ }
          // Respuesta sintetica para que la UI continue con normalidad.
          return Promise.resolve({
            data: { _offlineQueued: true },
            status: 202,
            statusText: 'Queued Offline',
            headers: {},
            config: originalRequest,
            _offlineQueued: true,
          });
        } catch (e) {
          try { window.dispatchEvent(new Event('cortexia:offline')); } catch { /* noop */ }
          return Promise.reject(error);
        }
      }
      try { window.dispatchEvent(new Event('cortexia:offline')); } catch { /* noop */ }
      return Promise.reject(error);
    }

    if (error.response?.status === 401 && !originalRequest._retry && !isAuthRoute) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(() => api(originalRequest));
      }
      originalRequest._retry = true;
      isRefreshing = true;
      try {
        await api.post('/api/auth/refresh');
        processQueue(null);
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError);
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Algo salió mal. Intente de nuevo.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = not authenticated
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    try {
      const { data } = await api.get('/api/auth/me');
      setUser(data);
    } catch (error) {
      setUser(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = async (email, password) => {
    const { data } = await api.post('/api/auth/login', { email, password });
    setUser(data);
    return data;
  };

  const register = async (email, password, name) => {
    const { data } = await api.post('/api/auth/register', { email, password, name });
    setUser(data);
    return data;
  };

  const logout = async () => {
    try {
      await api.post('/api/auth/logout');
    } finally {
      setUser(false);
    }
  };

  const value = {
    user,
    loading,
    login,
    register,
    logout,
    checkAuth,
    isAuthenticated: !!user,
    isSuperAdmin: user?.role === 'superadmin',
    isAdmin: user?.role === 'admin',
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export { api };
