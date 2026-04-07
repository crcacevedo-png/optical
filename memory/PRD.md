# PRD: Cortexia Optical - Plataforma SaaS para Opticas

## Problema Original
Plataforma web SaaS multi-tenant para administracion integral de opticas en Latinoamerica.

## Arquitectura
- Frontend: React 19 + Tailwind CSS + Shadcn UI
- Backend: FastAPI + Motor (MongoDB async)
- Auth: JWT con cookies httpOnly (secure=True, samesite=none)
- Moneda: Quetzal (GTQ) | Idioma: Espanol

## Lo Implementado

### Modulos Funcionales (100% testeados)
- **Auth**: JWT login, register, logout, refresh, brute force, auto-refresh
- **Panel SuperAdmin**: CRUD Opticas + Sucursales + Usuarios por empresa
- **Dashboard**: 4 cards estadisticas + 3 financieros + citas + alertas detalladas por producto
- **Pacientes**: lista + busqueda + detalle con tabs + paginacion + boton Nueva Consulta + ver consulta (read-only) con historia clinica completa
- **Consultas Opticas (Actualizado 7 Abr 2026)**: Ficha clinica completa con 4 secciones:
  - I. Motivo de Consulta
  - II. Historia Clinica (Antecedentes Oculares, Sistemicos, Familiares con checkboxes/toggles)
  - III. Agudeza Visual (tabla OD/OI con 5 mediciones + metodo Snellen/logMAR/ETDRS)
  - IV. Hallazgos y Plan (anamnesis, hallazgos, diagnostico, tratamiento, recomendaciones, observaciones)
  - CRUD completo, edicion, detalle visual con badges, tablas AV, y recetas vinculadas
- **Agenda**: 3 vistas (Dia/Semana/Mes) + CRUD citas + filtro sucursal
- **Recetas**: 3 tabs (anteojos OD/OI, lentes de contacto, medicas) + PDF + consultation_id
- **Cotizaciones**: CRUD + estados + convertir a venta + PDF
- **Inventario**: productos + stock + movimientos + alertas detalladas
- **Ventas**: POS con carrito + metodos de pago + filtro sucursal
- **Finanzas**: ingresos/egresos + resumen mensual + filtro sucursal + rango de fechas + desglose por categoria
- **Sucursales y Usuarios**: gestion completa

### Modelo de Datos - optical_consultations (actualizado)
Campos originales: patient_id, branch_id, company_id, consultation_date/time/type, chief_complaint, anamnesis, findings, diagnosis, treatment_plan, recommendations, notes
Nuevos campos Historia Clinica: wears_glasses, glasses_since, glasses_type, ocular_surgeries, ocular_trauma, ocular_diseases, diabetes, hypertension, autoimmune_disease, autoimmune_details, current_medications, allergies, family_glaucoma + relationship, family_macular_degeneration + relationship, family_high_myopia + relationship, family_other_history
Nuevos campos Agudeza Visual: va_distance_without_rx_od/oi, va_distance_with_rx_od/oi, va_near_without_rx_od/oi, va_near_with_rx_od/oi, va_pinhole_od/oi, visual_acuity_method

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
