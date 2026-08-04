import React, { useState, useEffect } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { Plus, Users, UserCheck, UserX, Trash2, Key } from 'lucide-react';
import { toast } from 'sonner';

export default function UsersPage() {
  const { isAdmin, user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [branches, setBranches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [deleteDialog, setDeleteDialog] = useState(null);
  const [passwordDialog, setPasswordDialog] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    role: 'user',
    branch_id: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [usersRes, branchesRes] = await Promise.all([
        api.get('/api/users'),
        api.get('/api/branches')
      ]);
      setUsers(usersRes.data || []);
      setBranches(branchesRes.data || []);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/api/users', formData);
      toast.success('Usuario creado exitosamente');
      setShowDialog(false);
      setFormData({ name: '', email: '', password: '', role: 'user', branch_id: '' });
      fetchData();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const toggleUserStatus = async (userId, currentStatus) => {
    try {
      await api.put(`/api/users/${userId}`, { is_active: !currentStatus });
      toast.success('Estado actualizado');
      fetchData();
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const getRoleBadge = (role) => {
    const styles = {
      superadmin: 'bg-purple-100 text-purple-800',
      admin: 'bg-blue-100 text-blue-800',
      user: 'bg-slate-100 text-slate-800'
    };
    const labels = {
      superadmin: 'Super Admin',
      admin: 'Administrador',
      user: 'Atencion al Cliente'
    };
    return (
      <Badge className={styles[role] || styles.user}>
        {labels[role] || role}
      </Badge>
    );
  };

  const getBranchName = (branchId) => {
    const branch = branches.find(b => b._id === branchId);
    return branch?.name || '-';
  };

  const handleDeleteUser = async () => {
    if (!deleteDialog) return;
    try {
      await api.delete(`/api/users/${deleteDialog._id}`);
      toast.success('Usuario eliminado');
      setDeleteDialog(null);
      fetchData();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (!passwordDialog) return;
    if (newPassword.length < 6) {
      toast.error('La contraseña debe tener al menos 6 caracteres');
      return;
    }
    try {
      await api.put(`/api/users/${passwordDialog._id}`, { password: newPassword });
      toast.success(`Contraseña actualizada para ${passwordDialog.name}`);
      setPasswordDialog(null);
      setNewPassword('');
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const isSuperAdmin = currentUser?.role === 'superadmin';

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="users-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Usuarios</h1>
          <p className="text-slate-500 mt-1">Gestiona los usuarios del sistema</p>
        </div>
        {isAdmin && (
          <Dialog open={showDialog} onOpenChange={setShowDialog}>
            <DialogTrigger asChild>
              <Button className="bg-pine-900 hover:bg-pine-700" data-testid="add-user-btn">
                <Plus className="w-4 h-4 mr-2" /> Nuevo Usuario
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle className="font-heading">Nuevo Usuario</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label>Nombre *</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    required
                    data-testid="user-name"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Correo Electrónico *</Label>
                  <Input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                    required
                    data-testid="user-email"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Contraseña *</Label>
                  <Input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({...formData, password: e.target.value})}
                    required
                    data-testid="user-password"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Rol</Label>
                    <Select value={formData.role} onValueChange={(v) => setFormData({...formData, role: v})}>
                      <SelectTrigger data-testid="user-role">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="user">Atencion al Cliente</SelectItem>
                        <SelectItem value="admin">Administrador</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Sucursal</Label>
                    <Select value={formData.branch_id} onValueChange={(v) => setFormData({...formData, branch_id: v})}>
                      <SelectTrigger data-testid="user-branch">
                        <SelectValue placeholder="Seleccionar" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Sin asignar</SelectItem>
                        {branches.map((b) => (
                          <SelectItem key={b._id} value={b._id}>{b.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="flex justify-end gap-2 pt-4">
                  <Button type="button" variant="outline" onClick={() => setShowDialog(false)}>
                    Cancelar
                  </Button>
                  <Button type="submit" className="bg-pine-900 hover:bg-pine-700" data-testid="save-user">
                    Guardar
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* Users Table */}
      <Card className="border-slate-200/80">
        <CardHeader>
          <CardTitle className="font-heading text-lg">Lista de Usuarios ({users.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="data-table-header">
                <TableHead>Usuario</TableHead>
                <TableHead>Correo</TableHead>
                <TableHead>Rol</TableHead>
                <TableHead>Sucursal</TableHead>
                <TableHead>Estado</TableHead>
                {(isAdmin || isSuperAdmin) && <TableHead className="text-right">Acciones</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user._id} className="data-table-row" data-testid={`user-row-${user._id}`}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-full bg-pine-100 flex items-center justify-center text-pine-700 font-medium text-sm">
                        {user.name?.split(' ').map(n => n[0]).join('').slice(0, 2) || 'U'}
                      </div>
                      <span className="font-medium">{user.name}</span>
                    </div>
                  </TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>{getRoleBadge(user.role)}</TableCell>
                  <TableCell>{getBranchName(user.branch_id)}</TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      user.is_active !== false 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {user.is_active !== false ? <UserCheck className="w-3 h-3" /> : <UserX className="w-3 h-3" />}
                      {user.is_active !== false ? 'Activo' : 'Inactivo'}
                    </span>
                  </TableCell>
                  {(isAdmin || isSuperAdmin) && (
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        {user.role !== 'superadmin' && (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => toggleUserStatus(user._id, user.is_active !== false)}
                              data-testid={`toggle-user-${user._id}`}
                            >
                              {user.is_active !== false ? 'Desactivar' : 'Activar'}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => { setPasswordDialog(user); setNewPassword(''); }}
                              title="Cambiar contraseña"
                              data-testid={`reset-password-${user._id}`}
                            >
                              <Key className="w-4 h-4 text-blue-600" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setDeleteDialog(user)}
                              data-testid={`delete-user-${user._id}`}
                            >
                              <Trash2 className="w-4 h-4 text-red-500" />
                            </Button>
                          </>
                        )}
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
              {users.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-slate-500">
                    <Users className="w-12 h-12 mx-auto mb-2 opacity-30" />
                    <p>No hay usuarios registrados</p>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Delete Confirmation */}
      <Dialog open={!!deleteDialog} onOpenChange={(open) => !open && setDeleteDialog(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Eliminar Usuario</DialogTitle>
            <DialogDescription>
              Desactivar al usuario <strong>{deleteDialog?.name}</strong> ({deleteDialog?.email})? No podra acceder al sistema.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialog(null)}>Cancelar</Button>
            <Button variant="destructive" onClick={handleDeleteUser} data-testid="confirm-delete-user">Eliminar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {/* Reset Password Dialog */}
      <Dialog open={!!passwordDialog} onOpenChange={(open) => { if (!open) { setPasswordDialog(null); setNewPassword(''); } }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-heading">Cambiar Contraseña</DialogTitle>
            <DialogDescription>
              Asigna una nueva contraseña para <strong>{passwordDialog?.name}</strong> ({passwordDialog?.email}).
              El usuario podrá ingresar con esta nueva contraseña la próxima vez.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleResetPassword} className="space-y-4 pt-2">
            <div className="space-y-2">
              <Label>Nueva contraseña *</Label>
              <Input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Mínimo 6 caracteres"
                minLength={6}
                required
                data-testid="new-password-input"
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => { setPasswordDialog(null); setNewPassword(''); }}>
                Cancelar
              </Button>
              <Button type="submit" className="bg-pine-900 hover:bg-pine-700" data-testid="save-new-password">
                Guardar contraseña
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
