import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail, useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { toast } from 'sonner';
import { Settings, Building2, Upload, FileText, Save, ImageIcon, Glasses, Pill, ShieldCheck, Lock, KeyRound, Server, Users as UsersIcon, Activity, Database, Download, BookOpen, MessageCircle, Copy, Link as LinkIcon } from 'lucide-react';
import { RolePermissionsSection } from '../components/RolePermissionsSection';
import SessionsPanel from '../components/security/SessionsPanel';
import { Monitor } from 'lucide-react';

const PRESCRIPTION_FONTS = [
  { value: 'Helvetica', label: 'Helvetica (Moderno)' },
  { value: 'Times-Roman', label: 'Times Roman (Clasico)' },
  { value: 'Courier', label: 'Courier (Monoespaciado)' },
];

const PRESCRIPTION_SIZES = [
  { value: 'compact', label: 'Compacto' },
  { value: 'standard', label: 'Estandar' },
  { value: 'large', label: 'Grande' },
];

const PRESCRIPTION_TEMPLATES = [
  { value: 'clasico', label: 'Clasico', desc: 'Header verde oscuro, lineas limpias' },
  { value: 'moderno', label: 'Moderno', desc: 'Barra lateral teal, titulo en pastilla' },
  { value: 'elegante', label: 'Elegante', desc: 'Marco doble purpura, logo centrado' },
];

export default function SettingsPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [exportingDb, setExportingDb] = useState(false);
  const [downloadingGuide, setDownloadingGuide] = useState(false);
  const [shareDialogOpen, setShareDialogOpen] = useState(false);
  const [shareForm, setShareForm] = useState({ prospect_name: '', phone: '', message: '' });
  const [shareResult, setShareResult] = useState(null); // { url, expires_at, prospect_name }
  const [generatingLink, setGeneratingLink] = useState(false);
  const [company, setCompany] = useState(null);
  const [form, setForm] = useState({
    name: '', legal_name: '', tax_id: '', address: '', phone: '', email: '',
    contact_name: '', contact_phone: '', contact_email: '',
  });
  const [rxStyleOptica, setRxStyleOptica] = useState({
    font: 'Helvetica', size: 'standard', show_logo: true, header_text: '', footer_text: '', template: 'clasico',
  });
  const [rxStyleMedica, setRxStyleMedica] = useState({
    font: 'Helvetica', size: 'standard', show_logo: true, header_text: '', footer_text: '', template: 'clasico',
  });
  const [logoTimestamp, setLogoTimestamp] = useState(Date.now());

  const isSuperAdmin = user?.role === 'superadmin';

  const fetchCompany = useCallback(async () => {
    try {
      setLoading(true);
      if (isSuperAdmin) {
        setLoading(false);
        return;
      }
      const { data } = await api.get('/api/settings/company');
      setCompany(data);
      setForm({
        name: data.name || '', legal_name: data.legal_name || '', tax_id: data.tax_id || '',
        address: data.address || '', phone: data.phone || '', email: data.email || '',
        contact_name: data.contact_name || '', contact_phone: data.contact_phone || '',
        contact_email: data.contact_email || '',
      });
      const style = data.prescription_style || {};
      const optica = style.optica || style;
      const medica = style.medica || {};
      setRxStyleOptica({
        font: optica.font || 'Helvetica', size: optica.size || 'standard',
        show_logo: optica.show_logo !== false, header_text: optica.header_text || '', footer_text: optica.footer_text || '',
        template: optica.template || 'clasico',
      });
      setRxStyleMedica({
        font: medica.font || 'Helvetica', size: medica.size || 'standard',
        show_logo: medica.show_logo !== false, header_text: medica.header_text || '', footer_text: medica.footer_text || '',
        template: medica.template || 'clasico',
      });
    } catch (error) {
      // No mostrar toast si es 403 (rol sin permisos para settings de company).
      // El vendedor entra a /settings para ver Sesiones Activas y no necesita datos de la empresa.
      if (error?.response?.status !== 403) {
        toast.error('Error al cargar configuracion');
      }
    } finally {
      setLoading(false);
    }
  }, [isSuperAdmin]);

  useEffect(() => { fetchCompany(); }, [fetchCompany]);

  const handleSaveCompany = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.put('/api/settings/company', form);
      toast.success('Datos de empresa actualizados');
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail) || 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveRxStyle = async () => {
    setSaving(true);
    try {
      await api.put('/api/settings/company', {
        prescription_style: { optica: rxStyleOptica, medica: rxStyleMedica }
      });
      toast.success('Estilo de recetas actualizado');
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail) || 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  const handleExportDatabase = async () => {
    setExportingDb(true);
    const toastId = toast.loading('Generando exportacion completa de su base de datos...');
    try {
      const response = await api.get('/api/data-export/full-database', { responseType: 'blob' });
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      // Try to read filename from Content-Disposition header
      const cd = response.headers?.['content-disposition'] || '';
      const match = cd.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : `Cortexia_Export_${Date.now()}.xlsx`;
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.success('Base de datos exportada exitosamente', { id: toastId });
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail) || 'Error al exportar', { id: toastId });
    } finally {
      setExportingDb(false);
    }
  };

  const handleDownloadUserGuide = async () => {
    setDownloadingGuide(true);
    const toastId = toast.loading('Generando guia de usuario...');
    try {
      const response = await api.get('/api/docs/user-guide.pdf', { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const cd = response.headers?.['content-disposition'] || '';
      const match = cd.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : `cortexia-optical-guia-usuario.pdf`;
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.success('Guia descargada', { id: toastId });
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail) || 'Error al descargar la guia', { id: toastId });
    } finally {
      setDownloadingGuide(false);
    }
  };

  const openShareDialog = () => {
    setShareForm({ prospect_name: '', phone: '', message: '' });
    setShareResult(null);
    setShareDialogOpen(true);
  };

  const handleGenerateShareLink = async () => {
    const name = shareForm.prospect_name.trim();
    if (!name) {
      toast.error('Ingresa el nombre de la optica prospecto.');
      return;
    }
    setGeneratingLink(true);
    try {
      const resp = await api.post('/api/docs/share-link', {
        prospect_name: name,
        expires_hours: 720,
      });
      const path = resp.data.path;
      const fullUrl = `${window.location.origin}${path}`;
      setShareResult({ url: fullUrl, expires_at: resp.data.expires_at, prospect_name: name });
      toast.success('Enlace personalizado listo');
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail) || 'Error al generar el enlace');
    } finally {
      setGeneratingLink(false);
    }
  };

  const sendShareViaWhatsApp = () => {
    if (!shareResult) return;
    const raw = (shareForm.phone || '').replace(/[^\d]/g, '');
    const phone = raw.length === 8 ? `502${raw}` : raw; // Guatemala default
    if (!phone) {
      toast.error('Ingresa un numero de WhatsApp valido');
      return;
    }
    const defaultMsg =
      `Hola! Te comparto la guia completa de Cortexia Optical, el SaaS que digitaliza toda la operacion de una optica.\n\n` +
      `Preparada especialmente para ${shareResult.prospect_name}:\n${shareResult.url}\n\n` +
      `Cualquier duda escribeme por aqui. Saludos!`;
    const msg = (shareForm.message || defaultMsg).trim();
    const waUrl = `https://wa.me/${phone}?text=${encodeURIComponent(msg)}`;
    window.open(waUrl, '_blank', 'noopener,noreferrer');
  };

  const copyShareUrl = async () => {
    if (!shareResult) return;
    try {
      await navigator.clipboard.writeText(shareResult.url);
      toast.success('Enlace copiado al portapapeles');
    } catch {
      toast.error('No se pudo copiar. Selecciona el enlace manualmente.');
    }
  };

  const downloadPersonalizedGuide = async () => {
    const name = shareForm.prospect_name.trim();
    if (!name) {
      toast.error('Ingresa el nombre de la optica prospecto.');
      return;
    }
    setDownloadingGuide(true);
    const toastId = toast.loading('Generando guia personalizada...');
    try {
      const response = await api.get('/api/docs/user-guide.pdf', {
        params: { prospect: name },
        responseType: 'blob',
      });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const cd = response.headers?.['content-disposition'] || '';
      const match = cd.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : `cortexia-optical-guia-${name}.pdf`;
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.success('Guia personalizada descargada', { id: toastId });
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail) || 'Error al descargar', { id: toastId });
    } finally {
      setDownloadingGuide(false);
    }
  };

  const handleDownloadManifesto = async () => {
    const toastId = toast.loading('Generando manifiesto...');
    try {
      const response = await api.get('/api/security/manifesto.pdf', { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'Cortexia_Manifiesto_Seguridad.pdf';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.success('Manifiesto descargado', { id: toastId });
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail) || 'Error al descargar', { id: toastId });
    }
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingLogo(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      await api.post('/api/settings/logo', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success('Logo actualizado');
      setLogoTimestamp(Date.now());
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail) || 'Error al subir logo');
    } finally {
      setUploadingLogo(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-pine-200 border-t-pine-600 rounded-full animate-spin" />
      </div>
    );
  }

  if (isSuperAdmin) {
    return (
      <div className="p-6 max-w-4xl mx-auto" data-testid="settings-page">
        <div className="flex items-center gap-3 mb-8">
          <Settings className="w-7 h-7 text-pine-700" />
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Configuracion</h1>
            <p className="text-slate-500 text-sm">Panel SuperAdmin</p>
          </div>
        </div>
        <Card>
          <CardContent className="p-8 text-center text-slate-500">
            <Settings className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>Las configuraciones de cada optica se gestionan desde el panel de Opticas.</p>
            <p className="text-sm mt-1">Seleccione una optica para editar sus datos, logo y estilo.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto" data-testid="settings-page">
      <div className="flex items-center gap-3 mb-8">
        <Settings className="w-7 h-7 text-pine-700" />
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Configuracion</h1>
          <p className="text-slate-500 text-sm">Administre los datos de su empresa, logo y estilo de recetas</p>
        </div>
      </div>

      <div className="space-y-6">
        {/* DATOS DE EMPRESA */}
        <Card data-testid="settings-company-card">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Building2 className="w-5 h-5 text-pine-700" /> Datos de la Empresa
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSaveCompany} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-slate-500 uppercase">Nombre Comercial</Label>
                  <Input value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} data-testid="settings-name" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-slate-500 uppercase">Razon Social</Label>
                  <Input value={form.legal_name} onChange={(e) => setForm({...form, legal_name: e.target.value})} data-testid="settings-legal-name" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-slate-500 uppercase">NIT</Label>
                  <Input value={form.tax_id} onChange={(e) => setForm({...form, tax_id: e.target.value})} placeholder="123456-7" data-testid="settings-nit" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-slate-500 uppercase">Telefono</Label>
                  <Input value={form.phone} onChange={(e) => setForm({...form, phone: e.target.value})} data-testid="settings-phone" />
                </div>
                <div className="space-y-1.5 sm:col-span-2">
                  <Label className="text-xs font-semibold text-slate-500 uppercase">Direccion</Label>
                  <Input value={form.address} onChange={(e) => setForm({...form, address: e.target.value})} data-testid="settings-address" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-slate-500 uppercase">Email</Label>
                  <Input type="email" value={form.email} onChange={(e) => setForm({...form, email: e.target.value})} data-testid="settings-email" />
                </div>
              </div>
              <div className="border-t pt-4 mt-4">
                <p className="text-xs font-semibold text-slate-400 uppercase mb-3">Persona de Contacto</p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-xs font-semibold text-slate-500 uppercase">Nombre</Label>
                    <Input value={form.contact_name} onChange={(e) => setForm({...form, contact_name: e.target.value})} data-testid="settings-contact-name" />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs font-semibold text-slate-500 uppercase">Telefono</Label>
                    <Input value={form.contact_phone} onChange={(e) => setForm({...form, contact_phone: e.target.value})} data-testid="settings-contact-phone" />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs font-semibold text-slate-500 uppercase">Email</Label>
                    <Input value={form.contact_email} onChange={(e) => setForm({...form, contact_email: e.target.value})} data-testid="settings-contact-email" />
                  </div>
                </div>
              </div>
              <div className="flex justify-end pt-2">
                <Button type="submit" className="bg-pine-900 hover:bg-pine-700" disabled={saving} data-testid="save-company-btn">
                  <Save className="w-4 h-4 mr-1.5" /> {saving ? 'Guardando...' : 'Guardar Datos'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {/* LOGO */}
        <Card data-testid="settings-logo-card">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2 text-lg">
              <ImageIcon className="w-5 h-5 text-pine-700" /> Logo de la Empresa
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-6">
              <div className="w-32 h-32 rounded-xl border-2 border-slate-200 overflow-hidden bg-slate-50 flex items-center justify-center shrink-0" data-testid="settings-logo-preview">
                {company?.logo_filename ? (
                  <img
                    src={`/api/companies/${company._id}/logo?t=${logoTimestamp}`}
                    alt="Logo"
                    className="w-full h-full object-contain p-2"
                    onError={(e) => { e.target.style.display = 'none'; }}
                  />
                ) : (
                  <div className="text-center text-slate-400">
                    <ImageIcon className="w-10 h-10 mx-auto mb-1 opacity-40" />
                    <span className="text-xs">Sin logo</span>
                  </div>
                )}
              </div>
              <div className="space-y-3">
                <p className="text-sm text-slate-600">
                  El logo aparecera en las recetas, cotizaciones y documentos PDF generados por el sistema.
                </p>
                <p className="text-xs text-slate-400">Formatos: PNG, JPG, WEBP. Recomendado: fondo transparente, min 400x400px.</p>
                <label className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer transition-colors">
                  <Upload className="w-4 h-4 text-slate-500" />
                  <span className="text-sm font-medium text-slate-700">{uploadingLogo ? 'Subiendo...' : 'Subir Logo'}</span>
                  <input type="file" accept="image/*" className="hidden" onChange={handleLogoUpload} disabled={uploadingLogo} data-testid="settings-logo-input" />
                </label>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ESTILO DE RECETAS */}
        <Card data-testid="settings-rx-style-card">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2 text-lg">
              <FileText className="w-5 h-5 text-pine-700" /> Estilo de Recetas
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Anteojos / Lentes de Contacto */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 pb-2 border-b">
                <Glasses className="w-4 h-4 text-slate-600" />
                <h3 className="text-sm font-semibold text-slate-700">Recetas de Anteojos / Lentes de Contacto</h3>
              </div>
              <div>
                <Label className="text-xs font-semibold text-slate-500 uppercase mb-2 block">Plantilla Visual</Label>
                <div className="grid grid-cols-3 gap-3">
                  {PRESCRIPTION_TEMPLATES.map(t => (
                    <button key={t.value} type="button" onClick={() => setRxStyleOptica({...rxStyleOptica, template: t.value})}
                      className={`p-3 rounded-lg border-2 text-left transition-all ${rxStyleOptica.template === t.value ? 'border-pine-600 bg-pine-50' : 'border-slate-200 hover:border-slate-300'}`}
                      data-testid={`rx-optica-template-${t.value}`}>
                      <span className="text-sm font-semibold text-slate-800 block">{t.label}</span>
                      <span className="text-xs text-slate-500">{t.desc}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-slate-500 uppercase">Tipografia</Label>
                  <Select value={rxStyleOptica.font} onValueChange={(v) => setRxStyleOptica({...rxStyleOptica, font: v})}>
                    <SelectTrigger data-testid="settings-rx-optica-font"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {PRESCRIPTION_FONTS.map(f => <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-slate-500 uppercase">Tamano</Label>
                  <Select value={rxStyleOptica.size} onValueChange={(v) => setRxStyleOptica({...rxStyleOptica, size: v})}>
                    <SelectTrigger data-testid="settings-rx-optica-size"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {PRESCRIPTION_SIZES.map(s => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-slate-500 uppercase">Mostrar Logo</Label>
                  <Select value={rxStyleOptica.show_logo ? 'si' : 'no'} onValueChange={(v) => setRxStyleOptica({...rxStyleOptica, show_logo: v === 'si'})}>
                    <SelectTrigger data-testid="settings-rx-optica-logo"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="si">Si, mostrar logo</SelectItem>
                      <SelectItem value="no">No mostrar logo</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-slate-500 uppercase">Texto de Encabezado</Label>
                  <Input value={rxStyleOptica.header_text} onChange={(e) => setRxStyleOptica({...rxStyleOptica, header_text: e.target.value})} placeholder="Ej: Optica Altavista - Su Vision es Nuestra Prioridad" data-testid="settings-rx-optica-header" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-slate-500 uppercase">Texto de Pie de Pagina</Label>
                  <Input value={rxStyleOptica.footer_text} onChange={(e) => setRxStyleOptica({...rxStyleOptica, footer_text: e.target.value})} placeholder="Ej: Valida por 6 meses a partir de la fecha" data-testid="settings-rx-optica-footer" />
                </div>
              </div>
            </div>

            {/* Recetas Medicas */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 pb-2 border-b">
                <Pill className="w-4 h-4 text-slate-600" />
                <h3 className="text-sm font-semibold text-slate-700">Recetas de Medicamentos</h3>
              </div>
              <div>
                <Label className="text-xs font-semibold text-slate-500 uppercase mb-2 block">Plantilla Visual</Label>
                <div className="grid grid-cols-3 gap-3">
                  {PRESCRIPTION_TEMPLATES.map(t => (
                    <button key={t.value} type="button" onClick={() => setRxStyleMedica({...rxStyleMedica, template: t.value})}
                      className={`p-3 rounded-lg border-2 text-left transition-all ${rxStyleMedica.template === t.value ? 'border-pine-600 bg-pine-50' : 'border-slate-200 hover:border-slate-300'}`}
                      data-testid={`rx-medica-template-${t.value}`}>
                      <span className="text-sm font-semibold text-slate-800 block">{t.label}</span>
                      <span className="text-xs text-slate-500">{t.desc}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-slate-500 uppercase">Tipografia</Label>
                  <Select value={rxStyleMedica.font} onValueChange={(v) => setRxStyleMedica({...rxStyleMedica, font: v})}>
                    <SelectTrigger data-testid="settings-rx-medica-font"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {PRESCRIPTION_FONTS.map(f => <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-slate-500 uppercase">Tamano</Label>
                  <Select value={rxStyleMedica.size} onValueChange={(v) => setRxStyleMedica({...rxStyleMedica, size: v})}>
                    <SelectTrigger data-testid="settings-rx-medica-size"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {PRESCRIPTION_SIZES.map(s => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-slate-500 uppercase">Mostrar Logo</Label>
                  <Select value={rxStyleMedica.show_logo ? 'si' : 'no'} onValueChange={(v) => setRxStyleMedica({...rxStyleMedica, show_logo: v === 'si'})}>
                    <SelectTrigger data-testid="settings-rx-medica-logo"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="si">Si, mostrar logo</SelectItem>
                      <SelectItem value="no">No mostrar logo</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-slate-500 uppercase">Texto de Encabezado</Label>
                  <Input value={rxStyleMedica.header_text} onChange={(e) => setRxStyleMedica({...rxStyleMedica, header_text: e.target.value})} placeholder="Ej: Recetario Medico - Dr. Nombre" data-testid="settings-rx-medica-header" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-slate-500 uppercase">Texto de Pie de Pagina</Label>
                  <Input value={rxStyleMedica.footer_text} onChange={(e) => setRxStyleMedica({...rxStyleMedica, footer_text: e.target.value})} placeholder="Ej: Receta valida por 30 dias" data-testid="settings-rx-medica-footer" />
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button onClick={handleSaveRxStyle} className="bg-pine-900 hover:bg-pine-700" disabled={saving} data-testid="save-rx-style-btn">
                <Save className="w-4 h-4 mr-1.5" /> {saving ? 'Guardando...' : 'Guardar Estilos'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Exportacion de Datos */}
        {!isSuperAdmin && (
          <Card className="border-slate-200/80" data-testid="data-export-card">
            <CardHeader>
              <CardTitle className="font-heading text-lg flex items-center gap-2">
                <Database className="w-5 h-5 text-blue-700" />
                Exportacion de Base de Datos
              </CardTitle>
              <p className="text-sm text-slate-500 mt-1">
                Descarga una copia completa de todos los datos de tu optica en un solo archivo Excel.
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                <div className="flex items-center gap-2 text-slate-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                  Pacientes, citas y consultas
                </div>
                <div className="flex items-center gap-2 text-slate-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                  Recetas oftalmicas, contacto y medicas
                </div>
                <div className="flex items-center gap-2 text-slate-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                  Inventario, stock y movimientos
                </div>
                <div className="flex items-center gap-2 text-slate-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                  Ventas, cotizaciones y finanzas
                </div>
                <div className="flex items-center gap-2 text-slate-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                  Proveedores y sucursales
                </div>
                <div className="flex items-center gap-2 text-slate-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                  Usuarios (sin contrase&#241;as)
                </div>
              </div>

              <div className="p-3 rounded-lg bg-amber-50/60 border border-amber-200/60 text-xs text-amber-900">
                <strong>Importante:</strong> Este archivo contiene informacion clinica y personal confidencial.
                Almacenalo en un lugar seguro y nunca lo compartas con terceros no autorizados.
              </div>

              <div className="flex justify-end pt-1">
                <Button
                  onClick={handleExportDatabase}
                  disabled={exportingDb}
                  className="bg-blue-700 hover:bg-blue-800 text-white"
                  data-testid="export-database-btn"
                >
                  {exportingDb ? (
                    <>
                      <div className="w-4 h-4 mr-2 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Generando...
                    </>
                  ) : (
                    <>
                      <Download className="w-4 h-4 mr-2" />
                      Descargar Base de Datos (Excel)
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Permisos por Rol (admin only) */}
        {user?.role === 'admin' && <RolePermissionsSection />}

        {/* Documentacion (admin y superadmin) */}
        {(user?.role === 'admin' || user?.role === 'superadmin') && (
          <Card className="border-slate-200/80" data-testid="documentation-card">
            <CardHeader>
              <CardTitle className="font-heading text-lg flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-purple-700" />
                Documentacion
              </CardTitle>
              <p className="text-sm text-slate-500 mt-1">
                Guia completa de uso de Cortexia Optical con instrucciones detalladas para cada rol.
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                <div className="flex items-center gap-2 text-slate-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                  Configuracion inicial de la optica
                </div>
                <div className="flex items-center gap-2 text-slate-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                  Guia paso a paso para el Vendedor
                </div>
                <div className="flex items-center gap-2 text-slate-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                  Guia paso a paso para el Doctor
                </div>
                <div className="flex items-center gap-2 text-slate-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                  Modulo especial de Jornadas
                </div>
                <div className="flex items-center gap-2 text-slate-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                  Buenas practicas y consejos
                </div>
                <div className="flex items-center gap-2 text-slate-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                  Contacto y soporte tecnico
                </div>
              </div>

              <div className="p-3 rounded-lg bg-purple-50/60 border border-purple-200/60 text-xs text-purple-900">
                <strong>Ideal para:</strong> Onboarding de nuevos empleados, capacitacion de equipo,
                material comercial para prospectos. Documento profesional listo para compartir.
              </div>

              <div className="flex flex-col sm:flex-row justify-end gap-2 pt-1">
                <Button
                  onClick={openShareDialog}
                  variant="outline"
                  className="border-emerald-600 text-emerald-700 hover:bg-emerald-50"
                  data-testid="share-user-guide-btn"
                >
                  <MessageCircle className="w-4 h-4 mr-2" />
                  Compartir personalizada por WhatsApp
                </Button>
                <Button
                  onClick={handleDownloadUserGuide}
                  disabled={downloadingGuide}
                  className="bg-purple-700 hover:bg-purple-800 text-white"
                  data-testid="download-user-guide-btn"
                >
                  {downloadingGuide ? (
                    <>
                      <div className="w-4 h-4 mr-2 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Generando...
                    </>
                  ) : (
                    <>
                      <Download className="w-4 h-4 mr-2" />
                      Descargar Guia de Usuario (PDF)
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Dialog: Compartir guia personalizada por WhatsApp */}
        <Dialog open={shareDialogOpen} onOpenChange={setShareDialogOpen}>
          <DialogContent className="max-w-lg" data-testid="share-guide-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <MessageCircle className="w-5 h-5 text-emerald-700" />
                Compartir guia personalizada
              </DialogTitle>
              <DialogDescription>
                Personaliza la portada del PDF con el nombre del prospecto y comparte el enlace por WhatsApp Web.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <div>
                <Label htmlFor="prospect-name" className="text-sm font-medium text-slate-700">
                  Nombre de la optica prospecto *
                </Label>
                <Input
                  id="prospect-name"
                  data-testid="share-prospect-name-input"
                  placeholder="Ej. Optica Vision de Xela"
                  value={shareForm.prospect_name}
                  onChange={(e) => {
                    setShareForm({ ...shareForm, prospect_name: e.target.value });
                    setShareResult(null); // reset link cuando cambia el nombre
                  }}
                  maxLength={80}
                  className="mt-1"
                />
                <p className="text-xs text-slate-500 mt-1">
                  Aparecera en la portada del PDF (max 80 caracteres).
                </p>
              </div>

              {!shareResult && (
                <div className="flex gap-2">
                  <Button
                    onClick={handleGenerateShareLink}
                    disabled={generatingLink || !shareForm.prospect_name.trim()}
                    className="bg-purple-700 hover:bg-purple-800 text-white flex-1"
                    data-testid="generate-share-link-btn"
                  >
                    {generatingLink ? (
                      <>
                        <div className="w-4 h-4 mr-2 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Generando enlace...
                      </>
                    ) : (
                      <>
                        <LinkIcon className="w-4 h-4 mr-2" />
                        Generar enlace personalizado
                      </>
                    )}
                  </Button>
                  <Button
                    onClick={downloadPersonalizedGuide}
                    disabled={downloadingGuide || !shareForm.prospect_name.trim()}
                    variant="outline"
                    data-testid="download-personalized-btn"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Solo descargar
                  </Button>
                </div>
              )}

              {shareResult && (
                <>
                  <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200" data-testid="share-link-result">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="text-xs text-emerald-800 font-medium">
                        Enlace listo (valido 30 dias)
                      </div>
                      <button
                        onClick={copyShareUrl}
                        className="text-xs text-emerald-700 hover:text-emerald-900 flex items-center gap-1"
                        data-testid="copy-share-url-btn"
                      >
                        <Copy className="w-3 h-3" /> Copiar
                      </button>
                    </div>
                    <div className="text-xs text-slate-700 break-all font-mono bg-white p-2 rounded border border-emerald-200">
                      {shareResult.url}
                    </div>
                  </div>

                  <div>
                    <Label htmlFor="wa-phone" className="text-sm font-medium text-slate-700">
                      Numero WhatsApp del prospecto
                    </Label>
                    <Input
                      id="wa-phone"
                      data-testid="share-phone-input"
                      placeholder="Ej. 55551234 (Guatemala) o 502xxxxxxxx"
                      value={shareForm.phone}
                      onChange={(e) => setShareForm({ ...shareForm, phone: e.target.value })}
                      className="mt-1"
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      Solo digitos. Guatemala: 8 digitos (agregamos 502 automatico).
                    </p>
                  </div>

                  <div>
                    <Label htmlFor="wa-message" className="text-sm font-medium text-slate-700">
                      Mensaje (opcional)
                    </Label>
                    <Textarea
                      id="wa-message"
                      data-testid="share-message-input"
                      rows={4}
                      placeholder="Deja vacio para usar mensaje sugerido con el enlace incluido"
                      value={shareForm.message}
                      onChange={(e) => setShareForm({ ...shareForm, message: e.target.value })}
                      className="mt-1"
                    />
                  </div>
                </>
              )}
            </div>

            <DialogFooter className="gap-2">
              <Button
                variant="outline"
                onClick={() => setShareDialogOpen(false)}
                data-testid="share-dialog-close-btn"
              >
                Cerrar
              </Button>
              {shareResult && (
                <Button
                  onClick={sendShareViaWhatsApp}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  data-testid="send-whatsapp-btn"
                >
                  <MessageCircle className="w-4 h-4 mr-2" />
                  Abrir WhatsApp
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Seguridad y Cumplimiento */}
        <Card className="border-slate-200/80" data-testid="security-compliance-card">
          <CardHeader>
            <CardTitle className="font-heading text-lg flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-700" />
              Seguridad y Cumplimiento
            </CardTitle>
            <p className="text-sm text-slate-500 mt-1">
              Tu información clínica y de pacientes está protegida con las mejores prácticas de la industria.
            </p>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <SecurityFeature
                icon={<Lock className="w-5 h-5" />}
                title="Contraseñas con bcrypt"
                desc="Las contraseñas se almacenan con hash bcrypt (salt único por usuario). Imposibles de revertir incluso si la base de datos fuera comprometida."
              />
              <SecurityFeature
                icon={<KeyRound className="w-5 h-5" />}
                title="Autenticación JWT + cookies HttpOnly"
                desc="Tokens firmados con HS256, transmitidos en cookies HttpOnly y Secure. No accesibles desde JavaScript: protección contra robo por XSS."
              />
              <SecurityFeature
                icon={<UsersIcon className="w-5 h-5" />}
                title="Aislamiento multi-empresa"
                desc="Cada óptica solo accede a sus propios datos. Aislamiento estricto por company_id en todas las consultas a la base de datos."
              />
              <SecurityFeature
                icon={<Activity className="w-5 h-5" />}
                title="Rate limiting y anti brute-force"
                desc="Login limitado a 10 intentos/min por IP. Bloqueo automático tras 5 fallos consecutivos. Defensa en profundidad contra ataques."
              />
              <SecurityFeature
                icon={<ShieldCheck className="w-5 h-5" />}
                title="Política de contraseñas robusta"
                desc="Mínimo 8 caracteres con mayúsculas, minúsculas y dígitos. Sesiones revocables al cambiar la contraseña."
              />
              <SecurityFeature
                icon={<Server className="w-5 h-5" />}
                title="Infraestructura cifrada"
                desc="HTTPS/TLS en todo el tráfico. MongoDB Atlas con cifrado en reposo. Backups automáticos diarios."
              />
            </div>

            <div className="mt-6 p-4 bg-emerald-50/50 border border-emerald-200/60 rounded-lg">
              <p className="text-sm text-slate-700">
                <strong className="text-emerald-800">Tus datos clínicos son críticos.</strong> Cortexia Optical cumple con
                principios de privacidad para datos de salud: consultas, recetas, diagnósticos y datos personales
                de pacientes nunca son compartidos con terceros y se acceden únicamente con autenticación válida.
              </p>
            </div>

            <div className="mt-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-4 border-t border-slate-100">
              <div className="text-xs text-slate-500">
                ¿Detectaste un problema de seguridad? Reporta de forma responsable a{' '}
                <a href="mailto:info@cortexiagt.com" className="text-pine-700 underline font-medium">
                  info@cortexiagt.com
                </a>
              </div>
              <a
                href="#"
                onClick={(e) => { e.preventDefault(); handleDownloadManifesto(); }}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium transition-colors shrink-0 cursor-pointer"
                data-testid="download-security-manifesto"
              >
                <FileText className="w-4 h-4" />
                Descargar Manifiesto PDF
              </a>
            </div>
          </CardContent>
        </Card>

        {/* SESIONES ACTIVAS (para admin: ve todas del equipo; para otros: solo las suyas) */}
        <Card className="border-slate-200/80" data-testid="sessions-card">
          <CardHeader>
            <CardTitle className="font-heading text-lg flex items-center gap-2">
              <Monitor className="w-5 h-5 text-pine-700" />
              Sesiones Activas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <SessionsPanel />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function SecurityFeature({ icon, title, desc }) {
  return (
    <div className="flex gap-3 p-4 border border-slate-200/80 rounded-lg bg-white hover:border-emerald-200 hover:bg-emerald-50/30 transition-colors" data-testid={`security-feature-${title.toLowerCase().replace(/\s+/g, '-')}`}>
      <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center">
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <h4 className="text-sm font-semibold text-slate-900 mb-1">{title}</h4>
        <p className="text-xs text-slate-600 leading-relaxed">{desc}</p>
      </div>
    </div>
  );
}
