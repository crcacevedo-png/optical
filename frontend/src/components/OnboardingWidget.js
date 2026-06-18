import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../context/AuthContext';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Progress } from './ui/progress';
import { Rocket, ArrowRight, X } from 'lucide-react';
import { STEPS } from '../pages/OnboardingPage';

/**
 * Widget que se muestra en el Dashboard recordando al admin completar
 * el onboarding cuando el progreso es menor al 100%.
 * Solo visible para usuarios con rol "admin" y cuando no se ha cerrado.
 */
export function OnboardingWidget({ userRole }) {
  const [progress, setProgress] = useState({});
  const [dismissed, setDismissed] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (userRole !== 'admin') return;
    let active = true;
    api.get('/api/onboarding/status')
      .then(({ data }) => {
        if (!active) return;
        setProgress(data.progress || {});
        setDismissed(!!data.dismissed);
      })
      .catch(() => {})
      .finally(() => active && setLoaded(true));
    return () => { active = false; };
  }, [userRole]);

  const handleDismiss = async () => {
    setDismissed(true);
    try { await api.post('/api/onboarding/dismiss'); } catch { /* silent */ }
  };

  if (userRole !== 'admin' || !loaded || dismissed) return null;

  const completedCount = STEPS.filter(s => progress[s.id]).length;
  const total = STEPS.length;
  const progressPct = Math.round((completedCount / total) * 100);

  // Ocultar si ya está al 100%
  if (completedCount >= total) return null;

  return (
    <Card
      className="border-0 overflow-hidden relative"
      style={{ background: 'linear-gradient(135deg, #6D35D8 0%, #13B8B0 100%)' }}
      data-testid="onboarding-widget"
    >
      <button
        type="button"
        onClick={handleDismiss}
        className="absolute top-3 right-3 p-1.5 rounded-full text-white/70 hover:text-white hover:bg-white/15 transition-colors"
        aria-label="Cerrar"
        data-testid="onboarding-widget-dismiss"
      >
        <X className="w-4 h-4" />
      </button>
      <CardContent className="p-5 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-6">
          <div className="flex items-center gap-3 sm:flex-col sm:items-start sm:gap-2 sm:min-w-[150px]">
            <div className="w-11 h-11 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center shrink-0">
              <Rocket className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wider text-white/70">
                Inicio rápido
              </p>
              <p className="font-heading text-lg font-semibold text-white leading-tight">
                Configuración inicial pendiente
              </p>
            </div>
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-baseline justify-between mb-2">
              <p className="text-sm text-white/90">
                Llevas <span className="font-bold text-white">{completedCount} de {total}</span> pasos completados
              </p>
              <p className="text-sm font-bold text-white">{progressPct}%</p>
            </div>
            <Progress
              value={progressPct}
              className="h-2 bg-white/20 [&>div]:bg-white"
            />
            <p className="text-xs text-white/75 mt-2.5 leading-relaxed">
              Completa la configuración para dejar tu óptica 100% operativa: datos fiscales, sucursales, equipo, inventario y primera venta.
            </p>
          </div>

          <div className="sm:shrink-0">
            <Link to="/onboarding">
              <Button
                className="w-full sm:w-auto bg-white text-slate-900 hover:bg-white/90 font-semibold shadow-md"
                data-testid="onboarding-widget-cta"
              >
                Continuar <ArrowRight className="w-4 h-4 ml-1.5" />
              </Button>
            </Link>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
