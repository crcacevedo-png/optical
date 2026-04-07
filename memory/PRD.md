# PRD: Cortexia Optical - Plataforma SaaS para Opticas

## Problema Original
Plataforma web SaaS multi-tenant para administracion integral de opticas en Latinoamerica.

## Arquitectura
- Frontend: React 19 + Tailwind CSS + Shadcn UI
- Backend: FastAPI + Motor (MongoDB async)
- Auth: JWT con cookies httpOnly
- Moneda: Quetzal (GTQ) | Idioma: Espanol

## Lo Implementado

### Modulos Funcionales (100% testeados)
- **Auth**: JWT login, register, logout, refresh, brute force, auto-refresh
- **Panel SuperAdmin**: CRUD Opticas + Sucursales (con eliminar) + Usuarios. Logo por optica. Persona de contacto.
- **Dashboard**: estadisticas + financieros + citas + alertas detalladas por producto
- **Pacientes**: lista + busqueda + paginacion + detalle con tabs + **edicion completa** + boton Nueva Consulta + ver consulta (read-only con PDF de recetas)
- **Consultas Opticas**: Ficha clinica completa (4 secciones): Motivo, Historia Clinica (oculares, sistemicos, familiares), Agudeza Visual (tabla OD/OI), Hallazgos y Plan. CRUD + edicion + recetas vinculadas.
- **Recetas**: 3 tipos (anteojos, lentes contacto, medicas). Generacion desde consulta. **PDF con logo de optica**.
- **Busqueda Global (Ctrl+K)**: Busca pacientes, productos y consultas desde cualquier vista.
- **Agenda**: 3 vistas (Dia/Semana/Mes) + CRUD citas + filtro sucursal
- **Cotizaciones**: CRUD + estados + convertir a venta + PDF con logo
- **Inventario**: productos + stock + movimientos + alertas detalladas
- **Ventas**: POS con carrito + metodos de pago + filtro sucursal
- **Finanzas**: ingresos/egresos + resumen mensual + filtro sucursal + rango fechas + desglose por categoria
- **Sucursales y Usuarios**: gestion completa

### Componentes Globales
- BranchFilter: filtro sucursal en Dashboard, Agenda, Inventario, Ventas, Consultas, Finanzas
- GlobalSearch: Ctrl+K busca pacientes, productos, consultas. Navega al modulo correcto.

## Backlog Priorizado

### P1 - Alta
- [ ] Facturacion formal (IVA Guatemala)

### P2 - Media
- [ ] Reportes por sucursal + Exportacion a Excel
- [ ] Recordatorios de citas
- [ ] Portal del paciente (ver receta, proxima cita)

### P3 - Baja
- [ ] Recordatorios reemplazo lentes de contacto
- [ ] Marketing (origen de pacientes)
- [ ] Recuperacion de contrasena
- [ ] Gestion de proveedores
