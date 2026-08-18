import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

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

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const isAuthRoute = originalRequest.url?.includes('/auth/');
    
    // Never intercept auth routes or network errors (no response)
    if (isAuthRoute || !error.response) {
      return Promise.reject(error);
    }
    
    if (error.response?.status === 401 && !originalRequest._retry) {
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
