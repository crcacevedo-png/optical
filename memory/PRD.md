# PRD: Cortexia Optical - Plataforma SaaS para Opticas

## Problema Original
Plataforma web SaaS multi-tenant para administracion integral de opticas en Latinoamerica.

## Arquitectura
- Frontend: React 19 + Tailwind CSS + Shadcn UI
- Backend: FastAPI + Motor (MongoDB async) - Modular (19 archivos de rutas)
- Auth: JWT con cookies httpOnly
- Moneda: Quetzal (GTQ) | Idioma: Espanol

## Estructura Backend
```
/app/backend/
├── server.py          (setup, middleware, startup/seed)
├── db.py, auth_utils.py, models.py
├── routes/
│   ├── auth.py, companies.py, settings.py, branches.py
│   ├── patients.py, appointments.py, consultations.py
│   ├── prescriptions.py (+ PDF generation)
│   ├── inventory.py, sales.py, quotations.py
│   ├── finance.py, reports.py, plans.py
│   ├── users.py, suppliers.py
```

## Lo Implementado

### Sistema de Planes (Abril 2026)
- 3 planes por defecto: Free (Q0, 1 suc, 50 pac), Basic (Q299, 3 suc, 500 pac), Enterprise (Q799, ilimitado)
- Modulos opcionales por plan: inventario, ventas, proveedores, finanzas
- CRUD completo de planes (SuperAdmin)
- Asignacion de plan a empresas
- Sidebar filtrado por modulos del plan
- Alertas de limite en Dashboard (admin)
- Validacion de limites al crear pacientes/sucursales (403 si excede)
- Badges de plan y alertas en panel de opticas (SuperAdmin)

### Modulos Funcionales
- Auth: JWT login, register, logout, refresh, brute force
- Login Page Premium: Split-screen, red neuronal CSS, glassmorphism
- Panel SuperAdmin: CRUD Opticas + Sucursales + Usuarios + Planes
- Dashboard: estadisticas + financieros + citas + alertas + alertas de plan
- Pacientes: lista + busqueda + paginacion + detalle + eliminar soft
- Consultas Opticas: Ficha clinica completa (4 secciones)
- Recetas: 3 tipos + 3 estilos visuales en media carta horizontal
- Busqueda Global (Ctrl+K)
- Agenda: 3 vistas + CRUD citas + filtro sucursal
- Cotizaciones: CRUD + estados + convertir a venta + PDF
- Inventario: productos + stock + movimientos + alertas (modulo opcional)
- Ventas: POS + metodos de pago + filtro sucursal (modulo opcional)
- Proveedores: CRUD con categorias (modulo opcional)
- Finanzas: ingresos/egresos + resumen + categorias (modulo opcional)
- Reportes por Sucursal: Filtro dropdown para admins
- Configuracion: Datos empresa, Logo, Estilos de recetas

## Backlog Priorizado

### P1 - Alta
- [ ] Facturacion formal (IVA Guatemala)

### P2 - Media
- [ ] Exportacion de reportes a Excel
- [ ] Portal del paciente (ver receta, proxima cita)

### P3 - Baja
- [ ] Recordatorios citas (WhatsApp/SMS)
- [ ] Marketing (origen de pacientes, segmentacion)
