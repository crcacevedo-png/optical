import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth, formatApiErrorDetail } from '../context/AuthContext';
import { Mail, Lock, Eye, EyeOff, Users, Package, Calendar, FileText, ShoppingCart } from 'lucide-react';

const LOGO_URL = 'https://customer-assets.emergentagent.com/job_eyecare-erp/artifacts/80lobcqc_logo%20cortexia%20optical%20transparente.png';

// Imagen oficial provista por el usuario (mantener proporción completa)
const OPTICAL_STORE_IMG = 'https://customer-assets.emergentagent.com/job_eyecare-erp/artifacts/a56thl1o_Captura%20de%20pantalla%202026-06-11%20212336.png';

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
        {/* Decorative curve - top left */}
        <svg
          className="absolute -top-32 -left-32 w-[420px] h-[420px] pointer-events-none"
          viewBox="0 0 400 400"
          fill="none"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="curveLeftTop" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#6D35D8" stopOpacity="0.16" />
              <stop offset="100%" stopColor="#13B8B0" stopOpacity="0.04" />
            </linearGradient>
            <filter id="curveLeftBlur" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="18" />
            </filter>
          </defs>
          <path
            d="M0,0 C140,20 260,60 340,140 C400,210 380,300 320,340 C260,380 160,360 80,300 C20,250 -20,160 0,0 Z"
            fill="url(#curveLeftTop)"
            filter="url(#curveLeftBlur)"
          />
        </svg>

        {/* Decorative curve - bottom left (sutil acento secundario) */}
        <svg
          className="absolute -bottom-40 -left-24 w-[360px] h-[360px] pointer-events-none opacity-70"
          viewBox="0 0 400 400"
          fill="none"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="curveLeftBottom" x1="0%" y1="100%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#13B8B0" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#6D35D8" stopOpacity="0.05" />
            </linearGradient>
          </defs>
          <path
            d="M0,400 C20,280 80,180 180,140 C280,100 380,160 400,260 C400,360 320,400 220,400 C140,400 60,400 0,400 Z"
            fill="url(#curveLeftBottom)"
            style={{ filter: 'blur(24px)' }}
          />
        </svg>

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
        {/* Background image: optical store - imagen completa sin recortar */}
        <img
          src={OPTICAL_STORE_IMG}
          alt="Óptica Cortexia"
          className="absolute inset-0 w-full h-full object-contain"
          style={{ objectPosition: 'center center' }}
          draggable="false"
        />

        {/* Light wash overlay - sutil para mantener detalles de la imagen */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: 'linear-gradient(110deg, rgba(255,255,255,0.55) 0%, rgba(248,250,255,0.30) 40%, rgba(255,255,255,0.10) 75%, rgba(255,255,255,0.05) 100%)',
          }}
        />

        {/* Decorative curve - bottom right (forma curva prominente) */}
        <svg
          className="absolute -bottom-32 -right-24 w-[640px] h-[640px] pointer-events-none"
          viewBox="0 0 600 600"
          fill="none"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="curveRightBottom" x1="0%" y1="100%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#13B8B0" stopOpacity="0.42" />
              <stop offset="55%" stopColor="#6D35D8" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#6D35D8" stopOpacity="0.08" />
            </linearGradient>
            <filter id="curveRightBlur" x="-10%" y="-10%" width="120%" height="120%">
              <feGaussianBlur stdDeviation="22" />
            </filter>
          </defs>
          <path
            d="M600,200 C600,420 480,580 280,600 C140,600 40,520 0,360 C40,260 120,180 240,140 C360,100 480,120 560,160 C580,170 600,185 600,200 Z"
            fill="url(#curveRightBottom)"
            filter="url(#curveRightBlur)"
          />
        </svg>

        {/* Decorative curve - top left of right panel (acento violeta) */}
        <svg
          className="absolute -top-28 -left-20 w-[400px] h-[400px] pointer-events-none"
          viewBox="0 0 400 400"
          fill="none"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="curveRightTop" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#6D35D8" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#13B8B0" stopOpacity="0.10" />
            </linearGradient>
          </defs>
          <path
            d="M0,0 C160,10 280,50 360,140 C420,220 400,310 320,360 C240,400 140,380 70,320 C10,260 -20,140 0,0 Z"
            fill="url(#curveRightTop)"
            style={{ filter: 'blur(28px)' }}
          />
        </svg>

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
