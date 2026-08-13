import React, { useState, useEffect } from 'react';
import { api, formatApiErrorDetail, useAuth } from '../../context/AuthContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../ui/dialog';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { RadioGroup, RadioGroupItem } from '../ui/radio-group';
import { Checkbox } from '../ui/checkbox';
import { Sparkles, Heart } from 'lucide-react';
import { toast } from 'sonner';

const REASONS = [
  { value: 'sin_tiempo', label: 'Falta de tiempo' },
  { value: 'no_supe_empezar', label: 'No supe por donde empezar' },
  { value: 'olvide_password', label: 'Olvide mi contrasena' },
  { value: 'precio', label: 'Precio' },
  { value: 'no_lo_necesitaba', label: 'No lo necesitaba en ese momento' },
  { value: 'otro', label: 'Otro' },
];

export function ReactivationFeedbackDialog() {
  const { user, checkAuth } = useAuth();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [comment, setComment] = useState('');
  const [allowContact, setAllowContact] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user?.needs_reactivation_feedback && user.role === 'admin') {
      // Delay para no aparecer justo al cargar la app
      const t = setTimeout(() => setOpen(true), 1200);
      return () => clearTimeout(t);
    }
  }, [user?.needs_reactivation_feedback, user?.role]);

  const closeAndRefresh = async () => {
    setOpen(false);
    try { if (checkAuth) await checkAuth(); } catch (e) { /* noop */ }
  };

  const submit = async () => {
    if (!reason) {
      toast.error('Selecciona un motivo');
      return;
    }
    setSubmitting(true);
    try {
      await api.post('/api/reactivation-feedback', {
        reason,
        comment: comment.trim() || null,
        allow_contact: allowContact,
      });
      toast.success('Gracias por tu feedback — nos ayuda a mejorar');
      await closeAndRefresh();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail) || 'Error al enviar');
    } finally {
      setSubmitting(false);
    }
  };

  const skip = async () => {
    setSubmitting(true);
    try {
      await api.post('/api/reactivation-feedback/skip');
      await closeAndRefresh();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail) || 'Error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o && !submitting) skip(); else setOpen(o); }}>
      <DialogContent className="sm:max-w-lg" data-testid="reactivation-feedback-dialog">
        <DialogHeader>
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-100 to-teal-100 flex items-center justify-center mb-2">
            <Heart className="w-6 h-6 text-purple-600" />
          </div>
          <DialogTitle className="text-xl">Bienvenido de vuelta a Cortexia!</DialogTitle>
          <DialogDescription>
            Nos alegra tenerte de regreso. Nos podrias regalar 30 segundos para
            ayudarnos a mejorar la plataforma?
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div>
            <Label className="text-sm font-semibold text-slate-700 mb-2 block">
              Que te freno la primera vez?
            </Label>
            <RadioGroup value={reason} onValueChange={setReason} className="space-y-1.5">
              {REASONS.map((r) => (
                <div key={r.value} className="flex items-center space-x-2">
                  <RadioGroupItem value={r.value} id={`reason-${r.value}`} data-testid={`reason-${r.value}`} />
                  <label htmlFor={`reason-${r.value}`} className="text-sm text-slate-700 cursor-pointer">
                    {r.label}
                  </label>
                </div>
              ))}
            </RadioGroup>
          </div>

          <div>
            <Label htmlFor="fb-comment" className="text-sm font-semibold text-slate-700 mb-2 block">
              Cuentanos mas (opcional)
            </Label>
            <Textarea
              id="fb-comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Ideas, sugerencias, cosas que te confundieron..."
              rows={3}
              className="resize-none"
              maxLength={1000}
              data-testid="fb-comment"
            />
          </div>

          <div className="flex items-start space-x-2 bg-slate-50 rounded-md p-3">
            <Checkbox
              id="fb-allow-contact"
              checked={allowContact}
              onCheckedChange={setAllowContact}
              data-testid="fb-allow-contact"
              className="mt-0.5"
            />
            <label htmlFor="fb-allow-contact" className="text-sm text-slate-700 cursor-pointer leading-snug">
              Esta bien que nos contactemos contigo para ayudarte a arrancar tu optica en Cortexia
            </label>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={skip}
            disabled={submitting}
            data-testid="fb-skip"
          >
            Ahora no
          </Button>
          <Button
            onClick={submit}
            disabled={submitting || !reason}
            className="bg-gradient-to-r from-purple-600 to-teal-600 hover:from-purple-700 hover:to-teal-700"
            data-testid="fb-submit"
          >
            <Sparkles className="w-4 h-4 mr-1.5" />
            {submitting ? 'Enviando...' : 'Enviar feedback'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
