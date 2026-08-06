# PRD: Cortexia Optical - Plataforma SaaS para Opticas

## Problema Original
Plataforma web SaaS multi-tenant para administracion integral de opticas en Latinoamerica.

## Arquitectura
- Frontend: React 19 + Tailwind CSS + Shadcn UI + Recharts
- Backend: FastAPI + Motor (MongoDB async) - Modular (22 archivos de rutas)
- Auth: JWT con cookies httpOnly | Moneda: GTQ | Idioma: Espanol

## Lo Implementado

### Caja embebida en modulo Ventas (Feb 2026)
- Componente `SalesCashBar` integrado en `SalesPage.js`: muestra estado de caja (abierta/cerrada) con acciones para abrir/cerrar sin salir del modulo.
- Business rule: `Nueva Venta` queda **deshabilitado** cuando la caja esta cerrada (tooltip "Abre la caja para poder registrar ventas") y el dialog no se abre.
- Sincronizacion: cada apertura/cierre de caja refresca la lista de ventas.
- **Menu "Caja" eliminado del sidebar.** Ruta `/cash-register` sigue existiendo por retrocompatibilidad pero no se muestra en navegacion.
- **Detalle de cierre visible desde Ventas:**
  - "Ver cierre en vivo": modal con totales corrientes por metodo de pago (Efectivo, Tarjeta, Transferencia, Cheque, Otro), efectivo esperado y ventas del turno.
  - "Historial": tabla con cierres anteriores; cada fila abre el detalle completo con desglose por metodo, cuentas por cobrar generadas y auditoria de pagos.
  - Al cerrar caja se muestra automaticamente el detalle post-cierre.
- **Nuevo metodo de pago "Cheque"** en `PAYMENT_METHODS` (front) y `totals_by_method` (backend `cash_register.py`), con etiqueta "N° de Cheque".
- Nuevo endpoint: `GET /api/cash-register/current/preview` calcula totales en vivo sin cerrar la caja.

### Escalabilidad Fase 2 - parcial (Feb 2026)
- **Pool MongoDB tuneado** en `db.py` (maxPoolSize=200, minPool=20, waitQueue=3s, retryWrites). Configurable via env sin redeploy.
- **Object Storage compartido**: nuevo `backend/object_storage.py` usa Emergent Object Storage. Migrados endpoints de logo (`/api/settings/logo` y `/api/companies/{id}/logo`). Multi-pod safe. Fallback local si no hay `EMERGENT_LLM_KEY`.
  - Nuevo campo Mongo: `companies.logo_storage_path`.
- **Redis Upstash conectado (ACTIVO en preview)**:
  - `cache.py` con backend Redis via `REDIS_URL`. Verificado: hit_rate 66.7% en `plans_cache` tras warmup, backend=redis en `/api/health/metrics`.
  - `rate_limiter.py` con `storage_uri=REDIS_URL` en slowapi. Verificado: key `LIMITS:LIMITER/{ip}//api/auth/login/10/1/minute` persiste en Redis.
  - Multi-pod safe: cache y rate-limits coherentes entre replicas.
- Verificado E2E: upload PNG a Object Storage remoto, DB guarda `logo_storage_path`, download por API devuelve mismo contenido (69 bytes, PNG magic OK). Redis muestra keys correctos con TTL.
- Pendiente para 1000 usuarios: uvicorn `--workers 4` sin `--reload` (requiere cambio en pipeline de deploy Emergent), HPA multi-pod (soporte), Celery/RQ para emails/PDFs.

### Optimizaciones de performance (Feb 2026)
- **N+1 eliminado en `/api/quotations`**: `list_quotations` ahora usa batch `$in` para pacientes y creadores + `update_many` bulk para vencidas. Antes: 1 + 2N queries (300+ para 100 cotizaciones). Ahora: 3 queries constantes. **p95 bajo carga 100 VUs: 1288ms → 483ms (-62%)**. Meta <500ms cumplida.
- **Cache Redis TTL 60s en inventario**: `/api/inventory/products` y `/api/inventory/stock` cachean con namespace por empresa+sucursal. Invalidacion automatica en `POST /products`, `PUT /products`, `POST /movement`, `POST /sales`, `DELETE /sales`. Filtros por category/search NO se cachean (siempre fresh).
- **p95 general bajo carga 100 VUs: 888ms → 577ms (-35%)**. Verificado E2E con 13/13 tests (testing agent) — sin issues.

### Cache Dashboard + Cursor Pagination Ventas (Feb 2026)
- **Cache Redis TTL 30s en `/api/reports/dashboard`** (`routes/reports.py`):
  - Namespace `dashboard`, key `{company_id}:{branch_id_or_all}`.
  - Sums convertidos a MongoDB aggregation pipelines (`$group`) — antes traía 100+1000 docs.
  - Batch fetch de `upcoming_appointments.patient_name` (N+1 fix).
  - `_get_stock_alerts_count` batch fetch de products (N+1 fix).
- **Cursor pagination en `/api/sales`** (`routes/sales.py`):
  - Retro-compatible: sin `cursor`/`include_cursor` devuelve lista plana (frontend actual sigue funcionando).
  - Con `?include_cursor=true` o `?cursor=...` devuelve `{items, next_cursor, has_more}`.
  - Ordena por `_id desc` (cronologico gracias a ObjectId timestamp) usando `_id<cursor` (mejor que skip/limit para 10.000+ registros).
  - Batch fetch de patients y sellers (N+1 fix).
- Verificado: 15/15 tests (testing agent). Suite en `/app/backend/tests/test_dashboard_cache_and_sales_cursor.py`.

### Sistema de Tickets de Soporte (Feb 2026)
- Cualquier usuario autenticado (admin, user "atencion al cliente", doctor) puede crear tickets que llegan al SuperAdmin.
- Backend `/app/backend/routes/support_tickets.py`:
  - `POST /api/support-tickets` con subject, message, category (bug|consulta|mejora|facturacion|otro), priority (baja|media|alta).
  - `GET /api/support-tickets` — vendedor/admin ven solo los suyos; SuperAdmin ve TODOS con `company_name`. Filtros por status/priority/category.
  - `GET /api/support-tickets/{id}` — devuelve el hilo completo. 403 para no-owner no-super.
  - `POST /api/support-tickets/{id}/reply` — creador y SuperAdmin agregan mensajes. Al responder SuperAdmin a ticket `abierto`, pasa a `en_progreso`.
  - `PATCH /api/support-tickets/{id}/status` — SuperAdmin cambia cualquiera; creador solo puede cerrar.
  - `GET /api/support-tickets/stats/summary` — contadores por estado.
- Notification push al SuperAdmin en creacion (event_type `SUPPORT_TICKET_CREATED`).
- 3 indexes: `created_by+_id`, `status+_id`, `company_id+_id`.
- Frontend: nueva pagina `SupportTicketsPage.js` accesible en `/support` para usuarios y `/admin/soporte` para SuperAdmin. Menu "Soporte" siempre visible (bypass allowed_menu_items).
- 4 stat cards por estado, filtro rapido por click en cards, dialogo de creacion con validaciones, hilo de conversacion tipo chat, badges de estado/prioridad/categoria/optica.
- Verificado E2E: 30/30 tests (testing agent) — 0 issues.

### Tickets Soporte v2: Email + Adjuntos + Read/Unread + SLA (Feb 2026)
- **Email al equipo Cortexia**: al crear ticket se envia email via Resend (queue_email best-effort) a `crcacevedo@gmail.com` (`SUPPORT_EMAIL` env override). Template `render_support_ticket()` con badge de prioridad, tabla de metadata y CTA al panel admin.
- **Screenshots (adjuntos)**:
  - Max 5 por ticket, max 5MB, solo PNG/JPG/WEBP/GIF.
  - `POST /api/support-tickets/{id}/attachments` sube a Object Storage compartido con path `cortexia-optical/support/{ticket_id}/{filename}`.
  - `GET /api/support-tickets/{id}/attachments/{filename}` sirve la imagen (403 si no owner/super).
  - Frontend: file input multiple en dialog de creacion + boton "Adjuntar" en respuestas; galeria en detalle.
- **Read/Unread**:
  - Campos `last_read_by_creator` y `last_read_by_super` en Mongo.
  - `POST /api/support-tickets/{id}/read` marca como leido para el usuario actual.
  - Lista y detalle incluyen `unread: bool` calculado (`updated_at > last_read_by_<role>`).
  - Stats incluye `unread: int` (contador global).
  - Frontend: badge rojo "N sin leer" en header, punto rojo por fila, fondo azul suave, auto-mark-as-read al abrir detalle.
- **SLA por prioridad (frontend)**: alta 24h, media 48h, baja 72h. Badge dinamico refrescado cada 60s con colores (verde/amber/rojo/vencido rojo intenso). Tickets `resuelto` y `cerrado` no muestran SLA.
- Fix aplicado por testing agent: `_serialize_ticket` ahora serializa `attachments[].uploaded_by_id` (evita 500 en list/detail).
- Verificado E2E: 50/50 tests (30 previos + 20 nuevos) — 0 issues.

### Bugfix Caja: admin sin branch_id (Feb 2026)
- **Problema en produccion**: usuarios admin no podian abrir caja. Backend respondia 400 `"El usuario no tiene sucursal asignada. Especifica una."` porque los admins normalmente no tienen `branch_id` asignado (ven todas las sucursales).
- **Fix en `_get_branch_id_or_400` (`routes/cash_register.py`)**: si no hay override ni `user.branch_id`, se busca automaticamente:
  1. La sucursal principal (`is_main: true`) activa de la empresa.
  2. Si no existe, la primera sucursal activa.
  3. Solo si la empresa no tiene NINGUNA sucursal activa, retorna 400 con mensaje mas util ("La empresa no tiene sucursales activas. Crea una en Configuracion > Sucursales.").
- Aplica a: `/open`, `/close`, `/current`, `/current/preview`.
- Testing agent: **12/12 tests OK** — sin regresion en vendedores con branch propio ni en el override explicito.

### Reporte de Cierres de Caja (Feb 2026)
- Nuevos endpoints backend:
  - `GET /api/cash-register/report` — agrega cierres cerrados en rango `date_from/date_to` (opcional filtro por sucursal), con totales por metodo (cash, transfer, card, check, other), grand totals, cuentas por cobrar acumuladas y diferencia de efectivo consolidada.
  - `GET /api/cash-register/report/pdf` — descarga PDF (reportlab platypus) con resumen y tabla detallada.
- UI en `ReportsPage`: nueva card "Reporte de Cierres de Caja" con 5 tiles por metodo, totales consolidados, tabla por cierre y boton "Descargar PDF".
- Reutiliza filtros de rango de fechas y sucursal existentes en la pagina de reportes.


### Hardening de Seguridad P1 (Junio 2026)
- **#5 Revocacion de tokens:** Campo `password_changed_at` en users. `get_current_user` y `/refresh` invalidan tokens emitidos antes del ultimo cambio de password (JWT `iat` < `password_changed_at` -> 401). Aplica tambien cuando admin resetea pw a otro usuario.
- **#6 Refresh + me con cuenta desactivada:** `/api/auth/me` y `/api/auth/refresh` verifican `is_active`. Usuario desactivado recibe 401 inmediatamente sin esperar expiracion.
- **#7 X-Forwarded-For:** Helper `get_real_ip()` lee header proxy. Brute force y rate limiting usan IP real del cliente.
- **#8 Rate limiting global:** slowapi instalado. 120/min default, 10/min login, 5/min change-password, 30/min refresh. HTTP 429 al exceder.
- **#9 PII en logs reducida:** Solo `pw_len` (sin chars del password) en logs de seed.
- **#10 Password policy:** Mínimo 8 chars + 1 mayúscula + 1 minúscula + 1 dígito. Aplicado en `/api/users` POST, PUT, y `/api/auth/change-password`. Validacion en `auth_utils.validate_password_strength()`.
- Verificado E2E: weak passwords rechazadas, token viejo post-change devuelve "Sesion invalidada", usuario desactivado bloqueado, rate limit 429 confirmado, login frontend sigue funcionando.

### Hardening de Seguridad P0 (Junio 2026)
- **#1 Mass-assignment fix:** `PUT /api/users/{id}` ahora valida con modelo Pydantic `UserUpdate`. Solo superadmin puede cambiar `role`. Nadie puede auto-desactivarse ni auto-cambiar rol. Admin no puede modificar superadmins.
- **#2 CORS whitelist:** Reemplazado el reflejo de cualquier origen por whitelist explicita (cortexiaoptical.com, www, preview). Defensa en profundidad: el ingress responde `*` sin credentials (bloqueando CSRF), y el backend solo emite headers CORS para origenes permitidos.
- **#3 Registro publico deshabilitado:** `POST /api/auth/register` devuelve 403. Creacion de usuarios solo via admin/superadmin.
- **#4 Password SuperAdmin no hardcodeada:** Lee de env vars `ADMIN_EMAIL` y `ADMIN_PASSWORD` (con check >= 8 chars). Si no estan, el seed se omite con warning. Log de password reducido a `pw_len` solamente (sin chars).
- Verificado E2E con curl + login screenshot.

### Fix Login Produccion - Hardcode SuperAdmin (Mayo 2026)
- Eliminado el lookup de env var ADMIN_PASSWORD en server.py seed
- Password hardcodeado "Montecristo2026" para evitar corrupcion de shell ($ expansion) en deploy
- Seed resetea password en cada startup garantizando acceso
- Verificado en preview: login + /me HTTP 200 OK
- Requiere REDEPLOY en cortexiaoptical.com para aplicar

### Notificaciones Push SuperAdmin (Mayo 2026)
- Campana con badge rojo de no leidas en header (polling 30s)
- Dropdown con lista de notificaciones ordenadas por fecha
- Auto-generacion en: nueva empresa, cambio de plan, limite de pacientes (80%/100%)
- Marcar como leida individual o todas, iconos por tipo de evento
- Solo visible para SuperAdmin

### Dashboard SaaS SuperAdmin
- Revenue: MRR, ARPU, Churn rate, Revenue por plan
- Engagement: Usuarios activos 7/30 dias, Top 5 opticas, Modulos usados
- Operativo: Volumen transaccional, Pacientes promedio, Crecimiento 6 meses
- Funnel de conversion Free->Basic->Enterprise con upgrades/downgrades
- Alertas de limite, Cambios de plan recientes

### WhatsApp + Rol Doctor (Feb 2026)
- **Envio por WhatsApp**: boton verde "WhatsApp" en `QuotationDetailDialog` genera link `wa.me/{phone}?text=...` con mensaje pre-armado (numero cotizacion, total, vigencia). Usa `patient_whatsapp` si existe, sino `patient_phone`. Sin costo de API externa.
- **Rol Doctor**: nuevo rol paralelo a "Atencion al Cliente" para optometristas/oftalmologos. Backend `settings.role-permissions` acepta `doctor` como rol configurable (ALLOWED_ROLES = {user, doctor}); default = todos los modulos. Frontend: opcion "Doctor" en select de UsersPage y CreateUserDialog, label en MainLayout, seccion propia en RolePermissionsSection con descripcion.
- Los role checks del backend permiten acceso al doctor por defecto (usan `!= superadmin`); admin puede restringir sus modulos desde `/settings > Permisos por Rol`.
- `patient_whatsapp` agregado a la respuesta del GET /quotations para habilitar el boton desde el listado.

### Envio de Cotizacion por Email (Feb 2026)
- **Backend**: `POST /api/quotations/{id}/send-email` — Genera el PDF de la cotizacion (reutilizando `_build_quotation_pdf_bytes`) y lo envia adjunto al email del paciente via Resend con template `render_quotation_email`. Guarda historial en `quotations.emails_sent[]` (to, sent_at, sent_by, sent_by_name).
- `email_service.send_email` extendido para soportar `attachments=[{filename, content (bytes o base64), content_type}]` con encoding automatico a base64.
- Endpoints `GET /quotations` y `GET /quotations/{id}` ahora incluyen `patient_email` y serializan correctamente `emails_sent[].sent_by` (fix ObjectId serialization).
- **Frontend**: `QuotationDetailDialog` recibe `onSendEmail` y `sendingEmail`. Boton "Enviar a &lt;email&gt;" visible solo cuando el paciente tiene email. En `QuotationsPage`, al aceptar una cotizacion, se muestra un toast con accion "Enviar email" para one-click send.

### Refactorizacion React (Feb 2026)
- **`PatientsPage.js`: 1,578 → 763 lineas (-51.6%)** — extrae 8 dialogos:
  - `PatientAddDialog`, `PatientEditDialog`, `PatientDeleteDialog`, `EyeglassRxDialog`, `ContactRxDialog`, `MedicalRxDialog` en `components/patients/PatientDialogs.js`
  - `ConsultationViewDialog` en `components/patients/ConsultationViewDialog.js`
  - `ConsultationFormDialog` (formulario mas grande del sistema, 289 lineas) en `components/patients/ConsultationFormDialog.js` con 18 props
- **`ConsultationsPage.js`: 987 → 875 lineas (-11%)** — reutiliza `EyeglassRxDialog` y `MedicalRxDialog` con `testIdPrefix=""`.
- **`AdminOpticasPage.js`: 802 → 562 lineas (-30%)** — 4 dialogos en `components/admin/AdminOpticasDialogs.js`.
- **`QuotationsPage.js`: 743 → 366 lineas (-50.7%)** — extraidos 3 dialogos: `QuotationDetailDialog`, `ConvertToSaleDialog` (en `QuotationDialogs.js`) y `CreateQuotationDialog` (en archivo propio por complejidad, 20 props).
- Total: **15 componentes reutilizables, -1,544 lineas eliminadas de las paginas principales (-37.6%)**.
- **Bonus DRY**: `PatientFormFields` compartido entre `PatientAddDialog` y `PatientEditDialog` (elimina ~40 lineas duplicadas dentro de `PatientDialogs.js`, ahora 397 -> 357 lineas). Config via props: `testIdPrefix`, `requiredContact`, `spacing`.
- Diseno: props explicitos. Estado permanece en pagina padre. Cero cambios de comportamiento. Data-testids preservados 1:1 gracias al `testIdPrefix` opcional.

### Permisos por Rol + Rename Rol (Feb 2026)
- **Rename**: rol `user` cambia display de "Usuario" a "Atencion al Cliente" (badge en UsersPage, avatar en MainLayout, label en select de creacion, docs).
- **Permisos por Rol** (Admin only en Configuracion):
  - Backend: `GET /api/settings/role-permissions` retorna `{permissions: {user: [...]}, available_modules: [...]}`; `PUT` persiste en `companies.role_permissions`.
  - Login y `/api/auth/me` inyectan `allowed_menu_items` en la respuesta segun el rol del usuario (admin -> null / sin restriccion).
  - Frontend `MainLayout`: filtra navItems por `key` cruzando con `user.allowed_menu_items`.
  - Componente `RolePermissionsSection`: card con checkboxes para el rol "Atencion al Cliente" con badge "Modulo de plan" para modulos gated. Dashboard siempre bloqueado activo. Botones rapidos "Todo"/"Solo Dashboard".
- 13 modulos configurables: dashboard, patients, consultations, agenda, prescriptions, quotations, inventory, sales, cash-register, receivables, suppliers, finance, reports.

### Caja (Abrir/Cerrar) + Referencia por Medio de Pago (Feb 2026)
- **Feature 1: Numero de Autorizacion / Transferencia**: en `PaymentLinesEditor` y `AddPaymentDialog` el campo `note` ahora tiene label dinamico segun metodo — `card` → "N° de Autorizacion", `transfer` → "N° de Transferencia", `other` → "Referencia", `cash` → oculto. Sin cambios de modelo (usa `note` existente).
- **Feature 2: Modulo de Caja** (`/cash-register`, sidebar "Caja"):
  - Coleccion `cash_registers` con estados `open`/`closed`. Una caja abierta por sucursal a la vez.
  - `POST /api/cash-register/open`: crea caja con `opening_amount` (fondo inicial) y `opening_notes`.
  - `POST /api/cash-register/close`: computa totales agregando `sale.payments[]` cuyo `created_at` cae en la ventana `[opened_at, closed_at]`. Agrupa por metodo (cash/card/transfer/other). Lista `sales_in_window` y `receivables_in_window` (ventas creadas con `balance > 0`).
  - Detecta diferencia de efectivo: `expected_cash = opening_amount + cash_totals`; si operador cuenta el efectivo real (`counted_cash`), calcula `cash_difference` (sobrante/faltante).
  - `GET /current`, `GET /`, `GET /{id}` para consultar. Audit logs `CASH_REGISTER_OPENED` y `CASH_REGISTER_CLOSED`.
  - Frontend: hero card con estado + botones Abrir/Cerrar, tabla historial, dialog detalle con tiles coloridos por metodo, panel de cuentas por cobrar generadas con nombres de pacientes, tabla completa de pagos con referencias.
- Indices MongoDB agregados: `cash_registers.(company_id, branch_id, status)` y `(company_id, opened_at desc)`.

### Eliminacion de Ventas (Admin only, Feb 2026)
- **`DELETE /api/sales/{id}`** solo permitido para `role == 'admin'`. Vendedores reciben 403.
- Al eliminar: restaura stock (+quantity por item), borra `inventory_movements` (por `reference`), borra `finance_entries` de la venta y sus abonos (por `reference_id + reference_type IN [sale, sale_payment]`), y borra el documento de venta.
- Registra evento `SALE_DELETED` en `audit_log` con metadata: total, pagado, patient_id, items_count, stock_restored, inv_movements_deleted, finance_entries_deleted.
- **Frontend**: boton trash rojo en cada fila del historial + boton "Eliminar venta" en el modal de detalle. Solo visible cuando `user.role === 'admin'`.
- **AlertDialog** de confirmacion explica los 4 efectos irreversibles y muestra card con datos de la venta antes de confirmar.

### Ventas Multi-Pago + Cuentas por Cobrar (Feb 2026)
- **Sale.payments[]**: array con historial de pagos por venta `{method, amount, note, created_at, created_by}`.
- **Nueva Venta** ahora permite N pagos con diferentes metodos (efectivo/tarjeta/transferencia/otro). Editor dinamico agregar/quitar filas + botones "Pagar total". Puede enviarse con saldo pendiente > 0.
- **Endpoint POST /api/sales/receivables**: ventas con `balance > 0` + patient info + antiguedad en dias + agregados (`total_pending`, `count`).
- **Endpoint POST /api/sales/{id}/payment**: acepta `method`, `amount`, `note`. Persiste en `payments[]` y registra `finance_entry` por cada pago.
- **Nueva pagina "Cuentas por Cobrar" (`/receivables`)**: KPIs (saldo total, clientes con deuda, antiguedad maxima), tabla con badge de aging (verde <= 7d, ambar <= 30d, naranja <= 60d, rojo > 60d), busqueda por paciente/telefono/ID, boton "Abonar" que abre dialogo reusable.
- **Detalle de Venta** ahora muestra historial de pagos + boton "Registrar abono" cuando `balance > 0`.
- Menu lateral: "Cuentas por Cobrar" agregado (solo para planes con modulo `ventas`).

### Modulo de Comunicacion
- Anuncios segmentados por plan/ciudad con metricas de visualizacion

### Fase 1 Escalabilidad (Feb 2026) — objetivo ~1,000 opticas / 5,000 usuarios
- **Indices MongoDB comprehensivos** en startup (`server.py`): compound `(company_id, ...)` en patients/products/stock/sales/finance/quotations/consultations/prescriptions/appointments/notifications/announcements/branches/suppliers. Idempotente.
- **TTL audit_log**: elimina automaticamente registros > 180 dias.
- **TTL login_attempts**: elimina automaticamente registros > 24h.
- **Gzip compression** (`GZipMiddleware` con minimum_size=500): reduce payloads de listados en ~70% (verificado: /api/companies bajo de 2,502 -> 736 bytes).
- **Cache TTL en memoria** (`/app/backend/cache.py`): planes cacheados 5 min, invalidado en create/update/delete de plan.
- **Emails fire-and-forget** (`queue_email` en `email_service.py`): welcome, password reset, alertas de seguridad ya no bloquean la respuesta HTTP.
- **Endpoint `/api/companies`**: paginacion + eliminacion del N+1 (aggregation por batch: 3 queries totales en vez de 3N).
- **Endpoint `/api/health/metrics`** + pagina "Salud Sistema" (`/admin/health` solo SuperAdmin): monitoreo en tiempo real de MongoDB (ping, tamaño, docs), recursos del pod (CPU/RAM/disco), cache hit rate, actividad 24h y signals automaticos para saber cuando activar Fase 2 (multi-pod, Redis, S3).

### Onboarding "Inicio Rápido" (Feb 2026)
- Página interactiva `/onboarding` con 7 pasos checklist (datos óptica, sucursales, equipo, inventario, primer paciente, primera venta, cambio password) + barra de progreso animada.
- Backend: `GET/PUT /api/onboarding/status` y `POST /api/onboarding/dismiss` con persistencia por usuario (`onboarding_progress`, `onboarding_dismissed`).
- Menú lateral: ítem "Inicio rápido" colocado entre Reportes y Configuración (admins).
- **Widget Dashboard (Feb 2026):** Card gradient (#6D35D8 → #13B8B0) visible solo para admins con progreso < 100% y no descartado. Muestra "X de 7 pasos completados", % progreso, CTA "Continuar" → `/onboarding`, y botón X para descartar (persistente vía `/api/onboarding/dismiss`).

### Sistema de Planes, Exportacion Excel, Reportes por Sucursal

### Modulos Funcionales
- Auth, Login Premium, Pacientes, Consultas, Recetas (3 tipos, 3 estilos PDF)
- Busqueda Global, Agenda, Cotizaciones
- Inventario (min stock editable), Ventas, Proveedores, Finanzas
- Configuracion

## Backlog
### P1: Facturacion formal IVA Guatemala
### P2: Portal del paciente
### P3: Recordatorios WhatsApp/SMS, Marketing
