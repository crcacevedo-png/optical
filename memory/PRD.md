# PRD: Cortexia Optical - Plataforma SaaS para Opticas

## Problema Original
Plataforma web SaaS multi-tenant para administracion integral de opticas en Latinoamerica.

## Arquitectura
- Frontend: React 19 + Tailwind CSS + Shadcn UI
- Backend: FastAPI + Motor (MongoDB async) - Modular (19 archivos de rutas)
- Auth: JWT con cookies httpOnly
- Moneda: Quetzal (GTQ) | Idioma: Espanol

## Lo Implementado

### Sistema de Planes (Abril 2026)
- 3 planes: Free (Q0, 1 suc, 50 pac), Basic (Q299, 3 suc, 500 pac), Enterprise (Q799, ilimitado)
- Modulos opcionales: inventario, ventas, proveedores, finanzas
- CRUD planes, asignacion, sidebar filtrado, alertas limite, validacion al crear
- Historial de cambios de plan por empresa con timeline visual

### Exportacion Excel (Abril 2026)
- Boton "Excel" en pagina de Reportes
- Genera .xlsx con 3 hojas: Resumen, Ventas detalladas, Finanzas
- Respeta filtro de sucursal y rango de fechas
- Incluye nombres de pacientes, sucursales, metodos de pago

### Modulos Funcionales
- Auth, Login Premium, Panel SuperAdmin, Dashboard con alertas
- Pacientes, Consultas Opticas, Recetas (3 tipos, 3 estilos PDF)
- Busqueda Global (Ctrl+K), Agenda, Cotizaciones
- Inventario, Ventas, Proveedores, Finanzas (modulos opcionales por plan)
- Reportes por Sucursal, Configuracion

## Backlog Priorizado

### P1 - Alta
- [ ] Facturacion formal (IVA Guatemala)

### P2 - Media
- [ ] Portal del paciente (ver receta, proxima cita)

### P3 - Baja
- [ ] Recordatorios citas (WhatsApp/SMS)
- [ ] Marketing (origen de pacientes, segmentacion)
