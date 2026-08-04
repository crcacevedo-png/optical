/**
 * Dialogos extraidos de PatientsPage.js para reducir su tamano.
 * Cada dialogo recibe su form + setter + handler explicitos por props,
 * manteniendo la logica de estado en la pagina padre.
 */
import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Glasses, Eye, Pill, Pencil, Trash2, Save, Plus } from 'lucide-react';

// ═══════════════════════════════════════════════════════════════════
// Eyeglass Rx Dialog
// ═══════════════════════════════════════════════════════════════════
export function EyeglassRxDialog({ open, onOpenChange, form, setForm, onSubmit }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Glasses className="w-5 h-5 text-blue-600" /> Receta de Anteojos</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-3">
            {[
              { side: 'od', title: 'OJO DERECHO (OD)', bg: 'bg-blue-50', txt: 'text-blue-700' },
              { side: 'oi', title: 'OJO IZQUIERDO (OI)', bg: 'bg-green-50', txt: 'text-green-700' },
            ].map(({ side, title, bg, txt }) => (
              <div key={side} className={`p-3 ${bg} rounded-lg`}>
                <p className={`text-xs font-bold ${txt} mb-2`}>{title}</p>
                <div className="grid grid-cols-5 gap-2">
                  {['sphere', 'cylinder', 'axis', 'addition', 'dp'].map(f => (
                    <div key={f} className="space-y-1">
                      <Label className="text-[10px] uppercase">
                        {f === 'dp' ? 'DP' : f === 'sphere' ? 'Esfera' : f === 'cylinder' ? 'Cilindro' : f === 'axis' ? 'Eje' : 'Adicion'}
                      </Label>
                      <Input
                        className="h-8 text-sm"
                        value={form[`${side}_${f}`]}
                        onChange={(e) => setForm(p => ({ ...p, [`${side}_${f}`]: e.target.value }))}
                        data-testid={`p-rx-${side}-${f}`}
                      />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label className="text-xs">Tipo de Lente</Label>
              <Input value={form.lens_type} onChange={(e) => setForm(p => ({ ...p, lens_type: e.target.value }))} placeholder="Monofocal, bifocal, progresivo..." />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Tipo de Armazon</Label>
              <Input value={form.frame_type} onChange={(e) => setForm(p => ({ ...p, frame_type: e.target.value }))} />
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Observaciones</Label>
            <Textarea value={form.observations} onChange={(e) => setForm(p => ({ ...p, observations: e.target.value }))} rows={2} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button className="bg-blue-600 hover:bg-blue-700" onClick={onSubmit} data-testid="p-save-eyeglass-rx-btn">
              <Save className="w-4 h-4 mr-2" /> Guardar Receta
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Contact Lens Rx Dialog
// ═══════════════════════════════════════════════════════════════════
const CONTACT_FIELDS = [
  { k: 'power', l: 'Poder' }, { k: 'bc', l: 'CB' }, { k: 'dia', l: 'DIA' },
  { k: 'cylinder', l: 'Cilindro' }, { k: 'axis', l: 'Eje' }, { k: 'addition', l: 'Adicion' },
];

export function ContactRxDialog({ open, onOpenChange, form, setForm, onSubmit }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Eye className="w-5 h-5 text-teal-600" /> Receta de Lentes de Contacto</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-3">
            {[
              { side: 'od', title: 'OJO DERECHO (OD)', bg: 'bg-blue-50', txt: 'text-blue-700' },
              { side: 'oi', title: 'OJO IZQUIERDO (OI)', bg: 'bg-green-50', txt: 'text-green-700' },
            ].map(({ side, title, bg, txt }) => (
              <div key={side} className={`p-3 ${bg} rounded-lg`}>
                <p className={`text-xs font-bold ${txt} mb-2`}>{title}</p>
                <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                  {CONTACT_FIELDS.map(({ k, l }) => (
                    <div key={k} className="space-y-1">
                      <Label className="text-[10px] uppercase">{l}</Label>
                      <Input
                        className="h-8 text-sm"
                        value={form[`${side}_${k}`]}
                        onChange={(e) => setForm(p => ({ ...p, [`${side}_${k}`]: e.target.value }))}
                      />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Marca</Label>
              <Input value={form.brand} onChange={(e) => setForm(p => ({ ...p, brand: e.target.value }))} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Tipo de Lente</Label>
              <Input value={form.lens_type} onChange={(e) => setForm(p => ({ ...p, lens_type: e.target.value }))} placeholder="Blanda, rigida..." />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Reemplazo</Label>
              <Input value={form.replacement} onChange={(e) => setForm(p => ({ ...p, replacement: e.target.value }))} placeholder="Mensual, quincenal..." />
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Observaciones</Label>
            <Textarea value={form.observations} onChange={(e) => setForm(p => ({ ...p, observations: e.target.value }))} rows={2} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={onSubmit} data-testid="p-save-contact-rx-btn">
              <Save className="w-4 h-4 mr-2" /> Guardar Receta
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Medical Rx Dialog
// ═══════════════════════════════════════════════════════════════════
export function MedicalRxDialog({ open, onOpenChange, form, setForm, onSubmit, addMedication, updateMedication, removeMedication }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Pill className="w-5 h-5 text-purple-600" /> Receta Medica</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1">
            <Label>Diagnostico</Label>
            <Input value={form.diagnosis} onChange={(e) => setForm(f => ({ ...f, diagnosis: e.target.value }))} data-testid="p-med-rx-diagnosis" />
          </div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <Label>Medicamentos</Label>
              <Button type="button" variant="outline" size="sm" onClick={addMedication} data-testid="p-add-medication-btn">
                <Plus className="w-3 h-3 mr-1" /> Agregar
              </Button>
            </div>
            {form.medications.map((med, idx) => (
              <div key={med._uid || idx} className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-2 mb-2 items-end">
                <div className="space-y-1">
                  <Label className="text-[10px]">Medicamento</Label>
                  <Input className="h-8 text-sm" value={med.name} onChange={(e) => updateMedication(idx, 'name', e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label className="text-[10px]">Dosis</Label>
                  <Input className="h-8 text-sm w-20" value={med.dosage} onChange={(e) => updateMedication(idx, 'dosage', e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label className="text-[10px]">Frecuencia</Label>
                  <Input className="h-8 text-sm w-24" value={med.frequency} onChange={(e) => updateMedication(idx, 'frequency', e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label className="text-[10px]">Duracion</Label>
                  <Input className="h-8 text-sm w-20" value={med.duration} onChange={(e) => updateMedication(idx, 'duration', e.target.value)} />
                </div>
                {form.medications.length > 1 && (
                  <Button variant="ghost" size="sm" className="text-red-500 h-8 w-8 p-0" onClick={() => removeMedication(idx)}>X</Button>
                )}
              </div>
            ))}
          </div>
          <div className="space-y-1">
            <Label>Instrucciones</Label>
            <Textarea value={form.instructions} onChange={(e) => setForm(f => ({ ...f, instructions: e.target.value }))} rows={2} data-testid="p-med-rx-instructions" />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button className="bg-purple-600 hover:bg-purple-700" onClick={onSubmit} data-testid="p-save-medical-rx-btn">
              <Save className="w-4 h-4 mr-2" /> Guardar Receta
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Edit Patient Dialog
// ═══════════════════════════════════════════════════════════════════
export function PatientEditDialog({ open, onOpenChange, form, setForm, onSubmit }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto" data-testid="edit-patient-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Pencil className="w-5 h-5 text-pine-700" /> Editar Paciente</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Nombre *</Label>
              <Input value={form.first_name} onChange={(e) => setForm(f => ({ ...f, first_name: e.target.value }))} data-testid="edit-first-name" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Apellido *</Label>
              <Input value={form.last_name} onChange={(e) => setForm(f => ({ ...f, last_name: e.target.value }))} data-testid="edit-last-name" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">DPI</Label>
              <Input value={form.dpi} onChange={(e) => setForm(f => ({ ...f, dpi: e.target.value }))} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Genero</Label>
              <Select value={form.gender || 'none'} onValueChange={(v) => setForm(f => ({ ...f, gender: v === 'none' ? '' : v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Sin especificar</SelectItem>
                  <SelectItem value="M">Masculino</SelectItem>
                  <SelectItem value="F">Femenino</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Fecha de Nacimiento</Label>
              <Input type="date" value={form.birth_date} onChange={(e) => setForm(f => ({ ...f, birth_date: e.target.value }))} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Telefono</Label>
              <Input value={form.phone} onChange={(e) => setForm(f => ({ ...f, phone: e.target.value }))} data-testid="edit-phone" />
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Email</Label>
            <Input type="email" value={form.email} onChange={(e) => setForm(f => ({ ...f, email: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Direccion</Label>
            <Input value={form.address} onChange={(e) => setForm(f => ({ ...f, address: e.target.value }))} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Contacto Emergencia</Label>
              <Input value={form.emergency_contact} onChange={(e) => setForm(f => ({ ...f, emergency_contact: e.target.value }))} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Tel. Emergencia</Label>
              <Input value={form.emergency_phone} onChange={(e) => setForm(f => ({ ...f, emergency_phone: e.target.value }))} />
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Notas</Label>
            <Textarea value={form.notes} onChange={(e) => setForm(f => ({ ...f, notes: e.target.value }))} rows={2} />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button
              className="bg-pine-700 hover:bg-pine-800"
              onClick={onSubmit}
              disabled={!form.first_name || !form.last_name}
              data-testid="save-edit-patient-btn"
            >
              <Save className="w-4 h-4 mr-2" /> Guardar Cambios
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Delete Patient Confirm Dialog
// ═══════════════════════════════════════════════════════════════════
export function PatientDeleteDialog({ open, onOpenChange, patient, onConfirm }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm" data-testid="delete-patient-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-red-600">
            <Trash2 className="w-5 h-5" /> Eliminar Paciente
          </DialogTitle>
          <DialogDescription className="text-slate-500 pt-2">
            Esta accion eliminara a <span className="font-semibold text-slate-700">{patient?.first_name} {patient?.last_name}</span> y no se puede deshacer.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="cancel-delete-btn">Cancelar</Button>
          <Button variant="destructive" onClick={onConfirm} data-testid="confirm-delete-btn">Eliminar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
