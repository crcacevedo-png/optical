import React, { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import { CheckCircle2, Loader2, Sparkles, Eye, EyeOff, MailCheck, ShieldCheck } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const publicApi = axios.create({ baseURL: API_URL, withCredentials: false });

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const CONSENT_TEXT =
  'Acepto que Cortexia Optical utilice mis datos para crear y administrar mi cuenta, y para contactarme por WhatsApp y correo electrónico. Mis datos serán tratados de forma confidencial y puedo solicitar su eliminación cuando lo desee.';

const errText = (detail) => (typeof detail === 'string' ? detail : 'Ocurrió un error. Intenta de nuevo en un momento.');

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
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50 flex flex-col items-center justify-center px-4 py-8" data-testid="register-page">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center mb-6">
          <img
            src="https://customer-assets.emergentagent.com/job_eyecare-erp/artifacts/80lobcqc_logo%20cortexia%20optical%20transparente.png"
            alt="Cortexia Optical"
            className="h-24 w-auto object-contain"
            data-testid="register-logo"
          />
        </div>

        {done ? (
          <div className="bg-white rounded-3xl shadow-xl border border-slate-100 p-8 text-center" data-testid="register-success">
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
          <div className="bg-white rounded-3xl shadow-xl border border-slate-100 p-6 sm:p-8">
            <div className="text-center mb-5">
              <h1 className="text-2xl font-bold text-slate-900">Crea tu cuenta gratis</h1>
              <p className="text-sm text-slate-500 mt-1">Empieza hoy mismo a administrar tu óptica. Sin tarjeta.</p>
            </div>

            <div className="flex items-center justify-center gap-4 mb-5 text-[11px] text-slate-500">
              <span className="inline-flex items-center gap-1"><ShieldCheck className="w-3.5 h-3.5 text-emerald-500" /> Sin tarjeta</span>
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
                  placeholder="Tu nombre" className="mt-1 h-11 rounded-xl" />
                {errors.name && <p className="text-xs text-red-500 mt-1" data-testid="error-name">{errors.name}</p>}
              </div>

              <div>
                <Label htmlFor="optica" className="text-slate-700">Nombre de la óptica *</Label>
                <Input id="optica" data-testid="register-optica-input" value={form.optica_name}
                  onChange={(e) => setField('optica_name', e.target.value)} onBlur={() => blur('optica_name')}
                  placeholder="Ej: Óptica Visión Clara" className="mt-1 h-11 rounded-xl" />
                {errors.optica_name && <p className="text-xs text-red-500 mt-1" data-testid="error-optica">{errors.optica_name}</p>}
              </div>

              <div>
                <Label htmlFor="email" className="text-slate-700">Correo electrónico *</Label>
                <Input id="email" type="email" data-testid="register-email-input" value={form.email}
                  onChange={(e) => setField('email', e.target.value)} onBlur={() => blur('email')}
                  placeholder="tucorreo@ejemplo.com" className="mt-1 h-11 rounded-xl" />
                {errors.email && <p className="text-xs text-red-500 mt-1" data-testid="error-email">{errors.email}</p>}
              </div>

              <div>
                <Label htmlFor="password" className="text-slate-700">Contraseña *</Label>
                <div className="relative">
                  <Input id="password" type={showPw ? 'text' : 'password'} data-testid="register-password-input" value={form.password}
                    onChange={(e) => setField('password', e.target.value)} onBlur={() => blur('password')}
                    placeholder="Mínimo 8 caracteres" className="mt-1 h-11 rounded-xl pr-11" />
                  <button type="button" onClick={() => setShowPw((s) => !s)} tabIndex={-1}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600" data-testid="register-toggle-password">
                    {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {errors.password
                  ? <p className="text-xs text-red-500 mt-1" data-testid="error-password">{errors.password}</p>
                  : <p className="text-xs text-slate-400 mt-1">Usa mayúsculas, minúsculas y números.</p>}
              </div>

              <div>
                <Label htmlFor="confirm" className="text-slate-700">Confirmar contraseña *</Label>
                <Input id="confirm" type={showPw ? 'text' : 'password'} data-testid="register-confirm-input" value={form.confirm}
                  onChange={(e) => setField('confirm', e.target.value)} onBlur={() => blur('confirm')}
                  placeholder="Repite tu contraseña" className="mt-1 h-11 rounded-xl" />
                {errors.confirm && <p className="text-xs text-red-500 mt-1" data-testid="error-confirm">{errors.confirm}</p>}
              </div>

              <div>
                <Label htmlFor="whatsapp" className="text-slate-700">Número de WhatsApp *</Label>
                <Input id="whatsapp" data-testid="register-whatsapp-input" value={form.whatsapp} inputMode="tel"
                  onChange={(e) => setField('whatsapp', e.target.value)} onBlur={() => blur('whatsapp')}
                  placeholder="Ej: 5555 5555 (Guatemala)" className="mt-1 h-11 rounded-xl" />
                {errors.whatsapp
                  ? <p className="text-xs text-red-500 mt-1" data-testid="error-whatsapp">{errors.whatsapp}</p>
                  : <p className="text-xs text-slate-400 mt-1">Si es de Guatemala, basta con los 8 dígitos.</p>}
              </div>

              <div>
                <Label htmlFor="location" className="text-slate-700">Ciudad / país</Label>
                <Input id="location" data-testid="register-location-input" value={form.location}
                  onChange={(e) => setField('location', e.target.value)}
                  placeholder="Ej: Ciudad de Guatemala, Guatemala" className="mt-1 h-11 rounded-xl" />
              </div>

              <div>
                <Label htmlFor="promo" className="text-slate-700 flex items-center gap-1">
                  <Sparkles className="w-3.5 h-3.5 text-amber-500" /> Código de promoción (opcional)
                </Label>
                <Input id="promo" data-testid="register-promo-input" value={form.promo_code}
                  onChange={(e) => setField('promo_code', e.target.value.toUpperCase())}
                  placeholder="Si tienes un código, escríbelo aquí" className="mt-1 h-11 rounded-xl uppercase" />
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
                className="w-full h-12 rounded-full text-base bg-[#1B2A49] hover:bg-[#111d33]">
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
  );
}
