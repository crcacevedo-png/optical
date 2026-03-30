import React, { useState, useEffect } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Plus, Building2, MapPin, Phone, Mail } from 'lucide-react';
import { toast } from 'sonner';

export default function BranchesPage() {
  const { isAdmin } = useAuth();
  const [branches, setBranches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    address: '',
    phone: '',
    email: ''
  });

  useEffect(() => {
    fetchBranches();
  }, []);

  const fetchBranches = async () => {
    try {
      const { data } = await api.get('/api/branches');
      setBranches(data || []);
    } catch (error) {
      console.error('Error fetching branches:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/api/branches', formData);
      toast.success('Sucursal creada exitosamente');
      setShowDialog(false);
      setFormData({ name: '', address: '', phone: '', email: '' });
      fetchBranches();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
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
    <div className="space-y-6" data-testid="branches-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Sucursales</h1>
          <p className="text-slate-500 mt-1">Gestiona las sucursales de tu óptica</p>
        </div>
        {isAdmin && (
          <Dialog open={showDialog} onOpenChange={setShowDialog}>
            <DialogTrigger asChild>
              <Button className="bg-pine-900 hover:bg-pine-700" data-testid="add-branch-btn">
                <Plus className="w-4 h-4 mr-2" /> Nueva Sucursal
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle className="font-heading">Nueva Sucursal</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label>Nombre *</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    required
                    data-testid="branch-name"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Dirección *</Label>
                  <Input
                    value={formData.address}
                    onChange={(e) => setFormData({...formData, address: e.target.value})}
                    required
                    data-testid="branch-address"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Teléfono *</Label>
                  <Input
                    value={formData.phone}
                    onChange={(e) => setFormData({...formData, phone: e.target.value})}
                    required
                    data-testid="branch-phone"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Correo Electrónico</Label>
                  <Input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                    data-testid="branch-email"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-4">
                  <Button type="button" variant="outline" onClick={() => setShowDialog(false)}>
                    Cancelar
                  </Button>
                  <Button type="submit" className="bg-pine-900 hover:bg-pine-700" data-testid="save-branch">
                    Guardar
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* Branches Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {branches.map((branch) => (
          <Card key={branch._id} className="border-slate-200/80" data-testid={`branch-card-${branch._id}`}>
            <CardContent className="p-5">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-lg bg-pine-100 flex items-center justify-center text-pine-700">
                  <Building2 className="w-6 h-6" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-slate-900">{branch.name}</h3>
                  <div className="space-y-1 mt-2 text-sm text-slate-500">
                    {branch.address && (
                      <p className="flex items-center gap-2">
                        <MapPin className="w-4 h-4" /> {branch.address}
                      </p>
                    )}
                    {branch.phone && (
                      <p className="flex items-center gap-2">
                        <Phone className="w-4 h-4" /> {branch.phone}
                      </p>
                    )}
                    {branch.email && (
                      <p className="flex items-center gap-2">
                        <Mail className="w-4 h-4" /> {branch.email}
                      </p>
                    )}
                  </div>
                  <span className={`mt-3 inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    branch.is_active !== false 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-red-100 text-red-800'
                  }`}>
                    {branch.is_active !== false ? 'Activa' : 'Inactiva'}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
        {branches.length === 0 && (
          <Card className="col-span-full border-slate-200/80">
            <CardContent className="py-12 text-center text-slate-500">
              <Building2 className="w-12 h-12 mx-auto mb-4 opacity-30" />
              <p>No hay sucursales registradas</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
