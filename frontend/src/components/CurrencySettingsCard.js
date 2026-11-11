import React, { useMemo, useState } from 'react';
import { api, formatApiErrorDetail, useAuth } from '../context/AuthContext';
import { CURRENCIES, getCurrency, DEFAULT_CURRENCY } from '../lib/currency';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { Command, CommandInput, CommandList, CommandEmpty, CommandGroup, CommandItem } from './ui/command';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from './ui/dialog';
import { toast } from 'sonner';
import { Coins, Check, ChevronsUpDown, AlertTriangle } from 'lucide-react';

const label = (c) => `${c.name} (${c.country}) — ${c.symbol}`;

export function CurrencySettingsCard() {
  const { user, checkAuth } = useAuth();
  const currentCode = (user && user.currency) || DEFAULT_CURRENCY;
  const [selected, setSelected] = useState(currentCode);
  const [open, setOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const currentInfo = useMemo(() => getCurrency(currentCode), [currentCode]);
  const selectedInfo = useMemo(() => getCurrency(selected), [selected]);
  const changed = selected !== currentCode;

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/api/settings/company', { currency: selected });
      await checkAuth(); // refresca user.currency -> toda la app usa el nuevo simbolo
      try { await api.put('/api/onboarding/status', { step_id: 'choose_currency', completed: true }); } catch { /* silent */ }
      toast.success(`Moneda actualizada a ${selectedInfo.name} (${selectedInfo.symbol})`);
      setConfirmOpen(false);
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail) || 'Error al guardar la moneda');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="border-slate-200/80" data-testid="currency-settings-card">
      <CardHeader>
        <CardTitle className="font-heading text-lg flex items-center gap-2">
          <Coins className="w-5 h-5 text-pine-700" />
          Moneda
        </CardTitle>
        <p className="text-sm text-slate-500 mt-1">
          Elige la moneda en la que trabaja tu optica. Aplica a ventas, caja, finanzas, reportes y documentos.
          Solo cambia el simbolo y el formato: no convierte las cifras ya registradas.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-3 text-sm">
          <span className="text-slate-500">Moneda actual:</span>
          <span className="font-semibold text-slate-800" data-testid="current-currency">
            {currentInfo.name} ({currentInfo.country}) — {currentInfo.symbol}
          </span>
        </div>

        <div className="max-w-md">
          <label className="text-xs font-semibold text-slate-500 uppercase mb-1.5 block">Moneda de la optica</label>
          <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                role="combobox"
                aria-expanded={open}
                className="w-full justify-between font-normal"
                data-testid="currency-select-trigger"
              >
                {label(selectedInfo)}
                <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
              <Command>
                <CommandInput placeholder="Buscar moneda o pais..." data-testid="currency-search-input" />
                <CommandList>
                  <CommandEmpty>Sin resultados.</CommandEmpty>
                  <CommandGroup>
                    {CURRENCIES.map((c) => (
                      <CommandItem
                        key={c.code}
                        value={`${c.name} ${c.country} ${c.code} ${c.symbol}`}
                        onSelect={() => { setSelected(c.code); setOpen(false); }}
                        data-testid={`currency-option-${c.code}`}
                      >
                        <Check className={`mr-2 h-4 w-4 ${selected === c.code ? 'opacity-100' : 'opacity-0'}`} />
                        <span className="flex-1">{label(c)}</span>
                        <span className="text-xs text-slate-400 ml-2">{c.code}</span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
        </div>

        <div className="flex justify-end">
          <Button
            className="bg-pine-900 hover:bg-pine-700 text-white"
            disabled={!changed || saving}
            onClick={() => setConfirmOpen(true)}
            data-testid="currency-save-btn"
          >
            Guardar moneda
          </Button>
        </div>
      </CardContent>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent data-testid="currency-confirm-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-600" />
              Cambiar moneda de la optica
            </DialogTitle>
            <DialogDescription asChild>
              <div className="space-y-2 text-sm text-slate-600 pt-1">
                <p>
                  Vas a cambiar la moneda de <strong>{currentInfo.symbol} {currentInfo.name}</strong> a{' '}
                  <strong>{selectedInfo.symbol} {selectedInfo.name}</strong>.
                </p>
                <p className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-xs">
                  Esto solo cambia el <strong>simbolo y el formato</strong> que se muestra en todo el sistema.
                  Los montos historicos (ventas, precios, saldos, reportes) <strong>no se convierten</strong>;
                  conservan su numero tal cual.
                </p>
              </div>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setConfirmOpen(false)} data-testid="currency-cancel-btn">Cancelar</Button>
            <Button className="bg-pine-900 hover:bg-pine-700 text-white" disabled={saving} onClick={handleSave} data-testid="currency-confirm-btn">
              {saving ? 'Guardando...' : 'Si, cambiar moneda'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

export default CurrencySettingsCard;
