# PRD: OptiSaaS - Plataforma SaaS para Ópticas

## Problema Original
Desarrollar una plataforma web SaaS profesional, moderna, escalable y multi-empresa para la administración integral de ópticas en Latinoamérica. El sistema soporta desde una óptica hasta más de 1000, con arquitectura multi-tenant.

## Arquitectura
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI + Motor (MongoDB async)
- **Base de datos**: MongoDB
- **Autenticación**: JWT con cookies httpOnly
- **Moneda**: Quetzal (GTQ)
- **Idioma**: Español

## User Personas
1. **SuperAdmin**: Gestión global de empresas (ópticas)
2. **Administrador de Óptica**: Gestión completa de su empresa y sucursales
3. **Usuario/Vendedor**: Operaciones diarias (ventas, citas, pacientes)

## Core Requirements
- [x] Autenticación JWT multi-tenant
- [x] Dashboard con métricas en tiempo real
- [x] Gestión de pacientes con historial clínico
- [x] Agenda/Calendario de citas
- [x] Recetas de anteojos (OD/OI con PDF)
- [x] Recetas médicas (con PDF)
- [x] Inventario multi-sucursal
- [x] Punto de venta
- [x] Control de ingresos/egresos
- [x] Gestión de sucursales
- [x] Gestión de usuarios y roles
- [x] Reportes financieros
- [x] Datos demo para pruebas

## Lo Implementado (30 Mar 2026)
### Backend
- Autenticación JWT completa (login, register, logout, refresh, me)
- CRUD completo para: empresas, sucursales, pacientes, citas, recetas, inventario, ventas, finanzas, usuarios
- Generación de PDFs para recetas
- Dashboard con métricas
- Reportes de ventas y finanzas
- Seed de datos demo (Óptica Visión Clara)
- Protección brute force
- Índices MongoDB

### Frontend
- Página de login con diseño 50/50
- Dashboard con métricas y gráficos
- Gestión de pacientes (lista + detalle)
- Agenda con calendario semanal
- Recetas de anteojos (formulario OD/OI)
- Recetas médicas
- Inventario con alertas de stock
- Punto de venta con carrito
- Finanzas (ingresos/egresos)
- Sucursales
- Usuarios
- Reportes con gráficos (Recharts)
- Navegación responsive

## Backlog Priorizado

### P0 - Crítico
- [ ] Recuperación de contraseña (email)
- [ ] Validación de permisos más granular por rol

### P1 - Alta
- [ ] Edición de pacientes existentes
- [ ] Cotizaciones
- [ ] Facturación formal (IVA Guatemala)
- [ ] Abonos a ventas pendientes UI
- [ ] Gestión de proveedores

### P2 - Media
- [ ] Reportes por sucursal
- [ ] Exportación a Excel
- [ ] Historial de movimientos de inventario
- [ ] Recordatorios de citas (email/SMS)
- [ ] Marketing básico (origen de pacientes)

### P3 - Baja
- [ ] Multi-idioma
- [ ] Multi-moneda
- [ ] App móvil
- [ ] Integración con dispositivos ópticos

## Próximas Tareas
1. Implementar envío de emails para recuperación de contraseña
2. Agregar edición de pacientes
3. Sistema de cotizaciones
4. Facturación con IVA
5. Gestión de abonos desde UI

## Credenciales Demo
- Admin: admin@visionclara.gt / Demo123!
- Usuario: vendedor@visionclara.gt / Demo123!
- SuperAdmin: superadmin@opticasaas.com / Admin123!
