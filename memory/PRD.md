# PRD: Cortexia Optical - Plataforma SaaS para Opticas

## Problema Original
Plataforma web SaaS multi-tenant para administracion integral de opticas en Latinoamerica.

## Arquitectura
- Frontend: React 19 + Tailwind CSS + Shadcn UI
- Backend: FastAPI + Motor (MongoDB async)
- Auth: JWT con cookies httpOnly (secure=True, samesite=none)
- Moneda: Quetzal (GTQ) | Idioma: Espanol

## Lo Implementado (7 Abr 2026)

### Modulos Funcionales (100% testeados)
- **Auth**: JWT login, register, logout, refresh, brute force, auto-refresh
- **Panel SuperAdmin**: CRUD Opticas + Sucursales + Usuarios por empresa. Persona de contacto.
- **Dashboard**: 4 cards estadisticas + 3 financieros + citas + alertas detalladas por producto + filtro sucursal
- **Pacientes**: lista + busqueda + detalle con tabs (Consultas, Recetas, Citas, Compras, Info) + paginacion + boton Nueva Consulta desde detalle
- **Consultas**: Entidad clinica principal. CRUD completo con ficha clinica. Generar recetas vinculadas.
- **Agenda**: 3 vistas (Dia/Semana/Mes) + CRUD citas + filtro sucursal
- **Recetas**: 3 tabs (anteojos OD/OI, lentes de contacto, medicas) + PDF + consultation_id
- **Cotizaciones**: CRUD + estados + convertir a venta + PDF
- **Inventario**: productos + stock + movimientos + alertas detalladas por producto + filtro sucursal
- **Ventas**: POS con carrito + metodos de pago + filtro sucursal
- **Finanzas**: ingresos/egresos + resumen mensual + filtro sucursal + rango de fechas + desglose por categoria
- **Sucursales**: lista (admin) + gestion por empresa (superadmin)
- **Usuarios**: lista + crear + editar + activar/desactivar
- **BranchFilter**: componente reutilizable en Dashboard, Agenda, Inventario, Ventas, Consultas, Finanzas

### Flujo Clinico
1. Seleccionar paciente
2. Crear nueva consulta (boton directo desde detalle del paciente)
3. Registrar datos clinicos
4. Guardar consulta
5. Desde la consulta generar receta de anteojos o receta medica
6. Todo queda enlazado al historial del paciente

### Mejoras P1-P2 (7 Abr 2026)
- Paginacion en lista de pacientes (30 por pagina)
- Dashboard financiero mejorado: filtro sucursal + rango de fechas + desglose por categoria con barras visuales
- Alertas de stock detalladas: muestra cada producto con stock actual/minimo en Dashboard e Inventario

## Backlog Priorizado

### P1 - Alta
- [ ] Edicion de pacientes existentes
- [ ] Facturacion formal (IVA Guatemala)

### P2 - Media
- [ ] Reportes por sucursal + Exportacion a Excel
- [ ] Recordatorios de citas
- [ ] Abonos a ventas pendientes UI

### P3 - Baja
- [ ] Recordatorios reemplazo lentes de contacto
- [ ] Marketing (origen de pacientes)
- [ ] Recuperacion de contrasena
- [ ] Gestion de proveedores
