# PRD: Cortexia Optical - Plataforma SaaS para Opticas

## Problema Original
Plataforma web SaaS multi-tenant para administracion integral de opticas en Latinoamerica.

## Arquitectura
- Frontend: React 19 + Tailwind CSS + Shadcn UI
- Backend: FastAPI + Motor (MongoDB async) - **Modular** (18 archivos)
- Auth: JWT con cookies httpOnly
- Moneda: Quetzal (GTQ) | Idioma: Espanol

## Estructura Backend (Refactorizado - Abril 2026)
```
/app/backend/
├── server.py          (~206 lineas - setup, middleware, startup/seed)
├── db.py              (MongoDB connection, serialize_doc, calculate_age)
├── auth_utils.py      (JWT, hash, get_current_user)
├── models.py          (Pydantic models)
├── routes/
│   ├── auth.py, companies.py, settings.py, branches.py
│   ├── patients.py, appointments.py, consultations.py
│   ├── prescriptions.py (+ PDF generation)
│   ├── inventory.py, sales.py, quotations.py
│   ├── finance.py, reports.py
│   ├── users.py, suppliers.py
```

## Lo Implementado

### Modulos Funcionales (100% testeados)
- **Auth**: JWT login, register, logout, refresh, brute force, auto-refresh
- **Login Page Premium**: Split-screen 50/50, red neuronal CSS, glassmorphism
- **Panel SuperAdmin**: CRUD Opticas + Sucursales + Usuarios. Logo por optica.
- **Dashboard**: estadisticas + financieros + citas + alertas
- **Pacientes**: lista + busqueda + paginacion + detalle con tabs + edicion + eliminar soft
- **Consultas Opticas**: Ficha clinica completa (4 secciones)
- **Recetas**: 3 tipos + 3 estilos visuales (Clasico, Moderno, Elegante) en media carta horizontal
- **Busqueda Global (Ctrl+K)**
- **Agenda**: 3 vistas + CRUD citas + filtro sucursal
- **Cotizaciones**: CRUD + estados + convertir a venta + PDF
- **Inventario**: productos + stock + movimientos + alertas + agregar stock rapido
- **Ventas**: POS + metodos de pago + filtro sucursal + descuento inventario
- **Finanzas**: ingresos/egresos + resumen + filtro sucursal + categorias
- **Sucursales y Usuarios**: gestion completa
- **Configuracion**: Datos empresa, Logo, Estilos de recetas
- **Reportes por Sucursal**: Filtro dropdown para admins
- **Gestion de Proveedores**: CRUD completo con categorias
- **Refactorizacion Backend**: server.py de 3066 a 206 lineas, 18 modulos

## Backlog Priorizado

### P1 - Alta
- [ ] Facturacion formal (IVA Guatemala)

### P2 - Media
- [ ] Exportacion de reportes a Excel
- [ ] Portal del paciente (ver receta, proxima cita)

### P3 - Baja
- [ ] Recordatorios citas y reemplazo lentes de contacto (WhatsApp/SMS)
- [ ] Marketing (origen de pacientes, segmentacion)
