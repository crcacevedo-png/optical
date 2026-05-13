# PRD: Cortexia Optical - Plataforma SaaS para Opticas

## Problema Original
Plataforma web SaaS multi-tenant para administracion integral de opticas en Latinoamerica.

## Arquitectura
- Frontend: React 19 + Tailwind CSS + Shadcn UI + Recharts
- Backend: FastAPI + Motor (MongoDB async) - Modular (21 archivos de rutas)
- Auth: JWT con cookies httpOnly
- Moneda: Quetzal (GTQ) | Idioma: Espanol

## Lo Implementado

### Modulo de Comunicacion (Mayo 2026)
- CRUD de anuncios para SuperAdmin (titulo, mensaje, tipo, segmentacion)
- 3 tipos: Informativo (azul), Alerta (amarillo), Promocion (verde)
- Segmentacion por plan (Free/Basic/Enterprise) y por ciudad
- Fecha de vigencia (inicio/fin)
- Toggle activo/inactivo
- Banners en dashboard de admins con colores segun tipo
- Boton X para descartar por sesion
- Filtrado automatico: cada admin solo ve anuncios relevantes a su plan

### Dashboard SuperAdmin
- 4 KPIs, graficas pie/barras, alertas de limite, timeline cambios

### Sistema de Planes
- 3 planes, modulos opcionales, CRUD, historial de cambios

### Exportacion Excel
- 3 hojas: Resumen, Ventas, Finanzas

### Modulos Funcionales
- Auth, Login Premium, Panel SuperAdmin + Dashboard
- Pacientes, Consultas Opticas, Recetas (3 tipos, 3 estilos PDF)
- Busqueda Global (Ctrl+K), Agenda, Cotizaciones
- Inventario (con min stock editable), Ventas, Proveedores, Finanzas
- Reportes por Sucursal, Configuracion

## Backlog

### P1 - Alta
- [ ] Facturacion formal (IVA Guatemala)

### P2 - Media
- [ ] Portal del paciente (ver receta, proxima cita)

### P3 - Baja
- [ ] Recordatorios citas (WhatsApp/SMS)
- [ ] Marketing (origen de pacientes, segmentacion)
