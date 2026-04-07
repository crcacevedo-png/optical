# PRD: Cortexia Optical - Plataforma SaaS para Opticas

## Problema Original
Plataforma web SaaS multi-tenant para administracion integral de opticas en Latinoamerica. Arquitectura multi-tenant (company_id, branch_id).

## Arquitectura
- Frontend: React 19 + Tailwind CSS + Shadcn UI
- Backend: FastAPI + Motor (MongoDB async)
- Auth: JWT con cookies httpOnly (secure=True, samesite=none)
- Moneda: Quetzal (GTQ) | Idioma: Espanol

## Lo Implementado (7 Abr 2026)

### Modulos Funcionales (100% testeados)
- **Auth**: JWT login, register, logout, refresh, brute force protection, auto-refresh interceptor
- **Panel SuperAdmin**: Gestion de Opticas (crear empresa + admin), Sucursales por empresa, Usuarios por empresa. Sidebar dedicado. Solo superadmin puede crear Opticas.
- **Dashboard**: 4 cards estadisticas + 3 cards financieros + proximas citas + alertas stock
- **Pacientes**: lista + busqueda + detalle con tabs (recetas, citas, compras, info)
- **Agenda**: 3 vistas (Dia/Semana/Mes) + crear citas + confirmar/completar/cancelar
- **Recetas**: 3 tabs (anteojos OD/OI, lentes de contacto, medicas) + PDF
- **Cotizaciones**: CRUD + estados + convertir a venta + PDF + descuento + notas + condiciones
- **Inventario**: productos + stock + movimientos + alertas stock bajo + filtro categoria
- **Ventas**: POS con carrito + grid de productos + metodos de pago
- **Finanzas**: ingresos/egresos + resumen mensual
- **Sucursales**: lista (admin) + gestion por empresa (superadmin)
- **Usuarios**: lista + crear + editar + activar/desactivar

### Roles y Permisos
- **SuperAdmin**: CRUD empresas/sucursales/usuarios globales. No ve modulos operativos.
- **Admin**: Gestion completa de su empresa y sucursales.
- **Usuario**: Operaciones diarias (ventas, citas, pacientes).

## Backlog Priorizado

### P1 - Alta
- [ ] Filtrado por branch_id en Agenda, Inventario y Ventas
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
