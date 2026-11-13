import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../ui/dialog';
import { Button } from '../ui/button';
import { Textarea } from '../ui/textarea';
import { Label } from '../ui/label';
import { Checkbox } from '../ui/checkbox';
import { Loader2 } from 'lucide-react';

export function ConfirmDialog({ open, onOpenChange, title, description, children, confirmLabel = 'Confirmar', onConfirm, danger = false, testId = 'confirm-dialog' }) {
  const [busy, setBusy] = useState(false);
  const run = async () => { setBusy(true); try { await onConfirm(); } finally { setBusy(false); } };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid={testId}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        {children}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid={`${testId}-cancel`}>Cancelar</Button>
          <Button onClick={run} disabled={busy} className={danger ? 'bg-red-600 hover:bg-red-700' : 'bg-pine-700 hover:bg-pine-800'} data-testid={`${testId}-confirm`}>
            {busy && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}{confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ReasonDialog({ open, onOpenChange, title, description, confirmLabel = 'Confirmar', onConfirm, danger = true, testId = 'reason-dialog' }) {
  const [reason, setReason] = useState('');
  useEffect(() => { if (open) setReason(''); }, [open]);
  return (
    <ConfirmDialog open={open} onOpenChange={onOpenChange} title={title} description={description} danger={danger}
      confirmLabel={confirmLabel} testId={testId} onConfirm={() => onConfirm(reason.trim())}>
      <div className="space-y-1">
        <Label className="text-xs">Motivo (obligatorio)</Label>
        <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Describe el motivo…" data-testid={`${testId}-reason`} />
        {reason.trim().length > 0 && reason.trim().length < 5 && <p className="text-[11px] text-red-600">Mínimo 5 caracteres.</p>}
      </div>
    </ConfirmDialog>
  );
}

export function IssueDialog({ open, onOpenChange, summary, onConfirm }) {
  const [checked, setChecked] = useState(false);
  useEffect(() => { if (open) setChecked(false); }, [open]);
  return (
    <ConfirmDialog open={open} onOpenChange={onOpenChange} testId="issue-dialog" confirmLabel="Validar y emitir"
      title="Validar y emitir receta"
      description="Al emitirla se guarda una instantánea de valores, indicaciones y datos de emisión. Una receta emitida ya no se edita como borrador."
      onConfirm={() => onConfirm(checked)}>
      {summary}
      <label className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 cursor-pointer">
        <Checkbox checked={checked} onCheckedChange={(v) => setChecked(!!v)} className="mt-0.5" data-testid="issue-confirm-reviewed" />
        <span>Revisé y confirmo los valores particulares de esta receta (OD y OS, uso e indicaciones).</span>
      </label>
    </ConfirmDialog>
  );
}
