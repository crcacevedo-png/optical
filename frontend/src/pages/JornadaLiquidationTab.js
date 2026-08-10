// Tab de Liquidacion de Consignacion + descarga de reportes
import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { Receipt, FileDown, FileSpreadsheet, TrendingUp, TrendingDown, RefreshCcw } from 'lucide-react';

const fmtQ = (n) => `Q ${(Number(n) || 0).toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function JornadaLiquidationTab({ jornada }) {
  const jid = jornada._id;
  const [data, setData] = useState(null);
  const [uploads, setUploads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [liq, ups] = await Promise.all([
        api.get(`/api/jornadas/${jid}/liquidation`),
        api.get(`/api/jornadas/${jid}/excel/uploads`).catch(() => ({ data: { items: [] } })),
      ]);
      setData(liq.data);
      setUploads(ups.data.items || []);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setLoading(false); }
  }, [jid]);
  useEffect(() => { load(); }, [load]);

  const revertUpload = async (uid) => {
    if (!window.confirm('Se eliminaran los productos cargados y su registro. Esto solo aplica si no tienen ventas. Continuar?')) return;
    setProcessing(true);
    try {
      await api.post(`/api/jornadas/${jid}/excel/${uid}/revert`);
      toast.success('Carga revertida');
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setProcessing(false); }
  };

  if (loading || !data) {
    return <div className="flex items-center justify-center h-32"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-pine-900" /></div>;
  }

  const t = data.totals;
  const backend = process.env.REACT_APP_BACKEND_URL;

  return (
    <div className="space-y-4">
      {/* Descargas de reporte */}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" asChild data-testid="tab-liq-pdf">
          <a href={`${backend}/api/jornadas/${jid}/report.pdf`} target="_blank" rel="noopener noreferrer">
            <FileDown className="w-4 h-4 mr-1.5" /> Descargar reporte PDF
          </a>
        </Button>
        <Button size="sm" variant="outline" asChild data-testid="tab-liq-xlsx">
          <a href={`${backend}/api/jornadas/${jid}/report.xlsx`} target="_blank" rel="noopener noreferrer">
            <FileSpreadsheet className="w-4 h-4 mr-1.5" /> Descargar reporte Excel
          </a>
        </Button>
      </div>

      {/* Totales de liquidacion */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MiniStat label="Unidades vendidas" value={t.sold_units} icon={TrendingUp} color="text-emerald-700 bg-emerald-50" />
        <MiniStat label="Devuelto" value={t.returned_units} icon={RefreshCcw} color="text-blue-700 bg-blue-50" />
        <MiniStat label="Faltante" value={t.missing_units} icon={TrendingDown} color="text-rose-700 bg-rose-50" />
        <MiniStat label="A pagar consignatarios" value={fmtQ(t.to_pay)} icon={Receipt} color="text-amber-700 bg-amber-50" highlight />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-100">
          <p className="text-xs text-emerald-600 uppercase">Ingreso consignacion</p>
          <p className="font-heading text-xl font-bold text-emerald-900">{fmtQ(t.revenue)}</p>
        </div>
        <div className="p-3 rounded-lg bg-pine-50 border border-pine-200">
          <p className="text-xs text-pine-700 uppercase">Utilidad optica</p>
          <p className="font-heading text-xl font-bold text-pine-900">{fmtQ(t.margin)}</p>
        </div>
      </div>

      {/* Detalle por proveedor */}
      {data.per_supplier.length === 0 ? (
        <Card className="border-dashed border-slate-300"><CardContent className="py-8 text-center">
          <Receipt className="w-10 h-10 text-slate-400 mx-auto mb-2" />
          <p className="text-sm text-slate-600">Sin inventario de consignacion</p>
          <p className="text-xs text-slate-400 mt-1">Carga un archivo Excel desde la pestana Inventario.</p>
        </CardContent></Card>
      ) : (
        <div className="space-y-3">
          {data.per_supplier.map((sup) => (
            <Card key={sup.supplier} data-testid={`liq-supplier-${sup.supplier}`}>
              <CardContent className="pt-5 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="font-heading font-semibold text-slate-800">{sup.supplier}</p>
                  <div className="flex gap-3 text-sm">
                    <span>Vendido: <strong>{sup.sold_units}</strong></span>
                    <span>Devuelto: <strong>{sup.returned_units}</strong></span>
                    <span>Faltante: <strong className={sup.missing_units > 0 ? 'text-rose-600' : ''}>{sup.missing_units}</strong></span>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div className="p-2 rounded bg-amber-50 border border-amber-100">
                    <p className="text-[10px] text-amber-600 uppercase">A pagar</p>
                    <p className="font-bold text-amber-900">{fmtQ(sup.to_pay)}</p>
                  </div>
                  <div className="p-2 rounded bg-emerald-50 border border-emerald-100">
                    <p className="text-[10px] text-emerald-600 uppercase">Ingreso</p>
                    <p className="font-bold text-emerald-900">{fmtQ(sup.revenue)}</p>
                  </div>
                  <div className="p-2 rounded bg-pine-50 border border-pine-200">
                    <p className="text-[10px] text-pine-700 uppercase">Utilidad</p>
                    <p className="font-bold text-pine-900">{fmtQ(sup.margin)}</p>
                  </div>
                </div>
                <div className="border-t border-slate-100 pt-2">
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead className="text-slate-400 uppercase">
                        <tr>
                          <th className="text-left py-1">Producto</th>
                          <th className="text-right py-1">Inicial</th>
                          <th className="text-right py-1">Vendido</th>
                          <th className="text-right py-1">Actual</th>
                          <th className="text-right py-1">Falt.</th>
                          <th className="text-right py-1">A pagar</th>
                          <th className="text-right py-1">Utilidad</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {sup.items.map(it => (
                          <tr key={it.product_id}>
                            <td className="py-1 truncate max-w-[180px]">{it.product_name}</td>
                            <td className="text-right">{it.initial_qty}</td>
                            <td className="text-right text-emerald-700">{it.sold_qty}</td>
                            <td className="text-right">{it.current_qty}</td>
                            <td className={`text-right ${it.missing_qty > 0 ? 'text-rose-600' : ''}`}>{it.missing_qty}</td>
                            <td className="text-right">{fmtQ(it.to_pay)}</td>
                            <td className="text-right">{fmtQ(it.margin)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Historial de cargas Excel */}
      {uploads.length > 0 && (
        <Card><CardContent className="pt-5">
          <p className="text-sm font-semibold text-slate-700 mb-3">Historial de cargas Excel</p>
          <div className="space-y-2">
            {uploads.map((u) => (
              <div key={u._id} className="flex items-center justify-between p-2 rounded border border-slate-200 text-sm" data-testid={`upload-${u._id}`}>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{u.filename}</p>
                  <p className="text-xs text-slate-500">
                    {u.rows_created} creado(s) · {u.rows_linked} vinculado(s) · {u.rows_errors?.length || 0} error(es) · {new Date(u.created_at).toLocaleString('es-GT')}
                  </p>
                </div>
                <Badge variant="outline" className={u.status === 'imported' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-slate-100'}>
                  {u.status === 'imported' ? 'Cargado' : 'Revertido'}
                </Badge>
                {u.status === 'imported' && (jornada.status === 'planificada' || jornada.status === 'activa') && (
                  <Button size="sm" variant="ghost" disabled={processing} onClick={() => revertUpload(u._id)} data-testid={`revert-${u._id}`}>
                    Revertir
                  </Button>
                )}
              </div>
            ))}
          </div>
        </CardContent></Card>
      )}
    </div>
  );
}

function MiniStat({ label, value, icon: Icon, color, highlight }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? 'border-amber-300' : 'border-slate-200'} bg-white`}>
      <div className="flex items-center gap-2 mb-1">
        <div className={`w-6 h-6 rounded ${color} flex items-center justify-center`}><Icon className="w-3.5 h-3.5" /></div>
        <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      </div>
      <p className="font-heading text-lg font-bold text-slate-900">{value}</p>
    </div>
  );
}
