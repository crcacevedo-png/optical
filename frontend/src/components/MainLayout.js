import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate, Outlet } from 'react-router-dom';
import { api, useAuth } from '../context/AuthContext';
import { GlobalSearch } from './GlobalSearch';
import { NotificationBell } from './NotificationBell';
import { OfflineIndicator } from './OfflineIndicator';
import { ChangeMyPasswordDialog } from './ChangeMyPasswordDialog';
import { ReactivationFeedbackDialog } from './retention/ReactivationFeedbackDialog';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { 
  LayoutDashboard, Users, Calendar, FileText, Package, 
  ShoppingCart, DollarSign, Building2, UserCog, BarChart3,
  Glasses, LogOut, Menu, X, ChevronDown, ClipboardList, Store, Eye, Settings, Truck, CreditCard, Megaphone, Key, ShieldAlert, Rocket, Activity, HandCoins, LifeBuoy, Tent, Sparkles, Mail, UserPlus, Banknote
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';

export default function MainLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showPasswordDialog, setShowPasswordDialog] = useState(false);
  const [payablesBadge, setPayablesBadge] = useState(0);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const isSuperAdmin = user?.role === 'superadmin';

  const isAdmin = user?.role === 'admin';

  const planModules = user?.plan_modules || [];
  const hasPlanInfo = user?.plan_name !== undefined;
  const hasModule = (mod) => !hasPlanInfo || planModules.includes(mod);

  // Permisos por rol (config del admin). null = sin restriccion (admin).
  const allowedMenuItems = user?.allowed_menu_items;
  const canAccess = (key) => !allowedMenuItems || allowedMenuItems.includes(key);

  useEffect(() => {
    if (user && user.role !== 'superadmin' && hasModule('finanzas') && canAccess('payables')) {
      api.get('/api/finance/payables/alerts')
        .then((r) => setPayablesBadge((r.data?.overdue?.count || 0) + (r.data?.due_soon?.count || 0)))
        .catch(() => setPayablesBadge(0));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const navItems = isSuperAdmin ? [
    { path: '/admin/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/admin/opticas', icon: Store, label: 'Opticas' },
    { path: '/admin/retencion', icon: Sparkles, label: 'Retencion' },
    { path: '/admin/planes', icon: CreditCard, label: 'Planes' },
    { path: '/admin/comunicacion', icon: Megaphone, label: 'Comunicacion' },
    { path: '/admin/soporte', icon: LifeBuoy, label: 'Soporte' },
    { path: '/admin/audit', icon: ShieldAlert, label: 'Auditoria' },
    { path: '/admin/health', icon: Activity, label: 'Salud Sistema' },
    { path: '/admin/correos', icon: Mail, label: 'Correos' },
    { path: '/admin/leads', icon: UserPlus, label: 'Solicitudes' },
    { path: '/users', icon: UserCog, label: 'Usuarios' },
    { path: '/settings', icon: Settings, label: 'Configuracion' },
  ] : [
    // Inicio rapido primero (solo admin)
    ...(isAdmin ? [{ path: '/onboarding', icon: Rocket, label: 'Inicio rapido' }] : []),
    { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', key: 'dashboard' },
    { path: '/agenda', icon: Calendar, label: 'Agenda', key: 'agenda' },
    { path: '/patients', icon: Users, label: 'Pacientes', key: 'patients' },
    { path: '/consultations', icon: Eye, label: 'Consultas', key: 'consultations' },
    { path: '/prescriptions', icon: FileText, label: 'Recetas', key: 'prescriptions' },
    ...(hasModule('ventas') ? [{ path: '/sales', icon: ShoppingCart, label: 'Punto de Venta', key: 'sales' }] : []),
    ...(hasModule('ventas') ? [{ path: '/receivables', icon: HandCoins, label: 'Cuentas por Cobrar', key: 'receivables' }] : []),
    { path: '/quotations', icon: ClipboardList, label: 'Cotizaciones', key: 'quotations' },
    ...(hasModule('inventario') ? [{ path: '/inventory', icon: Package, label: 'Inventario', key: 'inventory' }] : []),
    ...(hasModule('jornadas') ? [{ path: '/jornadas', icon: Tent, label: 'Jornadas', key: 'jornadas' }] : []),
    ...(hasModule('finanzas') ? [{ path: '/finance', icon: DollarSign, label: 'Finanzas', key: 'finance' }] : []),
    ...(hasModule('finanzas') ? [{ path: '/payables', icon: Banknote, label: 'Cuentas por Pagar', key: 'payables', badge: payablesBadge }] : []),
    ...(hasModule('proveedores') ? [{ path: '/suppliers', icon: Truck, label: 'Proveedores', key: 'suppliers' }] : []),
    ...(isAdmin ? [
      { path: '/reports', icon: BarChart3, label: 'Reportes' },
      {
        path: '/settings', icon: Settings, label: 'Configuracion',
        children: [
          { path: '/settings', icon: Building2, label: 'Perfil de la Optica' },
          { path: '/branches', icon: Store, label: 'Sucursales' },
          { path: '/users', icon: UserCog, label: 'Usuarios' },
          { path: '/my-plan', icon: CreditCard, label: 'Mi Plan' },
          { path: '/support', icon: LifeBuoy, label: 'Soporte' },
        ],
      },
    ] : []),
    // Para roles no-admin (user/doctor), Soporte queda en el top level
    // porque no tienen acceso al menu Configuracion.
    ...(!isAdmin ? [{ path: '/support', icon: LifeBuoy, label: 'Soporte', key: 'support', alwaysShow: true }] : []),
  ].filter(item => item.alwaysShow || !item.key || canAccess(item.key));

  const NavLink = ({ item, mobile = false }) => {
    const isActive = location.pathname === item.path;
    const hasChildren = Array.isArray(item.children) && item.children.length > 0;
    const childActive = hasChildren && item.children.some((c) => location.pathname === c.path);
    const isOpen = isActive || childActive;
    return (
      <div>
        <Link
          to={item.path}
          onClick={() => mobile && setSidebarOpen(false)}
          className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
            isActive
              ? 'bg-pine-900 text-white'
              : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
          }`}
          data-testid={`nav-${item.path.replace(/\//g, '').replace('admin', 'admin-')}`}
        >
          <item.icon className="w-5 h-5" />
          <span>{item.label}</span>
          {item.badge > 0 && (
            <span
              className="ml-auto inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-red-500 text-white text-[11px] font-semibold"
              data-testid={`nav-badge-${item.path.replace(/\//g, '')}`}
            >
              {item.badge}
            </span>
          )}
        </Link>
        {hasChildren && isOpen && (
          <div className="mt-1 ml-4 pl-3 border-l border-slate-200 space-y-1" data-testid={`submenu-${item.label.toLowerCase()}`}>
            {item.children.map((child) => {
              const childIsActive = location.pathname === child.path;
              return (
                <Link
                  key={child.path}
                  to={child.path}
                  onClick={() => mobile && setSidebarOpen(false)}
                  className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                    childIsActive
                      ? 'bg-pine-50 text-pine-900 font-medium'
                      : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'
                  }`}
                  data-testid={`nav-${child.path.replace(/\//g, '')}`}
                >
                  <child.icon className="w-4 h-4" />
                  <span>{child.label}</span>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-[#FAFAFA] flex">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex w-64 flex-shrink-0 flex-col bg-white border-r border-slate-200 h-screen sticky top-0">
        {/* Logo */}
        <div className="p-5 border-b border-slate-100">
          <Link to="/dashboard" className="flex items-center justify-center">
            <img 
              src="https://customer-assets.emergentagent.com/job_eyecare-erp/artifacts/80lobcqc_logo%20cortexia%20optical%20transparente.png" 
              alt="Cortexia Optical" 
              className="h-40 object-contain"
            />
          </Link>
        </div>

        {/* Navigation */}
        <ScrollArea className="flex-1 px-3 py-4">
          <nav className="space-y-1">
            {navItems.map((item) => (
              <NavLink key={item.path} item={item} />
            ))}
          </nav>
        </ScrollArea>

        {/* User Info */}
        <div className="p-4 border-t border-slate-100">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-slate-50 transition-colors">
                <div className="w-9 h-9 rounded-full bg-pine-100 flex items-center justify-center text-pine-700 font-medium text-sm">
                  {user?.name?.split(' ').map(n => n[0]).join('').slice(0, 2) || 'U'}
                </div>
                <div className="flex-1 text-left min-w-0">
                  <p className="text-sm font-medium text-slate-900 truncate">{user?.name}</p>
                  <p className="text-xs text-slate-500 truncate">{user?.email}</p>
                </div>
                <ChevronDown className="w-4 h-4 text-slate-400" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <div className="px-2 py-1.5">
                <p className="text-xs text-slate-500">Sesión iniciada como</p>
                <p className="text-sm font-medium">{user?.role === 'admin' ? 'Administrador' : user?.role === 'superadmin' ? 'Super Admin' : user?.role === 'doctor' ? 'Doctor' : 'Atencion al Cliente'}</p>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => setShowPasswordDialog(true)} className="cursor-pointer" data-testid="change-my-password-btn">
                <Key className="w-4 h-4 mr-2" /> Cambiar mi contraseña
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout} className="text-red-600 cursor-pointer" data-testid="logout-btn">
                <LogOut className="w-4 h-4 mr-2" /> Cerrar Sesión
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      {/* Mobile Header & Sidebar */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-50 bg-white border-b border-slate-200">
        <div className="flex items-center justify-between p-4">
          <Link to="/dashboard" className="flex items-center gap-2">
            <img 
              src="https://customer-assets.emergentagent.com/job_eyecare-erp/artifacts/80lobcqc_logo%20cortexia%20optical%20transparente.png" 
              alt="Cortexia Optical" 
              className="h-24 object-contain"
            />
          </Link>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            data-testid="mobile-menu-btn"
          >
            {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </Button>
        </div>

        {/* Mobile Sidebar Overlay */}
        {sidebarOpen && (
          <div className="fixed inset-0 top-[65px] bg-black/50 z-40" onClick={() => setSidebarOpen(false)}>
            <div 
              className="w-72 bg-white h-full overflow-y-auto animate-slide-in"
              onClick={(e) => e.stopPropagation()}
            >
              <nav className="p-4 space-y-1">
                {navItems.map((item) => (
                  <NavLink key={item.path} item={item} mobile />
                ))}
              </nav>
              <div className="p-4 border-t border-slate-100">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-9 h-9 rounded-full bg-pine-100 flex items-center justify-center text-pine-700 font-medium text-sm">
                    {user?.name?.split(' ').map(n => n[0]).join('').slice(0, 2) || 'U'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 truncate">{user?.name}</p>
                    <p className="text-xs text-slate-500 truncate">{user?.email}</p>
                  </div>
                </div>
                <Button
                  variant="outline"
                  className="w-full mb-2"
                  onClick={() => { setShowPasswordDialog(true); setSidebarOpen(false); }}
                  data-testid="change-my-password-mobile-btn"
                >
                  <Key className="w-4 h-4 mr-2" /> Cambiar mi contraseña
                </Button>
                <Button
                  variant="outline"
                  className="w-full text-red-600 border-red-200 hover:bg-red-50"
                  onClick={handleLogout}
                >
                  <LogOut className="w-4 h-4 mr-2" /> Cerrar Sesión
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Main Content */}
      <main className="flex-1 lg:p-8 p-4 pt-[85px] lg:pt-8 min-h-screen">
        <div className="max-w-7xl mx-auto">
          <div className="flex justify-end items-center gap-3 mb-4">
            <OfflineIndicator />
            <NotificationBell />
            <GlobalSearch />
          </div>
          <Outlet />
        </div>
      </main>
      <ChangeMyPasswordDialog open={showPasswordDialog} onOpenChange={setShowPasswordDialog} />
      <ReactivationFeedbackDialog />
    </div>
  );
}
