# PRD: Cortexia Optical - Plataforma SaaS para Opticas

## Problema Original
Plataforma web SaaS multi-tenant para administracion integral de opticas en Latinoamerica.

## Arquitectura
- Frontend: React 19 + Tailwind CSS + Shadcn UI + Recharts
- Backend: FastAPI + Motor (MongoDB async) - Modular (20 archivos de rutas)
- Auth: JWT con cookies httpOnly
- Moneda: Quetzal (GTQ) | Idioma: Espanol

## Lo Implementado

### Dashboard SuperAdmin (Abril 2026)
- 4 KPIs: opticas activas (+nuevas este mes), pacientes totales, usuarios activos, revenue mensual estimado
- Grafica pie: opticas por plan
- Grafica barras: crecimiento de pacientes ultimos 6 meses
- Grafica barras horizontal: revenue estimado por plan
- Alertas: opticas cerca del limite con porcentajes (pacientes/sucursales)
- Timeline: cambios de plan recientes
- Redireccion automatica /dashboard -> /admin/dashboard para superadmin

### Sistema de Planes
- 3 planes: Free (Q0, 1 suc, 50 pac), Basic (Q299, 3 suc, 500 pac), Enterprise (Q799, ilimitado)
- Modulos opcionales: inventario, ventas, proveedores, finanzas
- CRUD planes, asignacion, sidebar filtrado, alertas limite, validacion
- Historial de cambios de plan con timeline visual

### Exportacion Excel
- Boton "Excel" en Reportes con 3 hojas: Resumen, Ventas, Finanzas

### Modulos Funcionales
- Auth, Login Premium, Panel SuperAdmin, Dashboard con alertas
- Pacientes, Consultas, Recetas (3 tipos, 3 estilos PDF)
- Busqueda Global (Ctrl+K), Agenda, Cotizaciones
- Inventario, Ventas, Proveedores, Finanzas (opcionales por plan)
- Reportes por Sucursal, Configuracion, Gestion de Proveedores

## Backlog

### P1 - Alta
- [ ] Facturacion formal (IVA Guatemala)

### P2 - Media
- [ ] Portal del paciente (ver receta, proxima cita)

### P3 - Baja
- [ ] Recordatorios citas (WhatsApp/SMS)
- [ ] Marketing (origen de pacientes, segmentacion)
