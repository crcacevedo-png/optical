import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth, formatApiErrorDetail } from '../context/AuthContext';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Eye, EyeOff, Users, Package, Calendar, FileText, ShoppingCart } from 'lucide-react';

const LOGO_URL = 'https://customer-assets.emergentagent.com/job_eyecare-erp/artifacts/80lobcqc_logo%20cortexia%20optical%20transparente.png';

// Imagen de óptica de fondo (lentes en estantes + lentes en mostrador)
const OPTICAL_STORE_IMG = 'https://images.unsplash.com/photo-1574258495973-f010dfbb5371?auto=format&fit=crop&w=1600&q=80';

// Tarjetas de features que aparecen sobre la imagen
const FEATURES = [
  { icon: Calendar, label: 'Citas', color: 'purple' },
  { icon: Package, label: 'Inventario', color: 'teal' },
  { icon: FileText, label: 'Recetas', color: 'purple' },
  { icon: ShoppingCart, label: 'Ventas', color: 'teal' },
  { icon: Users, label: 'Clientes', color: 'purple' },
];

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const userData = await login(email, password);
      if (userData?.role === 'superadmin') {
        navigate('/admin/opticas');
      } else {
        navigate('/dashboard');
      }
    } catch (err) {
      if (err.response?.data?.detail) {
        setError(formatApiErrorDetail(err.response.data.detail));
      } else if (err.message?.includes('Network Error')) {
        setError('Error de conexion con el servidor. Verifique su conexion a internet.');
      } else {
        setError('Error al iniciar sesion. Intente de nuevo.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2" data-testid="login-page">

      {/* ═══════ LEFT PANEL — Form ═══════ */}
      <div className="relative flex items-center justify-center px-6 py-10 sm:px-12 bg-white overflow-hidden">
        {/* Subtle accent blurs */}
        <div className="absolute -bottom-40 -left-40 w-[440px] h-[440px] rounded-full opacity-[0.035]"
          style={{ background: 'radial-gradient(circle, #1ABC9C 0%, transparent 70%)' }} />
        <div className="absolute -top-24 -right-24 w-[320px] h-[320px] rounded-full opacity-[0.025]"
          style={{ background: 'radial-gradient(circle, #5A2D82 0%, transparent 70%)' }} />

        <div className="w-full max-w-[400px] relative z-10">
          {/* Logo */}
          <div className="flex justify-center mb-6 login-stagger-1">
            <img
              src={LOGO_URL}
              alt="Cortexia Optical"
              className="h-40 sm:h-48 object-contain select-none"
              draggable="false"
              data-testid="login-logo"
            />
          </div>

          {/* Welcome */}
          <div className="mb-7 login-stagger-2">
            <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900 tracking-tight">
              Bienvenido
            </h1>
            <p className="mt-1 text-slate-400 text-sm">
              Ingrese sus credenciales para acceder al sistema
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5 login-stagger-3" data-testid="login-form">
            {error && (
              <div
                className="px-4 py-3 rounded-xl bg-red-50 border border-red-100 text-red-600 text-sm flex items-start gap-2"
                data-testid="login-error"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-red-400 mt-1.5 shrink-0" />
                {error}
              </div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-slate-600 text-xs font-semibold uppercase tracking-wide">
                Correo electrónico
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="correo@ejemplo.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                data-testid="login-email-input"
                className="h-12 rounded-xl bg-slate-50/80 border-slate-200/80 placeholder:text-slate-300 focus:bg-white focus:border-[#5A2D82]/30 focus:ring-2 focus:ring-[#5A2D82]/10 transition-all duration-200 text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-slate-600 text-xs font-semibold uppercase tracking-wide">
                Contraseña
              </Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  data-testid="login-password-input"
                  className="h-12 rounded-xl bg-slate-50/80 border-slate-200/80 placeholder:text-slate-300 focus:bg-white focus:border-[#5A2D82]/30 focus:ring-2 focus:ring-[#5A2D82]/10 transition-all duration-200 pr-11 text-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500 transition-colors"
                  data-testid="toggle-password-visibility"
                >
                  {showPassword ? <EyeOff className="w-[18px] h-[18px]" /> : <Eye className="w-[18px] h-[18px]" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="login-btn-gradient w-full h-12 rounded-xl text-white font-semibold text-sm disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center"
              data-testid="login-submit-button"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Iniciando sesión...
                </span>
              ) : 'Iniciar Sesión'}
            </button>

            <div className="text-center pt-1">
              <Link
                to="/forgot-password"
                className="text-[13px] text-slate-500 hover:text-pine-900 transition-colors"
                data-testid="forgot-password-link"
              >
                ¿Olvidaste tu contraseña?
              </Link>
            </div>
          </form>
        </div>
      </div>

      {/* ═══════ RIGHT PANEL — Optical Store Hero ═══════ */}
      <div
        className="hidden lg:flex relative overflow-hidden items-center justify-center bg-slate-100"
        data-testid="login-right-panel"
      >
        {/* Imagen de fondo de optica */}
        <img
          src={OPTICAL_STORE_IMG}
          alt="Optica Cortexia"
          className="absolute inset-0 w-full h-full object-cover"
          draggable="false"
        />
        {/* Overlay claro tipo wash blanco con tinte ligero */}
        <div
          className="absolute inset-0"
          style={{
            background: 'linear-gradient(120deg, rgba(255,255,255,0.85) 0%, rgba(248,250,252,0.65) 45%, rgba(255,255,255,0.45) 100%)',
          }}
        />
        {/* Acento decorativo morado-teal en esquinas (curvas suaves) */}
        <div
          className="absolute -bottom-32 -right-24 w-[420px] h-[420px] rounded-full opacity-40 pointer-events-none"
          style={{
            background: 'radial-gradient(circle, rgba(26,188,156,0.5) 0%, rgba(90,45,130,0.2) 50%, transparent 75%)',
            filter: 'blur(40px)',
          }}
        />
        <div
          className="absolute -top-20 -left-16 w-[320px] h-[320px] rounded-full opacity-30 pointer-events-none"
          style={{
            background: 'radial-gradient(circle, rgba(90,45,130,0.4) 0%, transparent 70%)',
            filter: 'blur(50px)',
          }}
        />

        {/* Contenido principal */}
        <div className="relative z-10 max-w-[560px] mx-12 px-4 login-glass-card">
          <h2 className="font-heading text-4xl xl:text-5xl font-bold leading-[1.15] text-slate-900 tracking-tight mb-3">
            Gestione su óptica
          </h2>
          <h2 className="font-heading text-4xl xl:text-5xl font-bold leading-[1.15] tracking-tight mb-6">
            <span className="text-slate-900">de manera </span>
            <span
              style={{
                background: 'linear-gradient(135deg, #5A2D82 0%, #1ABC9C 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}
            >
              eficiente
            </span>
          </h2>
          <p className="text-slate-600 text-[15px] leading-relaxed mb-10 max-w-[460px]">
            Control total de pacientes, inventario, ventas y finanzas en una sola plataforma diseñada para ópticas en Latinoamérica.
          </p>

          {/* Feature Cards - tarjetas blancas con icono */}
          <div className="flex flex-wrap gap-3 max-w-[520px]" data-testid="login-features">
            {FEATURES.map(({ icon: Icon, label, color }) => {
              const iconColor = color === 'teal' ? '#1ABC9C' : '#5A2D82';
              return (
                <div
                  key={label}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-full bg-white/95 border border-slate-200/80 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200"
                  data-testid={`feature-${label.toLowerCase()}`}
                >
                  <Icon className="w-4 h-4" style={{ color: iconColor }} strokeWidth={2.2} />
                  <span className="text-sm font-semibold text-slate-700">{label}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
