// Excel Import Wizard para consignacion
import React, { useState } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from '../components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { toast } from 'sonner';
import { Upload, FileSpreadsheet, ChevronRight, ChevronLeft, CheckCircle2 } from 'lucide-react';

const FIELD_LABELS = {
  code: 'Codigo / SKU',
  description: 'Descripcion *',
  category: 'Categoria',
  brand: 'Marca',
  model: 'Modelo',
  color: 'Color',
  size: 'Tamano',
  quantity: 'Cantidad *',
  unit_cost: 'Costo unitario',
  unit_price: 'Precio venta',
  supplier: 'Proveedor',
  batch: 'Lote',
};

export default function JornadaExcelImport({ jornadaId, open, onClose, onSuccess }) {
  const [step, setStep] = useState(0); // 0: upload, 1: mapping, 2: confirm
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [mapping, setMapping] = useState({});
  const [defaultSupplier, setDefaultSupplier] = useState('');
  const [defaultMargin, setDefaultMargin] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const reset = () => {
    setStep(0); setFile(null); setPreview(null); setMapping({});
    setDefaultSupplier(''); setDefaultMargin(''); setResult(null);
  };

  const handleFile = async (f) => {
    if (!f) return;
    setFile(f);
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append('file', f);
      const res = await api.post(`/api/jornadas/${jornadaId}/excel/preview`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setPreview(res.data);
      setMapping(res.data.suggested_mapping || {});
      setStep(1);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setLoading(false); }
  };

  const doImport = async () => {
    if (mapping.description === undefined || mapping.quantity === undefined) {
      toast.error('Descripcion y Cantidad son obligatorios');
      return;
    }
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('mapping_json', JSON.stringify({
        header_row: preview.header_row,
        mapping,
        default_supplier: defaultSupplier || null,
        default_margin_percent: defaultMargin ? parseFloat(defaultMargin) : null,
      }));
      const res = await api.post(`/api/jornadas/${jornadaId}/excel/import`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(res.data);
      setStep(2);
      toast.success(res.data.message);
      onSuccess?.();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setLoading(false); }
  };

  const close = () => { reset(); onClose(); };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) close(); }}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileSpreadsheet className="w-5 h-5" /> Carga Excel de Consignacion — Paso {step + 1} de 3
          </DialogTitle>
          <DialogDescription>
            {step === 0 && 'Sube el archivo del proveedor. Aceptamos xlsx.'}
            {step === 1 && 'Confirma el mapeo de columnas y ajustes opcionales.'}
            {step === 2 && 'Resumen de la carga.'}
          </DialogDescription>
        </DialogHeader>

        {step === 0 && (
          <div className="space-y-3">
            <label className="block border-2 border-dashed border-slate-300 rounded-lg p-8 text-center cursor-pointer hover:border-pine-500 hover:bg-pine-50 transition-colors" data-testid="excel-drop">
              <input
                type="file" accept=".xlsx,.xls"
                onChange={(e) => handleFile(e.target.files?.[0])}
                className="hidden"
                data-testid="excel-file"
              />
              <Upload className="w-10 h-10 text-slate-400 mx-auto mb-2" />
              <p className="text-sm text-slate-700 font-medium">Click para subir o arrastra el archivo</p>
              <p className="text-xs text-slate-400 mt-1">Excel (.xlsx), maximo 5 MB</p>
            </label>
            {loading && <p className="text-sm text-center text-slate-500">Procesando...</p>}
          </div>
        )}

        {step === 1 && preview && (
          <div className="space-y-3 max-h-[500px] overflow-y-auto">
            <div className="rounded-lg border border-slate-200 p-3 bg-slate-50 text-sm">
              <p><strong>Archivo:</strong> {preview.filename}</p>
              <p><strong>Filas estimadas:</strong> {preview.total_rows_estimate}</p>
              <p><strong>Encabezados detectados en fila:</strong> {preview.header_row}</p>
            </div>

            <div className="space-y-2">
              <Label>Mapeo de columnas *</Label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {Object.entries(FIELD_LABELS).map(([field, label]) => (
                  <div key={field} className="flex items-center gap-2 p-2 rounded border border-slate-200">
                    <Label className="text-xs w-32 flex-shrink-0">{label}</Label>
                    <Select
                      value={mapping[field] !== undefined ? String(mapping[field]) : 'none'}
                      onValueChange={(v) => {
                        const newMap = { ...mapping };
                        if (v === 'none') delete newMap[field];
                        else newMap[field] = parseInt(v, 10);
                        setMapping(newMap);
                      }}
                    >
                      <SelectTrigger className="h-8 text-xs" data-testid={`excel-map-${field}`}><SelectValue placeholder="No mapear" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">— No mapear —</SelectItem>
                        {preview.headers.map((h, i) => (
                          <SelectItem key={i} value={String(i)}>{h}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Proveedor por defecto</Label>
                <Input value={defaultSupplier} onChange={(e) => setDefaultSupplier(e.target.value)} placeholder="Ej: Distribuidor XYZ" data-testid="excel-supplier" />
              </div>
              <div className="space-y-1.5">
                <Label>Margen % (si no hay precio)</Label>
                <Input type="number" min="0" step="1" value={defaultMargin} onChange={(e) => setDefaultMargin(e.target.value)} placeholder="Opcional" data-testid="excel-margin" />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Vista previa (primeras filas)</Label>
              <div className="overflow-x-auto border rounded-md">
                <table className="text-xs w-full">
                  <thead className="bg-slate-50">
                    <tr>{preview.headers.map((h, i) => <th key={i} className="px-2 py-1.5 text-left font-medium">{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {preview.sample_rows.map((row, i) => (
                      <tr key={i} className="border-t">
                        {row.map((c, j) => <td key={j} className="px-2 py-1 truncate max-w-[120px]">{c}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {step === 2 && result && (
          <div className="space-y-3 text-center py-4">
            <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-8 h-8 text-emerald-600" />
            </div>
            <p className="font-heading text-lg font-semibold">Carga completada</p>
            <div className="grid grid-cols-3 gap-3 max-w-sm mx-auto text-sm">
              <div className="p-2 rounded bg-emerald-50"><p className="text-xs text-slate-500">Creados</p><p className="font-bold text-emerald-700">{result.rows_created}</p></div>
              <div className="p-2 rounded bg-blue-50"><p className="text-xs text-slate-500">Vinculados</p><p className="font-bold text-blue-700">{result.rows_linked}</p></div>
              <div className="p-2 rounded bg-rose-50"><p className="text-xs text-slate-500">Errores</p><p className="font-bold text-rose-700">{result.rows_errors?.length || 0}</p></div>
            </div>
            {result.rows_errors?.length > 0 && (
              <div className="text-left max-h-32 overflow-y-auto border rounded-md p-2 text-xs">
                {result.rows_errors.slice(0, 10).map((e, i) => (
                  <p key={i} className="text-rose-700">Fila {e.row}: {e.error}</p>
                ))}
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          {step > 0 && step < 2 && <Button variant="outline" onClick={() => setStep(s => s - 1)}><ChevronLeft className="w-4 h-4 mr-1" /> Atras</Button>}
          <Button variant="outline" onClick={close}>{step === 2 ? 'Cerrar' : 'Cancelar'}</Button>
          {step === 1 && (
            <Button className="bg-pine-900 hover:bg-pine-800" disabled={loading || mapping.description === undefined || mapping.quantity === undefined} onClick={doImport} data-testid="excel-import-confirm">
              {loading ? 'Cargando...' : 'Confirmar carga'} <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
