import React, { useState, useEffect } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Textarea } from '../components/ui/textarea';
import { 
  Plus, ShoppingCart, Trash2, User, CreditCard, 
  Banknote, Smartphone, Receipt
} from 'lucide-react';
import { toast } from 'sonner';

export default function SalesPage() {
  const [sales, setSales] = useState([]);
  const [patients, setPatients] = useState([]);
  const [products, setProducts] = useState([]);
  const [stock, setStock] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showSaleDialog, setShowSaleDialog] = useState(false);

  const [cart, setCart] = useState([]);
  const [saleForm, setSaleForm] = useState({
    patient_id: '',
    payment_method: 'cash',
    discount: 0,
    amount_paid: 0,
    notes: ''
  });

  const paymentMethods = [
    { value: 'cash', label: 'Efectivo', icon: Banknote },
    { value: 'card', label: 'Tarjeta', icon: CreditCard },
    { value: 'transfer', label: 'Transferencia', icon: Smartphone }
  ];

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [salesRes, patientsRes, productsRes, stockRes] = await Promise.all([
        api.get('/api/sales'),
        api.get('/api/patients', { params: { limit: 200 } }),
        api.get('/api/inventory/products'),
        api.get('/api/inventory/stock')
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
      await api.post('/api/sales', {
        patient_id: saleForm.patient_id || null,
        items: cart,
        subtotal,
        discount,
        tax: 0,
        total,
        payment_method: saleForm.payment_method,
        amount_paid: parseFloat(saleForm.amount_paid) || total,
        notes: saleForm.notes
      });
      toast.success('Venta registrada exitosamente');
      setShowSaleDialog(false);
      setCart([]);
      setSaleForm({ patient_id: '', payment_method: 'cash', discount: 0, amount_paid: 0, notes: '' });
      fetchData();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const formatCurrency = (amount) => {
    return `Q ${(amount || 0).toLocaleString('es-GT', { minimumFractionDigits: 2 })}`;
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
        <Dialog open={showSaleDialog} onOpenChange={setShowSaleDialog}>
          <DialogTrigger asChild>
            <Button className="bg-pine-900 hover:bg-pine-700" data-testid="new-sale-btn">
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
                    <Select value={saleForm.patient_id} onValueChange={(v) => setSaleForm({...saleForm, patient_id: v})}>
                      <SelectTrigger data-testid="sale-patient">
                        <SelectValue placeholder="Seleccionar cliente" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="">Sin cliente</SelectItem>
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

                  {/* Payment */}
                  <div className="space-y-2">
                    <Label>Método de Pago</Label>
                    <div className="flex gap-2">
                      {paymentMethods.map((pm) => (
                        <button
                          key={pm.value}
                          type="button"
                          onClick={() => setSaleForm({...saleForm, payment_method: pm.value})}
                          className={`flex-1 p-3 rounded-lg border flex items-center justify-center gap-2 transition-colors ${
                            saleForm.payment_method === pm.value
                              ? 'border-pine-500 bg-pine-50 text-pine-700'
                              : 'border-slate-200 hover:border-slate-300'
                          }`}
                          data-testid={`payment-${pm.value}`}
                        >
                          <pm.icon className="w-4 h-4" />
                          <span className="text-sm font-medium">{pm.label}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Monto Pagado</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={saleForm.amount_paid || total}
                      onChange={(e) => setSaleForm({...saleForm, amount_paid: e.target.value})}
                      data-testid="amount-paid"
                    />
                    {parseFloat(saleForm.amount_paid || total) < total && (
                      <p className="text-sm text-amber-600">
                        Saldo pendiente: {formatCurrency(total - parseFloat(saleForm.amount_paid || 0))}
                      </p>
                    )}
                  </div>
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
                      sale.status === 'completed' 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-amber-100 text-amber-800'
                    }`}>
                      {sale.status === 'completed' ? 'Pagado' : 'Pendiente'}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
              {sales.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-slate-500">
                    <ShoppingCart className="w-12 h-12 mx-auto mb-2 opacity-30" />
                    <p>No hay ventas registradas</p>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
