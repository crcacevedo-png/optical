import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Plus, Building2, MapPin, Phone, Mail, Users, GitBranch,
  Shield, UserCheck, UserX, Eye, EyeOff, ChevronRight, Store, UserCog
} from 'lucide-react';
import { toast } from 'sonner';

export default function AdminOpticasPage() {
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [companyBranches, setCompanyBranches] = useState([]);
  const [companyUsers, setCompanyUsers] = useState([]);
  const [showCreateCompany, setShowCreateCompany] = useState(false);
  const [showCreateBranch, setShowCreateBranch] = useState(false);
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [detailTab, setDetailTab] = useState('info');

  const [companyForm, setCompanyForm] = useState({
    name: '', legal_name: '', tax_id: '', address: '', phone: '', email: '',
    contact_name: '', contact_phone: '', contact_email: '',
    admin_name: '', admin_email: '', admin_password: ''
  });
  const [branchForm, setBranchForm] = useState({ name: '', address: '', phone: '', email: '' });
  const [userForm, setUserForm] = useState({ name: '', email: '', password: '', role: 'user', branch_id: '' });
  const [showCompanyPassword, setShowCompanyPassword] = useState(false);
  const [showUserPassword, setShowUserPassword] = useState(false);

  const loadCompanies = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await api.get('/api/companies');
      setCompanies(data || []);
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadCompanies(); }, [loadCompanies]);

  const loadCompanyDetail = async (company) => {
    setSelectedCompany(company);
    setDetailTab('info');
    try {
      const [brRes, usRes] = await Promise.all([
        api.get(`/api/branches?company_id=${company._id}`),
        api.get('/api/users'),
      ]);
      setCompanyBranches(brRes.data || []);
      setCompanyUsers((usRes.data || []).filter(u => u.company_id === company._id));
    } catch (err) {
      console.error(err);
    }
  };

  const handleCreateCompany = async (e) => {
    e.preventDefault();
    try {
      await api.post('/api/companies', companyForm);
      toast.success('Optica creada exitosamente');
      setShowCreateCompany(false);
      setShowCompanyPassword(false);
      setCompanyForm({ name: '', legal_name: '', tax_id: '', address: '', phone: '', email: '', contact_name: '', contact_phone: '', contact_email: '', admin_name: '', admin_email: '', admin_password: '' });
      loadCompanies();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  const handleCreateBranch = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/api/branches?company_id=${selectedCompany._id}`, branchForm);
      toast.success('Sucursal creada exitosamente');
      setShowCreateBranch(false);
      setBranchForm({ name: '', address: '', phone: '', email: '' });
      loadCompanyDetail(selectedCompany);
      loadCompanies();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/api/users?company_id=${selectedCompany._id}`, userForm);
      toast.success('Usuario creado exitosamente');
      setShowCreateUser(false);
      setShowUserPassword(false);
      setUserForm({ name: '', email: '', password: '', role: 'user', branch_id: '' });
      loadCompanyDetail(selectedCompany);
      loadCompanies();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  const toggleCompanyStatus = async (id, isActive) => {
    try {
      if (isActive) {
        await api.delete(`/api/companies/${id}`);
      } else {
        await api.put(`/api/companies/${id}`, { is_active: true });
      }
      toast.success('Estado actualizado');
      loadCompanies();
      if (selectedCompany?._id === id) {
        setSelectedCompany(prev => ({ ...prev, is_active: !isActive }));
      }
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  const toggleUserStatus = async (userId, isActive) => {
    try {
      await api.put(`/api/users/${userId}`, { is_active: !isActive });
      toast.success('Estado actualizado');
      loadCompanyDetail(selectedCompany);
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  const getRoleBadge = (role) => {
    const cfg = { admin: 'bg-blue-100 text-blue-800', user: 'bg-slate-100 text-slate-800' };
    const lbl = { admin: 'Administrador', user: 'Usuario' };
    return <Badge className={cfg[role] || cfg.user}>{lbl[role] || role}</Badge>;
  };

  return (
    <div className="space-y-6" data-testid="admin-opticas-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Administracion de Opticas</h1>
          <p className="text-slate-500 text-sm mt-1">Gestiona empresas, sucursales y usuarios de la plataforma</p>
        </div>
        <Button
          onClick={() => { setCompanyForm({ name: '', legal_name: '', tax_id: '', address: '', phone: '', email: '', contact_name: '', contact_phone: '', contact_email: '', admin_name: '', admin_email: '', admin_password: '' }); setShowCreateCompany(true); }}
          className="bg-pine-700 hover:bg-pine-800"
          data-testid="new-company-btn"
        >
          <Plus className="w-4 h-4 mr-2" /> Nueva Optica
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Companies List */}
        <div className="lg:col-span-1 space-y-3">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider px-1">Opticas ({companies.length})</h2>
          {loading ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-pine-900"></div>
            </div>
          ) : companies.length === 0 ? (
            <Card><CardContent className="py-8 text-center text-slate-400">
              <Store className="w-10 h-10 mx-auto mb-2 opacity-30" />
              <p>No hay opticas registradas</p>
            </CardContent></Card>
          ) : (
            companies.map((c) => (
              <Card
                key={c._id}
                className={`cursor-pointer transition-all hover:shadow-md ${
                  selectedCompany?._id === c._id ? 'ring-2 ring-pine-500 bg-pine-50/50' : ''
                }`}
                onClick={() => loadCompanyDetail(c)}
                data-testid={`company-card-${c._id}`}
              >
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-pine-100 flex items-center justify-center">
                        <Store className="w-5 h-5 text-pine-700" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-sm text-slate-900">{c.name}</h3>
                        <p className="text-xs text-slate-400">{c.email}</p>
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-300" />
                  </div>
                  <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
                    <span className="flex items-center gap-1"><GitBranch className="w-3 h-3" /> {c.branches_count || 0} sucursales</span>
                    <span className="flex items-center gap-1"><Users className="w-3 h-3" /> {c.users_count || 0} usuarios</span>
                  </div>
                  <div className="mt-2">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium ${
                      c.is_active !== false ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                    }`}>
                      {c.is_active !== false ? 'Activa' : 'Inactiva'}
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>

        {/* Company Detail */}
        <div className="lg:col-span-2">
          {!selectedCompany ? (
            <Card className="h-full flex items-center justify-center">
              <CardContent className="py-16 text-center text-slate-400">
                <Eye className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p className="font-medium">Selecciona una optica</p>
                <p className="text-sm mt-1">Haz clic en una optica para ver sus detalles</p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg">{selectedCompany.name}</CardTitle>
                    <p className="text-sm text-slate-400">{selectedCompany.legal_name}</p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => toggleCompanyStatus(selectedCompany._id, selectedCompany.is_active !== false)}
                    className={selectedCompany.is_active !== false ? 'text-red-600 border-red-200' : 'text-green-600 border-green-200'}
                  >
                    {selectedCompany.is_active !== false ? 'Desactivar' : 'Activar'}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <Tabs value={detailTab} onValueChange={setDetailTab}>
                  <TabsList className="mb-4">
                    <TabsTrigger value="info" data-testid="tab-info">Info</TabsTrigger>
                    <TabsTrigger value="branches" data-testid="tab-branches">Sucursales ({companyBranches.length})</TabsTrigger>
                    <TabsTrigger value="users" data-testid="tab-users">Usuarios ({companyUsers.length})</TabsTrigger>
                  </TabsList>

                  {/* INFO TAB */}
                  <TabsContent value="info">
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div><span className="text-slate-400">NIT:</span> <span className="font-medium ml-2">{selectedCompany.tax_id || '-'}</span></div>
                      <div className="flex items-center gap-2"><Phone className="w-3.5 h-3.5 text-slate-400" /> {selectedCompany.phone || '-'}</div>
                      <div className="flex items-center gap-2"><Mail className="w-3.5 h-3.5 text-slate-400" /> {selectedCompany.email || '-'}</div>
                      <div className="flex items-center gap-2"><MapPin className="w-3.5 h-3.5 text-slate-400" /> {selectedCompany.address || '-'}</div>
                      <div><span className="text-slate-400">Pacientes:</span> <span className="font-medium ml-2">{selectedCompany.patients_count || 0}</span></div>
                      <div><span className="text-slate-400">Creada:</span> <span className="font-medium ml-2">{selectedCompany.created_at?.slice(0, 10)}</span></div>
                    </div>
                    {(selectedCompany.contact_name || selectedCompany.contact_phone || selectedCompany.contact_email) && (
                      <div className="mt-4 pt-3 border-t">
                        <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Persona de Contacto</p>
                        <div className="grid grid-cols-3 gap-2 text-sm">
                          <div>{selectedCompany.contact_name || '-'}</div>
                          <div className="flex items-center gap-1"><Phone className="w-3.5 h-3.5 text-slate-400" /> {selectedCompany.contact_phone || '-'}</div>
                          <div className="flex items-center gap-1"><Mail className="w-3.5 h-3.5 text-slate-400" /> {selectedCompany.contact_email || '-'}</div>
                        </div>
                      </div>
                    )}
                  </TabsContent>

                  {/* BRANCHES TAB */}
                  <TabsContent value="branches">
                    <div className="flex justify-end mb-3">
                      <Button size="sm" className="bg-pine-700 hover:bg-pine-800" onClick={() => { setBranchForm({ name: '', address: '', phone: '', email: '' }); setShowCreateBranch(true); }} data-testid="new-branch-btn">
                        <Plus className="w-4 h-4 mr-1" /> Nueva Sucursal
                      </Button>
                    </div>
                    {companyBranches.length === 0 ? (
                      <div className="py-8 text-center text-slate-400">
                        <Building2 className="w-10 h-10 mx-auto mb-2 opacity-30" />
                        <p>No hay sucursales</p>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {companyBranches.map((b) => (
                          <div key={b._id} className="p-3 border rounded-lg flex items-center justify-between" data-testid={`branch-row-${b._id}`}>
                            <div className="flex items-center gap-3">
                              <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center">
                                <Building2 className="w-4 h-4 text-slate-600" />
                              </div>
                              <div>
                                <p className="font-medium text-sm">{b.name}</p>
                                <p className="text-xs text-slate-400">{b.address} &middot; {b.phone}</p>
                              </div>
                            </div>
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                              b.is_active !== false ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                            }`}>
                              {b.is_active !== false ? 'Activa' : 'Inactiva'}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </TabsContent>

                  {/* USERS TAB */}
                  <TabsContent value="users">
                    <div className="flex justify-end mb-3">
                      <Button size="sm" className="bg-pine-700 hover:bg-pine-800" onClick={() => { setUserForm({ name: '', email: '', password: '', role: 'user', branch_id: '' }); setShowCreateUser(true); }} data-testid="new-user-btn">
                        <Plus className="w-4 h-4 mr-1" /> Nuevo Usuario
                      </Button>
                    </div>
                    {companyUsers.length === 0 ? (
                      <div className="py-8 text-center text-slate-400">
                        <Users className="w-10 h-10 mx-auto mb-2 opacity-30" />
                        <p>No hay usuarios</p>
                      </div>
                    ) : (
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Usuario</TableHead>
                            <TableHead>Correo</TableHead>
                            <TableHead>Rol</TableHead>
                            <TableHead>Estado</TableHead>
                            <TableHead className="text-right">Acciones</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {companyUsers.map((u) => (
                            <TableRow key={u._id} data-testid={`user-row-${u._id}`}>
                              <TableCell className="font-medium text-sm">{u.name}</TableCell>
                              <TableCell className="text-sm">{u.email}</TableCell>
                              <TableCell>{getRoleBadge(u.role)}</TableCell>
                              <TableCell>
                                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                                  u.is_active !== false ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                                }`}>
                                  {u.is_active !== false ? <UserCheck className="w-3 h-3" /> : <UserX className="w-3 h-3" />}
                                  {u.is_active !== false ? 'Activo' : 'Inactivo'}
                                </span>
                              </TableCell>
                              <TableCell className="text-right">
                                <Button size="sm" variant="outline" onClick={() => toggleUserStatus(u._id, u.is_active !== false)}>
                                  {u.is_active !== false ? 'Desactivar' : 'Activar'}
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    )}
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* ===== CREATE COMPANY DIALOG ===== */}
      <Dialog open={showCreateCompany} onOpenChange={setShowCreateCompany}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Nueva Optica</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreateCompany} className="space-y-4">
            <div className="p-3 bg-slate-50 rounded-lg">
              <p className="text-xs font-semibold text-slate-500 uppercase mb-3">Datos de la Empresa</p>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs">Nombre de la Optica *</Label>
                  <Input value={companyForm.name} onChange={(e) => setCompanyForm({...companyForm, name: e.target.value})} required data-testid="company-name" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Razon Social</Label>
                  <Input value={companyForm.legal_name} onChange={(e) => setCompanyForm({...companyForm, legal_name: e.target.value})} data-testid="company-legal" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">NIT</Label>
                  <Input value={companyForm.tax_id} onChange={(e) => setCompanyForm({...companyForm, tax_id: e.target.value})} data-testid="company-nit" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Telefono *</Label>
                  <Input value={companyForm.phone} onChange={(e) => setCompanyForm({...companyForm, phone: e.target.value})} required data-testid="company-phone" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Email *</Label>
                  <Input type="email" value={companyForm.email} onChange={(e) => setCompanyForm({...companyForm, email: e.target.value})} required data-testid="company-email" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Direccion</Label>
                  <Input value={companyForm.address} onChange={(e) => setCompanyForm({...companyForm, address: e.target.value})} data-testid="company-address" />
                </div>
              </div>
            </div>

            <div className="p-3 bg-amber-50/60 rounded-lg">
              <p className="text-xs font-semibold text-amber-700 uppercase mb-3 flex items-center gap-1">
                <Phone className="w-3.5 h-3.5" /> Persona de Contacto
              </p>
              <div className="grid grid-cols-3 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs">Nombre</Label>
                  <Input value={companyForm.contact_name} onChange={(e) => setCompanyForm({...companyForm, contact_name: e.target.value})} data-testid="company-contact-name" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Telefono</Label>
                  <Input value={companyForm.contact_phone} onChange={(e) => setCompanyForm({...companyForm, contact_phone: e.target.value})} data-testid="company-contact-phone" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Email</Label>
                  <Input type="email" value={companyForm.contact_email} onChange={(e) => setCompanyForm({...companyForm, contact_email: e.target.value})} data-testid="company-contact-email" />
                </div>
              </div>
            </div>

            <div className="p-3 bg-blue-50 rounded-lg">
              <p className="text-xs font-semibold text-blue-600 uppercase mb-3 flex items-center gap-1">
                <Shield className="w-3.5 h-3.5" /> Administrador de la Optica
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5 col-span-2">
                  <Label className="text-xs">Nombre del Admin *</Label>
                  <Input value={companyForm.admin_name} onChange={(e) => setCompanyForm({...companyForm, admin_name: e.target.value})} required data-testid="company-admin-name" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Email del Admin *</Label>
                  <Input type="email" value={companyForm.admin_email} onChange={(e) => setCompanyForm({...companyForm, admin_email: e.target.value})} required data-testid="company-admin-email" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Contrasena del Admin *</Label>
                  <div className="relative">
                    <Input type={showCompanyPassword ? "text" : "password"} value={companyForm.admin_password} onChange={(e) => setCompanyForm({...companyForm, admin_password: e.target.value})} required className="pr-10" data-testid="company-admin-password" />
                    <button type="button" onClick={() => setShowCompanyPassword(!showCompanyPassword)} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600" data-testid="toggle-company-password">
                      {showCompanyPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setShowCreateCompany(false)}>Cancelar</Button>
              <Button type="submit" className="bg-pine-700 hover:bg-pine-800" data-testid="save-company-btn">
                <Store className="w-4 h-4 mr-2" /> Crear Optica
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* ===== CREATE BRANCH DIALOG ===== */}
      <Dialog open={showCreateBranch} onOpenChange={setShowCreateBranch}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nueva Sucursal para {selectedCompany?.name}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreateBranch} className="space-y-4">
            <div className="space-y-2">
              <Label>Nombre *</Label>
              <Input value={branchForm.name} onChange={(e) => setBranchForm({...branchForm, name: e.target.value})} required data-testid="sa-branch-name" />
            </div>
            <div className="space-y-2">
              <Label>Direccion *</Label>
              <Input value={branchForm.address} onChange={(e) => setBranchForm({...branchForm, address: e.target.value})} required data-testid="sa-branch-address" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Telefono *</Label>
                <Input value={branchForm.phone} onChange={(e) => setBranchForm({...branchForm, phone: e.target.value})} required data-testid="sa-branch-phone" />
              </div>
              <div className="space-y-2">
                <Label>Email</Label>
                <Input type="email" value={branchForm.email} onChange={(e) => setBranchForm({...branchForm, email: e.target.value})} data-testid="sa-branch-email" />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setShowCreateBranch(false)}>Cancelar</Button>
              <Button type="submit" className="bg-pine-700 hover:bg-pine-800" data-testid="save-branch-btn">Crear Sucursal</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* ===== CREATE USER DIALOG ===== */}
      <Dialog open={showCreateUser} onOpenChange={setShowCreateUser}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nuevo Usuario para {selectedCompany?.name}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreateUser} className="space-y-4">
            <div className="space-y-2">
              <Label>Nombre *</Label>
              <Input value={userForm.name} onChange={(e) => setUserForm({...userForm, name: e.target.value})} required data-testid="sa-user-name" />
            </div>
            <div className="space-y-2">
              <Label>Email *</Label>
              <Input type="email" value={userForm.email} onChange={(e) => setUserForm({...userForm, email: e.target.value})} required data-testid="sa-user-email" />
            </div>
            <div className="space-y-2">
              <Label>Contrasena *</Label>
              <div className="relative">
                <Input type={showUserPassword ? "text" : "password"} value={userForm.password} onChange={(e) => setUserForm({...userForm, password: e.target.value})} required className="pr-10" data-testid="sa-user-password" />
                <button type="button" onClick={() => setShowUserPassword(!showUserPassword)} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600" data-testid="toggle-user-password">
                  {showUserPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Rol</Label>
                <Select value={userForm.role} onValueChange={(v) => setUserForm({...userForm, role: v})}>
                  <SelectTrigger data-testid="sa-user-role">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="user">Usuario</SelectItem>
                    <SelectItem value="admin">Administrador</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Sucursal</Label>
                <Select value={userForm.branch_id} onValueChange={(v) => setUserForm({...userForm, branch_id: v})}>
                  <SelectTrigger data-testid="sa-user-branch">
                    <SelectValue placeholder="Sin asignar" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Sin asignar</SelectItem>
                    {companyBranches.map((b) => (
                      <SelectItem key={b._id} value={b._id}>{b.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setShowCreateUser(false)}>Cancelar</Button>
              <Button type="submit" className="bg-pine-700 hover:bg-pine-800" data-testid="save-user-btn">Crear Usuario</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
