import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { CheckCircle2, Loader2, XCircle, Clock } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const publicApi = axios.create({ baseURL: API_URL, withCredentials: false });

export default function VerifyRegistrationPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('loading'); // loading | success | expired | error
  const [message, setMessage] = useState('');
  const [company, setCompany] = useState('');
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    const token = searchParams.get('token');
    if (!token) {
      setStatus('error');
      setMessage('El enlace de verificación no es válido.');
      return;
    }
    (async () => {
      try {
        const { data } = await publicApi.post('/api/registration/verify', { token });
        setCompany(data?.company_name || '');
        setStatus('success');
      } catch (err) {
        const code = err?.response?.status;
        const detail = err?.response?.data?.detail;
        if (code === 410) {
          setStatus('expired');
          setMessage(typeof detail === 'string' ? detail : 'El enlace expiró.');
        } else {
          setStatus('error');
          setMessage(typeof detail === 'string' ? detail : 'No se pudo verificar tu cuenta.');
        }
      }
    })();
  }, [searchParams]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50 flex flex-col items-center justify-center px-4 py-8" data-testid="verify-page">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center mb-6">
          <img
            src="https://customer-assets.emergentagent.com/job_eyecare-erp/artifacts/80lobcqc_logo%20cortexia%20optical%20transparente.png"
            alt="Cortexia Optical"
            className="h-24 w-auto object-contain"
          />
        </div>

        <div className="bg-white rounded-3xl shadow-xl border border-slate-100 p-8 text-center">
          {status === 'loading' && (
            <div data-testid="verify-loading">
              <Loader2 className="w-10 h-10 text-[#1B2A49] animate-spin mx-auto mb-4" />
              <h1 className="text-xl font-bold text-slate-900">Verificando tu cuenta…</h1>
              <p className="text-slate-500 mt-1">Un momento por favor.</p>
            </div>
          )}

          {status === 'success' && (
            <div data-testid="verify-success">
              <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="w-9 h-9 text-emerald-600" />
              </div>
              <h1 className="text-2xl font-bold text-slate-900 mb-2">¡Correo verificado!</h1>
              <p className="text-slate-500">
                Tu cuenta{company ? <> de <strong className="text-slate-700">{company}</strong></> : ''} ya está activa.
                Ya puedes iniciar sesión y empezar a usar Cortexia.
              </p>
              <Button className="mt-6 w-full h-12 rounded-full text-base bg-[#1B2A49] hover:bg-[#111d33]"
                onClick={() => navigate('/login')} data-testid="verify-login-btn">
                Iniciar sesión
              </Button>
            </div>
          )}

          {status === 'expired' && (
            <div data-testid="verify-expired">
              <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center mx-auto mb-4">
                <Clock className="w-9 h-9 text-amber-600" />
              </div>
              <h1 className="text-2xl font-bold text-slate-900 mb-2">Enlace expirado</h1>
              <p className="text-slate-500">{message}</p>
              <Link to="/registro">
                <Button variant="outline" className="mt-6 rounded-full" data-testid="verify-register-again-btn">
                  Volver a registrarme
                </Button>
              </Link>
            </div>
          )}

          {status === 'error' && (
            <div data-testid="verify-error">
              <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
                <XCircle className="w-9 h-9 text-red-600" />
              </div>
              <h1 className="text-2xl font-bold text-slate-900 mb-2">No pudimos verificar tu cuenta</h1>
              <p className="text-slate-500">{message}</p>
              <div className="mt-6 flex flex-col gap-2">
                <Link to="/registro">
                  <Button variant="outline" className="rounded-full w-full" data-testid="verify-register-btn">Volver a registrarme</Button>
                </Link>
                <Link to="/login" className="text-sm text-[#1B2A49] font-semibold hover:underline">Ir a iniciar sesión</Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
