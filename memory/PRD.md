# PRD: Cortexia Optical - Plataforma SaaS para Ópticas

## Problema Original
Desarrollar una plataforma web SaaS profesional, moderna, escalable y multi-empresa para la administración integral de ópticas en Latinoamérica. El sistema soporta desde una óptica hasta más de 1000, con arquitectura multi-tenant (company_id, branch_id).

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

## Lo Implementado (7 Abr 2026)

### Backend (100% funcional - 23/23 tests)
- Autenticación JWT completa (login, register, logout, refresh, me)
- CRUD completo: empresas, sucursales, pacientes, citas, recetas (3 tipos), inventario, ventas, finanzas, usuarios
- Generación de PDFs para recetas (anteojos, contacto, médicas) con ReportLab
- Dashboard con métricas
- Reportes de ventas y finanzas
- Seed de datos demo (Cortexia Optical Demo)
- Protección brute force
- Índices MongoDB
- Función serialize_doc() para conversión correcta de ObjectId a string

### Frontend (100% funcional - todos los módulos)
- Login con credenciales demo
- Dashboard con 4 cards de estadísticas + 3 cards financieros + próximas citas + alertas stock
- Pacientes: lista + búsqueda + detalle con tabs (recetas, citas, compras, info)
- Agenda: vista semanal + slots horarios + crear/confirmar/completar/cancelar citas
- Recetas: 3 tabs (anteojos con OD/OI, lentes de contacto, médicas) + PDF
- Inventario: productos + stock + movimientos + alertas stock bajo + filtro categoría + búsqueda
- Ventas: punto de venta con carrito + grid de productos + métodos de pago
- Finanzas: ingresos/egresos + resumen mensual + crear entradas
- Sucursales: lista
- Usuarios: lista
- Branding Cortexia Optical con logo

## Backlog Priorizado

### P1 - Alta
- [ ] Generación de PDF para lentes de contacto (ya implementado en backend)
- [ ] Filtrado correcto por branch_id en Agenda, Inventario y Ventas
- [ ] Búsqueda rápida y listas paginadas en Pacientes
- [ ] Edición de pacientes existentes
- [ ] Cotizaciones
- [ ] Facturación formal (IVA Guatemala)

### P2 - Media
- [ ] Alertas de stock mínimo en Inventario (widget dashboard ya funciona)
- [ ] Dashboard financiero con cálculos mensuales detallados
- [ ] Reportes por sucursal
- [ ] Exportación a Excel
- [ ] Historial de movimientos de inventario
- [ ] Recordatorios de citas (email/SMS)
- [ ] Abonos a ventas pendientes UI

### P3 - Baja
- [ ] Recordatorios de reemplazo de lentes de contacto
- [ ] Marketing (origen de pacientes, segmentación)
- [ ] Recuperación de contraseña
- [ ] Validación de permisos más granular por rol
- [ ] Gestión de proveedores
