/**
 * Dialogos extraidos de AdminOpticasPage.js para reducir su tamano.
 * Cada dialogo recibe su form + setter + handler explicitos por props.
 */
import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Store, Phone, Shield, Eye, EyeOff } from 'lucide-react';

// ═══════════════════════════════════════════════════════════════════
// Nueva Optica
// ═══════════════════════════════════════════════════════════════════
export function CreateCompanyDialog({ open, onOpenChange, form, setForm, onSubmit, showPassword, setShowPassword }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nueva Optica</DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="p-3 bg-slate-50 rounded-lg">
            <p className="text-xs font-semibold text-slate-500 uppercase mb-3">Datos de la Empresa</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs">Nombre de la Optica *</Label>
                <Input value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} required data-testid="company-name" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Razon Social</Label>
                <Input value={form.legal_name} onChange={(e) => setForm({...form, legal_name: e.target.value})} data-testid="company-legal" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">NIT</Label>
                <Input value={form.tax_id} onChange={(e) => setForm({...form, tax_id: e.target.value})} data-testid="company-nit" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Telefono *</Label>
                <Input value={form.phone} onChange={(e) => setForm({...form, phone: e.target.value})} required data-testid="company-phone" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Email *</Label>
                <Input type="email" value={form.email} onChange={(e) => setForm({...form, email: e.target.value})} required data-testid="company-email" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Direccion</Label>
                <Input value={form.address} onChange={(e) => setForm({...form, address: e.target.value})} data-testid="company-address" />
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
                <Input value={form.contact_name} onChange={(e) => setForm({...form, contact_name: e.target.value})} data-testid="company-contact-name" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Telefono</Label>
                <Input value={form.contact_phone} onChange={(e) => setForm({...form, contact_phone: e.target.value})} data-testid="company-contact-phone" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Email</Label>
                <Input type="email" value={form.contact_email} onChange={(e) => setForm({...form, contact_email: e.target.value})} data-testid="company-contact-email" />
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
                <Input value={form.admin_name} onChange={(e) => setForm({...form, admin_name: e.target.value})} required data-testid="company-admin-name" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Email del Admin *</Label>
                <Input type="email" value={form.admin_email} onChange={(e) => setForm({...form, admin_email: e.target.value})} required data-testid="company-admin-email" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Contrasena del Admin *</Label>
                <div className="relative">
                  <Input type={showPassword ? "text" : "password"} value={form.admin_password} onChange={(e) => setForm({...form, admin_password: e.target.value})} required className="pr-10" data-testid="company-admin-password" />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600" data-testid="toggle-company-password">
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" className="bg-pine-700 hover:bg-pine-800" data-testid="save-company-btn">
              <Store className="w-4 h-4 mr-2" /> Crear Optica
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Nueva Sucursal
// ═══════════════════════════════════════════════════════════════════
export function CreateBranchDialog({ open, onOpenChange, form, setForm, onSubmit, companyName }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nueva Sucursal para {companyName}</DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Nombre *</Label>
            <Input value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} required data-testid="sa-branch-name" />
          </div>
          <div className="space-y-2">
            <Label>Direccion *</Label>
            <Input value={form.address} onChange={(e) => setForm({...form, address: e.target.value})} required data-testid="sa-branch-address" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Telefono *</Label>
              <Input value={form.phone} onChange={(e) => setForm({...form, phone: e.target.value})} required data-testid="sa-branch-phone" />
            </div>
            <div className="space-y-2">
              <Label>Email</Label>
              <Input type="email" value={form.email} onChange={(e) => setForm({...form, email: e.target.value})} data-testid="sa-branch-email" />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" className="bg-pine-700 hover:bg-pine-800" data-testid="save-branch-btn">Crear Sucursal</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Nuevo Usuario
// ═══════════════════════════════════════════════════════════════════
export function CreateUserDialog({ open, onOpenChange, form, setForm, onSubmit, showPassword, setShowPassword, companyName, branches }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nuevo Usuario para {companyName}</DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Nombre *</Label>
            <Input value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} required data-testid="sa-user-name" />
          </div>
          <div className="space-y-2">
            <Label>Email *</Label>
            <Input type="email" value={form.email} onChange={(e) => setForm({...form, email: e.target.value})} required data-testid="sa-user-email" />
          </div>
          <div className="space-y-2">
            <Label>Contrasena *</Label>
            <div className="relative">
              <Input type={showPassword ? "text" : "password"} value={form.password} onChange={(e) => setForm({...form, password: e.target.value})} required className="pr-10" data-testid="sa-user-password" />
              <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600" data-testid="toggle-user-password">
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Rol</Label>
              <Select value={form.role} onValueChange={(v) => setForm({...form, role: v})}>
                <SelectTrigger data-testid="sa-user-role"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="user">Atencion al Cliente</SelectItem>
                  <SelectItem value="admin">Administrador</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Sucursal</Label>
              <Select value={form.branch_id} onValueChange={(v) => setForm({...form, branch_id: v})}>
                <SelectTrigger data-testid="sa-user-branch"><SelectValue placeholder="Sin asignar" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Sin asignar</SelectItem>
                  {branches.map((b) => (
                    <SelectItem key={b._id} value={b._id}>{b.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" className="bg-pine-700 hover:bg-pine-800" data-testid="save-user-btn">Crear Usuario</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Editar Optica
// ═══════════════════════════════════════════════════════════════════
export function EditCompanyDialog({ open, onOpenChange, form, setForm, onSubmit }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="edit-company-dialog">
        <DialogHeader>
          <DialogTitle>Modificar Optica</DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-500 uppercase">Nombre Comercial</Label>
              <Input value={form.name || ''} onChange={(e) => setForm({...form, name: e.target.value})} data-testid="edit-company-name" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-500 uppercase">Razon Social</Label>
              <Input value={form.legal_name || ''} onChange={(e) => setForm({...form, legal_name: e.target.value})} data-testid="edit-company-legal" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-500 uppercase">NIT</Label>
              <Input value={form.tax_id || ''} onChange={(e) => setForm({...form, tax_id: e.target.value})} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-500 uppercase">Telefono</Label>
              <Input value={form.phone || ''} onChange={(e) => setForm({...form, phone: e.target.value})} />
            </div>
            <div className="space-y-1.5 col-span-2">
              <Label className="text-xs font-semibold text-slate-500 uppercase">Direccion</Label>
              <Input value={form.address || ''} onChange={(e) => setForm({...form, address: e.target.value})} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-500 uppercase">Email</Label>
              <Input value={form.email || ''} onChange={(e) => setForm({...form, email: e.target.value})} />
            </div>
          </div>
          <div className="border-t pt-3">
            <p className="text-xs font-semibold text-slate-400 uppercase mb-3">Persona de Contacto</p>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold text-slate-500 uppercase">Nombre</Label>
                <Input value={form.contact_name || ''} onChange={(e) => setForm({...form, contact_name: e.target.value})} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold text-slate-500 uppercase">Telefono</Label>
                <Input value={form.contact_phone || ''} onChange={(e) => setForm({...form, contact_phone: e.target.value})} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold text-slate-500 uppercase">Email</Label>
                <Input value={form.contact_email || ''} onChange={(e) => setForm({...form, contact_email: e.target.value})} />
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" className="bg-pine-700 hover:bg-pine-800" data-testid="save-edit-company-btn">Guardar Cambios</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
