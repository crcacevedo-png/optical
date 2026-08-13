import React, { useState, useEffect } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { 
  Plus, Search, Package, AlertTriangle, ArrowUpCircle, 
  ArrowDownCircle, Glasses, Droplets, Box, Edit, Check
} from 'lucide-react';
import { toast } from 'sonner';
import { BranchFilter } from '../components/BranchFilter';

export default function InventoryPage() {
  const [products, setProducts] = useState([]);
  const [stock, setStock] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [branches, setBranches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [branchId, setBranchId] = useState('');
  const [showProductDialog, setShowProductDialog] = useState(false);
  const [showMovementDialog, setShowMovementDialog] = useState(false);
  const [showAddStockDialog, setShowAddStockDialog] = useState(false);
  const [addStockForm, setAddStockForm] = useState({ quantity: '', notes: '' });
  const [addStockProduct, setAddStockProduct] = useState(null);
  const [editingMinStock, setEditingMinStock] = useState(null);
  const [minStockValue, setMinStockValue] = useState('');

  const [productForm, setProductForm] = useState({
    name: '', sku: '', category: '', brand: '', description: '',
    cost_price: '', sale_price: '', min_stock: 1, initial_stock: 0, is_external_supplier: false
  });

  const [movementForm, setMovementForm] = useState({
    product_id: '', branch_id: '', type: 'entrada', quantity: '', notes: ''
  });

  const categories = [
    { value: 'armazones', label: 'Armazones', icon: Glasses },
    { value: 'lentes', label: 'Lentes', icon: Package },
    { value: 'contactos', label: 'Lentes de Contacto', icon: Droplets },
    { value: 'accesorios', label: 'Accesorios', icon: Box }
  ];

  useEffect(() => {
    fetchData();
  }, [branchId]);

  const fetchData = async () => {
    try {
      const params = branchId ? { branch_id: branchId } : {};
      const [productsRes, stockRes, alertsRes, branchesRes] = await Promise.all([
        api.get('/api/inventory/products'),
        api.get('/api/inventory/stock', { params }),
        api.get('/api/inventory/alerts', { params }),
        api.get('/api/branches')
      ]);
      setProducts(productsRes.data || []);
      setStock(stockRes.data || []);
      setAlerts(alertsRes.data || []);
      setBranches(branchesRes.data || []);
    } catch (error) {
      console.error('Error fetching inventory:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleProductSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/api/inventory/products', {
        ...productForm,
        cost_price: parseFloat(productForm.cost_price),
        sale_price: parseFloat(productForm.sale_price),
        min_stock: productForm.is_external_supplier ? 0 : parseInt(productForm.min_stock),
        initial_stock: parseInt(productForm.initial_stock) || 0,
        is_external_supplier: Boolean(productForm.is_external_supplier),
      });
      toast.success('Producto creado exitosamente');
      setShowProductDialog(false);
      setProductForm({ name: '', sku: '', category: '', brand: '', description: '', cost_price: '', sale_price: '', min_stock: 1, initial_stock: 0, is_external_supplier: false });
      fetchData();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const handleMovementSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/api/inventory/movement', {
        ...movementForm,
        quantity: parseInt(movementForm.quantity)
      });
      toast.success('Movimiento registrado');
      setShowMovementDialog(false);
      setMovementForm({ product_id: '', branch_id: '', type: 'in', quantity: '', notes: '' });
      fetchData();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const openAddStock = (product) => {
    setAddStockProduct(product);
    setAddStockForm({ quantity: '', notes: '' });
    setShowAddStockDialog(true);
  };

  const handleAddStock = async (e) => {
    e.preventDefault();
    try {
      await api.post('/api/inventory/movement', {
        product_id: addStockProduct._id,
        branch_id: branchId || '',
        type: 'entrada',
        quantity: parseInt(addStockForm.quantity),
        notes: addStockForm.notes || `Ingreso de ${addStockForm.quantity} unidades`
      });
      toast.success(`${addStockForm.quantity} unidades agregadas a ${addStockProduct.name}`);
      setShowAddStockDialog(false);
      fetchData();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail) || 'Error al agregar stock');
    }
  };

  const formatCurrency = (amount) => {
    return `Q ${(amount || 0).toLocaleString('es-GT', { minimumFractionDigits: 2 })}`;
  };

  const handleSaveMinStock = async (productId) => {
    const val = parseInt(minStockValue);
    if (isNaN(val) || val < 0) {
      toast.error('El stock minimo debe ser mayor o igual a 0');
      return;
    }
    try {
      await api.put(`/api/inventory/products/${productId}`, { min_stock: val });
      toast.success('Stock minimo actualizado');
      setEditingMinStock(null);
      fetchData();
    } catch (error) {
      toast.error('Error al actualizar');
    }
  };

  const filteredProducts = products.filter(p => {
    const matchesSearch = p.name.toLowerCase().includes(search.toLowerCase()) || 
                          p.sku.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = categoryFilter === 'all' || p.category === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  const getStockForProduct = (productId) => {
    return stock.find(s => s.product_id === productId)?.quantity || 0;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="inventory-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Inventario</h1>
          <p className="text-slate-500 mt-1">Gestiona productos y stock</p>
        </div>
        <div className="flex gap-2">
          <BranchFilter value={branchId} onChange={setBranchId} />
          <Dialog open={showMovementDialog} onOpenChange={setShowMovementDialog}>
            <DialogTrigger asChild>
              <Button variant="outline" data-testid="add-movement-btn">
                <ArrowUpCircle className="w-4 h-4 mr-2" /> Movimiento
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle className="font-heading">Registrar Movimiento</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleMovementSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label>Producto *</Label>
                  <Select value={movementForm.product_id} onValueChange={(v) => setMovementForm({...movementForm, product_id: v})}>
                    <SelectTrigger data-testid="movement-product">
                      <SelectValue placeholder="Seleccionar producto" />
                    </SelectTrigger>
                    <SelectContent>
                      {products.map((p) => (
                        <SelectItem key={p._id} value={p._id}>{p.name} ({p.sku})</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Sucursal *</Label>
                  <Select value={movementForm.branch_id} onValueChange={(v) => setMovementForm({...movementForm, branch_id: v})}>
                    <SelectTrigger data-testid="movement-branch">
                      <SelectValue placeholder="Seleccionar sucursal" />
                    </SelectTrigger>
                    <SelectContent>
                      {branches.map((b) => (
                        <SelectItem key={b._id} value={b._id}>{b.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Tipo *</Label>
                    <Select value={movementForm.type} onValueChange={(v) => setMovementForm({...movementForm, type: v})}>
                      <SelectTrigger data-testid="movement-type">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="entrada">Entrada</SelectItem>
                        <SelectItem value="salida">Salida</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Cantidad *</Label>
                    <Input
                      type="number"
                      min="0"
                      value={movementForm.quantity}
                      onChange={(e) => setMovementForm({...movementForm, quantity: e.target.value})}
                      required
                      data-testid="movement-quantity"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Notas</Label>
                  <Input
                    value={movementForm.notes}
                    onChange={(e) => setMovementForm({...movementForm, notes: e.target.value})}
                    placeholder="Ej: Compra a proveedor"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-4">
                  <Button type="button" variant="outline" onClick={() => setShowMovementDialog(false)}>Cancelar</Button>
                  <Button type="submit" className="bg-pine-900 hover:bg-pine-700" data-testid="save-movement">Registrar</Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
          
          <Dialog open={showProductDialog} onOpenChange={setShowProductDialog}>
            <DialogTrigger asChild>
              <Button className="bg-pine-900 hover:bg-pine-700" data-testid="add-product-btn">
                <Plus className="w-4 h-4 mr-2" /> Nuevo Producto
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle className="font-heading">Nuevo Producto</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleProductSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Nombre *</Label>
                    <Input
                      value={productForm.name}
                      onChange={(e) => setProductForm({...productForm, name: e.target.value})}
                      required
                      data-testid="product-name"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>SKU *</Label>
                    <Input
                      value={productForm.sku}
                      onChange={(e) => setProductForm({...productForm, sku: e.target.value})}
                      required
                      data-testid="product-sku"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Categoría *</Label>
                    <Select value={productForm.category} onValueChange={(v) => setProductForm({...productForm, category: v})}>
                      <SelectTrigger data-testid="product-category">
                        <SelectValue placeholder="Seleccionar" />
                      </SelectTrigger>
                      <SelectContent>
                        {categories.map((c) => (
                          <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Marca</Label>
                    <Input
                      value={productForm.brand}
                      onChange={(e) => setProductForm({...productForm, brand: e.target.value})}
                      data-testid="product-brand"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="space-y-2">
                    <Label>Costo *</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={productForm.cost_price}
                      onChange={(e) => setProductForm({...productForm, cost_price: e.target.value})}
                      required
                      data-testid="product-cost"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Precio Venta *</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={productForm.sale_price}
                      onChange={(e) => setProductForm({...productForm, sale_price: e.target.value})}
                      required
                      data-testid="product-price"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Cantidad Inicial</Label>
                    <Input
                      type="number"
                      min="0"
                      value={productForm.initial_stock}
                      onChange={(e) => setProductForm({...productForm, initial_stock: e.target.value})}
                      data-testid="product-initial-stock"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Stock Min</Label>
                    <Input
                      type="number"
                      min="0"
                      value={productForm.min_stock}
                      onChange={(e) => setProductForm({...productForm, min_stock: e.target.value})}
                      disabled={productForm.is_external_supplier}
                      data-testid="product-min-stock"
                    />
                  </div>
                </div>
                <label className="flex items-start gap-3 p-3 rounded-lg border border-slate-200 bg-slate-50 cursor-pointer hover:border-pine-400 transition-colors" data-testid="product-external-supplier-wrap">
                  <input
                    type="checkbox"
                    className="mt-0.5 w-4 h-4 accent-pine-900"
                    checked={Boolean(productForm.is_external_supplier)}
                    onChange={(e) => setProductForm({...productForm, is_external_supplier: e.target.checked, min_stock: e.target.checked ? 0 : productForm.min_stock})}
                    data-testid="product-external-supplier"
                  />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-800">Proveedor externo</p>
                    <p className="text-xs text-slate-500 mt-0.5">Marca este producto como fabricado o pedido a laboratorio externo (ej. lentes graduados). No se aplicara stock minimo ni aparecera en alertas.</p>
                  </div>
                </label>
                <div className="flex justify-end gap-2 pt-4">
                  <Button type="button" variant="outline" onClick={() => setShowProductDialog(false)}>Cancelar</Button>
                  <Button type="submit" className="bg-pine-900 hover:bg-pine-700" data-testid="save-product">Guardar</Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Alerts */}
      {alerts.length > 0 && (
        <Card className="border-amber-200 bg-amber-50" data-testid="inventory-alerts">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2 text-amber-800">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              {alerts.length} producto{alerts.length !== 1 ? 's' : ''} con stock bajo
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {alerts.map((a) => (
                <div key={a.product_id} className="flex items-center justify-between p-2 bg-white rounded-lg border border-amber-200" data-testid={`alert-${a.product_id}`}>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-900 truncate">{a.product_name}</p>
                    <p className="text-xs text-slate-500">{a.sku}</p>
                  </div>
                  <div className="text-right ml-3 flex-shrink-0">
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-800">
                      {a.current_stock} / {a.min_stock}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <Input
            placeholder="Buscar producto..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
            data-testid="inventory-search"
          />
        </div>
        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-[180px]" data-testid="category-filter">
            <SelectValue placeholder="Categoría" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas las categorías</SelectItem>
            {categories.map((c) => (
              <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Products Table */}
      <Card className="border-slate-200/80">
        <CardHeader>
          <CardTitle className="font-heading text-lg">Productos ({filteredProducts.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="data-table-header">
                <TableHead>Producto</TableHead>
                <TableHead>SKU</TableHead>
                <TableHead>Categoría</TableHead>
                <TableHead>Costo</TableHead>
                <TableHead>Precio</TableHead>
                <TableHead className="text-center">Stock</TableHead>
                <TableHead className="text-center">Min</TableHead>
                <TableHead className="text-center">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredProducts.map((product) => {
                const currentStock = getStockForProduct(product._id);
                const isLowStock = currentStock <= (product.min_stock ?? 0);
                return (
                  <TableRow key={product._id} className="data-table-row" data-testid={`product-row-${product._id}`}>
                    <TableCell>
                      <div>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <p className="font-medium text-slate-900">{product.name}</p>
                          {product.is_external_supplier && (
                            <Badge variant="outline" className="bg-violet-50 text-violet-700 border-violet-200 text-[10px] px-1.5 py-0" data-testid={`ext-badge-${product._id}`}>
                              Proveedor externo
                            </Badge>
                          )}
                        </div>
                        {product.brand && <p className="text-sm text-slate-500">{product.brand}</p>}
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-sm">{product.sku}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="capitalize">
                        {product.category}
                      </Badge>
                    </TableCell>
                    <TableCell>{formatCurrency(product.cost_price)}</TableCell>
                    <TableCell className="font-medium">{formatCurrency(product.sale_price)}</TableCell>
                    <TableCell className="text-center">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium ${
                        isLowStock ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
                      }`}>
                        {currentStock}
                      </span>
                    </TableCell>
                    <TableCell className="text-center">
                      {editingMinStock === product._id ? (
                        <div className="flex items-center gap-1 justify-center">
                          <Input
                            type="number"
                            min="0"
                            className="w-16 h-7 text-center text-xs px-1"
                            value={minStockValue}
                            onChange={(e) => setMinStockValue(e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter') handleSaveMinStock(product._id); if (e.key === 'Escape') setEditingMinStock(null); }}
                            autoFocus
                            data-testid={`min-stock-input-${product._id}`}
                          />
                          <button onClick={() => handleSaveMinStock(product._id)} className="p-0.5 rounded hover:bg-green-100 text-green-600" data-testid={`min-stock-save-${product._id}`}>
                            <Check className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ) : (
                        <button
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs text-slate-600 hover:bg-slate-100 transition-colors"
                          onClick={() => { setEditingMinStock(product._id); setMinStockValue(String(product.min_stock || 1)); }}
                          data-testid={`min-stock-edit-${product._id}`}
                        >
                          {product.min_stock || 1}
                          <Edit className="w-3 h-3 text-slate-400" />
                        </button>
                      )}
                    </TableCell>
                    <TableCell className="text-center">
                      <Button size="sm" variant="outline" className="text-pine-700 border-pine-200 hover:bg-pine-50" onClick={() => openAddStock(product)} data-testid={`add-stock-${product._id}`}>
                        <Plus className="w-3.5 h-3.5 mr-1" /> Agregar
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
              {filteredProducts.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-8 text-slate-500">
                    <Package className="w-12 h-12 mx-auto mb-2 opacity-30" />
                    <p>No se encontraron productos</p>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Add Stock Dialog */}
      <Dialog open={showAddStockDialog} onOpenChange={setShowAddStockDialog}>
        <DialogContent className="max-w-sm" data-testid="add-stock-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ArrowUpCircle className="w-5 h-5 text-green-600" /> Agregar Producto
            </DialogTitle>
          </DialogHeader>
          {addStockProduct && (
            <form onSubmit={handleAddStock} className="space-y-4">
              <div className="p-3 bg-slate-50 rounded-lg">
                <p className="font-medium text-slate-900">{addStockProduct.name}</p>
                <p className="text-sm text-slate-500">{addStockProduct.sku} — Stock actual: {getStockForProduct(addStockProduct._id)}</p>
              </div>
              <div className="space-y-2">
                <Label>Cantidad a agregar *</Label>
                <Input
                  type="number"
                  min="0"
                  value={addStockForm.quantity}
                  onChange={(e) => setAddStockForm({...addStockForm, quantity: e.target.value})}
                  required
                  autoFocus
                  placeholder="Ej: 10"
                  data-testid="add-stock-quantity"
                />
              </div>
              <div className="space-y-2">
                <Label>Nota (opcional)</Label>
                <Input
                  value={addStockForm.notes}
                  onChange={(e) => setAddStockForm({...addStockForm, notes: e.target.value})}
                  placeholder="Ej: Compra proveedor"
                  data-testid="add-stock-notes"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => setShowAddStockDialog(false)}>Cancelar</Button>
                <Button type="submit" className="bg-pine-900 hover:bg-pine-700" disabled={!addStockForm.quantity} data-testid="save-add-stock">
                  <Plus className="w-4 h-4 mr-1" /> Agregar
                </Button>
              </div>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
