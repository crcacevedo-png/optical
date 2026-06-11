import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { Glasses, Lock, Eye, EyeOff, CheckCircle, AlertTriangle } from 'lucide-react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';

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
      <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
        <div className="bg-white rounded-2xl border border-slate-200/80 p-8 max-w-md text-center">
          <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
          <h1 className="font-heading text-xl font-semibold mb-2">Enlace inválido</h1>
          <p className="text-sm text-slate-500 mb-6">El enlace de restablecimiento no es válido. Solicita uno nuevo.</p>
          <Link to="/forgot-password"><Button>Solicitar nuevo enlace</Button></Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-white to-slate-50 px-4 py-12">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-8 sm:p-10">
          <div className="flex items-center gap-2 mb-8">
            <div className="w-10 h-10 rounded-xl bg-pine-900 flex items-center justify-center">
              <Glasses className="w-5 h-5 text-white" />
            </div>
            <span className="font-heading text-xl font-bold text-slate-900">Cortexia Optical</span>
          </div>

          {!success ? (
            <>
              <h1 className="font-heading text-2xl font-semibold text-slate-900 mb-2">
                Crear nueva contraseña
              </h1>
              <p className="text-sm text-slate-500 mb-6 leading-relaxed">
                Define una contraseña nueva, segura y que recuerdes.
              </p>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="newPwd" className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                    Nueva contraseña
                  </Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <Input
                      id="newPwd"
                      type={showPwd ? 'text' : 'password'}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="Mínimo 8 caracteres"
                      className="pl-9 pr-10"
                      minLength={8}
                      required
                      data-testid="reset-new-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPwd(!showPwd)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    >
                      {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="confirm" className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                    Confirmar contraseña
                  </Label>
                  <Input
                    id="confirm"
                    type={showPwd ? 'text' : 'password'}
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    placeholder="Repite la contraseña"
                    minLength={8}
                    required
                    data-testid="reset-confirm-password"
                  />
                </div>

                <div className="text-xs text-slate-500 bg-slate-50 rounded-lg p-3 leading-relaxed">
                  Tu contraseña debe tener: <strong>mínimo 8 caracteres</strong>, al menos <strong>1 mayúscula</strong>, <strong>1 minúscula</strong> y <strong>1 dígito</strong>.
                </div>

                <Button
                  type="submit"
                  className="w-full bg-pine-900 hover:bg-pine-700"
                  disabled={loading}
                  data-testid="reset-submit-btn"
                >
                  {loading ? 'Restableciendo...' : 'Restablecer contraseña'}
                </Button>
              </form>
            </>
          ) : (
            <div className="text-center py-4" data-testid="reset-success">
              <div className="w-14 h-14 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-4">
                <CheckCircle className="w-7 h-7 text-emerald-600" />
              </div>
              <h2 className="font-heading text-xl font-semibold text-slate-900 mb-3">
                ¡Contraseña restablecida!
              </h2>
              <p className="text-sm text-slate-500 mb-6 leading-relaxed">
                Tu contraseña fue actualizada correctamente. Redirigiendo al login...
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
