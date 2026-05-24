# PRD: Cortexia Optical - Plataforma SaaS para Opticas

## Problema Original
Plataforma web SaaS multi-tenant para administracion integral de opticas en Latinoamerica.

## Arquitectura
- Frontend: React 19 + Tailwind CSS + Shadcn UI + Recharts
- Backend: FastAPI + Motor (MongoDB async) - Modular (21 archivos de rutas)
- Auth: JWT con cookies httpOnly | Moneda: GTQ | Idioma: Espanol

## Lo Implementado

### Dashboard SaaS SuperAdmin (Mayo 2026) - COMPLETO
**Revenue & Conversion:**
- MRR (Monthly Recurring Revenue), ARPU (Average Revenue Per User)
- Churn rate (opticas inactivas vs total)
- Funnel de conversion Free -> Basic -> Enterprise con upgrades/downgrades
- Revenue estimado por plan (grafica barras)

**Engagement:**
- Usuarios activos ultimos 7 y 30 dias (basado en actividad real: ventas, citas, consultas, pacientes)
- Top 5 opticas por actividad (pacientes + ventas + consultas, con ranking)
- Modulos mas usados: cuantas opticas tienen acceso a inventario, ventas, proveedores, finanzas

**Operativo:**
- Pacientes promedio por optica
- Volumen transaccional (ventas totales plataforma + mes actual)
- Crecimiento de pacientes 6 meses (area chart)
- Opticas cerca del limite con porcentajes
- Cambios de plan recientes (timeline)

### Otros Modulos
- Comunicacion: anuncios segmentados + metricas de visualizacion
- Planes: Free/Basic/Enterprise, modulos opcionales, historial
- Exportacion Excel, Reportes por Sucursal
- Auth, Login Premium, Pacientes, Consultas, Recetas (3 tipos, 3 estilos PDF)
- Busqueda Global, Agenda, Cotizaciones
- Inventario (min stock editable), Ventas, Proveedores, Finanzas
- Configuracion, Gestion Proveedores

## Backlog
### P1: Facturacion formal IVA Guatemala
### P2: Portal del paciente
### P3: Recordatorios WhatsApp/SMS, Marketing
