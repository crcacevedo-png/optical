# PRD: Cortexia Optical - Plataforma SaaS para Opticas

## Problema Original
Desarrollar una plataforma web SaaS profesional, moderna, escalable y multi-empresa para la administracion integral de opticas en Latinoamerica. El sistema soporta desde una optica hasta mas de 1000, con arquitectura multi-tenant (company_id, branch_id).

## Arquitectura
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI + Motor (MongoDB async)
- **Base de datos**: MongoDB
- **Autenticacion**: JWT con cookies httpOnly
- **Moneda**: Quetzal (GTQ)
- **Idioma**: Espanol

## User Personas
1. **SuperAdmin**: Gestion global de empresas (opticas)
2. **Administrador de Optica**: Gestion completa de su empresa y sucursales
3. **Usuario/Vendedor**: Operaciones diarias (ventas, citas, pacientes)

## Lo Implementado (7 Abr 2026)

### Backend (100% funcional)
- Autenticacion JWT completa (login, register, logout, refresh, me)
- CRUD completo: empresas, sucursales, pacientes, citas, recetas (3 tipos), inventario, ventas, finanzas, usuarios
- **Modulo de Cotizaciones** (CRUD + PDF + convertir a venta)
- Generacion de PDFs para recetas y cotizaciones con ReportLab
- Dashboard con metricas
- Reportes de ventas y finanzas
- Seed de datos demo (Cortexia Optical Demo)
- Proteccion brute force
- Indices MongoDB
- Funcion serialize_doc() para conversion correcta de ObjectId a string

### Frontend (100% funcional - todos los modulos)
- Login con credenciales demo
- Dashboard con 4 cards de estadisticas + 3 cards financieros + proximas citas + alertas stock
- Pacientes: lista + busqueda + detalle con tabs (recetas, citas, compras, info)
- Agenda: vista semanal + slots horarios + crear/confirmar/completar/cancelar citas
- Recetas: 3 tabs (anteojos con OD/OI, lentes de contacto, medicas) + PDF
- **Cotizaciones**: crear con productos del inventario, descuento, notas, condiciones de pago, vigencia. Estados: pendiente/aceptada/rechazada/vencida/convertida. Convertir a venta. Descargar PDF.
- Inventario: productos + stock + movimientos + alertas stock bajo + filtro categoria + busqueda
- Ventas: punto de venta con carrito + grid de productos + metodos de pago
- Finanzas: ingresos/egresos + resumen mensual + crear entradas
- Sucursales: lista
- Usuarios: lista
- Branding Cortexia Optical con logo

## Backlog Priorizado

### P1 - Alta
- [ ] Filtrado correcto por branch_id en Agenda, Inventario y Ventas
- [ ] Busqueda rapida y listas paginadas en Pacientes
- [ ] Edicion de pacientes existentes
- [ ] Facturacion formal (IVA Guatemala)

### P2 - Media
- [ ] Alertas de stock minimo en Inventario (widget dashboard ya funciona)
- [ ] Dashboard financiero con calculos mensuales detallados
- [ ] Reportes por sucursal
- [ ] Exportacion a Excel
- [ ] Historial de movimientos de inventario
- [ ] Recordatorios de citas (email/SMS)
- [ ] Abonos a ventas pendientes UI

### P3 - Baja
- [ ] Recordatorios de reemplazo de lentes de contacto
- [ ] Marketing (origen de pacientes, segmentacion)
- [ ] Recuperacion de contrasena
- [ ] Validacion de permisos mas granular por rol
- [ ] Gestion de proveedores
