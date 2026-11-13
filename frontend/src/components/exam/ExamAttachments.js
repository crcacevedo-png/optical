import React, { useRef, useState } from 'react';
import { Paperclip, FileText, Trash2, Loader2, Upload } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { apiError, fmtDate } from './examShared';

export function ExamAttachments({ exam, onChange, readOnly }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const files = exam?.attachments || [];

  const upload = async (file) => {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { toast.error('Archivo demasiado grande (máx. 10MB)'); return; }
    const fd = new FormData();
    fd.append('file', file);
    setBusy(true);
    try {
      await api.post(`/api/clinical/exams/${exam._id}/attachments`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success('Archivo adjuntado');
      onChange();
    } catch (err) { toast.error(apiError(err, 'No se pudo adjuntar')); }
    finally { setBusy(false); if (inputRef.current) inputRef.current.value = ''; }
  };
  const open = async (a) => {
    try {
      const res = await api.get(`/api/clinical/exams/${exam._id}/attachments/${a.id}`, { responseType: 'blob' });
      window.open(window.URL.createObjectURL(new Blob([res.data], { type: a.content_type })), '_blank');
    } catch (err) { toast.error(apiError(err, 'No se pudo abrir el archivo')); }
  };
  const remove = async (a) => {
    try { await api.delete(`/api/clinical/exams/${exam._id}/attachments/${a.id}`); onChange(); }
    catch (err) { toast.error(apiError(err)); }
  };

  return (
    <div className="space-y-2" data-testid="exam-attachments">
      {files.length === 0 && <p className="text-xs text-slate-400">Sin archivos adjuntos.</p>}
      {files.map((a) => (
        <div key={a.id} className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm" data-testid={`attachment-${a.id}`}>
          <FileText className="w-4 h-4 text-slate-400 shrink-0" />
          <button type="button" className="flex-1 truncate text-left text-slate-700 hover:text-teal-700 hover:underline" onClick={() => open(a)} data-testid={`attachment-open-${a.id}`}>{a.filename}</button>
          <span className="text-[11px] text-slate-400 hidden sm:inline">{fmtDate(a.uploaded_at)} · {Math.round((a.size || 0) / 1024)} KB</span>
          {!readOnly && <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-red-600" onClick={() => remove(a)} data-testid={`attachment-delete-${a.id}`}><Trash2 className="w-3.5 h-3.5" /></Button>}
        </div>
      ))}
      {!readOnly && (
        <>
          <input ref={inputRef} type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" className="hidden" onChange={(e) => upload(e.target.files?.[0])} data-testid="attachment-file-input" />
          <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => inputRef.current?.click()} data-testid="attachment-upload-btn">
            {busy ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Upload className="w-3.5 h-3.5 mr-1.5" />} Adjuntar estudio (PDF o imagen)
          </Button>
        </>
      )}
      <p className="text-[11px] text-slate-400 flex items-center gap-1"><Paperclip className="w-3 h-3" /> Máx. 10MB por archivo. Se guardan de forma privada en el expediente.</p>
    </div>
  );
}
