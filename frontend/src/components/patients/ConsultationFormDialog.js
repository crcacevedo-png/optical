/**
 * Dialogo de "Nueva Consulta" extraido de PatientsPage.js.
 * Requiere muchos props porque es el formulario mas grande del sistema
 * (historia clinica completa, agudeza visual, hallazgos, diagnostico, plan
 * y las 3 recetas vinculadas). El estado sigue en la pagina padre.
 */
import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Checkbox } from '../ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Eye, Glasses, Pill, Save } from 'lucide-react';

export function ConsultationFormDialog({
  open, onOpenChange, patient, form, setForm, onSubmit,
  savedId, setSavedId, submitting, resetForm,
  CONSULTATION_TYPES, VA_METHODS,
  setEyeglassForm, openEyeglassRx,
  setContactForm, openContactRx,
  setMedicalForm, openMedicalRx,
}) {
  return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-heading">
              <Eye className="w-5 h-5 text-pine-700" />
              Nueva Consulta - {patient?.first_name} {patient?.last_name}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-5">
            {/* Header fields */}
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1">
                <Label className="text-xs">Fecha *</Label>
                <Input type="date" value={form.consultation_date}
                  onChange={(e) => setForm(f => ({ ...f, consultation_date: e.target.value }))}
                  data-testid="consultation-date" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Hora</Label>
                <Input type="time" value={form.consultation_time}
                  onChange={(e) => setForm(f => ({ ...f, consultation_time: e.target.value }))}
                  data-testid="consultation-time" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Tipo de Consulta</Label>
                <Select value={form.consultation_type}
                  onValueChange={(v) => setForm(f => ({ ...f, consultation_type: v }))}>
                  <SelectTrigger data-testid="consultation-type"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {CONSULTATION_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* I. Motivo */}
            <div className="space-y-2">
              <Label className="font-semibold text-pine-700">I. Motivo de Consulta *</Label>
              <Textarea value={form.chief_complaint} rows={2}
                onChange={(e) => setForm(f => ({ ...f, chief_complaint: e.target.value }))}
                placeholder="Describir sintomas principales, duracion y factores asociados" data-testid="consultation-chief-complaint" />
            </div>

            {/* II. Historia Clinica */}
            <div className="border rounded-lg p-4 space-y-4">
              <p className="text-sm font-semibold text-pine-700">II. Historia Clinica</p>
              {/* A. Oculares */}
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase mb-2">A. Antecedentes Oculares</p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Checkbox id="p-wears" checked={form.wears_glasses}
                        onCheckedChange={(v) => setForm(f => ({ ...f, wears_glasses: !!v }))} />
                      <Label htmlFor="p-wears" className="text-sm cursor-pointer">Usa lentes</Label>
                    </div>
                    {form.wears_glasses && (
                      <div className="pl-6 space-y-1">
                        <Input placeholder="Desde cuando" value={form.glasses_since} className="h-7 text-sm"
                          onChange={(e) => setForm(f => ({ ...f, glasses_since: e.target.value }))} />
                        <Input placeholder="Tipo de lentes" value={form.glasses_type} className="h-7 text-sm"
                          onChange={(e) => setForm(f => ({ ...f, glasses_type: e.target.value }))} />
                      </div>
                    )}
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Cirugias oculares</Label>
                    <Input value={form.ocular_surgeries} placeholder="Ninguna" className="h-7 text-sm"
                      onChange={(e) => setForm(f => ({ ...f, ocular_surgeries: e.target.value }))} />
                    <Label className="text-xs">Traumatismos</Label>
                    <Input value={form.ocular_trauma} placeholder="Ninguno" className="h-7 text-sm"
                      onChange={(e) => setForm(f => ({ ...f, ocular_trauma: e.target.value }))} />
                  </div>
                </div>
                <div className="mt-2">
                  <Label className="text-xs">Enfermedades oculares</Label>
                  <Input value={form.ocular_diseases} placeholder="Ninguna" className="h-7 text-sm mt-1"
                    onChange={(e) => setForm(f => ({ ...f, ocular_diseases: e.target.value }))} />
                </div>
              </div>
              {/* B. Sistemicos */}
              <div className="pt-3 border-t">
                <p className="text-xs font-semibold text-slate-500 uppercase mb-2">B. Antecedentes Sistemicos</p>
                <div className="flex flex-wrap gap-4 mb-2">
                  <div className="flex items-center gap-2">
                    <Checkbox id="p-diabetes" checked={form.diabetes}
                      onCheckedChange={(v) => setForm(f => ({ ...f, diabetes: !!v }))} />
                    <Label htmlFor="p-diabetes" className="text-sm cursor-pointer">Diabetes</Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox id="p-hyp" checked={form.hypertension}
                      onCheckedChange={(v) => setForm(f => ({ ...f, hypertension: !!v }))} />
                    <Label htmlFor="p-hyp" className="text-sm cursor-pointer">Hipertension</Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox id="p-auto" checked={form.autoimmune_disease}
                      onCheckedChange={(v) => setForm(f => ({ ...f, autoimmune_disease: !!v }))} />
                    <Label htmlFor="p-auto" className="text-sm cursor-pointer">Autoinmune</Label>
                  </div>
                </div>
                {form.autoimmune_disease && (
                  <Input placeholder="Cual enfermedad autoinmune" value={form.autoimmune_details} className="h-7 text-sm mb-2"
                    onChange={(e) => setForm(f => ({ ...f, autoimmune_details: e.target.value }))} />
                )}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label className="text-xs">Medicamentos</Label>
                    <Input value={form.current_medications} placeholder="Ninguno" className="h-7 text-sm"
                      onChange={(e) => setForm(f => ({ ...f, current_medications: e.target.value }))} />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Alergias</Label>
                    <Input value={form.allergies} placeholder="Ninguna" className="h-7 text-sm"
                      onChange={(e) => setForm(f => ({ ...f, allergies: e.target.value }))} />
                  </div>
                </div>
              </div>
              {/* C. Familiares */}
              <div className="pt-3 border-t">
                <p className="text-xs font-semibold text-slate-500 uppercase mb-2">C. Antecedentes Familiares</p>
                <div className="space-y-2">
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                      <Checkbox id="p-fglau" checked={form.family_glaucoma}
                        onCheckedChange={(v) => setForm(f => ({ ...f, family_glaucoma: !!v }))} />
                      <Label htmlFor="p-fglau" className="text-sm cursor-pointer">Glaucoma</Label>
                    </div>
                    {form.family_glaucoma && (
                      <Input placeholder="Parentesco" value={form.family_glaucoma_relationship} className="h-7 text-sm w-32"
                        onChange={(e) => setForm(f => ({ ...f, family_glaucoma_relationship: e.target.value }))} />
                    )}
                  </div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                      <Checkbox id="p-fmac" checked={form.family_macular_degeneration}
                        onCheckedChange={(v) => setForm(f => ({ ...f, family_macular_degeneration: !!v }))} />
                      <Label htmlFor="p-fmac" className="text-sm cursor-pointer">Deg. macular</Label>
                    </div>
                    {form.family_macular_degeneration && (
                      <Input placeholder="Parentesco" value={form.family_macular_relationship} className="h-7 text-sm w-32"
                        onChange={(e) => setForm(f => ({ ...f, family_macular_relationship: e.target.value }))} />
                    )}
                  </div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                      <Checkbox id="p-fmyo" checked={form.family_high_myopia}
                        onCheckedChange={(v) => setForm(f => ({ ...f, family_high_myopia: !!v }))} />
                      <Label htmlFor="p-fmyo" className="text-sm cursor-pointer">Miopia alta</Label>
                    </div>
                    {form.family_high_myopia && (
                      <Input placeholder="Parentesco" value={form.family_high_myopia_relationship} className="h-7 text-sm w-32"
                        onChange={(e) => setForm(f => ({ ...f, family_high_myopia_relationship: e.target.value }))} />
                    )}
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Otros</Label>
                    <Input value={form.family_other_history} placeholder="Ninguno" className="h-7 text-sm"
                      onChange={(e) => setForm(f => ({ ...f, family_other_history: e.target.value }))} />
                  </div>
                </div>
              </div>
            </div>

            {/* III. Agudeza Visual */}
            <div className="border rounded-lg p-4 space-y-3">
              <p className="text-sm font-semibold text-pine-700">III. Agudeza Visual</p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-1 pr-2 text-xs font-semibold text-slate-500 uppercase">Medicion</th>
                    <th className="text-center py-1 px-1 text-xs font-semibold text-blue-700 uppercase">OD</th>
                    <th className="text-center py-1 px-1 text-xs font-semibold text-green-700 uppercase">OI</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { label: 'AV Lejos sin Rx', od: 'va_distance_without_rx_od', oi: 'va_distance_without_rx_oi' },
                    { label: 'AV Lejos con Rx', od: 'va_distance_with_rx_od', oi: 'va_distance_with_rx_oi' },
                    { label: 'AV Cerca sin Rx', od: 'va_near_without_rx_od', oi: 'va_near_without_rx_oi' },
                    { label: 'AV Cerca con Rx', od: 'va_near_with_rx_od', oi: 'va_near_with_rx_oi' },
                    { label: 'AV Estenopeico', od: 'va_pinhole_od', oi: 'va_pinhole_oi' },
                  ].map((row) => (
                    <tr key={row.od} className="border-b last:border-0">
                      <td className="py-1 pr-2 text-slate-700 text-xs">{row.label}</td>
                      <td className="py-1 px-1">
                        <Input className="h-7 text-sm text-center" value={form[row.od]} placeholder="20/20"
                          onChange={(e) => setForm(f => ({ ...f, [row.od]: e.target.value }))} />
                      </td>
                      <td className="py-1 px-1">
                        <Input className="h-7 text-sm text-center" value={form[row.oi]} placeholder="20/20"
                          onChange={(e) => setForm(f => ({ ...f, [row.oi]: e.target.value }))} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="flex items-center gap-2">
                <Label className="text-xs">Metodo:</Label>
                <Select value={form.visual_acuity_method}
                  onValueChange={(v) => setForm(f => ({ ...f, visual_acuity_method: v }))}>
                  <SelectTrigger className="w-32 h-7 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {VA_METHODS.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* IV. Hallazgos y Plan */}
            <div className="space-y-3">
              <p className="text-sm font-semibold text-pine-700">IV. Hallazgos y Plan</p>
              <div className="space-y-2">
                <Label className="text-xs">Historia / Anamnesis</Label>
                <Textarea value={form.anamnesis} rows={2}
                  onChange={(e) => setForm(f => ({ ...f, anamnesis: e.target.value }))}
                  placeholder="Antecedentes, sintomas previos..." data-testid="consultation-anamnesis" />
              </div>
              <div className="space-y-2">
                <Label className="text-xs">Hallazgos</Label>
                <Textarea value={form.findings} rows={2}
                  onChange={(e) => setForm(f => ({ ...f, findings: e.target.value }))}
                  placeholder="Resultados del examen visual, agudeza visual..." data-testid="consultation-findings" />
              </div>
              <div className="space-y-2">
                <Label className="text-xs">Diagnostico</Label>
                <Textarea value={form.diagnosis} rows={2}
                  onChange={(e) => setForm(f => ({ ...f, diagnosis: e.target.value }))}
                  placeholder="Diagnostico o impresion clinica..." data-testid="consultation-diagnosis" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label className="text-xs">Plan / Tratamiento</Label>
                  <Textarea value={form.treatment_plan} rows={2}
                    onChange={(e) => setForm(f => ({ ...f, treatment_plan: e.target.value }))}
                    placeholder="Plan de tratamiento..." data-testid="consultation-treatment" />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs">Recomendaciones</Label>
                  <Textarea value={form.recommendations} rows={2}
                    onChange={(e) => setForm(f => ({ ...f, recommendations: e.target.value }))}
                    placeholder="Recomendaciones al paciente..." data-testid="consultation-recommendations" />
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-xs">Observaciones</Label>
                <Textarea value={form.notes} rows={2}
                  onChange={(e) => setForm(f => ({ ...f, notes: e.target.value }))}
                  placeholder="Notas adicionales..." data-testid="consultation-notes" />
              </div>
            </div>

            <div className="flex justify-between items-center gap-2 pt-2 border-t">
              {savedId ? (
                <div className="flex flex-wrap gap-2" data-testid="new-rx-actions">
                  <Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={() => {
                    setEyeglassForm({ od_sphere: '', od_cylinder: '', od_axis: '', od_addition: '', od_dp: '', oi_sphere: '', oi_cylinder: '', oi_axis: '', oi_addition: '', oi_dp: '', lens_type: '', frame_type: '', observations: '' });
                    openEyeglassRx();
                  }} data-testid="new-gen-eyeglass-rx-btn">
                    <Glasses className="w-4 h-4 mr-1" /> Receta Anteojos
                  </Button>
                  <Button size="sm" className="bg-teal-600 hover:bg-teal-700" onClick={() => {
                    setContactForm({ od_power: '', od_bc: '', od_dia: '', od_cylinder: '', od_axis: '', od_addition: '', oi_power: '', oi_bc: '', oi_dia: '', oi_cylinder: '', oi_axis: '', oi_addition: '', brand: '', lens_type: '', replacement: '', observations: '' });
                    openContactRx();
                  }} data-testid="new-gen-contact-rx-btn">
                    <Eye className="w-4 h-4 mr-1" /> Lentes de Contacto
                  </Button>
                  <Button size="sm" className="bg-purple-600 hover:bg-purple-700" onClick={() => {
                    setMedicalForm({ diagnosis: form.diagnosis || '', medications: [{ name: '', dosage: '', frequency: '', duration: '' }], instructions: '' });
                    openMedicalRx();
                  }} data-testid="new-gen-medical-rx-btn">
                    <Pill className="w-4 h-4 mr-1" /> Receta Medica
                  </Button>
                </div>
              ) : <div />}
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => { onOpenChange(false); setSavedId(null); resetForm(); }}>
                  {savedId ? 'Cerrar' : 'Cancelar'}
                </Button>
                {!savedId && (
                  <Button className="bg-pine-700 hover:bg-pine-800" onClick={onSubmit}
                    disabled={!form.chief_complaint || submitting} data-testid="save-consultation-from-patient-btn">
                    <Save className="w-4 h-4 mr-2" /> Guardar Consulta
                  </Button>
                )}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
  );
}
