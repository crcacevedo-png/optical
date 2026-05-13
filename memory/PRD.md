# PRD: Cortexia Optical - Plataforma SaaS para Opticas

## Problema Original
Plataforma web SaaS multi-tenant para administracion integral de opticas en Latinoamerica.

## Arquitectura
- Frontend: React 19 + Tailwind CSS + Shadcn UI + Recharts
- Backend: FastAPI + Motor (MongoDB async) - Modular (21 archivos de rutas)
- Auth: JWT con cookies httpOnly
- Moneda: Quetzal (GTQ) | Idioma: Espanol

## Lo Implementado

### Metricas de Anuncios (Mayo 2026)
- Tracking automatico de vistas al cargar dashboard del admin
- Tracking de descartes al cerrar banner con X
- Deduplicacion por empresa (una vista/descarte por optica por anuncio)
- Contadores inline en tabla de anuncios (vistas | descartes)
- Dialog detallado con: KPIs (vistas, descartes, tasa descarte %), lista de opticas con nombre, usuario y fecha

### Modulo de Comunicacion
- CRUD anuncios con segmentacion por plan y ciudad
- 3 tipos: Info, Alerta, Promocion
- Banners en dashboard de admins con colores segun tipo

### Dashboard SuperAdmin
- KPIs, graficas, alertas de limite, timeline cambios

### Sistema de Planes
- 3 planes, modulos opcionales, CRUD, historial

### Exportacion Excel + Reportes por Sucursal

### Modulos Funcionales
- Auth, Login Premium, Panel SuperAdmin
- Pacientes, Consultas, Recetas (3 tipos, 3 estilos PDF)
- Busqueda Global, Agenda, Cotizaciones
- Inventario (min stock editable), Ventas, Proveedores, Finanzas
- Configuracion, Gestion Proveedores

## Backlog

### P1
- [ ] Facturacion formal (IVA Guatemala)

### P2
- [ ] Portal del paciente

### P3
- [ ] Recordatorios WhatsApp/SMS
- [ ] Marketing (origen pacientes)
