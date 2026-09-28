import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, formatApiErrorDetail, useAuth } from '../context/AuthContext';
import { Button } from './ui/button';
import { Lock, CreditCard, RefreshCw, LifeBuoy, LogOut } from 'lucide-react';
import { toast } from 'sonner';

const fmt = (n, cur = 'USD') => {
  const c = (cur || 'USD').toUpperCase();
  const symbol = c === 'GTQ' ? 'Q' : c === 'USD' ? '$' : c;
  return `${symbol} ${(Number(n) || 0).toFixed(2)}`;
};

// Muro de pago para cuentas SUSPENDIDAS por impago.
// - Admin: ve el estado + botones para actualizar el pago / elegir plan.
// - Otros roles: ven un aviso para contactar a su administrador.
export function PaymentWall() {
  const { user, logout, checkAuth } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === 'admin';
  const [status, setStatus] = useState(user?.billing || null);
  const [portalLoading, setPortalLoading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get('/api/billing/account-status');
      setStatus(data);
      if (data.state === 'active') {
        toast.success('¡Pago confirmado! Reactivando tu cuenta...', { duration: 4000 });
        await checkAuth();
      }
      return data;
    } catch {
      return null;
    }
  }, [checkAuth]);

  // Poll para reactivación automática mientras el admin regulariza.
  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 15000);
    return () => clearInterval(iv);
  }, [refresh]);

  const openPortal = async () => {
    try {
      setPortalLoading(true);
      const { data } = await api.post('/api/billing/portal', { origin_url: window.location.origin });
      if (data.url) window.location.href = data.url;
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || 'No se pudo abrir el portal de pago.');
      setPortalLoading(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  // ── Vista para roles no-admin ──
  if (!isAdmin) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center px-4" data-testid="payment-wall">
        <div className="max-w-md w-full text-center bg-white rounded-2xl border border-slate-200 shadow-sm p-8" data-testid="payment-wall-staff-message">
          <div className="w-16 h-16 rounded-2xl bg-red-100 flex items-center justify-center mx-auto mb-5">
            <Lock className="w-8 h-8 text-red-600" />
          </div>
          <h1 className="font-heading text-xl font-semibold text-slate-900 mb-2">Cuenta suspendida</h1>
          <p className="text-slate-600 text-sm mb-6">
            El acceso de esta óptica está temporalmente suspendido por un tema de pago.
            Por favor contacta a tu <strong>administrador</strong> para regularizarlo.
          </p>
          <Button variant="outline" onClick={handleLogout} data-testid="payment-wall-logout-btn">
            <LogOut className="w-4 h-4 mr-2" /> Cerrar sesión
          </Button>
        </div>
      </div>
    );
  }

  // ── Vista para el admin ──
  const reason = status?.suspended_reason === 'subscription_canceled'
    ? 'Tu suscripción fue cancelada.'
    : 'No pudimos procesar tu pago.';

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4" data-testid="payment-wall">
      <div className="max-w-lg w-full bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="bg-gradient-to-br from-red-600 to-rose-600 px-8 py-7 text-center">
          <div className="w-16 h-16 rounded-2xl bg-white/15 flex items-center justify-center mx-auto mb-4">
            <Lock className="w-8 h-8 text-white" />
          </div>
          <h1 className="font-heading text-2xl font-semibold text-white">Cuenta suspendida</h1>
          <p className="text-white/85 text-sm mt-1">{reason} Reactiva tu cuenta para seguir operando.</p>
        </div>

        <div className="p-8 space-y-5">
          {status?.plan_name && (
            <div className="flex items-center justify-between rounded-lg bg-slate-50 border border-slate-100 px-4 py-3">
              <span className="text-sm text-slate-600">Plan {status.plan_name} · {status.billing_cycle === 'yearly' ? 'Anual' : 'Mensual'}</span>
              <span className="font-heading font-bold text-slate-900">{fmt(status.amount, status.currency)}</span>
            </div>
          )}

          <div className="space-y-3">
            <Button
              onClick={openPortal}
              disabled={portalLoading}
              className="w-full bg-red-600 hover:bg-red-700 text-white h-11"
              data-testid="payment-wall-portal-btn"
            >
              <CreditCard className="w-4 h-4 mr-2" />
              {portalLoading ? 'Abriendo...' : 'Actualizar método de pago'}
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate('/my-plan')}
              className="w-full h-11"
              data-testid="payment-wall-plans-btn"
            >
              Elegir un plan y pagar
            </Button>
          </div>

          <div className="flex items-center justify-center gap-2 text-xs text-slate-500 pt-1">
            <RefreshCw className="w-3.5 h-3.5" />
            <span>La reactivación es automática al confirmarse el pago.</span>
          </div>

          <div className="flex items-center justify-between pt-3 border-t border-slate-100">
            <a
              href="mailto:info@cortexiagt.com"
              className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1.5"
            >
              <LifeBuoy className="w-4 h-4" /> Necesito ayuda
            </a>
            <button
              onClick={handleLogout}
              className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1.5"
              data-testid="payment-wall-logout-btn"
            >
              <LogOut className="w-4 h-4" /> Cerrar sesión
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
