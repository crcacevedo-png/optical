import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Glasses, Mail, ArrowLeft, CheckCircle } from 'lucide-react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';

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
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-white to-slate-50 px-4 py-12">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-8 sm:p-10">
          <div className="flex items-center gap-2 mb-8">
            <div className="w-10 h-10 rounded-xl bg-pine-900 flex items-center justify-center">
              <Glasses className="w-5 h-5 text-white" />
            </div>
            <span className="font-heading text-xl font-bold text-slate-900">Cortexia Optical</span>
          </div>

          {!submitted ? (
            <>
              <h1 className="font-heading text-2xl font-semibold text-slate-900 mb-2">
                Restablecer contraseña
              </h1>
              <p className="text-sm text-slate-500 mb-6 leading-relaxed">
                Ingresa el email de tu cuenta y te enviaremos un enlace para crear una nueva contraseña.
              </p>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="email" className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                    Email
                  </Label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <Input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="tu@email.com"
                      className="pl-9"
                      required
                      data-testid="forgot-email-input"
                    />
                  </div>
                </div>

                <Button
                  type="submit"
                  className="w-full bg-pine-900 hover:bg-pine-700"
                  disabled={loading}
                  data-testid="forgot-submit-btn"
                >
                  {loading ? 'Enviando...' : 'Enviar enlace de restablecimiento'}
                </Button>
              </form>

              <Link
                to="/login"
                className="mt-6 flex items-center justify-center gap-1.5 text-sm text-slate-500 hover:text-pine-900 transition-colors"
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
              <h2 className="font-heading text-xl font-semibold text-slate-900 mb-3">
                Revisa tu email
              </h2>
              <p className="text-sm text-slate-500 mb-6 leading-relaxed">
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
