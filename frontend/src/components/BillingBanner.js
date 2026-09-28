import React from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle } from 'lucide-react';
import { Button } from './ui/button';

// Banner NO bloqueante que se muestra durante el periodo de gracia (pago fallido).
export function BillingGraceBanner({ billing, isAdmin }) {
  if (!billing || billing.state !== 'grace') return null;
  const days = billing.days_remaining;
  const dayTxt = days == null ? '' : `${days} día${days === 1 ? '' : 's'}`;
  return (
    <div
      data-testid="billing-grace-banner"
      className="mb-5 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3.5 flex flex-col sm:flex-row sm:items-center gap-3"
    >
      <div className="flex items-start gap-3 flex-1 min-w-0">
        <div className="w-9 h-9 rounded-lg bg-amber-100 flex items-center justify-center shrink-0">
          <AlertTriangle className="w-5 h-5 text-amber-600" />
        </div>
        <div className="min-w-0">
          <p className="font-semibold text-amber-900 text-sm">
            Pago pendiente — regulariza para evitar la suspensión{dayTxt ? ` (${dayTxt})` : ''}
          </p>
          <p className="text-sm text-amber-800">
            {isAdmin
              ? 'Tu último pago no se pudo procesar. Actualiza tu método de pago antes de que termine el periodo de gracia.'
              : 'La cuenta tiene un pago pendiente. Avísale al administrador para regularizarlo.'}
          </p>
        </div>
      </div>
      {isAdmin && (
        <Link to="/my-plan" className="shrink-0">
          <Button size="sm" className="bg-amber-600 hover:bg-amber-700 text-white" data-testid="grace-banner-pay-btn">
            Regularizar pago
          </Button>
        </Link>
      )}
    </div>
  );
}

// Aviso en línea (sobre el contenido) cuando el admin suspendido está en /my-plan.
export function SuspendedInlineBanner() {
  return (
    <div
      data-testid="suspended-inline-banner"
      className="mb-5 rounded-xl border border-red-300 bg-red-50 px-4 py-3.5 flex items-start gap-3"
    >
      <div className="w-9 h-9 rounded-lg bg-red-100 flex items-center justify-center shrink-0">
        <AlertTriangle className="w-5 h-5 text-red-600" />
      </div>
      <div>
        <p className="font-semibold text-red-900 text-sm">Cuenta suspendida por falta de pago</p>
        <p className="text-sm text-red-800">
          Elige un plan y completa el pago, o actualiza tu método de pago para reactivar el acceso de inmediato.
        </p>
      </div>
    </div>
  );
}
