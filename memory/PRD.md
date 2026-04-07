# PRD: Cortexia Optical - Plataforma SaaS para Opticas

## Problema Original
Plataforma web SaaS multi-tenant para administracion integral de opticas en Latinoamerica.

## Arquitectura
- Frontend: React 19 + Tailwind CSS + Shadcn UI
- Backend: FastAPI + Motor (MongoDB async)
- Auth: JWT con cookies httpOnly (secure=True, samesite=none)
- Moneda: Quetzal (GTQ) | Idioma: Espanol

## Lo Implementado (7 Abr 2026)

### Modulos Funcionales (100% testeados)
- **Auth**: JWT login, register, logout, refresh, brute force protection, auto-refresh interceptor
- **Panel SuperAdmin**: Gestion de Opticas + Sucursales + Usuarios por empresa
- **Dashboard**: 4 cards estadisticas + 3 cards financieros + proximas citas + alertas stock + **filtro por sucursal**
- **Pacientes**: lista + busqueda + detalle con tabs
- **Agenda**: 3 vistas (Dia/Semana/Mes) + crear citas + estados + **filtro por sucursal**
- **Recetas**: 3 tabs (anteojos, lentes de contacto, medicas) + PDF
- **Cotizaciones**: CRUD + estados + convertir a venta + PDF
- **Inventario**: productos + stock + movimientos + alertas + **filtro por sucursal**
- **Ventas**: POS con carrito + metodos de pago + **filtro por sucursal**
- **Finanzas**: ingresos/egresos + resumen mensual
- **Sucursales**: lista (admin) + gestion por empresa (superadmin)
- **Usuarios**: lista + crear + editar + activar/desactivar
- **BranchFilter**: componente reutilizable, se oculta si solo hay 1 sucursal

## Backlog Priorizado

### P1 - Alta
- [ ] Busqueda paginada en Pacientes
- [ ] Edicion de pacientes existentes
- [ ] Facturacion formal (IVA Guatemala)

### P2 - Media
- [ ] Dashboard financiero detallado
- [ ] Reportes por sucursal + Exportacion a Excel
- [ ] Recordatorios de citas
- [ ] Abonos a ventas pendientes UI

### P3 - Baja
- [ ] Recordatorios reemplazo lentes de contacto
- [ ] Marketing (origen de pacientes)
- [ ] Recuperacion de contrasena
- [ ] Gestion de proveedores
