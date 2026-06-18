import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../context/AuthContext';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/progress';
import {
  Rocket, CheckCircle2, Circle, ArrowRight, Lock, Building2,
  Store, Users, Package, UserPlus, ShoppingCart, Sparkles, Download,
  ShieldCheck, Mail
} from 'lucide-react';
import { toast } from 'sonner';

const STEPS = [
  {
    id: 'change_password',
    icon: Lock,
    title: 'Cambia tu contraseña inicial',
    description: 'Por seguridad, define una contraseña nueva que solo tú conozcas.',
    cta: 'Cambiar mi contraseña',
    href: null,
    action: 'open_password_dialog',
    color: '#6D35D8',
  },
  {
    id: 'company_data',
    icon: Building2,
    title: 'Configura los datos de tu óptica',
    description: 'Sube el logo, completa la dirección, NIT y datos fiscales que aparecerán en recetas y facturas.',
    cta: 'Ir a Configuración',
    href: '/settings',
    color: '#13B8B0',
  },
  {
    id: 'branches',
    icon: Store,
    title: 'Crea tus sucursales',
    description: 'Si tu óptica tiene más de una ubicación, créalas para asignar inventario y ventas por sucursal.',
    cta: 'Gestionar sucursales',
    href: '/branches',
    color: '#6D35D8',
  },
  {
    id: 'users',
    icon: Users,
    title: 'Da de alta a tu equipo',
    description: 'Crea cuentas para optometristas, vendedores y administradores adicionales.',
    cta: 'Crear usuarios',
    href: '/users',
    color: '#13B8B0',
  },
  {
    id: 'inventory',
    icon: Package,
    title: 'Carga tu inventario inicial',
    description: 'Registra monturas, lentes y accesorios con SKU, precios y stock por sucursal.',
    cta: 'Ir a inventario',
    href: '/inventory',
    color: '#6D35D8',
  },
  {
    id: 'first_patient',
    icon: UserPlus,
    title: 'Registra tu primer paciente',
    description: 'Comienza tu base de datos clínica registrando tu primer paciente.',
    cta: 'Agregar paciente',
    href: '/patients',
    color: '#13B8B0',
  },
  {
    id: 'first_sale',
    icon: ShoppingCart,
    title: 'Realiza tu primera venta',
    description: 'Crea una venta de prueba para validar el flujo completo de cobro y comprobantes.',
    cta: 'Ir a ventas',
    href: '/sales',
    color: '#6D35D8',
  },
];

export default function OnboardingPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [progress, setProgress] = useState({});
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      const { data } = await api.get('/api/onboarding/status');
      setProgress(data.progress || {});
    } catch (err) {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const toggleStep = async (stepId, completed) => {
    const next = { ...progress, [stepId]: completed };
    setProgress(next);
    try {
      await api.put('/api/onboarding/status', { step_id: stepId, completed });
      if (completed) {
        toast.success('¡Paso completado!');
      }
    } catch (err) {
      toast.error('No se pudo guardar el progreso');
      setProgress(progress); // rollback
    }
  };

  const completedCount = STEPS.filter(s => progress[s.id]).length;
  const progressPct = Math.round((completedCount / STEPS.length) * 100);
  const isComplete = completedCount === STEPS.length;

  const handleAction = (step) => {
    if (step.href) {
      navigate(step.href);
    } else if (step.action === 'open_password_dialog') {
      toast('Abre el menú superior derecho → "Cambiar mi contraseña"', {
        icon: '👆',
        duration: 5000,
      });
    }
  };

  const handleDismiss = async () => {
    try {
      await api.post('/api/onboarding/dismiss');
      toast.success('Onboarding cerrado. Puedes volver a verlo desde el menú.');
      navigate('/dashboard');
    } catch {}
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto" data-testid="onboarding-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1.5">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #6D35D8 0%, #13B8B0 100%)' }}
            >
              <Rocket className="w-5 h-5 text-white" />
            </div>
            <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">
              Inicio rápido
            </h1>
          </div>
          <p className="text-slate-500">
            Bienvenido a Cortexia Optical{user?.name ? `, ${user.name.split(' ')[0]}` : ''}. Completa estos {STEPS.length} pasos para dejar tu óptica operativa.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleDismiss} data-testid="dismiss-onboarding">
            Cerrar guía
          </Button>
        </div>
      </div>

      {/* Progress Card */}
      <Card className="border-slate-200/80 overflow-hidden">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-0.5">
                Tu progreso
              </p>
              <p className="font-heading text-2xl font-semibold text-slate-900">
                {completedCount} de {STEPS.length} pasos completados
              </p>
            </div>
            <div className="text-right">
              <p className="text-3xl font-bold" style={{
                background: 'linear-gradient(135deg, #6D35D8 0%, #13B8B0 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}>
                {progressPct}%
              </p>
            </div>
          </div>
          <Progress value={progressPct} className="h-2.5" />
          {isComplete && (
            <div className="mt-5 p-4 rounded-xl bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200/60 flex items-center gap-3" data-testid="onboarding-complete">
              <Sparkles className="w-6 h-6 text-emerald-600 shrink-0" />
              <div className="flex-1">
                <p className="font-semibold text-emerald-900 text-sm">¡Felicidades! Has completado el onboarding.</p>
                <p className="text-xs text-emerald-700">Tu óptica está lista para operar. Explora el resto de la plataforma desde el menú lateral.</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Steps */}
      <div className="space-y-3">
        {STEPS.map((step, idx) => {
          const Icon = step.icon;
          const done = !!progress[step.id];
          return (
            <Card
              key={step.id}
              className={`border transition-all ${done ? 'border-emerald-200 bg-emerald-50/30' : 'border-slate-200/80 hover:border-slate-300 hover:shadow-sm'}`}
              data-testid={`step-${step.id}`}
            >
              <CardContent className="py-4">
                <div className="flex items-start gap-4">
                  {/* Checkbox */}
                  <button
                    type="button"
                    onClick={() => toggleStep(step.id, !done)}
                    className="shrink-0 mt-0.5 transition-transform hover:scale-110"
                    data-testid={`toggle-${step.id}`}
                    aria-label={done ? 'Marcar como pendiente' : 'Marcar como completado'}
                  >
                    {done ? (
                      <CheckCircle2 className="w-7 h-7 text-emerald-600" strokeWidth={2} />
                    ) : (
                      <Circle className="w-7 h-7 text-slate-300 hover:text-slate-400" strokeWidth={1.8} />
                    )}
                  </button>

                  {/* Icon + content */}
                  <div className="flex items-start gap-4 flex-1 min-w-0">
                    <div
                      className="shrink-0 w-11 h-11 rounded-xl flex items-center justify-center"
                      style={{ background: done ? '#D1FAE5' : `${step.color}15` }}
                    >
                      <Icon className="w-5 h-5" style={{ color: done ? '#059669' : step.color }} strokeWidth={2} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-2 mb-0.5">
                        <span className="text-xs font-bold text-slate-400">PASO {idx + 1}</span>
                        {done && (
                          <span className="text-xs font-semibold text-emerald-600">COMPLETADO</span>
                        )}
                      </div>
                      <h3 className={`font-heading text-base font-semibold mb-1 ${done ? 'text-slate-500 line-through decoration-emerald-400/40' : 'text-slate-900'}`}>
                        {step.title}
                      </h3>
                      <p className="text-sm text-slate-500 leading-relaxed mb-3">
                        {step.description}
                      </p>
                      {!done && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleAction(step)}
                          className="text-sm"
                          data-testid={`cta-${step.id}`}
                        >
                          {step.cta} <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Bonus tips */}
      <Card className="border-slate-200/80 mt-8 bg-slate-50/40">
        <CardContent className="pt-6">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
            Más recursos
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Link to="/settings" className="flex items-start gap-3 p-3 rounded-xl bg-white border border-slate-200 hover:border-slate-300 hover:shadow-sm transition-all">
              <Download className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-slate-900">Descarga tu base de datos</p>
                <p className="text-xs text-slate-500">Excel completo con todos los datos</p>
              </div>
            </Link>
            <Link to="/settings" className="flex items-start gap-3 p-3 rounded-xl bg-white border border-slate-200 hover:border-slate-300 hover:shadow-sm transition-all">
              <ShieldCheck className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-slate-900">Seguridad y cumplimiento</p>
                <p className="text-xs text-slate-500">Descarga el manifiesto PDF</p>
              </div>
            </Link>
            <a href="mailto:info@cortexiagt.com" className="flex items-start gap-3 p-3 rounded-xl bg-white border border-slate-200 hover:border-slate-300 hover:shadow-sm transition-all">
              <Mail className="w-5 h-5 text-purple-600 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-slate-900">¿Necesitas ayuda?</p>
                <p className="text-xs text-slate-500">info@cortexiagt.com</p>
              </div>
            </a>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
