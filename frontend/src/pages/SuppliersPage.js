import React, { useState, useEffect, useCallback } from 'react';
import { api, useAuth, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription
} from '../components/ui/dialog';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from '../components/ui/table';
import { toast } from 'sonner';
import {
  Plus, Search, Truck, Phone, Mail, MapPin, Edit, Trash2, Building2, FileText, Tag
} from 'lucide-react';

const CATEGORY_OPTIONS = [
  'Armazones', 'Lentes Oftálmicos', 'Lentes de Contacto', 'Soluciones',
  'Lentes de Sol', 'Accesorios', 'Equipos', 'Medicamentos', 'Otro'
];

const emptyForm = {
  name: '', contact_name: '', phone: '', email: '',
  address: '', city: '', country: 'Guatemala', tax_id: '',
  categories: [], notes: ''
};

export default function SuppliersPage() {
  const { user } = useAuth();
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [supplierToDelete, setSupplierToDelete] = useState(null);

  const isAdmin = user?.role === 'admin';

  const fetchSuppliers = useCallback(async () => {
    try {
      const params = search ? { search } : {};
      const res = await api.get('/api/suppliers', { params });
      setSuppliers(res.data);
    } catch (err) {
      toast.error('Error al cargar proveedores');
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    fetchSuppliers();
  }, [fetchSuppliers]);

  const openNew = () => {
    setEditing(null);
    setForm(emptyForm);
    setDialogOpen(true);
  };

  const openEdit = (supplier) => {
    setEditing(supplier);
    setForm({
      name: supplier.name || '',
      contact_name: supplier.contact_name || '',
      phone: supplier.phone || '',
      email: supplier.email || '',
      address: supplier.address || '',
      city: supplier.city || '',
      country: supplier.country || 'Guatemala',
      tax_id: supplier.tax_id || '',
      categories: supplier.categories || [],
      notes: supplier.notes || ''
    });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast.error('El nombre del proveedor es obligatorio');
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/api/suppliers/${editing._id}`, form);
        toast.success('Proveedor actualizado');
      } else {
        await api.post('/api/suppliers', form);
        toast.success('Proveedor creado');
      }
      setDialogOpen(false);
      fetchSuppliers();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!supplierToDelete) return;
    try {
      await api.delete(`/api/suppliers/${supplierToDelete._id}`);
      toast.success('Proveedor eliminado');
      setDeleteDialogOpen(false);
      setSupplierToDelete(null);
      fetchSuppliers();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const toggleCategory = (cat) => {
    setForm(prev => ({
      ...prev,
      categories: prev.categories.includes(cat)
        ? prev.categories.filter(c => c !== cat)
        : [...prev.categories, cat]
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="suppliers-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Proveedores</h1>
          <p className="text-slate-500 mt-1">Gestión de proveedores de productos</p>
        </div>
        <Button onClick={openNew} className="bg-pine-900 hover:bg-pine-800" data-testid="new-supplier-btn">
          <Plus className="w-4 h-4 mr-2" /> Nuevo Proveedor
        </Button>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <Input
          placeholder="Buscar proveedor..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10"
          data-testid="supplier-search"
        />
      </div>

      {/* Table */}
      <Card className="border-slate-200/80">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Proveedor</TableHead>
                <TableHead className="hidden md:table-cell">Contacto</TableHead>
                <TableHead className="hidden md:table-cell">Teléfono</TableHead>
                <TableHead className="hidden lg:table-cell">Categorías</TableHead>
                <TableHead className="text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {suppliers.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-12 text-slate-500">
                    <Truck className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p className="font-medium">Sin proveedores</p>
                    <p className="text-sm mt-1">Agrega tu primer proveedor</p>
                  </TableCell>
                </TableRow>
              ) : (
                suppliers.map(s => (
                  <TableRow key={s._id} data-testid={`supplier-row-${s._id}`}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-lg bg-pine-50 flex items-center justify-center">
                          <Truck className="w-4 h-4 text-pine-700" />
                        </div>
                        <div>
                          <p className="font-medium text-slate-900">{s.name}</p>
                          {s.email && (
                            <p className="text-xs text-slate-500 flex items-center gap-1">
                              <Mail className="w-3 h-3" /> {s.email}
                            </p>
                          )}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-slate-600">{s.contact_name || '-'}</TableCell>
                    <TableCell className="hidden md:table-cell text-slate-600">{s.phone || '-'}</TableCell>
                    <TableCell className="hidden lg:table-cell">
                      <div className="flex flex-wrap gap-1">
                        {(s.categories || []).slice(0, 3).map(c => (
                          <Badge key={c} variant="secondary" className="text-xs">{c}</Badge>
                        ))}
                        {(s.categories || []).length > 3 && (
                          <Badge variant="outline" className="text-xs">+{s.categories.length - 3}</Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" onClick={() => openEdit(s)} data-testid={`edit-supplier-${s._id}`}>
                          <Edit className="w-4 h-4 text-slate-500" />
                        </Button>
                        {isAdmin && (
                          <Button variant="ghost" size="icon" onClick={() => { setSupplierToDelete(s); setDeleteDialogOpen(true); }} data-testid={`delete-supplier-${s._id}`}>
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-heading">{editing ? 'Editar Proveedor' : 'Nuevo Proveedor'}</DialogTitle>
            <DialogDescription>
              {editing ? 'Modifica los datos del proveedor' : 'Ingresa los datos del nuevo proveedor'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5 sm:col-span-2">
                <Label>Nombre del Proveedor *</Label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm({...form, name: e.target.value})}
                  placeholder="Distribuidora Óptica SA"
                  data-testid="supplier-name-input"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Persona de Contacto</Label>
                <Input
                  value={form.contact_name}
                  onChange={(e) => setForm({...form, contact_name: e.target.value})}
                  placeholder="Juan Pérez"
                  data-testid="supplier-contact-input"
                />
              </div>
              <div className="space-y-1.5">
                <Label>NIT</Label>
                <Input
                  value={form.tax_id}
                  onChange={(e) => setForm({...form, tax_id: e.target.value})}
                  placeholder="123456-7"
                  data-testid="supplier-taxid-input"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Teléfono</Label>
                <Input
                  value={form.phone}
                  onChange={(e) => setForm({...form, phone: e.target.value})}
                  placeholder="+502 1234-5678"
                  data-testid="supplier-phone-input"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Email</Label>
                <Input
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({...form, email: e.target.value})}
                  placeholder="proveedor@empresa.com"
                  data-testid="supplier-email-input"
                />
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <Label>Dirección</Label>
                <Input
                  value={form.address}
                  onChange={(e) => setForm({...form, address: e.target.value})}
                  placeholder="Zona 10, Ciudad de Guatemala"
                  data-testid="supplier-address-input"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Ciudad</Label>
                <Input
                  value={form.city}
                  onChange={(e) => setForm({...form, city: e.target.value})}
                  placeholder="Guatemala"
                  data-testid="supplier-city-input"
                />
              </div>
              <div className="space-y-1.5">
                <Label>País</Label>
                <Input
                  value={form.country}
                  onChange={(e) => setForm({...form, country: e.target.value})}
                  data-testid="supplier-country-input"
                />
              </div>
            </div>

            {/* Categories */}
            <div className="space-y-1.5">
              <Label>Categorías de Productos</Label>
              <div className="flex flex-wrap gap-2" data-testid="supplier-categories">
                {CATEGORY_OPTIONS.map(cat => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => toggleCategory(cat)}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                      form.categories.includes(cat)
                        ? 'bg-pine-900 text-white border-pine-900'
                        : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'
                    }`}
                    data-testid={`supplier-cat-${cat.toLowerCase().replace(/\s/g, '-')}`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>Notas</Label>
              <Textarea
                value={form.notes}
                onChange={(e) => setForm({...form, notes: e.target.value})}
                placeholder="Observaciones adicionales..."
                rows={3}
                data-testid="supplier-notes-input"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} data-testid="supplier-cancel-btn">Cancelar</Button>
            <Button onClick={handleSave} disabled={saving} className="bg-pine-900 hover:bg-pine-800" data-testid="supplier-save-btn">
              {saving ? 'Guardando...' : editing ? 'Actualizar' : 'Crear Proveedor'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-heading">Eliminar Proveedor</DialogTitle>
            <DialogDescription>
              ¿Estás seguro de eliminar a <strong>{supplierToDelete?.name}</strong>? Esta acción no se puede deshacer.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)} data-testid="supplier-delete-cancel-btn">Cancelar</Button>
            <Button variant="destructive" onClick={handleDelete} data-testid="supplier-delete-confirm-btn">Eliminar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
