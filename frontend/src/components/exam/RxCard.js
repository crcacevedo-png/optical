import React from 'react';
import { MoreHorizontal, Pencil, Send, FileDown, Eye, MessageCircle, Mail, GitBranch, Copy, Ban, ExternalLink, AlertTriangle } from 'lucide-react';
import { Button } from '../ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '../ui/dropdown-menu';
import { KIND_META, RX_STATUS, rxStatusKey, eyeSummary, fmtDate } from './examShared';
import { rxTitle } from './rxUtils';

const Item = ({ icon: Icon, label, onClick, testId, danger }) => (
  <DropdownMenuItem onClick={onClick} className={danger ? 'text-red-600 focus:text-red-700' : ''} data-testid={testId}>
    <Icon className="w-4 h-4 mr-2" /> {label}
  </DropdownMenuItem>
);

export function RxCard({ rx, actions, onEdit, onView, onOpenExam, canIssue }) {
  const meta = KIND_META[rx.kind];
  const status = rxStatusKey(rx);
  const st = RX_STATUS[status];
  const draft = status === 'borrador';
  const issued = status === 'emitida';
  const id = `${rx.kind}-${rx._id}`;
  return (
    <article className={`group rounded-xl border bg-white p-4 transition-shadow hover:shadow-md ${draft ? 'border-amber-200' : 'border-slate-200'} ${['anulada', 'sustituida'].includes(status) ? 'opacity-70' : ''}`} data-testid={`rx-card-${id}`}>
      <div className="flex flex-wrap items-start gap-3">
        <span className={`w-9 h-9 shrink-0 rounded-lg flex items-center justify-center ${meta.cls}`}><meta.icon className="w-4 h-4" /></span>
        <div className="flex-1 min-w-[180px]">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className={`font-semibold text-slate-900 ${status === 'anulada' ? 'line-through' : ''}`} data-testid={`rx-card-title-${id}`}>{rxTitle(rx)}</h4>
            <span className={`text-[11px] font-semibold rounded-full border px-2 py-0.5 ${st.cls}`} data-testid={`rx-card-status-${id}`}>{st.label}</span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            <span className="font-mono">{rx.code_display}</span> · v{rx.version || 1} · {meta.label}
            {rx.usage ? ` · ${rx.usage}` : ''} · {issued || status === 'sustituida' ? `emitida ${fmtDate(rx.issued_at)}` : `creada ${fmtDate(rx.created_at)}`}
          </p>
          <div className="mt-2 grid gap-0.5 font-mono text-xs text-slate-700">
            <p><span className="font-sans font-bold text-blue-700 mr-1.5">OD</span>{eyeSummary(rx.kind, rx, 'od')}</p>
            <p><span className="font-sans font-bold text-emerald-700 mr-1.5">OS</span>{eyeSummary(rx.kind, rx, 'oi')}</p>
          </div>
          {rx.from_previous_fr && (
            <p className="mt-2 inline-flex items-center gap-1 text-[11px] font-semibold text-amber-800 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5" data-testid={`rx-card-prev-fr-${id}`}>
              <AlertTriangle className="w-3 h-3" /> Basada en la refracción final v{rx.source_ref?.fr_version} (existe una versión más reciente)
            </p>
          )}
          {status === 'anulada' && rx.void_reason && <p className="mt-1 text-[11px] text-red-700">Motivo: {rx.void_reason}</p>}
        </div>
        <div className="flex items-center gap-1.5 ml-auto">
          {draft ? (
            <>
              <Button size="sm" variant="outline" onClick={() => onEdit(rx)} data-testid={`rx-edit-${id}`}><Pencil className="w-3.5 h-3.5 mr-1" /> Editar</Button>
              {canIssue && <Button size="sm" className="bg-pine-700 hover:bg-pine-800" onClick={() => actions.issue(rx)} data-testid={`rx-issue-${id}`}><Send className="w-3.5 h-3.5 mr-1" /> Emitir</Button>}
            </>
          ) : issued ? (
            <Button size="sm" variant="outline" onClick={() => actions.pdf(rx)} data-testid={`rx-pdf-${id}`}><FileDown className="w-3.5 h-3.5 mr-1" /> PDF</Button>
          ) : (
            <Button size="sm" variant="outline" onClick={() => onView(rx)} data-testid={`rx-view-${id}`}><Eye className="w-3.5 h-3.5 mr-1" /> Ver</Button>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="icon" variant="ghost" className="h-8 w-8" data-testid={`rx-menu-${id}`}><MoreHorizontal className="w-4 h-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              {!draft && <Item icon={Eye} label="Ver detalle" onClick={() => onView(rx)} testId={`rx-menu-view-${id}`} />}
              <Item icon={FileDown} label={issued ? 'Descargar PDF' : 'Vista previa (sin validez)'} onClick={() => actions.pdf(rx)} testId={`rx-menu-pdf-${id}`} />
              {issued && <Item icon={MessageCircle} label="Enviar por WhatsApp" onClick={() => actions.whatsapp(rx)} testId={`rx-menu-wa-${id}`} />}
              {issued && <Item icon={Mail} label="Enviar por correo" onClick={() => actions.email(rx)} testId={`rx-menu-mail-${id}`} />}
              <DropdownMenuSeparator />
              {issued && <Item icon={GitBranch} label="Nueva versión" onClick={() => actions.newVersion(rx)} testId={`rx-menu-version-${id}`} />}
              <Item icon={Copy} label="Duplicar" onClick={() => actions.duplicate(rx)} testId={`rx-menu-duplicate-${id}`} />
              {onOpenExam && rx.consultation_id && <Item icon={ExternalLink} label="Abrir examen" onClick={() => onOpenExam(rx)} testId={`rx-menu-exam-${id}`} />}
              {(draft || issued) && canIssue && (
                <>
                  <DropdownMenuSeparator />
                  <Item icon={Ban} label="Anular" onClick={() => actions.void(rx)} testId={`rx-menu-void-${id}`} danger />
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </article>
  );
}
