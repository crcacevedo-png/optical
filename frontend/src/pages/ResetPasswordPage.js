import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { Lock, Eye, EyeOff, CheckCircle, AlertTriangle } from 'lucide-react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';

const LOGO_URL = 'https://customer-assets.emergentagent.com/job_eyecare-erp/artifacts/80lobcqc_logo%20cortexia%20optical%20transparente.png';

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token') || '';
  const [newPassword, setNewPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!token) {
      toast.error('Token no proporcionado');
    }
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (newPassword !== confirm) {
      toast.error('Las contraseñas no coinciden');
      return;
    }
    if (newPassword.length < 8) {
      toast.error('La contraseña debe tener al menos 8 caracteres');
      return;
    }
    setLoading(true);
    try {
      await api.post('/api/auth/reset-password', { token, new_password: newPassword });
      setSuccess(true);
      setTimeout(() => navigate('/login'), 3000);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || 'Error al restablecer contraseña');
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="login-root min-h-screen flex items-center justify-center px-4">
        <div className="bg-white rounded-2xl border border-slate-200/80 p-8 max-w-md text-center">
          <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
          <h1 className="login-title font-bold mb-2" style={{ fontSize: '24px' }}>Enlace inválido</h1>
          <p className="login-subtitle mb-6">El enlace de restablecimiento no es válido. Solicita uno nuevo.</p>
          <Link to="/forgot-password"><Button className="login-submit">Solicitar nuevo enlace</Button></Link>
        </div>
      </div>
    );
  }

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
          <linearGradient id="rpCurveTop" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#6D35D8" stopOpacity="0.16" />
            <stop offset="100%" stopColor="#13B8B0" stopOpacity="0.04" />
          </linearGradient>
          <filter id="rpBlur" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="18" />
          </filter>
        </defs>
        <path
          d="M0,0 C140,20 260,60 340,140 C400,210 380,300 320,340 C260,380 160,360 80,300 C20,250 -20,160 0,0 Z"
          fill="url(#rpCurveTop)"
          filter="url(#rpBlur)"
        />
      </svg>
      <svg
        className="absolute -bottom-40 -right-24 w-[480px] h-[480px] pointer-events-none"
        viewBox="0 0 400 400"
        fill="none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="rpCurveBottom" x1="100%" y1="100%" x2="0%" y2="0%">
            <stop offset="0%" stopColor="#13B8B0" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#6D35D8" stopOpacity="0.05" />
          </linearGradient>
        </defs>
        <path
          d="M400,0 C380,180 320,300 200,360 C100,400 20,340 0,260 C0,160 80,80 200,40 C280,20 360,0 400,0 Z"
          fill="url(#rpCurveBottom)"
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
              data-testid="reset-logo"
            />
          </div>

          {!success ? (
            <>
              <h1 className="login-title font-bold tracking-tight">
                Crear nueva contraseña
              </h1>
              <p className="login-subtitle mb-7">
                Define una contraseña nueva, segura y que recuerdes.
              </p>

              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-1.5">
                  <label htmlFor="newPwd" className="login-label">
                    NUEVA CONTRASEÑA
                  </label>
                  <div className="login-input-wrap">
                    <Lock className="login-input-icon-left" strokeWidth={1.8} />
                    <input
                      id="newPwd"
                      type={showPwd ? 'text' : 'password'}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="Mínimo 8 caracteres"
                      className="login-input pr-12"
                      minLength={8}
                      required
                      data-testid="reset-new-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPwd(!showPwd)}
                      className="login-input-icon-right"
                      aria-label={showPwd ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                    >
                      {showPwd ? <EyeOff className="w-[18px] h-[18px]" strokeWidth={1.8} /> : <Eye className="w-[18px] h-[18px]" strokeWidth={1.8} />}
                    </button>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="confirm" className="login-label">
                    CONFIRMAR CONTRASEÑA
                  </label>
                  <div className="login-input-wrap">
                    <Lock className="login-input-icon-left" strokeWidth={1.8} />
                    <input
                      id="confirm"
                      type={showPwd ? 'text' : 'password'}
                      value={confirm}
                      onChange={(e) => setConfirm(e.target.value)}
                      placeholder="Repite la contraseña"
                      className="login-input"
                      minLength={8}
                      required
                      data-testid="reset-confirm-password"
                    />
                  </div>
                </div>

                <div className="text-xs text-slate-500 bg-slate-50 rounded-xl p-3 leading-relaxed border border-slate-100">
                  Tu contraseña debe tener: <strong>mínimo 8 caracteres</strong>, al menos <strong>1 mayúscula</strong>, <strong>1 minúscula</strong> y <strong>1 dígito</strong>.
                </div>

                <button
                  type="submit"
                  className="login-submit"
                  disabled={loading}
                  data-testid="reset-submit-btn"
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Restableciendo...
                    </span>
                  ) : 'Restablecer contraseña'}
                </button>
              </form>
            </>
          ) : (
            <div className="text-center py-4" data-testid="reset-success">
              <div className="w-14 h-14 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-4">
                <CheckCircle className="w-7 h-7 text-emerald-600" />
              </div>
              <h2 className="login-title font-bold mb-3" style={{ fontSize: '24px' }}>
                ¡Contraseña restablecida!
              </h2>
              <p className="login-subtitle">
                Tu contraseña fue actualizada correctamente. Redirigiendo al login...
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
