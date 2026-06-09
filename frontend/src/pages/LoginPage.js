import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, formatApiErrorDetail } from '../context/AuthContext';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Eye, EyeOff, Users, Package, Calendar, FileText, ShieldCheck } from 'lucide-react';

const LOGO_URL = 'https://customer-assets.emergentagent.com/job_eyecare-erp/artifacts/80lobcqc_logo%20cortexia%20optical%20transparente.png';

const NODES = [
  { x: 12, y: 8, s: 4, d: 0 }, { x: 28, y: 14, s: 3, d: 0.5 },
  { x: 48, y: 6, s: 5, d: 1.2 }, { x: 72, y: 10, s: 3, d: 1.8 },
  { x: 88, y: 18, s: 4, d: 0.3 }, { x: 8, y: 32, s: 3, d: 0.8 },
  { x: 32, y: 28, s: 5, d: 1.5 }, { x: 55, y: 24, s: 4, d: 0.6 },
  { x: 78, y: 30, s: 3, d: 2.0 }, { x: 92, y: 40, s: 4, d: 0.4 },
  { x: 18, y: 48, s: 4, d: 1.1 }, { x: 42, y: 44, s: 5, d: 0.7 },
  { x: 62, y: 50, s: 3, d: 1.4 }, { x: 82, y: 46, s: 4, d: 0.2 },
  { x: 10, y: 64, s: 3, d: 1.6 }, { x: 35, y: 60, s: 4, d: 0.9 },
  { x: 52, y: 68, s: 5, d: 1.3 }, { x: 75, y: 62, s: 3, d: 0.5 },
  { x: 90, y: 58, s: 4, d: 1.7 }, { x: 22, y: 78, s: 3, d: 0.1 },
  { x: 48, y: 82, s: 4, d: 1.0 }, { x: 68, y: 76, s: 3, d: 0.6 },
  { x: 85, y: 72, s: 4, d: 1.9 }, { x: 15, y: 90, s: 3, d: 0.8 },
  { x: 58, y: 92, s: 4, d: 1.2 }, { x: 80, y: 88, s: 3, d: 0.4 },
];

const CONNECTIONS = [
  [0,1],[1,2],[2,3],[3,4],[5,6],[6,7],[7,8],[8,9],
  [10,11],[11,12],[12,13],[14,15],[15,16],[16,17],[17,18],
  [19,20],[20,21],[21,22],[23,24],[24,25],
  [1,6],[2,7],[3,8],[6,11],[7,12],[8,13],
  [10,15],[11,16],[12,17],[14,19],[15,20],[16,21],
  [17,22],[19,23],[20,24],[21,25],
  [0,5],[5,10],[10,14],[14,19],[19,23],
  [4,9],[9,13],[13,18],[18,22],[22,25],
];

const FEATURES = [
  { icon: Users, label: 'Pacientes' },
  { icon: Package, label: 'Inventario' },
  { icon: FileText, label: 'Recetas' },
  { icon: Calendar, label: 'Agenda' },
  { icon: ShieldCheck, label: 'Seguridad' },
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

  const nodeColor = (i) => {
    if (i % 3 === 0) return { bg: 'rgba(26,188,156,0.7)', shadow: '0 0 10px rgba(26,188,156,0.4)' };
    if (i % 3 === 1) return { bg: 'rgba(90,45,130,0.6)', shadow: '0 0 10px rgba(90,45,130,0.3)' };
    return { bg: 'rgba(255,255,255,0.45)', shadow: '0 0 8px rgba(255,255,255,0.2)' };
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
          </form>

          {/* Demo credentials */}
          <div className="mt-8 login-stagger-4">
            <div className="p-4 rounded-xl bg-slate-50/80 border border-slate-100">
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.15em] mb-3">
                Credenciales Demo
              </p>
              <div className="space-y-2 text-[13px]">
                <div className="flex items-center gap-2 text-slate-500">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#5A2D82] shrink-0" />
                  <span className="font-semibold text-slate-600">Admin:</span>
                  <span className="text-slate-400">admin@cortexia.gt / Demo123!</span>
                </div>
                <div className="flex items-center gap-2 text-slate-500">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#1ABC9C] shrink-0" />
                  <span className="font-semibold text-slate-600">Usuario:</span>
                  <span className="text-slate-400">vendedor@cortexia.gt / Demo123!</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ═══════ RIGHT PANEL — Abstract Tech ═══════ */}
      <div
        className="hidden lg:flex relative overflow-hidden items-center justify-center"
        style={{ background: 'linear-gradient(160deg, #1B2A49 0%, #162240 40%, #1B2A49 100%)' }}
        data-testid="login-right-panel"
      >
        {/* Gradient Orbs */}
        <div className="login-orb login-orb-purple" />
        <div className="login-orb login-orb-teal" />
        <div className="login-orb login-orb-purple-secondary" />

        {/* SVG Connection Lines */}
        <svg className="absolute inset-0 w-full h-full" style={{ zIndex: 1 }}>
          {CONNECTIONS.map(([a, b], i) => (
            <line
              key={`conn-${a}-${b}`}
              x1={`${NODES[a].x}%`} y1={`${NODES[a].y}%`}
              x2={`${NODES[b].x}%`} y2={`${NODES[b].y}%`}
              stroke="rgba(26,188,156,0.1)"
              strokeWidth="1"
              className="login-line"
              style={{ animationDelay: `${i * 0.04}s` }}
            />
          ))}
        </svg>

        {/* Neural Network Nodes */}
        {NODES.map((node, i) => {
          const c = nodeColor(i);
          return (
            <div
              key={i}
              className="absolute rounded-full login-node"
              style={{
                left: `${node.x}%`,
                top: `${node.y}%`,
                width: `${node.s}px`,
                height: `${node.s}px`,
                background: c.bg,
                boxShadow: c.shadow,
                animationDelay: `${node.d}s`,
                zIndex: 2,
              }}
            />
          );
        })}

        {/* Glassmorphism Central Card */}
        <div className="relative z-10 max-w-[420px] mx-8 login-glass-card">
          <div
            className="p-9 rounded-2xl"
            style={{
              background: 'rgba(255,255,255,0.05)',
              backdropFilter: 'blur(24px)',
              WebkitBackdropFilter: 'blur(24px)',
              border: '1px solid rgba(255,255,255,0.08)',
              boxShadow: '0 8px 40px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.05)',
            }}
            data-testid="login-glass-card"
          >
            <h2
              className="font-heading text-3xl sm:text-[2.1rem] font-bold leading-tight mb-4"
              style={{
                background: 'linear-gradient(135deg, #FFFFFF 0%, #1ABC9C 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}
            >
              Gestione su óptica de manera eficiente
            </h2>
            <p className="text-white/40 text-sm leading-relaxed mb-7">
              Control total de pacientes, inventario, ventas y finanzas en una sola plataforma diseñada para ópticas en Latinoamérica.
            </p>

            {/* Feature Tags */}
            <div className="flex flex-wrap gap-2">
              {FEATURES.map(({ icon: Icon, label }) => (
                <span
                  key={label}
                  className="login-feature-tag inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium"
                >
                  <Icon className="w-3 h-3" />
                  {label}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
