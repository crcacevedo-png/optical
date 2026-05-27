import React, { useState, useEffect, useCallback } from 'react';
import { api, formatApiErrorDetail, useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import { Settings, Building2, Upload, FileText, Save, ImageIcon, Glasses, Pill } from 'lucide-react';

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
      toast.error('Error al cargar configuracion');
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
      </div>
    </div>
  );
}
