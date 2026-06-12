import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth, formatApiErrorDetail } from '../context/AuthContext';
import { Mail, Lock, Eye, EyeOff, Users, Package, Calendar, FileText, ShoppingCart } from 'lucide-react';

const LOGO_URL = 'https://customer-assets.emergentagent.com/job_eyecare-erp/artifacts/80lobcqc_logo%20cortexia%20optical%20transparente.png';

// Imagen premium de interior de óptica con estantes de monturas + lentes al frente
const OPTICAL_STORE_IMG = 'https://images.unsplash.com/photo-1591076482161-42ce6da69f67?auto=format&fit=crop&w=1800&q=85';

// Chips de funcionalidades con iconos alternados violeta / teal
const FEATURES = [
  { icon: Calendar, label: 'Citas', color: '#6D35D8' },
  { icon: Package, label: 'Inventario', color: '#13B8B0' },
  { icon: FileText, label: 'Recetas', color: '#6D35D8' },
  { icon: ShoppingCart, label: 'Ventas', color: '#13B8B0' },
  { icon: Users, label: 'Clientes', color: '#6D35D8' },
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
      const user = await login(email, password);
      if (user.role === 'superadmin') navigate('/admin/opticas');
      else navigate('/dashboard');
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || 'Error al iniciar sesión');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-root min-h-screen w-full grid grid-cols-1 lg:grid-cols-[45%_55%]" data-testid="login-page">

      {/* ═══════ LEFT PANEL — Form ═══════ */}
      <div className="login-left relative flex items-center justify-center px-6 py-10 sm:px-12 overflow-hidden">
        {/* Subtle decorative blurs in corners */}
        <div
          className="absolute -bottom-44 -left-32 w-[460px] h-[460px] rounded-full pointer-events-none"
          style={{ background: 'radial-gradient(circle, rgba(109,53,216,0.10) 0%, transparent 70%)' }}
        />
        <div
          className="absolute -top-32 -right-28 w-[340px] h-[340px] rounded-full pointer-events-none"
          style={{ background: 'radial-gradient(circle, rgba(19,184,176,0.07) 0%, transparent 70%)' }}
        />

        <div className="w-full max-w-[420px] relative z-10">
          {/* Logo — INTACTO */}
          <div className="flex justify-center mb-7 login-stagger-1">
            <img
              src={LOGO_URL}
              alt="Cortexia Optical"
              className="h-40 sm:h-44 object-contain select-none"
              draggable="false"
              data-testid="login-logo"
            />
          </div>

          {/* Welcome */}
          <div className="mb-7 login-stagger-2">
            <h1 className="login-title font-bold tracking-tight">
              Bienvenido
            </h1>
            <p className="login-subtitle">
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

            {/* Email field */}
            <div className="space-y-1.5">
              <label htmlFor="email" className="login-label">
                CORREO ELECTRÓNICO
              </label>
              <div className="login-input-wrap">
                <Mail className="login-input-icon-left" strokeWidth={1.8} />
                <input
                  id="email"
                  type="email"
                  placeholder="correo@ejemplo.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="login-input"
                  data-testid="login-email-input"
                />
              </div>
            </div>

            {/* Password field */}
            <div className="space-y-1.5">
              <label htmlFor="password" className="login-label">
                CONTRASEÑA
              </label>
              <div className="login-input-wrap">
                <Lock className="login-input-icon-left" strokeWidth={1.8} />
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="login-input pr-12"
                  data-testid="login-password-input"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="login-input-icon-right"
                  data-testid="toggle-password-visibility"
                  aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                >
                  {showPassword ? <EyeOff className="w-[18px] h-[18px]" strokeWidth={1.8} /> : <Eye className="w-[18px] h-[18px]" strokeWidth={1.8} />}
                </button>
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="login-submit"
              data-testid="login-submit-button"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Iniciando sesión...
                </span>
              ) : 'Iniciar sesión'}
            </button>

            {/* Forgot password link */}
            <div className="text-center pt-1">
              <Link
                to="/forgot-password"
                className="login-forgot-link"
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
        className="hidden lg:flex login-right relative overflow-hidden items-center justify-start"
        data-testid="login-right-panel"
      >
        {/* Background image: optical store */}
        <img
          src={OPTICAL_STORE_IMG}
          alt="Óptica Cortexia"
          className="absolute inset-0 w-full h-full object-cover"
          draggable="false"
        />

        {/* Light wash overlay */}
        <div
          className="absolute inset-0"
          style={{
            background: 'linear-gradient(125deg, rgba(255,255,255,0.92) 0%, rgba(248,250,255,0.78) 35%, rgba(255,255,255,0.55) 70%, rgba(255,255,255,0.20) 100%)',
          }}
        />

        {/* Corner accent shapes (curva decorativa) */}
        <div
          className="absolute -bottom-32 -right-24 w-[560px] h-[560px] rounded-full pointer-events-none"
          style={{
            background: 'radial-gradient(circle, rgba(19,184,176,0.32) 0%, rgba(109,53,216,0.18) 50%, transparent 75%)',
            filter: 'blur(30px)',
          }}
        />
        <div
          className="absolute -top-24 -left-16 w-[320px] h-[320px] rounded-full opacity-40 pointer-events-none"
          style={{
            background: 'radial-gradient(circle, rgba(109,53,216,0.25) 0%, transparent 70%)',
            filter: 'blur(40px)',
          }}
        />

        {/* Hero content */}
        <div className="relative z-10 max-w-[560px] px-10 xl:px-16 login-glass-card">
          <h2 className="login-hero-title font-bold tracking-tight" style={{ color: '#10213F' }}>
            Gestione su óptica<br />
            de manera{' '}
            <span style={{ color: '#10AAA8' }}>eficiente</span>
          </h2>
          <p className="login-hero-text">
            Control total de pacientes, inventario, ventas
            y finanzas en una sola plataforma diseñada
            para ópticas en Latinoamérica.
          </p>

          {/* Feature chips */}
          <div className="flex flex-wrap gap-3 max-w-[520px] mt-2" data-testid="login-features">
            {FEATURES.map(({ icon: Icon, label, color }) => (
              <div
                key={label}
                className="login-chip"
                data-testid={`feature-${label.toLowerCase()}`}
              >
                <Icon className="w-[18px] h-[18px]" style={{ color }} strokeWidth={2} />
                <span style={{ color }}>{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
