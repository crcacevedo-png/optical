import React, { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import { CheckCircle2, Loader2, Sparkles, Eye, EyeOff, MailCheck, ShieldCheck, Glasses, Users, Lock } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const publicApi = axios.create({ baseURL: API_URL, withCredentials: false });

const LOGO_URL = 'https://customer-assets.emergentagent.com/job_eyecare-erp/artifacts/80lobcqc_logo%20cortexia%20optical%20transparente.png';
const OPTICA_IMG = 'https://images.unsplash.com/photo-1593214451196-37e0651f8ef2?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NTZ8MHwxfHNlYXJjaHwzfHxtb2Rlcm4lMjBvcHRpY2FsJTIwZXlld2VhciUyMHN0b3JlJTIwaW50ZXJpb3J8ZW58MHx8fHwxNzkwNzEwMjE1fDA&ixlib=rb-4.1.0&q=85';

const OVERLAY_DESKTOP =
  'linear-gradient(to top, rgba(8,14,26,0.96) 0%, rgba(12,22,40,0.55) 55%, rgba(16,28,52,0.30) 100%), linear-gradient(115deg, rgba(11,20,36,0.90) 0%, rgba(18,33,60,0.62) 60%, rgba(19,184,176,0.10) 100%)';
const OVERLAY_MOBILE =
  'linear-gradient(to top, rgba(8,14,26,0.94) 0%, rgba(12,22,40,0.70) 60%, rgba(16,28,52,0.45) 100%)';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const CONSENT_TEXT =
  'Acepto que Cortexia Optical utilice mis datos para crear y administrar mi cuenta, y para contactarme por WhatsApp y correo electrónico. Mis datos serán tratados de forma confidencial y puedo solicitar su eliminación cuando lo desee.';

const FEATURES = [
  { icon: Users, text: 'Pacientes, recetas y ventas en un solo lugar' },
  { icon: Sparkles, text: 'Gratis hasta 50 pacientes, para siempre' },
  { icon: ShieldCheck, text: 'Sin tarjeta de crédito para empezar' },
  { icon: Lock, text: 'Tus datos, seguros y respaldados' },
];

const errText = (detail) => (typeof detail === 'string' ? detail : 'Ocurrió un error. Intenta de nuevo en un momento.');

const Wordmark = ({ className = '' }) => (
  <div className={`flex items-center gap-2.5 ${className}`}>
    <span className="inline-flex items-center justify-center w-9 h-9 rounded-xl bg-white/10 ring-1 ring-white/20 backdrop-blur">
      <Glasses className="w-5 h-5 text-[#5EEAD4]" />
    </span>
    <div className="leading-none">
      <span className="block text-white font-bold tracking-[0.18em] text-sm">CORTEXIA</span>
      <span className="block text-[#8DD9D4] tracking-[0.42em] text-[10px] mt-0.5">OPTICAL</span>
    </div>
  </div>
);

export default function SelfRegisterPage() {
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState({
    name: '', optica_name: '', email: '', password: '', confirm: '',
    whatsapp: '', location: '', promo_code: '', consent: false, website: '',
  });
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [serverError, setServerError] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [source, setSource] = useState('no_especificado');
  const [sourceDetails, setSourceDetails] = useState({});
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  const [submittedEmail, setSubmittedEmail] = useState('');

  useEffect(() => {
    const params = Object.fromEntries(searchParams.entries());
    const src =
      params.utm_source || params.origen || params.source || params.ref ||
      (params.fbclid ? 'facebook' : '') || (params.gclid ? 'google' : '') || 'no_especificado';
    setSource(src);
    setSourceDetails(params);
    if (params.codigo || params.code) {
      setForm((f) => ({ ...f, promo_code: (params.codigo || params.code).toUpperCase() }));
    }
  }, [searchParams]);

  const validate = (f) => {
    const e = {};
    if (!f.name.trim()) e.name = 'El nombre es obligatorio.';
    if (!f.optica_name.trim()) e.optica_name = 'El nombre de la óptica es obligatorio.';
    if (!f.email.trim()) e.email = 'El correo es obligatorio.';
    else if (!EMAIL_RE.test(f.email.trim())) e.email = 'Ingresa un correo válido.';
    if (!f.password) e.password = 'Crea una contraseña.';
    else if (f.password.length < 8) e.password = 'Mínimo 8 caracteres.';
    else if (!/[A-Z]/.test(f.password)) e.password = 'Agrega al menos una mayúscula.';
    else if (!/[a-z]/.test(f.password)) e.password = 'Agrega al menos una minúscula.';
    else if (!/\d/.test(f.password)) e.password = 'Agrega al menos un número.';
    if (f.confirm !== f.password) e.confirm = 'Las contraseñas no coinciden.';
    const digits = (f.whatsapp || '').replace(/[^0-9]/g, '');
    if (!f.whatsapp.trim()) e.whatsapp = 'El número de WhatsApp es obligatorio.';
    else if (digits.length < 8) e.whatsapp = 'Ingresa un número de WhatsApp válido.';
    if (!f.consent) e.consent = 'Debes aceptar el consentimiento para continuar.';
    return e;
  };

  const setField = (k, v) => {
    const nf = { ...form, [k]: v };
    setForm(nf);
    if (touched[k] || k === 'consent') setErrors(validate(nf));
  };
  const blur = (k) => { setTouched((t) => ({ ...t, [k]: true })); setErrors(validate(form)); };

  const submit = async (e) => {
    e.preventDefault();
    setServerError('');
    const eObj = validate(form);
    setErrors(eObj);
    setTouched({ name: true, optica_name: true, email: true, password: true, confirm: true, whatsapp: true, consent: true });
    if (Object.keys(eObj).length > 0) return;
    setSubmitting(true);
    try {
      await publicApi.post('/api/registration', {
        name: form.name.trim(),
        optica_name: form.optica_name.trim(),
        email: form.email.trim(),
        password: form.password,
        whatsapp: form.whatsapp.trim(),
        location: form.location.trim(),
        promo_code: form.promo_code.trim(),
        consent: form.consent,
        website: form.website,
        source,
        source_details: sourceDetails,
      });
      setSubmittedEmail(form.email.trim());
      setDone(true);
    } catch (err) {
      setServerError(errText(err?.response?.data?.detail));
    } finally {
      setSubmitting(false);
    }
  };

  const resend = async () => {
    if (!submittedEmail) return;
    setResending(true);
    try {
      await publicApi.post('/api/registration/resend', { email: submittedEmail });
      setResent(true);
    } catch (_) {
      setResent(true);
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="min-h-screen w-full lg:grid lg:grid-cols-[46%_54%] bg-white" data-testid="register-page">
      <style>{`
        @keyframes cx-kenburns { 0% { transform: scale(1.05) translate(0,0); } 100% { transform: scale(1.15) translate(-1.5%, -2%); } }
        @keyframes cx-fade-up { 0% { opacity: 0; transform: translateY(14px); } 100% { opacity: 1; transform: translateY(0); } }
        .cx-anim { animation: cx-fade-up .6s cubic-bezier(.16,.84,.44,1) both; }
      `}</style>

      {/* ═══════ LEFT — Óptica image / brand (desktop) ═══════ */}
      <aside className="relative hidden lg:block overflow-hidden" data-testid="register-brand-panel">
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url(${OPTICA_IMG})`, animation: 'cx-kenburns 22s ease-out infinite alternate' }}
          aria-hidden="true"
        />
        <div className="absolute inset-0" style={{ backgroundImage: OVERLAY_DESKTOP }} aria-hidden="true" />
        <div className="relative z-10 h-full min-h-screen flex flex-col justify-between p-10 xl:p-14">
          <Wordmark className="cx-anim" />

          <div className="max-w-[440px]">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[#5EEAD4] bg-[#5EEAD4]/10 ring-1 ring-[#5EEAD4]/25 rounded-full px-3 py-1 mb-5 cx-anim" style={{ animationDelay: '.05s' }}>
              <Sparkles className="w-3.5 h-3.5" /> Empieza gratis hoy
            </span>
            <h2 className="text-white font-bold tracking-tight text-4xl xl:text-[2.75rem] leading-[1.1] cx-anim" style={{ animationDelay: '.1s' }}>
              Administra tu óptica,<br />
              <span className="text-[#5EEAD4]">sin complicaciones</span>
            </h2>
            <p className="text-slate-200/85 text-base mt-4 leading-relaxed max-w-[400px] cx-anim" style={{ animationDelay: '.16s' }}>
              Pacientes, recetas, inventario, ventas y finanzas en una sola plataforma diseñada para ópticas de Latinoamérica.
            </p>

            <ul className="mt-8 space-y-3.5">
              {FEATURES.map(({ icon: Icon, text }, i) => (
                <li key={text} className="flex items-center gap-3 text-slate-100 cx-anim" style={{ animationDelay: `${0.22 + i * 0.06}s` }}>
                  <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-white/10 ring-1 ring-white/15">
                    <Icon className="w-4 h-4 text-[#5EEAD4]" />
                  </span>
                  <span className="text-[15px]">{text}</span>
                </li>
              ))}
            </ul>
          </div>

          <p className="text-slate-300/70 text-xs cx-anim" style={{ animationDelay: '.5s' }}>
            © {new Date().getFullYear()} Cortexia Optical · Software para ópticas
          </p>
        </div>
      </aside>

      {/* ═══════ RIGHT — Form / success ═══════ */}
      <main className="relative flex flex-col lg:h-screen lg:overflow-y-auto">
        {/* Mobile hero band */}
        <div className="lg:hidden relative h-40 overflow-hidden">
          <div className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: `url(${OPTICA_IMG})` }} aria-hidden="true" />
          <div className="absolute inset-0" style={{ backgroundImage: OVERLAY_MOBILE }} aria-hidden="true" />
          <div className="relative z-10 h-full flex flex-col items-center justify-center gap-2 px-4 text-center">
            <Wordmark />
            <p className="text-slate-100 text-sm font-medium">Empieza gratis hasta 50 pacientes</p>
          </div>
        </div>

        <div className="flex-1 flex items-start lg:items-center justify-center px-4 sm:px-8 py-8 lg:py-10">
          <div className="w-full max-w-md">
            {/* Logo (desktop, white panel) */}
            <div className="hidden lg:flex justify-center mb-4">
              <img src={LOGO_URL} alt="Cortexia Optical" className="h-20 w-auto object-contain select-none" draggable="false" data-testid="register-logo" />
            </div>

            {done ? (
              <div className="bg-white rounded-3xl shadow-xl ring-1 ring-slate-100 p-8 text-center cx-anim" data-testid="register-success">
                <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-4">
                  <MailCheck className="w-9 h-9 text-emerald-600" />
                </div>
                <h1 className="text-2xl font-bold text-slate-900 mb-2">Revisa tu correo</h1>
                <p className="text-slate-500">
                  Enviamos un enlace de verificación a <strong className="text-slate-700">{submittedEmail}</strong>.
                  Haz clic en él para activar tu cuenta y empezar a usar Cortexia.
                </p>
                <p className="text-xs text-slate-400 mt-3">¿No lo ves? Revisa la carpeta de spam o correo no deseado.</p>
                <div className="mt-6 space-y-3">
                  {resent ? (
                    <p className="text-sm text-emerald-600 flex items-center justify-center gap-1.5" data-testid="register-resent-msg">
                      <CheckCircle2 className="w-4 h-4" /> Enlace reenviado. Revisa tu correo.
                    </p>
                  ) : (
                    <Button variant="outline" className="rounded-full" onClick={resend} disabled={resending} data-testid="register-resend-btn">
                      {resending ? <><Loader2 className="w-4 h-4 animate-spin mr-2" /> Reenviando…</> : 'Reenviar correo de verificación'}
                    </Button>
                  )}
                  <div>
                    <Link to="/login" className="text-sm text-[#1B2A49] font-semibold hover:underline" data-testid="register-goto-login">
                      Ir a iniciar sesión
                    </Link>
                  </div>
                </div>
              </div>
            ) : (
              <div className="cx-anim">
                <div className="text-center lg:text-left mb-5">
                  <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">Crea tu cuenta gratis</h1>
                  <p className="text-sm text-slate-500 mt-1.5">Empieza hoy mismo a administrar tu óptica. Sin tarjeta.</p>
                </div>

                <div className="flex items-center gap-4 mb-6 text-[11px] text-slate-500 justify-center lg:justify-start">
                  <span className="inline-flex items-center gap-1"><ShieldCheck className="w-3.5 h-3.5 text-emerald-500" /> Sin tarjeta</span>
                  <span className="w-1 h-1 rounded-full bg-slate-300" />
                  <span className="inline-flex items-center gap-1"><Sparkles className="w-3.5 h-3.5 text-amber-500" /> Gratis hasta 50 pacientes</span>
                </div>

                <form onSubmit={submit} className="space-y-4" noValidate>
                  {/* honeypot */}
                  <input type="text" name="website" value={form.website} onChange={(e) => setField('website', e.target.value)}
                    className="hidden" tabIndex={-1} autoComplete="off" aria-hidden="true" />

                  <div>
                    <Label htmlFor="name" className="text-slate-700">Nombre completo *</Label>
                    <Input id="name" data-testid="register-name-input" value={form.name}
                      onChange={(e) => setField('name', e.target.value)} onBlur={() => blur('name')}
                      placeholder="Tu nombre" className="mt-1 h-11 rounded-xl focus-visible:ring-[#13B8B0]" />
                    {errors.name && <p className="text-xs text-red-500 mt-1" data-testid="error-name">{errors.name}</p>}
                  </div>

                  <div>
                    <Label htmlFor="optica" className="text-slate-700">Nombre de la óptica *</Label>
                    <Input id="optica" data-testid="register-optica-input" value={form.optica_name}
                      onChange={(e) => setField('optica_name', e.target.value)} onBlur={() => blur('optica_name')}
                      placeholder="Ej: Óptica Visión Clara" className="mt-1 h-11 rounded-xl focus-visible:ring-[#13B8B0]" />
                    {errors.optica_name && <p className="text-xs text-red-500 mt-1" data-testid="error-optica">{errors.optica_name}</p>}
                  </div>

                  <div>
                    <Label htmlFor="email" className="text-slate-700">Correo electrónico *</Label>
                    <Input id="email" type="email" data-testid="register-email-input" value={form.email}
                      onChange={(e) => setField('email', e.target.value)} onBlur={() => blur('email')}
                      placeholder="tucorreo@ejemplo.com" className="mt-1 h-11 rounded-xl focus-visible:ring-[#13B8B0]" />
                    {errors.email && <p className="text-xs text-red-500 mt-1" data-testid="error-email">{errors.email}</p>}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="password" className="text-slate-700">Contraseña *</Label>
                      <div className="relative">
                        <Input id="password" type={showPw ? 'text' : 'password'} data-testid="register-password-input" value={form.password}
                          onChange={(e) => setField('password', e.target.value)} onBlur={() => blur('password')}
                          placeholder="Mín. 8 caracteres" className="mt-1 h-11 rounded-xl pr-11 focus-visible:ring-[#13B8B0]" />
                        <button type="button" onClick={() => setShowPw((s) => !s)} tabIndex={-1}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors" data-testid="register-toggle-password">
                          {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                      {errors.password && <p className="text-xs text-red-500 mt-1" data-testid="error-password">{errors.password}</p>}
                    </div>

                    <div>
                      <Label htmlFor="confirm" className="text-slate-700">Confirmar *</Label>
                      <Input id="confirm" type={showPw ? 'text' : 'password'} data-testid="register-confirm-input" value={form.confirm}
                        onChange={(e) => setField('confirm', e.target.value)} onBlur={() => blur('confirm')}
                        placeholder="Repite tu contraseña" className="mt-1 h-11 rounded-xl focus-visible:ring-[#13B8B0]" />
                      {errors.confirm && <p className="text-xs text-red-500 mt-1" data-testid="error-confirm">{errors.confirm}</p>}
                    </div>
                  </div>
                  {!errors.password && !errors.confirm && (
                    <p className="text-xs text-slate-400 -mt-2">Usa mayúsculas, minúsculas y números.</p>
                  )}

                  <div>
                    <Label htmlFor="whatsapp" className="text-slate-700">Número de WhatsApp *</Label>
                    <Input id="whatsapp" data-testid="register-whatsapp-input" value={form.whatsapp} inputMode="tel"
                      onChange={(e) => setField('whatsapp', e.target.value)} onBlur={() => blur('whatsapp')}
                      placeholder="Ej: 5555 5555 (Guatemala)" className="mt-1 h-11 rounded-xl focus-visible:ring-[#13B8B0]" />
                    {errors.whatsapp
                      ? <p className="text-xs text-red-500 mt-1" data-testid="error-whatsapp">{errors.whatsapp}</p>
                      : <p className="text-xs text-slate-400 mt-1">Si es de Guatemala, basta con los 8 dígitos.</p>}
                  </div>

                  <div>
                    <Label htmlFor="location" className="text-slate-700">Ciudad / país</Label>
                    <Input id="location" data-testid="register-location-input" value={form.location}
                      onChange={(e) => setField('location', e.target.value)}
                      placeholder="Ej: Ciudad de Guatemala, Guatemala" className="mt-1 h-11 rounded-xl focus-visible:ring-[#13B8B0]" />
                  </div>

                  <div>
                    <Label htmlFor="promo" className="text-slate-700 flex items-center gap-1">
                      <Sparkles className="w-3.5 h-3.5 text-amber-500" /> Código de promoción (opcional)
                    </Label>
                    <Input id="promo" data-testid="register-promo-input" value={form.promo_code}
                      onChange={(e) => setField('promo_code', e.target.value.toUpperCase())}
                      placeholder="Si tienes un código, escríbelo aquí" className="mt-1 h-11 rounded-xl uppercase focus-visible:ring-[#13B8B0]" />
                  </div>

                  <label className="flex items-start gap-3 cursor-pointer pt-1">
                    <Checkbox checked={form.consent} onCheckedChange={(v) => setField('consent', !!v)}
                      data-testid="register-consent-checkbox" className="mt-0.5" />
                    <span className="text-xs text-slate-500 leading-relaxed">{CONSENT_TEXT}</span>
                  </label>
                  {errors.consent && <p className="text-xs text-red-500 -mt-2" data-testid="error-consent">{errors.consent}</p>}

                  {serverError && (
                    <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-3 py-2" data-testid="register-server-error">
                      {serverError}
                    </div>
                  )}

                  <Button type="submit" disabled={submitting} data-testid="register-submit-btn"
                    className="w-full h-12 rounded-full text-base bg-[#1B2A49] hover:bg-[#111d33] shadow-lg shadow-[#1B2A49]/20 transition-all hover:shadow-xl hover:shadow-[#1B2A49]/25 hover:-translate-y-0.5">
                    {submitting ? <><Loader2 className="w-4 h-4 animate-spin mr-2" /> Creando cuenta…</> : 'Crear cuenta gratis'}
                  </Button>

                  <div className="text-center pt-1 space-y-2">
                    <p className="text-sm text-slate-500">
                      ¿Ya tienes cuenta?{' '}
                      <Link to="/login" className="text-[#1B2A49] font-semibold hover:underline" data-testid="register-login-link">Inicia sesión</Link>
                    </p>
                    <p className="text-xs text-slate-400">
                      ¿Necesitas un plan superior?{' '}
                      <Link to="/contacto" className="text-indigo-600 hover:underline" data-testid="register-contact-link">Contáctanos</Link>
                    </p>
                  </div>
                </form>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
