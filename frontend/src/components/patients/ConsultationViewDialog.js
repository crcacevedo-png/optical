/**
 * Dialogo de vista de una consulta (solo lectura), extraido de PatientsPage.js.
 * Muestra toda la ficha clinica: motivo, historia, agudeza visual, hallazgos,
 * diagnostico, plan, recomendaciones, observaciones y recetas vinculadas.
 */
import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Eye, Glasses, Pill, Download } from 'lucide-react';

export function ConsultationViewDialog({
  open, onOpenChange, loading, consultation, downloadPdf,
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="view-consultation-dialog">
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
          </div>
        ) : consultation ? (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 font-heading">
                <Eye className="w-5 h-5 text-pine-700" />
                Consulta del {consultation.consultation_date?.slice(0, 10)}
                <span className="px-2 py-0.5 bg-pine-50 text-pine-700 text-xs rounded-full font-medium ml-1">
                  {consultation.consultation_type}
                </span>
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              <div className="flex items-center justify-between text-sm text-slate-500 pb-3 border-b">
                <span>Hora: {consultation.consultation_time || '-'}</span>
                <span>Profesional: {consultation.professional_name || '-'}</span>
              </div>

              {consultation.chief_complaint && (
                <div>
                  <p className="text-xs font-semibold text-pine-700 uppercase mb-1">I. Motivo de Consulta</p>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{consultation.chief_complaint}</p>
                </div>
              )}

              {(consultation.wears_glasses || consultation.diabetes || consultation.hypertension || consultation.autoimmune_disease || consultation.ocular_surgeries || consultation.family_glaucoma || consultation.family_macular_degeneration || consultation.family_high_myopia || consultation.current_medications || consultation.allergies) && (
                <div className="border rounded-lg p-3 space-y-3">
                  <p className="text-xs font-semibold text-pine-700 uppercase">II. Historia Clinica</p>
                  {(consultation.wears_glasses || consultation.ocular_surgeries || consultation.ocular_trauma || consultation.ocular_diseases) && (
                    <div>
                      <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Antecedentes Oculares</p>
                      <div className="text-sm space-y-0.5">
                        {consultation.wears_glasses && <p><span className="text-slate-500">Usa lentes:</span> Si{consultation.glasses_since ? `, desde ${consultation.glasses_since}` : ''}{consultation.glasses_type ? ` (${consultation.glasses_type})` : ''}</p>}
                        {consultation.ocular_surgeries && <p><span className="text-slate-500">Cirugias:</span> {consultation.ocular_surgeries}</p>}
                        {consultation.ocular_trauma && <p><span className="text-slate-500">Traumatismos:</span> {consultation.ocular_trauma}</p>}
                        {consultation.ocular_diseases && <p><span className="text-slate-500">Enfermedades:</span> {consultation.ocular_diseases}</p>}
                      </div>
                    </div>
                  )}
                  {(consultation.diabetes || consultation.hypertension || consultation.autoimmune_disease || consultation.current_medications || consultation.allergies) && (
                    <div className="pt-2 border-t">
                      <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Antecedentes Sistemicos</p>
                      <div className="flex flex-wrap gap-1.5 mb-1">
                        {consultation.diabetes && <span className="px-2 py-0.5 bg-amber-50 text-amber-800 rounded text-xs font-medium">Diabetes</span>}
                        {consultation.hypertension && <span className="px-2 py-0.5 bg-red-50 text-red-800 rounded text-xs font-medium">Hipertension</span>}
                        {consultation.autoimmune_disease && <span className="px-2 py-0.5 bg-purple-50 text-purple-800 rounded text-xs font-medium">Autoinmune: {consultation.autoimmune_details || 'Si'}</span>}
                      </div>
                      <div className="text-sm space-y-0.5">
                        {consultation.current_medications && <p><span className="text-slate-500">Medicamentos:</span> {consultation.current_medications}</p>}
                        {consultation.allergies && <p><span className="text-slate-500">Alergias:</span> {consultation.allergies}</p>}
                      </div>
                    </div>
                  )}
                  {(consultation.family_glaucoma || consultation.family_macular_degeneration || consultation.family_high_myopia || consultation.family_other_history) && (
                    <div className="pt-2 border-t">
                      <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Antecedentes Familiares</p>
                      <div className="flex flex-wrap gap-1.5">
                        {consultation.family_glaucoma && <span className="px-2 py-0.5 bg-blue-50 text-blue-800 rounded text-xs font-medium">Glaucoma{consultation.family_glaucoma_relationship ? ` (${consultation.family_glaucoma_relationship})` : ''}</span>}
                        {consultation.family_macular_degeneration && <span className="px-2 py-0.5 bg-blue-50 text-blue-800 rounded text-xs font-medium">Deg. Macular{consultation.family_macular_relationship ? ` (${consultation.family_macular_relationship})` : ''}</span>}
                        {consultation.family_high_myopia && <span className="px-2 py-0.5 bg-blue-50 text-blue-800 rounded text-xs font-medium">Miopia Alta{consultation.family_high_myopia_relationship ? ` (${consultation.family_high_myopia_relationship})` : ''}</span>}
                      </div>
                      {consultation.family_other_history && <p className="text-sm text-slate-600 mt-1">Otros: {consultation.family_other_history}</p>}
                    </div>
                  )}
                </div>
              )}

              {(consultation.va_distance_without_rx_od || consultation.va_distance_without_rx_oi || consultation.va_distance_with_rx_od || consultation.va_near_without_rx_od || consultation.va_pinhole_od) && (
                <div className="border rounded-lg p-3">
                  <p className="text-xs font-semibold text-pine-700 uppercase mb-2">III. Agudeza Visual {consultation.visual_acuity_method ? `(${consultation.visual_acuity_method})` : ''}</p>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-1 text-xs text-slate-500 uppercase">Medicion</th>
                        <th className="text-center py-1 text-xs text-blue-700 uppercase">OD</th>
                        <th className="text-center py-1 text-xs text-green-700 uppercase">OI</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { label: 'AV Lejos sin Rx', od: consultation.va_distance_without_rx_od, oi: consultation.va_distance_without_rx_oi },
                        { label: 'AV Lejos con Rx', od: consultation.va_distance_with_rx_od, oi: consultation.va_distance_with_rx_oi },
                        { label: 'AV Cerca sin Rx', od: consultation.va_near_without_rx_od, oi: consultation.va_near_without_rx_oi },
                        { label: 'AV Cerca con Rx', od: consultation.va_near_with_rx_od, oi: consultation.va_near_with_rx_oi },
                        { label: 'AV Estenopeico', od: consultation.va_pinhole_od, oi: consultation.va_pinhole_oi },
                      ].filter(r => r.od || r.oi).map((r) => (
                        <tr key={r.label} className="border-b last:border-0">
                          <td className="py-1 text-slate-700">{r.label}</td>
                          <td className="py-1 text-center font-mono">{r.od || '-'}</td>
                          <td className="py-1 text-center font-mono">{r.oi || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {consultation.anamnesis && (
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase mb-1">Historia / Anamnesis</p>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{consultation.anamnesis}</p>
                </div>
              )}
              {consultation.findings && (
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase mb-1">Hallazgos</p>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{consultation.findings}</p>
                </div>
              )}
              {consultation.diagnosis && (
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase mb-1">Diagnostico</p>
                  <p className="text-sm font-medium text-pine-800 bg-pine-50/50 p-2 rounded whitespace-pre-wrap">{consultation.diagnosis}</p>
                </div>
              )}
              {consultation.treatment_plan && (
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase mb-1">Plan / Tratamiento</p>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{consultation.treatment_plan}</p>
                </div>
              )}
              {consultation.recommendations && (
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase mb-1">Recomendaciones</p>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{consultation.recommendations}</p>
                </div>
              )}
              {consultation.notes && (
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase mb-1">Observaciones</p>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{consultation.notes}</p>
                </div>
              )}

              {((consultation.eyeglass_prescriptions?.length || 0) + (consultation.contact_prescriptions?.length || 0) + (consultation.medical_prescriptions?.length || 0)) > 0 && (
                <div className="pt-3 border-t">
                  <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Recetas Vinculadas</p>
                  {(consultation.eyeglass_prescriptions || []).map((rx) => (
                    <div key={rx._id} className="flex items-center justify-between py-1.5">
                      <div className="flex items-center gap-2 text-sm">
                        <Glasses className="w-3.5 h-3.5 text-blue-500" />
                        <span>Receta de Anteojos ({rx.created_at?.slice(0, 10)})</span>
                      </div>
                      <Button size="sm" variant="ghost" className="h-7 text-xs text-blue-600 hover:text-blue-800"
                        onClick={() => downloadPdf('eyeglass', rx._id)} data-testid={`view-rx-pdf-${rx._id}`}>
                        <Download className="w-3 h-3 mr-1" /> PDF
                      </Button>
                    </div>
                  ))}
                  {(consultation.contact_prescriptions || []).map((rx) => (
                    <div key={rx._id} className="flex items-center justify-between py-1.5">
                      <div className="flex items-center gap-2 text-sm">
                        <Eye className="w-3.5 h-3.5 text-teal-500" />
                        <span>Lentes de Contacto ({rx.created_at?.slice(0, 10)})</span>
                      </div>
                      <Button size="sm" variant="ghost" className="h-7 text-xs text-teal-600 hover:text-teal-800"
                        onClick={() => downloadPdf('contact-lens', rx._id)}>
                        <Download className="w-3 h-3 mr-1" /> PDF
                      </Button>
                    </div>
                  ))}
                  {(consultation.medical_prescriptions || []).map((rx) => (
                    <div key={rx._id} className="flex items-center justify-between py-1.5">
                      <div className="flex items-center gap-2 text-sm">
                        <Pill className="w-3.5 h-3.5 text-purple-500" />
                        <span>Receta Medica ({rx.created_at?.slice(0, 10)})</span>
                      </div>
                      <Button size="sm" variant="ghost" className="h-7 text-xs text-purple-600 hover:text-purple-800"
                        onClick={() => downloadPdf('medical', rx._id)}>
                        <Download className="w-3 h-3 mr-1" /> PDF
                      </Button>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex justify-end pt-2">
                <Button variant="outline" onClick={() => onOpenChange(false)}>Cerrar</Button>
              </div>
            </div>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
