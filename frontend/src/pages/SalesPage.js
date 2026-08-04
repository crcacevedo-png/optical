import React, { useState, useEffect } from 'react';
import { api, formatApiErrorDetail, useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle
} from '../components/ui/alert-dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import {
  Plus, ShoppingCart, Trash2, User, Receipt, Eye, HandCoins
} from 'lucide-react';
import { toast } from 'sonner';
import { BranchFilter } from '../components/BranchFilter';
import { PaymentLinesEditor, paymentMethodLabel } from '../components/PaymentLinesEditor';
import { AddPaymentDialog } from '../components/AddPaymentDialog';
import { SalesCashBar } from '../components/SalesCashBar';

export default function SalesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [sales, setSales] = useState([]);
  const [patients, setPatients] = useState([]);
  const [products, setProducts] = useState([]);
  const [stock, setStock] = useState([]);
  const [loading, setLoading] = useState(true);
  const [branchId, setBranchId] = useState('');
  const [showSaleDialog, setShowSaleDialog] = useState(false);
  const [detailSale, setDetailSale] = useState(null);
  const [paymentSale, setPaymentSale] = useState(null);
  const [saleToDelete, setSaleToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const [cart, setCart] = useState([]);
  const [saleForm, setSaleForm] = useState({
    patient_id: '',
    discount: 0,
    notes: ''
  });
  // Nuevo: array dinamico de pagos [{method, amount, note}]
  const [payments, setPayments] = useState([{ method: 'cash', amount: 0, note: '' }]);
  // Estado de la caja: bloquea nueva venta si esta cerrada
  const [cashOpen, setCashOpen] = useState(false);

  useEffect(() => {
    fetchData();
  }, [branchId]);

  const fetchData = async () => {
    try {
      const params = branchId ? { branch_id: branchId } : {};
      const [salesRes, patientsRes, productsRes, stockRes] = await Promise.all([
        api.get('/api/sales', { params }),
        api.get('/api/patients', { params: { limit: 200 } }),
        api.get('/api/inventory/products'),
        api.get('/api/inventory/stock', { params })
      ]);
      setSales(salesRes.data || []);
      setPatients(patientsRes.data.patients || []);
      setProducts(productsRes.data || []);
      setStock(stockRes.data || []);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStockForProduct = (productId) => {
    const s = stock.find(item => item.product_id === productId);
    return s?.quantity || 0;
  };

  const addToCart = (product) => {
    const existing = cart.find(item => item.product_id === product._id);
    if (existing) {
      if (existing.quantity >= getStockForProduct(product._id)) {
        toast.error('Stock insuficiente');
        return;
      }
      setCart(cart.map(item => 
        item.product_id === product._id 
          ? { ...item, quantity: item.quantity + 1, total: (item.quantity + 1) * item.price }
          : item
      ));
    } else {
      setCart([...cart, {
        product_id: product._id,
        name: product.name,
        price: product.sale_price,
        quantity: 1,
        total: product.sale_price
      }]);
    }
  };

  const updateCartQuantity = (productId, quantity) => {
    if (quantity <= 0) {
      setCart(cart.filter(item => item.product_id !== productId));
    } else {
      const maxStock = getStockForProduct(productId);
      if (quantity > maxStock) {
        toast.error('Stock insuficiente');
        return;
      }
      setCart(cart.map(item =>
        item.product_id === productId
          ? { ...item, quantity, total: quantity * item.price }
          : item
      ));
    }
  };

  const removeFromCart = (productId) => {
    setCart(cart.filter(item => item.product_id !== productId));
  };

  const subtotal = cart.reduce((sum, item) => sum + item.total, 0);
  const discount = parseFloat(saleForm.discount) || 0;
  const total = subtotal - discount;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (cart.length === 0) {
      toast.error('Agregue productos al carrito');
      return;
    }

    try {
      const validPayments = payments
        .filter((p) => Number(p.amount) > 0)
        .map((p) => ({ method: p.method, amount: Number(p.amount), note: p.note || '' }));

      await api.post('/api/sales', {
        patient_id: saleForm.patient_id || null,
        items: cart,
        subtotal,
        discount,
        tax: 0,
        total,
        payments: validPayments,
        notes: saleForm.notes
      });
      const paidSum = validPayments.reduce((s, p) => s + p.amount, 0);
      if (paidSum < total) {
        toast.success(`Venta registrada. Saldo pendiente Q${(total - paidSum).toFixed(2)} agregado a Cuentas por Cobrar.`);
      } else {
        toast.success('Venta registrada exitosamente');
      }
      setShowSaleDialog(false);
      setCart([]);
      setSaleForm({ patient_id: '', discount: 0, notes: '' });
      setPayments([{ method: 'cash', amount: 0, note: '' }]);
      fetchData();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const formatCurrency = (amount) => {
    return `Q ${(amount || 0).toLocaleString('es-GT', { minimumFractionDigits: 2 })}`;
  };

  const handleDelete = async () => {
    if (!saleToDelete) return;
    try {
      setDeleting(true);
      const { data } = await api.delete(`/api/sales/${saleToDelete._id}`);
      toast.success(`Venta eliminada. Stock restaurado: ${data.stock_restored} unidad(es).`);
      setSaleToDelete(null);
      setDetailSale(null);
      fetchData();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="sales-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Ventas</h1>
          <p className="text-slate-500 mt-1">Punto de venta y registro de transacciones</p>
        </div>
        <div className="flex items-center gap-3">
          <BranchFilter value={branchId} onChange={setBranchId} />
          <Dialog open={showSaleDialog} onOpenChange={(o) => {
            if (o && !cashOpen) {
              toast.error('Debes abrir la caja antes de registrar una venta.');
              return;
            }
            setShowSaleDialog(o);
          }}>
          <DialogTrigger asChild>
            <Button
              className="bg-pine-900 hover:bg-pine-700 disabled:opacity-60 disabled:cursor-not-allowed"
              data-testid="new-sale-btn"
              disabled={!cashOpen}
              title={!cashOpen ? 'Abre la caja para poder registrar ventas' : ''}
            >
              <ShoppingCart className="w-4 h-4 mr-2" /> Nueva Venta
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="font-heading">Nueva Venta</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit}>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Products */}
                <div className="space-y-4">
                  <Label>Productos Disponibles</Label>
                  <div className="grid grid-cols-2 gap-2 max-h-[400px] overflow-y-auto">
                    {products.map((product) => {
                      const stockQty = getStockForProduct(product._id);
                      return (
                        <button
                          key={product._id}
                          type="button"
                          onClick={() => addToCart(product)}
                          disabled={stockQty <= 0}
                          className={`p-3 rounded-lg border text-left transition-colors ${
                            stockQty > 0 
                              ? 'border-slate-200 hover:border-pine-500 hover:bg-pine-50' 
                              : 'border-slate-100 bg-slate-50 opacity-50 cursor-not-allowed'
                          }`}
                          data-testid={`product-btn-${product._id}`}
                        >
                          <p className="font-medium text-sm text-slate-900 truncate">{product.name}</p>
                          <p className="text-xs text-slate-500">{formatCurrency(product.sale_price)}</p>
                          <p className="text-xs text-slate-400 mt-1">Stock: {stockQty}</p>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Cart */}
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Cliente (Opcional)</Label>
                    <Select value={saleForm.patient_id || "none"} onValueChange={(v) => setSaleForm({...saleForm, patient_id: v === "none" ? "" : v})}>
                      <SelectTrigger data-testid="sale-patient">
                        <SelectValue placeholder="Seleccionar cliente" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Sin cliente</SelectItem>
                        {patients.map((p) => (
                          <SelectItem key={p._id} value={p._id}>
                            {p.first_name} {p.last_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="border rounded-lg p-4">
                    <h3 className="font-medium text-slate-900 mb-3">Carrito</h3>
                    {cart.length === 0 ? (
                      <p className="text-sm text-slate-500 text-center py-4">
                        <ShoppingCart className="w-8 h-8 mx-auto mb-2 opacity-30" />
                        Carrito vacío
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {cart.map((item) => (
                          <div key={item.product_id} className="flex items-center justify-between gap-2 p-2 bg-slate-50 rounded">
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium truncate">{item.name}</p>
                              <p className="text-xs text-slate-500">{formatCurrency(item.price)} c/u</p>
                            </div>
                            <div className="flex items-center gap-2">
                              <Input
                                type="number"
                                min="1"
                                value={item.quantity}
                                onChange={(e) => updateCartQuantity(item.product_id, parseInt(e.target.value))}
                                className="w-16 h-8 text-center"
                              />
                              <button
                                type="button"
                                onClick={() => removeFromCart(item.product_id)}
                                className="text-red-500 hover:text-red-700"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                            <p className="font-medium w-20 text-right">{formatCurrency(item.total)}</p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Totals */}
                    <div className="border-t mt-4 pt-4 space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-slate-500">Subtotal</span>
                        <span>{formatCurrency(subtotal)}</span>
                      </div>
                      <div className="flex justify-between text-sm items-center">
                        <span className="text-slate-500">Descuento</span>
                        <Input
                          type="number"
                          min="0"
                          value={saleForm.discount}
                          onChange={(e) => setSaleForm({...saleForm, discount: e.target.value})}
                          className="w-24 h-8 text-right"
                          data-testid="sale-discount"
                        />
                      </div>
                      <div className="flex justify-between font-semibold text-lg">
                        <span>Total</span>
                        <span className="text-pine-700">{formatCurrency(total)}</span>
                      </div>
                    </div>
                  </div>

                  {/* Multi-payment editor */}
                  <PaymentLinesEditor
                    payments={payments}
                    onChange={setPayments}
                    total={total}
                    testIdPrefix="new-sale"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 mt-6 pt-4 border-t">
                <Button type="button" variant="outline" onClick={() => setShowSaleDialog(false)}>
                  Cancelar
                </Button>
                <Button type="submit" className="bg-pine-900 hover:bg-pine-700" data-testid="complete-sale-btn">
                  <Receipt className="w-4 h-4 mr-2" /> Completar Venta
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      {/* Cash Register Bar */}
      <SalesCashBar
        onStateChange={(isOpen) => setCashOpen(isOpen)}
        onCashChange={fetchData}
      />

      {/* Sales History */}
      <Card className="border-slate-200/80">
        <CardHeader>
          <CardTitle className="font-heading text-lg">Historial de Ventas</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="data-table-header">
                <TableHead>Fecha</TableHead>
                <TableHead>Cliente</TableHead>
                <TableHead>Artículos</TableHead>
                <TableHead>Total</TableHead>
                <TableHead>Pagado</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead className="text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sales.map((sale) => (
                <TableRow key={sale._id} className="data-table-row" data-testid={`sale-row-${sale._id}`}>
                  <TableCell>{sale.created_at?.slice(0, 10)}</TableCell>
                  <TableCell>
                    {sale.patient_name ? (
                      <div className="flex items-center gap-2">
                        <User className="w-4 h-4 text-slate-400" />
                        {sale.patient_name}
                      </div>
                    ) : (
                      <span className="text-slate-400">-</span>
                    )}
                  </TableCell>
                  <TableCell>{sale.items?.length || 0} item(s)</TableCell>
                  <TableCell className="font-medium">{formatCurrency(sale.total)}</TableCell>
                  <TableCell>{formatCurrency(sale.amount_paid)}</TableCell>
                  <TableCell>
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      sale.status === 'completada' 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-amber-100 text-amber-800'
                    }`}>
                      {sale.status === 'completada' ? 'Pagado' : 'Pendiente'}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" onClick={() => setDetailSale(sale)} data-testid={`view-sale-${sale._id}`}>
                        <Eye className="w-4 h-4 text-slate-500" />
                      </Button>
                      {isAdmin && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setSaleToDelete(sale)}
                          className="text-slate-400 hover:text-red-500 hover:bg-red-50"
                          data-testid={`delete-sale-${sale._id}`}
                          title="Eliminar venta (solo administrador)"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {sales.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-slate-500">
                    <ShoppingCart className="w-12 h-12 mx-auto mb-2 opacity-30" />
                    <p>No hay ventas registradas</p>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Sale Detail Dialog */}
      <Dialog open={!!detailSale} onOpenChange={(open) => !open && setDetailSale(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-heading flex items-center gap-2">
              <Receipt className="w-5 h-5 text-pine-700" /> Detalle de Venta
            </DialogTitle>
          </DialogHeader>
          {detailSale && (
            <div className="space-y-4" data-testid="sale-detail">
              {/* Header info */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="text-slate-400">Fecha:</span>
                  <span className="ml-2 font-medium">{detailSale.created_at?.slice(0, 10)}</span>
                </div>
                <div>
                  <span className="text-slate-400">Estado:</span>
                  <span className={`ml-2 px-2 py-0.5 rounded-full text-xs font-medium ${
                    detailSale.status === 'completada' ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'
                  }`}>{detailSale.status === 'completada' ? 'Pagado' : 'Pendiente'}</span>
                </div>
                <div>
                  <span className="text-slate-400">Cliente:</span>
                  <span className="ml-2 font-medium">{detailSale.patient_name || 'Consumidor final'}</span>
                </div>
                <div>
                  <span className="text-slate-400">Vendedor:</span>
                  <span className="ml-2 font-medium">{detailSale.seller_name || '-'}</span>
                </div>
                <div>
                  <span className="text-slate-400">Metodo:</span>
                  <span className="ml-2 font-medium">
                    {detailSale.payments && detailSale.payments.length > 1
                      ? `${detailSale.payments.length} pagos`
                      : paymentMethodLabel(detailSale.payment_method)}
                  </span>
                </div>
              </div>

              {/* Items */}
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Articulos</p>
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-slate-50 text-xs text-slate-500">
                        <th className="text-left p-2.5 font-medium">Producto</th>
                        <th className="text-center p-2.5 font-medium">Cant</th>
                        <th className="text-right p-2.5 font-medium">Precio</th>
                        <th className="text-right p-2.5 font-medium">Subtotal</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(detailSale.items || []).map((item, idx) => (
                        <tr key={item.product_id || `item-${idx}`} className="border-t border-slate-100">
                          <td className="p-2.5 font-medium text-slate-800">{item.name || 'Producto'}</td>
                          <td className="p-2.5 text-center text-slate-600">{item.quantity || 1}</td>
                          <td className="p-2.5 text-right text-slate-600">{formatCurrency(item.unit_price || item.price || 0)}</td>
                          <td className="p-2.5 text-right font-medium">{formatCurrency(item.subtotal || (item.unit_price || item.price || 0) * (item.quantity || 1))}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Payments history */}
              {detailSale.payments && detailSale.payments.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Historial de pagos</p>
                  <div className="border rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-slate-50 text-xs text-slate-500">
                          <th className="text-left p-2.5 font-medium">Fecha</th>
                          <th className="text-left p-2.5 font-medium">Metodo</th>
                          <th className="text-right p-2.5 font-medium">Monto</th>
                          <th className="text-left p-2.5 font-medium">Nota</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detailSale.payments.map((p, idx) => (
                          <tr key={idx} className="border-t border-slate-100">
                            <td className="p-2.5 text-slate-600">{(p.created_at || '').slice(0, 10)}</td>
                            <td className="p-2.5 text-slate-800">{paymentMethodLabel(p.method)}</td>
                            <td className="p-2.5 text-right font-medium">{formatCurrency(p.amount)}</td>
                            <td className="p-2.5 text-slate-500 text-xs">{p.note || '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Totals */}
              <div className="border-t pt-3 space-y-1.5 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-500">Subtotal</span>
                  <span>{formatCurrency(detailSale.subtotal)}</span>
                </div>
                {detailSale.discount > 0 && (
                  <div className="flex justify-between text-red-600">
                    <span>Descuento</span>
                    <span>-{formatCurrency(detailSale.discount)}</span>
                  </div>
                )}
                <div className="flex justify-between font-bold text-base pt-1 border-t">
                  <span>Total</span>
                  <span>{formatCurrency(detailSale.total)}</span>
                </div>
                <div className="flex justify-between text-slate-500">
                  <span>Pagado</span>
                  <span>{formatCurrency(detailSale.amount_paid)}</span>
                </div>
                {detailSale.balance > 0 && (
                  <div className="flex justify-between text-amber-600 font-medium">
                    <span>Saldo pendiente</span>
                    <span>{formatCurrency(detailSale.balance)}</span>
                  </div>
                )}
              </div>

              {detailSale.balance > 0 && (
                <Button
                  type="button"
                  className="w-full bg-emerald-600 hover:bg-emerald-700"
                  onClick={() => setPaymentSale(detailSale)}
                  data-testid="detail-add-payment-btn"
                >
                  <HandCoins className="w-4 h-4 mr-2" /> Registrar abono
                </Button>
              )}

              {isAdmin && (
                <Button
                  type="button"
                  variant="outline"
                  className="w-full text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700"
                  onClick={() => setSaleToDelete(detailSale)}
                  data-testid="detail-delete-btn"
                >
                  <Trash2 className="w-4 h-4 mr-2" /> Eliminar venta
                </Button>
              )}

              {detailSale.notes && (
                <div className="text-sm">
                  <span className="text-slate-400">Notas:</span>
                  <p className="mt-1 text-slate-600">{detailSale.notes}</p>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Add Payment Dialog */}
      <AddPaymentDialog
        sale={paymentSale}
        open={!!paymentSale}
        onOpenChange={(o) => !o && setPaymentSale(null)}
        onSuccess={async () => {
          setPaymentSale(null);
          // Refresh detail modal + list
          if (detailSale?._id) {
            try {
              const { data } = await api.get(`/api/sales/${detailSale._id}`);
              setDetailSale(data);
            } catch {} // eslint-disable-line no-empty
          }
          fetchData();
        }}
      />

      {/* Delete confirmation (admin only) */}
      <AlertDialog open={!!saleToDelete} onOpenChange={(o) => !o && setSaleToDelete(null)}>
        <AlertDialogContent data-testid="delete-sale-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-red-600 flex items-center gap-2">
              <Trash2 className="w-5 h-5" /> Eliminar venta
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2 text-sm text-slate-600">
                <p>Esta accion es <strong>irreversible</strong>. Al eliminar la venta:</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>Se restaurara el stock de los productos vendidos.</li>
                  <li>Se borraran los movimientos de inventario asociados.</li>
                  <li>Se borraran las entradas de finanzas (venta y abonos).</li>
                  <li>Se registrara el evento en el log de auditoria.</li>
                </ul>
                {saleToDelete && (
                  <div className="mt-3 p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                    <p><span className="text-slate-500">Cliente:</span> <strong>{saleToDelete.patient_name || 'Consumidor final'}</strong></p>
                    <p><span className="text-slate-500">Total:</span> <strong>{formatCurrency(saleToDelete.total)}</strong></p>
                    <p><span className="text-slate-500">Pagado:</span> <strong>{formatCurrency(saleToDelete.amount_paid)}</strong></p>
                    <p><span className="text-slate-500">Fecha:</span> <strong>{(saleToDelete.created_at || '').slice(0, 10)}</strong></p>
                  </div>
                )}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting} data-testid="delete-cancel">Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleting}
              className="bg-red-600 hover:bg-red-700"
              data-testid="delete-confirm"
            >
              {deleting ? 'Eliminando...' : 'Si, eliminar venta'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
