import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import { CheckCircle2, Loader2, Sparkles } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const publicApi = axios.create({ baseURL: API_URL, withCredentials: false });

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const CONSENT_TEXT =
  'Acepto que Cortexia Optical utilice mis datos para contactarme por WhatsApp y correo electrónico con el fin de gestionar la apertura de mi cuenta. Mis datos serán tratados de forma confidencial y puedo solicitar su eliminación cuando lo desee.';

export default function PublicLeadFormPage() {
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState({ name: '', optica_name: '', location: '', whatsapp: '', email: '', promo_code: '', consent: false, website: '' });
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [serverError, setServerError] = useState('');
  const [source, setSource] = useState('no_especificado');
  const [sourceDetails, setSourceDetails] = useState({});

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
    if (!f.location.trim()) e.location = 'La ciudad / país es obligatoria.';
    const digits = (f.whatsapp || '').replace(/[^0-9]/g, '');
    if (!f.whatsapp.trim()) e.whatsapp = 'El número de WhatsApp es obligatorio.';
    else if (digits.length < 8) e.whatsapp = 'Ingresa un número de WhatsApp válido.';
    if (!f.email.trim()) e.email = 'El correo es obligatorio.';
    else if (!EMAIL_RE.test(f.email.trim())) e.email = 'Ingresa un correo válido.';
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
    setTouched({ name: true, whatsapp: true, email: true, consent: true });
    if (Object.keys(eObj).length > 0) return;
    setSubmitting(true);
    try {
      await publicApi.post('/api/leads', {
        name: form.name.trim(),
        optica_name: form.optica_name.trim(),
        location: form.location.trim(),
        whatsapp: form.whatsapp.trim(),
        email: form.email.trim(),
        promo_code: form.promo_code.trim(),
        consent: form.consent,
        website: form.website,
        source,
        source_details: sourceDetails,
      });
      setDone(true);
      setForm({ name: '', optica_name: '', location: '', whatsapp: '', email: '', promo_code: '', consent: false, website: '' });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setServerError(typeof detail === 'string' ? detail : 'Ocurrió un error. Intenta de nuevo en un momento.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50 flex flex-col items-center justify-center px-4 py-8" data-testid="public-lead-page">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center mb-6">
          <img
            src="https://customer-assets.emergentagent.com/job_eyecare-erp/artifacts/80lobcqc_logo%20cortexia%20optical%20transparente.png"
            alt="Cortexia Optical"
            className="h-16 w-auto object-contain"
            data-testid="public-lead-logo"
          />
        </div>

        {done ? (
          <div className="bg-white rounded-3xl shadow-xl border border-slate-100 p-8 text-center" data-testid="lead-success">
            <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-9 h-9 text-emerald-600" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900 mb-2">¡Solicitud enviada!</h1>
            <p className="text-slate-500">Recibimos tu solicitud. El equipo de Cortexia Optical te contactará pronto por WhatsApp o correo para abrir la cuenta de tu óptica.</p>
            <Button className="mt-6 rounded-full" variant="outline" onClick={() => setDone(false)} data-testid="another-response-btn">
              Enviar otra solicitud
            </Button>
          </div>
        ) : (
          <div className="bg-white rounded-3xl shadow-xl border border-slate-100 p-6 sm:p-8">
            <div className="text-center mb-6">
              <h1 className="text-2xl font-bold text-slate-900">Solicita tu cuenta</h1>
              <p className="text-sm text-slate-500 mt-1">Completa tus datos y el equipo de Cortexia Optical te ayudará a abrir la cuenta de tu óptica.</p>
            </div>

            <form onSubmit={submit} className="space-y-4" noValidate>
              {/* honeypot */}
              <input type="text" name="website" value={form.website} onChange={(e) => setField('website', e.target.value)}
                className="hidden" tabIndex={-1} autoComplete="off" aria-hidden="true" />

              <div>
                <Label htmlFor="name" className="text-slate-700">Nombre completo *</Label>
                <Input id="name" data-testid="lead-name-input" value={form.name}
                  onChange={(e) => setField('name', e.target.value)} onBlur={() => blur('name')}
                  placeholder="Tu nombre" className="mt-1 h-11 rounded-xl" />
                {errors.name && <p className="text-xs text-red-500 mt-1" data-testid="error-name">{errors.name}</p>}
              </div>

              <div>
                <Label htmlFor="optica" className="text-slate-700">Nombre de la óptica *</Label>
                <Input id="optica" data-testid="lead-optica-input" value={form.optica_name}
                  onChange={(e) => setField('optica_name', e.target.value)} onBlur={() => blur('optica_name')}
                  placeholder="Ej: Óptica Visión Clara" className="mt-1 h-11 rounded-xl" />
                {errors.optica_name && <p className="text-xs text-red-500 mt-1" data-testid="error-optica">{errors.optica_name}</p>}
              </div>

              <div>
                <Label htmlFor="location" className="text-slate-700">Ciudad / país *</Label>
                <Input id="location" data-testid="lead-location-input" value={form.location}
                  onChange={(e) => setField('location', e.target.value)} onBlur={() => blur('location')}
                  placeholder="Ej: Ciudad de Guatemala, Guatemala" className="mt-1 h-11 rounded-xl" />
                {errors.location && <p className="text-xs text-red-500 mt-1" data-testid="error-location">{errors.location}</p>}
              </div>

              <div>
                <Label htmlFor="whatsapp" className="text-slate-700">Número de WhatsApp *</Label>
                <Input id="whatsapp" data-testid="lead-whatsapp-input" value={form.whatsapp} inputMode="tel"
                  onChange={(e) => setField('whatsapp', e.target.value)} onBlur={() => blur('whatsapp')}
                  placeholder="Ej: 5555 5555 (Guatemala)" className="mt-1 h-11 rounded-xl" />
                {errors.whatsapp
                  ? <p className="text-xs text-red-500 mt-1" data-testid="error-whatsapp">{errors.whatsapp}</p>
                  : <p className="text-xs text-slate-400 mt-1">Si es de Guatemala, basta con los 8 dígitos.</p>}
              </div>

              <div>
                <Label htmlFor="email" className="text-slate-700">Correo electrónico *</Label>
                <Input id="email" type="email" data-testid="lead-email-input" value={form.email}
                  onChange={(e) => setField('email', e.target.value)} onBlur={() => blur('email')}
                  placeholder="tucorreo@ejemplo.com" className="mt-1 h-11 rounded-xl" />
                {errors.email && <p className="text-xs text-red-500 mt-1" data-testid="error-email">{errors.email}</p>}
              </div>

              <div>
                <Label htmlFor="promo" className="text-slate-700 flex items-center gap-1">
                  <Sparkles className="w-3.5 h-3.5 text-amber-500" /> Código de promoción (opcional)
                </Label>
                <Input id="promo" data-testid="lead-promo-input" value={form.promo_code}
                  onChange={(e) => setField('promo_code', e.target.value.toUpperCase())}
                  placeholder="Si tienes un código, escríbelo aquí" className="mt-1 h-11 rounded-xl uppercase" />
              </div>

              <label className="flex items-start gap-3 cursor-pointer pt-1">
                <Checkbox checked={form.consent} onCheckedChange={(v) => setField('consent', !!v)}
                  data-testid="lead-consent-checkbox" className="mt-0.5" />
                <span className="text-xs text-slate-500 leading-relaxed">{CONSENT_TEXT}</span>
              </label>
              {errors.consent && <p className="text-xs text-red-500 -mt-2" data-testid="error-consent">{errors.consent}</p>}

              {serverError && (
                <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-3 py-2" data-testid="lead-server-error">
                  {serverError}
                </div>
              )}

              <Button type="submit" disabled={submitting} data-testid="lead-submit-btn"
                className="w-full h-12 rounded-full text-base bg-[#1B2A49] hover:bg-[#111d33]">
                {submitting ? <><Loader2 className="w-4 h-4 animate-spin mr-2" /> Enviando…</> : 'Solicitar mi cuenta'}
              </Button>
              <p className="text-[11px] text-center text-slate-400">Tus datos son confidenciales. Puedes solicitar su eliminación cuando quieras.</p>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
