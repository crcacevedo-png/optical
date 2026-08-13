import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail } from '../context/AuthContext';
import {
  CreateCompanyDialog, CreateBranchDialog, CreateUserDialog, EditCompanyDialog
} from '../components/admin/AdminOpticasDialogs';
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
  Shield, UserCheck, UserX, Eye, EyeOff, ChevronRight, Store, UserCog, Upload, Image, Trash2,
  AlertTriangle, CreditCard, History, ArrowRight
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
  const [plans, setPlans] = useState([]);
  const [planHistory, setPlanHistory] = useState([]);

  const [companyForm, setCompanyForm] = useState({
    name: '', legal_name: '', tax_id: '', address: '', phone: '', email: '',
    contact_name: '', contact_phone: '', contact_email: '',
    admin_name: '', admin_email: '', admin_password: ''
  });
  const [activationFilter, setActivationFilter] = useState('todas'); // todas | sin_activar | activas | inactivas
  const [branchForm, setBranchForm] = useState({ name: '', address: '', phone: '', email: '' });
  const [userForm, setUserForm] = useState({ name: '', email: '', password: '', role: 'user', branch_id: '' });
  const [showCompanyPassword, setShowCompanyPassword] = useState(false);
  const [showUserPassword, setShowUserPassword] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [showEditCompany, setShowEditCompany] = useState(false);
  const [editCompanyForm, setEditCompanyForm] = useState({});

  const openEditCompany = () => {
    setEditCompanyForm({
      name: selectedCompany.name || '',
      legal_name: selectedCompany.legal_name || '',
      tax_id: selectedCompany.tax_id || '',
      address: selectedCompany.address || '',
      phone: selectedCompany.phone || '',
      email: selectedCompany.email || '',
      contact_name: selectedCompany.contact_name || '',
      contact_phone: selectedCompany.contact_phone || '',
      contact_email: selectedCompany.contact_email || '',
    });
    setShowEditCompany(true);
  };

  const handleSaveEditCompany = async (e) => {
    e.preventDefault();
    try {
      await api.put(`/api/companies/${selectedCompany._id}`, editCompanyForm);
      toast.success('Optica actualizada');
      setShowEditCompany(false);
      setSelectedCompany(prev => ({ ...prev, ...editCompanyForm }));
      loadCompanies();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail) || 'Error al actualizar');
    }
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || !selectedCompany) return;
    setUploadingLogo(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      await api.post(`/api/companies/${selectedCompany._id}/logo`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success('Logo actualizado');
      setSelectedCompany(prev => ({ ...prev, logo_filename: `${selectedCompany._id}.${file.name.split('.').pop()}` }));
      loadCompanies();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    } finally {
      setUploadingLogo(false);
    }
  };

  const deleteBranch = async (branchId) => {
    if (!window.confirm('Eliminar esta sucursal? Esta accion no se puede deshacer.')) return;
    try {
      await api.delete(`/api/branches/${branchId}`);
      toast.success('Sucursal eliminada');
      loadCompanyDetail(selectedCompany);
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  const loadCompanies = useCallback(async () => {
    try {
      setLoading(true);
      const [compRes, planRes] = await Promise.all([
        api.get('/api/companies'),
        api.get('/api/plans')
      ]);
      setCompanies(compRes.data || []);
      setPlans(planRes.data || []);
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
      const [brRes, usRes, histRes] = await Promise.all([
        api.get(`/api/branches?company_id=${company._id}`),
        api.get('/api/users'),
        api.get(`/api/plans/history/${company._id}`).catch(() => ({ data: [] }))
      ]);
      setCompanyBranches(brRes.data || []);
      setCompanyUsers((usRes.data || []).filter(u => u.company_id === company._id));
      setPlanHistory(histRes.data || []);
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

  // Estado de activacion del admin (Issue 2)
  const getActivationBadge = (c) => {
    if (!c.admin_activated) {
      const daysCreated = c.days_since_created ?? 0;
      if (daysCreated >= 30) {
        return { label: 'Expirada', cls: 'bg-red-200 text-red-900 border-red-300', title: `No activo en ${daysCreated} dias` };
      }
      if (daysCreated >= 23) {
        return { label: `Por expirar (${30 - daysCreated}d)`, cls: 'bg-amber-100 text-amber-800 border-amber-200', title: 'Faltan menos de 7 dias para desactivarse' };
      }
      return { label: 'Sin activar', cls: 'bg-slate-100 text-slate-600 border-slate-200', title: `Creada hace ${daysCreated} dia(s), admin sin ingresar` };
    }
    const days = c.days_since_last_login;
    if (days === null || days === undefined) return null;
    if (days <= 7) return { label: 'Activo', cls: 'bg-green-100 text-green-700 border-green-200', title: `Ultimo acceso hace ${days} dia(s)` };
    if (days <= 30) return { label: `Hace ${days}d`, cls: 'bg-amber-100 text-amber-700 border-amber-200', title: `Ultimo acceso hace ${days} dia(s)` };
    return { label: 'Inactivo', cls: 'bg-red-100 text-red-700 border-red-200', title: `Ultimo acceso hace ${days} dia(s)` };
  };

  const filteredCompanies = companies.filter((c) => {
    if (activationFilter === 'todas') return true;
    if (activationFilter === 'sin_activar') return !c.admin_activated;
    if (activationFilter === 'activas') {
      return c.admin_activated && (c.days_since_last_login ?? 999) <= 7;
    }
    if (activationFilter === 'inactivas') {
      return c.admin_activated && (c.days_since_last_login ?? 0) > 30;
    }
    return true;
  });

  const handlePlanChange = async (companyId, planId) => {
    try {
      await api.put(`/api/plans/assign/${companyId}?plan_id=${planId}`);
      toast.success('Plan actualizado');
      loadCompanies();
      if (selectedCompany?._id === companyId) {
        const plan = plans.find(p => p._id === planId);
        setSelectedCompany(prev => ({ ...prev, plan_id: planId, plan_name: plan?.name }));
      }
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
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
          <div className="flex items-center justify-between px-1">
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Opticas ({filteredCompanies.length}/{companies.length})</h2>
          </div>
          {/* Filtro por estado de activacion */}
          <div className="flex flex-wrap gap-1.5">
            {[
              { k: 'todas', l: 'Todas' },
              { k: 'sin_activar', l: 'Sin activar' },
              { k: 'activas', l: 'Activas' },
              { k: 'inactivas', l: 'Inactivas' },
            ].map((opt) => (
              <button
                key={opt.k}
                onClick={() => setActivationFilter(opt.k)}
                className={`px-2.5 py-1 rounded-full text-[11px] font-medium border transition-colors ${activationFilter === opt.k ? 'bg-pine-700 text-white border-pine-700' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'}`}
                data-testid={`activation-filter-${opt.k}`}
              >
                {opt.l}
              </button>
            ))}
          </div>
          {loading ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-pine-900"></div>
            </div>
          ) : filteredCompanies.length === 0 ? (
            <Card><CardContent className="py-8 text-center text-slate-400">
              <Store className="w-10 h-10 mx-auto mb-2 opacity-30" />
              <p>No hay opticas para este filtro</p>
            </CardContent></Card>
          ) : (
            filteredCompanies.map((c) => {
              const actBadge = getActivationBadge(c);
              return (
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
                  <div className="mt-2 flex items-center gap-2 flex-wrap">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium ${
                      c.is_active !== false ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                    }`}>
                      {c.is_active !== false ? 'Activa' : 'Inactiva'}
                    </span>
                    {actBadge && (
                      <span
                        className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium border ${actBadge.cls}`}
                        title={actBadge.title}
                        data-testid={`activation-badge-${c._id}`}
                      >
                        {actBadge.label}
                      </span>
                    )}
                    <span className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-50 text-blue-700">
                      <CreditCard className="w-2.5 h-2.5 mr-1" /> {c.plan_name || 'Sin plan'}
                    </span>
                    {(c.patients_warning || c.branches_warning) && (
                      <span className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-100 text-amber-700">
                        <AlertTriangle className="w-2.5 h-2.5 mr-1" /> Cerca del limite
                      </span>
                    )}
                  </div>
                </CardContent>
              </Card>
              );
            })
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
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-lg">{selectedCompany.name}</CardTitle>
                    <p className="text-sm text-slate-400">{selectedCompany.legal_name}</p>
                  </div>
                  <div className="flex flex-col gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => toggleCompanyStatus(selectedCompany._id, selectedCompany.is_active !== false)}
                      className={selectedCompany.is_active !== false ? 'text-red-600 border-red-200' : 'text-green-600 border-green-200'}
                    >
                      {selectedCompany.is_active !== false ? 'Desactivar' : 'Activar'}
                    </Button>
                    <Button variant="outline" size="sm" onClick={openEditCompany} data-testid="edit-company-btn">
                      Modificar
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <Tabs value={detailTab} onValueChange={setDetailTab}>
                  <TabsList className="mb-4">
                    <TabsTrigger value="info" data-testid="tab-info">Info</TabsTrigger>
                    <TabsTrigger value="branches" data-testid="tab-branches">Sucursales ({companyBranches.length})</TabsTrigger>
                    <TabsTrigger value="users" data-testid="tab-users">Usuarios ({companyUsers.length})</TabsTrigger>
                    <TabsTrigger value="plan-history" data-testid="tab-plan-history">Historial Plan</TabsTrigger>
                  </TabsList>

                  {/* INFO TAB */}
                  <TabsContent value="info">
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div><span className="text-slate-400">NIT:</span> <span className="font-medium ml-2">{selectedCompany.tax_id || '-'}</span></div>
                      <div className="flex items-center gap-2"><Phone className="w-3.5 h-3.5 text-slate-400" /> {selectedCompany.phone || '-'}</div>
                      <div className="flex items-center gap-2"><Mail className="w-3.5 h-3.5 text-slate-400" /> {selectedCompany.email || '-'}</div>
                      <div className="flex items-center gap-2"><MapPin className="w-3.5 h-3.5 text-slate-400" /> {selectedCompany.address || '-'}</div>
                      <div><span className="text-slate-400">Pacientes:</span> <span className="font-medium ml-2">{selectedCompany.patients_count || 0}{selectedCompany.max_patients > 0 ? ` / ${selectedCompany.max_patients}` : ''}</span></div>
                      <div><span className="text-slate-400">Creada:</span> <span className="font-medium ml-2">{selectedCompany.created_at?.slice(0, 10)}</span></div>
                    </div>
                    {/* Activacion del admin */}
                    <div className="mt-4 pt-3 border-t" data-testid="admin-activation-section">
                      <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Activacion del Administrador</p>
                      {(() => {
                        const b = getActivationBadge(selectedCompany);
                        return (
                          <div className="grid grid-cols-2 gap-3 text-sm">
                            <div>
                              <span className="text-slate-400 text-xs">Estado:</span>
                              <div className="mt-1">
                                {b ? (
                                  <span className={`inline-flex px-2 py-0.5 rounded-full text-[11px] font-medium border ${b.cls}`}>{b.label}</span>
                                ) : <span className="text-slate-500 text-xs">-</span>}
                              </div>
                            </div>
                            <div>
                              <span className="text-slate-400 text-xs">Admin:</span>
                              <div className="font-medium text-slate-700 truncate">{selectedCompany.admin_name || '-'}</div>
                              <div className="text-xs text-slate-500 truncate">{selectedCompany.admin_email || '-'}</div>
                            </div>
                            <div>
                              <span className="text-slate-400 text-xs">Primer login:</span>
                              <div className="font-medium text-slate-700">
                                {selectedCompany.admin_first_login_at ? selectedCompany.admin_first_login_at.slice(0, 16).replace('T', ' ') : <span className="text-slate-400">Aun no ingresa</span>}
                              </div>
                            </div>
                            <div>
                              <span className="text-slate-400 text-xs">Ultimo acceso:</span>
                              <div className="font-medium text-slate-700">
                                {selectedCompany.admin_last_login_at ? (
                                  <>
                                    {selectedCompany.admin_last_login_at.slice(0, 16).replace('T', ' ')}
                                    {typeof selectedCompany.days_since_last_login === 'number' && (
                                      <span className="text-xs text-slate-400 ml-1">(hace {selectedCompany.days_since_last_login}d)</span>
                                    )}
                                  </>
                                ) : <span className="text-slate-400">-</span>}
                              </div>
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                    {/* Plan Selector */}
                    <div className="mt-4 pt-3 border-t">
                      <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Plan de Suscripcion</p>
                      <div className="flex items-center gap-3">
                        <Select value={selectedCompany.plan_id || ''} onValueChange={(v) => handlePlanChange(selectedCompany._id, v)}>
                          <SelectTrigger className="w-48" data-testid="company-plan-select">
                            <SelectValue placeholder="Seleccionar plan" />
                          </SelectTrigger>
                          <SelectContent>
                            {plans.map(p => (
                              <SelectItem key={p._id} value={p._id} data-testid={`plan-option-${p._id}`}>
                                {p.name} - Q{p.price}/mes
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        {selectedCompany.patients_warning && (
                          <Badge className="bg-amber-100 text-amber-800 text-xs">
                            <AlertTriangle className="w-3 h-3 mr-1" /> {selectedCompany.patients_count}/{selectedCompany.max_patients} pacientes
                          </Badge>
                        )}
                        {selectedCompany.branches_warning && (
                          <Badge className="bg-amber-100 text-amber-800 text-xs">
                            <AlertTriangle className="w-3 h-3 mr-1" /> {selectedCompany.branches_count}/{selectedCompany.max_branches} sucursales
                          </Badge>
                        )}
                      </div>
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
                    {/* Logo */}
                    <div className="mt-4 pt-3 border-t">
                      <p className="text-xs font-semibold text-slate-400 uppercase mb-3">Logo de la Optica</p>
                      <div className="flex items-center gap-4">
                        {selectedCompany.logo_filename ? (
                          <div className="w-24 h-24 rounded-lg border-2 border-slate-200 overflow-hidden bg-white flex items-center justify-center" data-testid="company-logo-preview">
                            <img
                              src={`/api/companies/${selectedCompany._id}/logo?t=${Date.now()}`}
                              alt="Logo"
                              className="max-w-full max-h-full object-contain"
                            />
                          </div>
                        ) : (
                          <div className="w-24 h-24 rounded-lg border-2 border-dashed border-slate-300 flex flex-col items-center justify-center text-slate-400" data-testid="company-logo-placeholder">
                            <Image className="w-8 h-8 mb-1 opacity-40" />
                            <span className="text-[10px]">Sin logo</span>
                          </div>
                        )}
                        <div className="space-y-2">
                          <label className="cursor-pointer">
                            <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden"
                              onChange={handleLogoUpload} data-testid="logo-upload-input" />
                            <div className="inline-flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium bg-pine-700 text-white hover:bg-pine-800 transition-colors">
                              <Upload className="w-4 h-4" />
                              {uploadingLogo ? 'Subiendo...' : selectedCompany.logo_filename ? 'Cambiar Logo' : 'Subir Logo'}
                            </div>
                          </label>
                          <p className="text-[10px] text-slate-400">PNG, JPG o WEBP. Se usara en recetas y documentos.</p>
                        </div>
                      </div>
                    </div>
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
                            <div className="flex items-center gap-2">
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                                b.is_active !== false ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                              }`}>
                                {b.is_active !== false ? 'Activa' : 'Inactiva'}
                              </span>
                              <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                                onClick={() => deleteBranch(b._id)} data-testid={`delete-branch-${b._id}`}>
                                <Trash2 className="w-3.5 h-3.5" />
                              </Button>
                            </div>
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

                  {/* PLAN HISTORY TAB */}
                  <TabsContent value="plan-history">
                    {planHistory.length === 0 ? (
                      <div className="py-8 text-center text-slate-400">
                        <History className="w-10 h-10 mx-auto mb-2 opacity-30" />
                        <p>Sin cambios de plan registrados</p>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {planHistory.map((h, idx) => (
                          <div key={h._id || idx} className="flex items-start gap-3 p-3 rounded-lg border border-slate-100 hover:bg-slate-50/50 transition-colors" data-testid={`plan-history-${idx}`}>
                            <div className="mt-0.5 w-8 h-8 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0">
                              <CreditCard className="w-4 h-4 text-blue-600" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <Badge className="bg-slate-100 text-slate-600 text-xs">{h.old_plan_name || 'Sin plan'}</Badge>
                                <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                                <Badge className="bg-pine-100 text-pine-700 text-xs">{h.new_plan_name}</Badge>
                              </div>
                              <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-400">
                                <span>{h.changed_at?.slice(0, 10)} {h.changed_at?.slice(11, 16)}</span>
                                <span>por {h.changed_by_name || 'Sistema'}</span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* ===== CREATE COMPANY DIALOG ===== */}
      <CreateCompanyDialog
        open={showCreateCompany}
        onOpenChange={setShowCreateCompany}
        form={companyForm}
        setForm={setCompanyForm}
        onSubmit={handleCreateCompany}
        showPassword={showCompanyPassword}
        setShowPassword={setShowCompanyPassword}
      />
      <CreateBranchDialog
        open={showCreateBranch}
        onOpenChange={setShowCreateBranch}
        form={branchForm}
        setForm={setBranchForm}
        onSubmit={handleCreateBranch}
        companyName={selectedCompany?.name}
      />
      <CreateUserDialog
        open={showCreateUser}
        onOpenChange={setShowCreateUser}
        form={userForm}
        setForm={setUserForm}
        onSubmit={handleCreateUser}
        showPassword={showUserPassword}
        setShowPassword={setShowUserPassword}
        companyName={selectedCompany?.name}
        branches={companyBranches}
      />
      <EditCompanyDialog
        open={showEditCompany}
        onOpenChange={setShowEditCompany}
        form={editCompanyForm}
        setForm={setEditCompanyForm}
        onSubmit={handleSaveEditCompany}
      />
    </div>
  );
}
