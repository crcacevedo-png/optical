import React, { useRef, useState } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { toast } from 'sonner';
import {
  FileSpreadsheet, Download, UploadCloud, FileCheck2, Users, AlertTriangle,
  CheckCircle2, RefreshCw, Glasses, X,
} from 'lucide-react';

const ACCEPT = '.xlsx,.csv';

function downloadBlob(response, fallbackName) {
  const cd = response.headers?.['content-disposition'] || '';
  const match = cd.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : fallbackName;
  const url = URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function PatientBulkImport() {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState(null);
  const [committing, setCommitting] = useState(false);
  const [report, setReport] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  const resetAll = () => {
    setFile(null);
    setPreview(null);
    setReport(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  const handleDownload = async (kind) => {
    setDownloading(true);
    const toastId = toast.loading('Generando plantilla...');
    try {
      const resp = await api.get(`/api/patients/import/template.${kind}`, { responseType: 'blob' });
      downloadBlob(resp, `plantilla_pacientes_cortexia.${kind}`);
      toast.success('Plantilla descargada', { id: toastId });
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail) || 'Error al descargar la plantilla', { id: toastId });
    } finally {
      setDownloading(false);
    }
  };

  const doPreview = async (f) => {
    setPreviewing(true);
    setPreview(null);
    setReport(null);
    const fd = new FormData();
    fd.append('file', f);
    try {
      const { data } = await api.post('/api/patients/import/preview', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setPreview(data);
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail) || 'No se pudo leer el archivo');
      resetAll();
    } finally {
      setPreviewing(false);
    }
  };

  const onFileSelected = (f) => {
    if (!f) return;
    const okExt = /\.(xlsx|csv)$/i.test(f.name);
    if (!okExt) {
      toast.error('Formato no soportado. Sube un archivo .xlsx o .csv');
      return;
    }
    setFile(f);
    doPreview(f);
  };

  const handleConfirm = async () => {
    if (!file) return;
    setCommitting(true);
    const toastId = toast.loading('Importando pacientes...');
    const fd = new FormData();
    fd.append('file', file);
    try {
      const { data } = await api.post('/api/patients/import/commit', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setReport(data);
      setPreview(null);
      toast.success(`Importacion lista: ${data.created} creados, ${data.updated} actualizados`, { id: toastId });
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail) || 'Error al importar', { id: toastId });
    } finally {
      setCommitting(false);
    }
  };

  const willSkip = preview && !preview.limit.unlimited && preview.limit.available != null
    ? Math.max(0, (preview.new_patients ?? 0) - preview.limit.available)
    : 0;

  return (
    <Card className="border-slate-200/80" data-testid="patient-import-card">
      <CardHeader>
        <CardTitle className="font-heading text-lg flex items-center gap-2">
          <FileSpreadsheet className="w-5 h-5 text-pine-700" />
          Ingreso masivo de pacientes
        </CardTitle>
        <p className="text-sm text-slate-500 mt-1">
          Carga muchos pacientes de una sola vez desde una hoja de calculo (Excel o CSV),
          en lugar de registrarlos uno por uno.
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Paso 1: Plantilla */}
        <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-4">
          <div className="flex items-start gap-3">
            <span className="shrink-0 w-7 h-7 rounded-full bg-pine-100 text-pine-800 text-sm font-bold flex items-center justify-center">1</span>
            <div className="flex-1">
              <p className="text-sm font-semibold text-slate-800">Descarga la plantilla y llenala con tus pacientes</p>
              <p className="text-xs text-slate-500 mt-0.5">
                Incluye las columnas correctas, una fila de ejemplo e instrucciones. 'Nombre completo' y 'Telefono' son obligatorios; las columnas de graduacion (anteojos y lentes de contacto "LC") son opcionales.
              </p>
              <div className="flex flex-wrap gap-2 mt-3">
                <Button type="button" variant="outline" size="sm" disabled={downloading}
                  onClick={() => handleDownload('xlsx')} data-testid="download-template-xlsx-btn">
                  <Download className="w-4 h-4 mr-1.5" /> Plantilla Excel
                </Button>
                <Button type="button" variant="outline" size="sm" disabled={downloading}
                  onClick={() => handleDownload('csv')} data-testid="download-template-csv-btn">
                  <Download className="w-4 h-4 mr-1.5" /> Plantilla CSV
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Paso 2: Subir archivo */}
        {!report && (
          <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-4">
            <div className="flex items-start gap-3">
              <span className="shrink-0 w-7 h-7 rounded-full bg-pine-100 text-pine-800 text-sm font-bold flex items-center justify-center">2</span>
              <div className="flex-1">
                <p className="text-sm font-semibold text-slate-800">Sube tu archivo lleno</p>
                <p className="text-xs text-slate-500 mt-0.5">Formatos: .xlsx o .csv. Maximo 2000 filas por carga.</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  Para cargar <strong>varias recetas a un mismo paciente</strong>, repite su correo o telefono en varias filas (una receta por fila).
                </p>

                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => inputRef.current?.click()}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click(); }}
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={(e) => { e.preventDefault(); setDragOver(false); onFileSelected(e.dataTransfer.files?.[0]); }}
                  className={`mt-3 flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 cursor-pointer transition-colors ${dragOver ? 'border-pine-500 bg-pine-50' : 'border-slate-300 hover:border-pine-400 hover:bg-white'}`}
                  data-testid="patient-import-dropzone"
                >
                  <UploadCloud className={`w-8 h-8 ${dragOver ? 'text-pine-600' : 'text-slate-400'}`} />
                  <p className="text-sm text-slate-600">
                    {file ? <span className="font-medium text-pine-800">{file.name}</span> : 'Arrastra tu archivo aqui o haz clic para seleccionarlo'}
                  </p>
                  {previewing && <p className="text-xs text-slate-400 flex items-center gap-1.5"><RefreshCw className="w-3 h-3 animate-spin" /> Leyendo archivo...</p>}
                  <input ref={inputRef} type="file" accept={ACCEPT} className="hidden"
                    onChange={(e) => onFileSelected(e.target.files?.[0])} data-testid="patient-import-file-input" />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Vista previa */}
        {preview && !report && (
          <div className="rounded-lg border border-slate-200 p-4 space-y-4" data-testid="patient-import-preview">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-slate-800 flex items-center gap-2">
                <FileCheck2 className="w-4 h-4 text-pine-700" /> Vista previa
              </p>
              <button onClick={resetAll} className="text-slate-400 hover:text-slate-600" data-testid="patient-import-cancel-btn" title="Quitar archivo">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <PreviewStat label="Filas detectadas" value={preview.total_rows} tone="slate" icon={<Users className="w-4 h-4" />} testid="preview-total" />
              <PreviewStat label="Pacientes nuevos" value={preview.new_patients ?? 0} tone="green" icon={<CheckCircle2 className="w-4 h-4" />} testid="preview-new" />
              <PreviewStat label="A actualizar" value={preview.update_patients ?? 0} tone="blue" icon={<RefreshCw className="w-4 h-4" />} testid="preview-update" />
              <PreviewStat label="Con error" value={preview.error_count} tone="red" icon={<AlertTriangle className="w-4 h-4" />} testid="preview-errors" />
            </div>

            {(preview.has_rx_count > 0 || preview.has_contact_count > 0) && (
              <p className="text-xs text-blue-700 flex items-center gap-1.5" data-testid="preview-rx-note">
                <Glasses className="w-3.5 h-3.5 shrink-0" />
                Se guardaran {preview.has_rx_count} recetas de anteojos y {preview.has_contact_count ?? 0} de lentes de contacto. Puedes repetir un paciente en varias filas para cargarle varias recetas.
              </p>
            )}

            {!preview.limit.unlimited && (
              <p className="text-xs text-slate-500">
                Cupo disponible en tu plan: <strong>{preview.limit.available}</strong> de {preview.limit.max} (tienes {preview.limit.current} pacientes).
                {willSkip > 0 && (
                  <span className="text-amber-700"> Se importaran los primeros {preview.limit.available} nuevos; {willSkip} quedarian fuera por el tope.</span>
                )}
              </p>
            )}

            {preview.sample.length > 0 && (
              <div className="overflow-x-auto">
                <p className="text-xs font-semibold text-slate-500 uppercase mb-1.5">Muestra de los primeros registros</p>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="h-8">Fila</TableHead>
                      <TableHead className="h-8">Nombre</TableHead>
                      <TableHead className="h-8">Telefono</TableHead>
                      <TableHead className="h-8">Correo</TableHead>
                      <TableHead className="h-8">Receta</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {preview.sample.map((r) => (
                      <TableRow key={r.row} data-testid={`preview-sample-${r.row}`}>
                        <TableCell className="py-1.5 text-slate-400">{r.row}</TableCell>
                        <TableCell className="py-1.5 font-medium text-slate-700">{r.name}</TableCell>
                        <TableCell className="py-1.5">{r.phone}</TableCell>
                        <TableCell className="py-1.5 text-slate-500">{r.email || '—'}</TableCell>
                        <TableCell className="py-1.5">{r.has_rx ? <Glasses className="w-4 h-4 text-blue-600" /> : '—'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}

            {preview.error_preview.length > 0 && (
              <div className="rounded-lg bg-red-50/70 border border-red-200 p-3">
                <p className="text-xs font-semibold text-red-700 mb-1.5">Filas con error (se omitiran):</p>
                <ul className="space-y-1">
                  {preview.error_preview.map((e, i) => (
                    <li key={i} className="text-xs text-red-800" data-testid={`preview-error-${e.row}`}>
                      <strong>Fila {e.row}</strong> ({e.name}): {e.reason}
                    </li>
                  ))}
                  {preview.error_count > preview.error_preview.length && (
                    <li className="text-xs text-red-600">…y {preview.error_count - preview.error_preview.length} mas.</li>
                  )}
                </ul>
              </div>
            )}

            <div className="flex flex-col sm:flex-row justify-end gap-2 pt-1">
              <Button variant="outline" onClick={resetAll} data-testid="patient-import-reset-btn">Cancelar</Button>
              <Button className="bg-pine-900 hover:bg-pine-700 text-white" disabled={committing || preview.valid_count === 0}
                onClick={handleConfirm} data-testid="patient-import-confirm-btn">
                {committing
                  ? <><RefreshCw className="w-4 h-4 mr-1.5 animate-spin" /> Importando...</>
                  : <><FileCheck2 className="w-4 h-4 mr-1.5" /> Confirmar importacion ({preview.valid_count})</>}
              </Button>
            </div>
          </div>
        )}

        {/* Reporte final */}
        {report && (
          <div className="rounded-lg border border-slate-200 p-4 space-y-4" data-testid="patient-import-report">
            <p className="text-sm font-semibold text-slate-800 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-pine-700" /> Importacion completada
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <PreviewStat label="Creados" value={report.created} tone="green" icon={<CheckCircle2 className="w-4 h-4" />} testid="import-count-created" />
              <PreviewStat label="Actualizados" value={report.updated} tone="blue" icon={<RefreshCw className="w-4 h-4" />} testid="import-count-updated" />
              <PreviewStat label="Fuera de tope" value={report.skipped_limit} tone="amber" icon={<Users className="w-4 h-4" />} testid="import-count-skipped" />
              <PreviewStat label="Con error" value={report.errors} tone="red" icon={<AlertTriangle className="w-4 h-4" />} testid="import-count-errors" />
            </div>
            {(report.prescriptions_created > 0 || report.contact_prescriptions_created > 0) && (
              <p className="text-xs text-blue-700 flex items-center gap-1.5">
                <Glasses className="w-3.5 h-3.5" /> Se guardaron {report.prescriptions_created} recetas de anteojos y {report.contact_prescriptions_created ?? 0} de lentes de contacto como historial.
              </p>
            )}

            {report.skipped_rows.length > 0 && (
              <div className="rounded-lg bg-amber-50/70 border border-amber-200 p-3">
                <p className="text-xs font-semibold text-amber-800 mb-1.5">Pacientes fuera del tope del plan:</p>
                <ul className="space-y-1">
                  {report.skipped_rows.map((s, i) => (
                    <li key={i} className="text-xs text-amber-800" data-testid={`report-skipped-${s.row}`}>
                      <strong>Fila {s.row}</strong> ({s.name}): {s.reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {report.error_rows.length > 0 && (
              <div className="rounded-lg bg-red-50/70 border border-red-200 p-3 max-h-56 overflow-y-auto">
                <p className="text-xs font-semibold text-red-700 mb-1.5">Filas con error (corrige y vuelve a subir solo esas):</p>
                <ul className="space-y-1">
                  {report.error_rows.map((e, i) => (
                    <li key={i} className="text-xs text-red-800" data-testid={`report-error-${e.row}`}>
                      <strong>Fila {e.row}</strong> ({e.name}): {e.reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex justify-end pt-1">
              <Button variant="outline" onClick={resetAll} data-testid="patient-import-again-btn">
                <UploadCloud className="w-4 h-4 mr-1.5" /> Importar otro archivo
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const TONES = {
  slate: 'bg-slate-50 border-slate-200 text-slate-700',
  green: 'bg-emerald-50 border-emerald-200 text-emerald-700',
  blue: 'bg-blue-50 border-blue-200 text-blue-700',
  amber: 'bg-amber-50 border-amber-200 text-amber-700',
  red: 'bg-red-50 border-red-200 text-red-700',
};

function PreviewStat({ label, value, tone, icon, testid }) {
  return (
    <div className={`rounded-lg border p-3 ${TONES[tone]}`} data-testid={testid}>
      <div className="flex items-center gap-1.5 text-xs font-medium opacity-80">{icon}{label}</div>
      <div className="text-2xl font-bold mt-1">{value}</div>
    </div>
  );
}

export default PatientBulkImport;
