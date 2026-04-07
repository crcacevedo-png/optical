import React, { useState, useEffect } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Badge } from '../components/ui/badge';
import { 
  Plus, Search, Package, AlertTriangle, ArrowUpCircle, 
  ArrowDownCircle, Glasses, Droplets, Box
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

  const [productForm, setProductForm] = useState({
    name: '', sku: '', category: '', brand: '', description: '',
    cost_price: '', sale_price: '', min_stock: 5
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
        min_stock: parseInt(productForm.min_stock)
      });
      toast.success('Producto creado exitosamente');
      setShowProductDialog(false);
      setProductForm({ name: '', sku: '', category: '', brand: '', description: '', cost_price: '', sale_price: '', min_stock: 5 });
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

  const formatCurrency = (amount) => {
    return `Q ${(amount || 0).toLocaleString('es-GT', { minimumFractionDigits: 2 })}`;
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
                      min="1"
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
                <div className="grid grid-cols-3 gap-4">
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
                    <Label>Stock Mín</Label>
                    <Input
                      type="number"
                      value={productForm.min_stock}
                      onChange={(e) => setProductForm({...productForm, min_stock: e.target.value})}
                      data-testid="product-min-stock"
                    />
                  </div>
                </div>
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
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="py-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-amber-800">
                  {alerts.length} producto{alerts.length !== 1 ? 's' : ''} con stock bajo
                </p>
                <p className="text-sm text-amber-700 mt-1">
                  {alerts.slice(0, 3).map(a => a.product_name).join(', ')}
                  {alerts.length > 3 && ` y ${alerts.length - 3} más`}
                </p>
              </div>
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
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredProducts.map((product) => {
                const currentStock = getStockForProduct(product._id);
                const isLowStock = currentStock <= (product.min_stock || 5);
                return (
                  <TableRow key={product._id} className="data-table-row" data-testid={`product-row-${product._id}`}>
                    <TableCell>
                      <div>
                        <p className="font-medium text-slate-900">{product.name}</p>
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
                  </TableRow>
                );
              })}
              {filteredProducts.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-slate-500">
                    <Package className="w-12 h-12 mx-auto mb-2 opacity-30" />
                    <p>No se encontraron productos</p>
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
