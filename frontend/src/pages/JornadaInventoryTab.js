// Tab de Inventario de la Jornada
import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import { Package, Truck, Search, Plus, Minus, RefreshCw, FileSpreadsheet } from 'lucide-react';
import JornadaExcelImport from './JornadaExcelImport';

const fmtQ = (n) => `Q ${(Number(n) || 0).toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function JornadaInventoryTab({ jornada, reload }) {
  const jid = jornada._id;
  const [items, setItems] = useState([]);
  const [totals, setTotals] = useState({ total_units: 0, total_value: 0 });
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [transferDialog, setTransferDialog] = useState(false);
  const [branches, setBranches] = useState([]);
  const [products, setProducts] = useState([]);
  const [selectedBranch, setSelectedBranch] = useState('');
  const [cart, setCart] = useState({}); // {product_id: quantity}
  const [prodSearch, setProdSearch] = useState('');
  const [processing, setProcessing] = useState(false);
  const [adjustDialog, setAdjustDialog] = useState(null); // row being adjusted
  const [adjustForm, setAdjustForm] = useState({ delta: 0, reason: 'dano', notes: '' });
  const [excelOpen, setExcelOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/api/jornadas/${jid}/inventory`, { params: search ? { search } : {} });
      setItems(res.data.items || []);
      setTotals({ total_units: res.data.total_units || 0, total_value: res.data.total_value || 0 });
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setLoading(false); }
  }, [jid, search]);
  useEffect(() => { load(); }, [load]);

  const openTransfer = async () => {
    setTransferDialog(true);
    try {
      const [bRes, pRes] = await Promise.all([
        api.get('/api/branches'),
        api.get('/api/inventory/products', { params: { limit: 500 } }).catch(() => ({ data: [] })),
      ]);
      setBranches(bRes.data || []);
      // products may come nested
      setProducts(Array.isArray(pRes.data) ? pRes.data : (pRes.data?.items || []));
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const submitTransfer = async () => {
    const items = Object.entries(cart).filter(([, q]) => q > 0).map(([product_id, quantity]) => ({ product_id, quantity: parseInt(quantity, 10) }));
    if (!selectedBranch) { toast.error('Selecciona sucursal fuente'); return; }
    if (items.length === 0) { toast.error('Agrega al menos un producto'); return; }
    setProcessing(true);
    try {
      const res = await api.post(`/api/jornadas/${jid}/inventory/transfer`, { source_branch_id: selectedBranch, items });
      toast.success(res.data.message);
      if (res.data.errors?.length) {
        res.data.errors.forEach((e) => toast.warning(`${e.product_id}: ${e.error}`));
      }
      setTransferDialog(false);
      setCart({});
      setSelectedBranch('');
      setProdSearch('');
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setProcessing(false); }
  };

  const doAdjust = async () => {
    if (!adjustDialog) return;
    const delta = parseInt(adjustForm.delta, 10);
    if (!delta || !adjustForm.reason.trim()) { toast.error('Delta y motivo obligatorios'); return; }
    setProcessing(true);
    try {
      await api.post(`/api/jornadas/${jid}/inventory/adjust`, { product_id: adjustDialog.product_id, delta, reason: adjustForm.reason, notes: adjustForm.notes });
      toast.success('Ajuste registrado');
      setAdjustDialog(null);
      setAdjustForm({ delta: 0, reason: 'dano', notes: '' });
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setProcessing(false); }
  };

  const filteredProducts = prodSearch
    ? products.filter(p => (p.name || '').toLowerCase().includes(prodSearch.toLowerCase()) || (p.sku || '').toLowerCase().includes(prodSearch.toLowerCase()))
    : products.slice(0, 50);

  const canOperate = jornada.status === 'activa' || jornada.status === 'planificada';

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 justify-between">
        <div className="flex gap-3">
          <div className="p-2 rounded-lg bg-blue-50 border border-blue-100">
            <p className="text-[10px] text-blue-600 uppercase">Unidades</p>
            <p className="font-heading font-bold text-blue-900">{totals.total_units}</p>
          </div>
          <div className="p-2 rounded-lg bg-emerald-50 border border-emerald-100">
            <p className="text-[10px] text-emerald-600 uppercase">Valor</p>
            <p className="font-heading font-bold text-emerald-900">{fmtQ(totals.total_value)}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2 top-2.5 w-4 h-4 text-slate-400" />
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar producto..." className="pl-8 w-56" data-testid="jinv-search" />
          </div>
          {canOperate && jornada.inventory_config?.use_branch_stock && (
            <Button size="sm" onClick={openTransfer} className="bg-pine-900 hover:bg-pine-800" data-testid="jinv-transfer-btn">
              <Truck className="w-4 h-4 mr-1.5" /> Traslado desde sucursal
            </Button>
          )}
          {canOperate && jornada.inventory_config?.use_consignment && (
            <Button size="sm" variant="outline" onClick={() => setExcelOpen(true)} data-testid="jinv-excel-btn">
              <FileSpreadsheet className="w-4 h-4 mr-1.5" /> Cargar Excel consignacion
            </Button>
          )}
        </div>
      </div>
      <JornadaExcelImport jornadaId={jid} open={excelOpen} onClose={() => setExcelOpen(false)} onSuccess={load} />

      {loading ? (
        <div className="flex items-center justify-center h-32"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-pine-900" /></div>
      ) : items.length === 0 ? (
        <Card className="border-dashed border-slate-300"><CardContent className="py-10 text-center">
          <Package className="w-10 h-10 text-slate-400 mx-auto mb-2" />
          <p className="text-sm text-slate-600">Aun no hay inventario cargado</p>
          <p className="text-xs text-slate-400 mt-1">Traslada productos desde una sucursal para empezar.</p>
        </CardContent></Card>
      ) : (
        <Card><CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="jinv-table">
              <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Producto</th>
                  <th className="px-3 py-2 text-right">Inicial</th>
                  <th className="px-3 py-2 text-right">Vendido</th>
                  <th className="px-3 py-2 text-right">Ajustes</th>
                  <th className="px-3 py-2 text-right">Disponible</th>
                  <th className="px-3 py-2 text-right">Precio</th>
                  <th className="px-3 py-2 text-right">Valor</th>
                  <th className="px-3 py-2">Origen</th>
                  {canOperate && <th className="px-3 py-2"></th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((it) => (
                  <tr key={it._id} className="hover:bg-slate-50" data-testid={`jinv-row-${it.product_id}`}>
                    <td className="px-3 py-2">
                      <p className="font-medium text-slate-800">{it.product_name}</p>
                      <p className="text-[11px] text-slate-400">{it.product_sku || '—'} · {it.product_brand || ''}</p>
                    </td>
                    <td className="px-3 py-2 text-right">{it.initial_qty}</td>
                    <td className="px-3 py-2 text-right text-emerald-700">{it.sold_qty}</td>
                    <td className="px-3 py-2 text-right text-slate-500">{it.adjusted_qty || 0}</td>
                    <td className={`px-3 py-2 text-right font-semibold ${it.current_qty === 0 ? 'text-rose-600' : ''}`}>{it.current_qty}</td>
                    <td className="px-3 py-2 text-right">{fmtQ(it.unit_price)}</td>
                    <td className="px-3 py-2 text-right">{fmtQ((it.current_qty || 0) * (it.unit_price || 0))}</td>
                    <td className="px-3 py-2">
                      <Badge variant="outline" className={it.source === 'consignment' ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-blue-50 text-blue-700 border-blue-200'}>
                        {it.source === 'consignment' ? 'Consignacion' : 'Sucursal'}
                      </Badge>
                    </td>
                    {canOperate && (
                      <td className="px-3 py-2">
                        <Button size="sm" variant="ghost" onClick={() => setAdjustDialog(it)} data-testid={`jinv-adjust-${it.product_id}`}>Ajustar</Button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent></Card>
      )}

      {/* Transfer dialog */}
      <Dialog open={transferDialog} onOpenChange={setTransferDialog}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader><DialogTitle>Trasladar productos desde sucursal</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>Sucursal fuente *</Label>
              <Select value={selectedBranch} onValueChange={setSelectedBranch}>
                <SelectTrigger data-testid="jinv-transfer-branch"><SelectValue placeholder="Selecciona" /></SelectTrigger>
                <SelectContent>{branches.map(b => <SelectItem key={b._id} value={b._id}>{b.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Buscar producto</Label>
              <div className="relative">
                <Search className="absolute left-2 top-2.5 w-4 h-4 text-slate-400" />
                <Input value={prodSearch} onChange={(e) => setProdSearch(e.target.value)} placeholder="Nombre o SKU..." className="pl-8" data-testid="jinv-transfer-search" />
              </div>
            </div>
            <div className="border rounded-md max-h-72 overflow-y-auto divide-y">
              {filteredProducts.length === 0 && <p className="p-4 text-xs text-slate-400 text-center">No hay productos</p>}
              {filteredProducts.map(p => (
                <div key={p._id} className="flex items-center gap-3 p-2 hover:bg-slate-50" data-testid={`jinv-transfer-prod-${p._id}`}>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{p.name}</p>
                    <p className="text-[11px] text-slate-400">{p.sku || '—'} · {fmtQ(p.sale_price || p.price)}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button size="sm" variant="ghost" onClick={() => setCart(c => ({ ...c, [p._id]: Math.max(0, (c[p._id] || 0) - 1) }))}><Minus className="w-3 h-3" /></Button>
                    <Input type="number" min="0" className="w-14 h-8 text-center" value={cart[p._id] || 0} onChange={(e) => setCart(c => ({ ...c, [p._id]: parseInt(e.target.value, 10) || 0 }))} data-testid={`jinv-qty-${p._id}`} />
                    <Button size="sm" variant="ghost" onClick={() => setCart(c => ({ ...c, [p._id]: (c[p._id] || 0) + 1 }))}><Plus className="w-3 h-3" /></Button>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-500">Total items: {Object.values(cart).reduce((s, v) => s + (v || 0), 0)}</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTransferDialog(false)}>Cancelar</Button>
            <Button className="bg-pine-900 hover:bg-pine-800" disabled={processing} onClick={submitTransfer} data-testid="jinv-transfer-confirm">
              {processing ? 'Trasladando...' : 'Trasladar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Adjust dialog */}
      <Dialog open={adjustDialog !== null} onOpenChange={(o) => { if (!o) setAdjustDialog(null); }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle>Ajustar inventario</DialogTitle></DialogHeader>
          {adjustDialog && (
            <div className="space-y-3">
              <p className="text-sm text-slate-600">{adjustDialog.product_name} · Actual: <strong>{adjustDialog.current_qty}</strong></p>
              <div className="space-y-1.5">
                <Label>Delta (+ suma, - resta) *</Label>
                <Input type="number" value={adjustForm.delta} onChange={(e) => setAdjustForm({ ...adjustForm, delta: e.target.value })} data-testid="jinv-adjust-delta" />
              </div>
              <div className="space-y-1.5">
                <Label>Motivo *</Label>
                <Select value={adjustForm.reason} onValueChange={(v) => setAdjustForm({ ...adjustForm, reason: v })}>
                  <SelectTrigger data-testid="jinv-adjust-reason"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="dano">Dano</SelectItem>
                    <SelectItem value="perdida">Perdida</SelectItem>
                    <SelectItem value="obsequio">Obsequio</SelectItem>
                    <SelectItem value="correccion_conteo">Correccion de conteo</SelectItem>
                    <SelectItem value="otro">Otro</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Notas</Label>
                <Input value={adjustForm.notes} onChange={(e) => setAdjustForm({ ...adjustForm, notes: e.target.value })} data-testid="jinv-adjust-notes" />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setAdjustDialog(null)}>Cancelar</Button>
            <Button className="bg-amber-600 hover:bg-amber-700" disabled={processing} onClick={doAdjust} data-testid="jinv-adjust-confirm">
              {processing ? 'Guardando...' : 'Ajustar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
