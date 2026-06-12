import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail, ArrowLeft, CheckCircle } from 'lucide-react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';

const LOGO_URL = 'https://customer-assets.emergentagent.com/job_eyecare-erp/artifacts/80lobcqc_logo%20cortexia%20optical%20transparente.png';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    try {
      await api.post('/api/auth/forgot-password', { email: email.trim().toLowerCase() });
      setSubmitted(true);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || 'Error al solicitar restablecimiento');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-root min-h-screen flex items-center justify-center px-4 py-12 relative overflow-hidden">
      {/* Decorative curves consistent with LoginPage */}
      <svg
        className="absolute -top-32 -left-32 w-[420px] h-[420px] pointer-events-none"
        viewBox="0 0 400 400"
        fill="none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="fpCurveTop" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#6D35D8" stopOpacity="0.16" />
            <stop offset="100%" stopColor="#13B8B0" stopOpacity="0.04" />
          </linearGradient>
          <filter id="fpBlur" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="18" />
          </filter>
        </defs>
        <path
          d="M0,0 C140,20 260,60 340,140 C400,210 380,300 320,340 C260,380 160,360 80,300 C20,250 -20,160 0,0 Z"
          fill="url(#fpCurveTop)"
          filter="url(#fpBlur)"
        />
      </svg>
      <svg
        className="absolute -bottom-40 -right-24 w-[480px] h-[480px] pointer-events-none"
        viewBox="0 0 400 400"
        fill="none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="fpCurveBottom" x1="100%" y1="100%" x2="0%" y2="0%">
            <stop offset="0%" stopColor="#13B8B0" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#6D35D8" stopOpacity="0.05" />
          </linearGradient>
        </defs>
        <path
          d="M400,0 C380,180 320,300 200,360 C100,400 20,340 0,260 C0,160 80,80 200,40 C280,20 360,0 400,0 Z"
          fill="url(#fpCurveBottom)"
          style={{ filter: 'blur(28px)' }}
        />
      </svg>

      <div className="w-full max-w-[480px] relative z-10 login-stagger-2">
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-8 sm:p-10">
          {/* Logo oficial */}
          <div className="flex justify-center mb-8">
            <img
              src={LOGO_URL}
              alt="Cortexia Optical"
              className="h-32 object-contain select-none"
              draggable="false"
              data-testid="forgot-logo"
            />
          </div>

          {!submitted ? (
            <>
              <h1 className="login-title font-bold tracking-tight">
                Restablecer contraseña
              </h1>
              <p className="login-subtitle mb-7">
                Ingresa el email de tu cuenta y te enviaremos un enlace para crear una nueva contraseña.
              </p>

              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-1.5">
                  <label htmlFor="email" className="login-label">
                    EMAIL
                  </label>
                  <div className="login-input-wrap">
                    <Mail className="login-input-icon-left" strokeWidth={1.8} />
                    <input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="tu@email.com"
                      className="login-input"
                      required
                      data-testid="forgot-email-input"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  className="login-submit"
                  disabled={loading}
                  data-testid="forgot-submit-btn"
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Enviando...
                    </span>
                  ) : 'Enviar enlace de restablecimiento'}
                </button>
              </form>

              <Link
                to="/login"
                className="mt-6 flex items-center justify-center gap-1.5 text-sm login-forgot-link"
                data-testid="back-to-login"
              >
                <ArrowLeft className="w-4 h-4" /> Volver a iniciar sesión
              </Link>
            </>
          ) : (
            <div className="text-center py-4" data-testid="forgot-success">
              <div className="w-14 h-14 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-4">
                <CheckCircle className="w-7 h-7 text-emerald-600" />
              </div>
              <h2 className="login-title font-bold mb-3" style={{ fontSize: '24px' }}>
                Revisa tu email
              </h2>
              <p className="login-subtitle mb-6">
                Si el email <strong className="text-slate-700">{email}</strong> está registrado en Cortexia, recibirás instrucciones para restablecer tu contraseña en los próximos minutos.
              </p>
              <p className="text-xs text-slate-400 mb-6">
                ¿No lo ves? Revisa la carpeta de <strong>spam o promociones</strong>. El enlace expira en <strong>1 hora</strong>.
              </p>
              <Link to="/login">
                <Button variant="outline" className="w-full" data-testid="back-after-success">
                  <ArrowLeft className="w-4 h-4 mr-2" /> Volver al login
                </Button>
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
