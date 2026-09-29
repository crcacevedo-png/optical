# PRD: Cortexia Optical - Plataforma SaaS para Opticas

## Problema Original
Plataforma web SaaS multi-tenant para administracion integral de opticas en Latinoamerica.

## Arquitectura
- Frontend: React 19 + Tailwind CSS + Shadcn UI + Recharts
- Backend: FastAPI + Motor (MongoDB async) - Modular (22 archivos de rutas)
- Auth: JWT con cookies httpOnly | Moneda: GTQ | Idioma: Espanol



### Autoservicio de registro — Plan Básico gratis con verificación de correo (Jun 2026)
Registro público self-service que reemplaza el formulario de solicitud en `/registro` para el plan gratuito. El interesado se inscribe solo, verifica su correo (doble opt-in) y entra de inmediato con el Plan gratuito (tope 50 pacientes). Provisión 100% automática, sin aprobación manual del Superadmin. Planes superiores siguen por solicitud (ahora en `/contacto`).
- **Backend NUEVO `routes/registration.py`** (colección `pending_registrations`): `POST /api/registration` (PÚBLICO, @limiter 5/min, honeypot `website`, consentimiento obligatorio, valida fortaleza de contraseña, hashea el password de inmediato y guarda un registro PENDIENTE con token seguro `secrets.token_urlsafe(48)` + expiración 48h; NO crea la óptica todavía; 409 si el correo ya es usuario). `POST /api/registration/verify` ({token}, @limiter 20/min): claim atómico (idempotente/doble-clic seguro), valida expiración (410) e invalidez (400), y PROVISIONA óptica + usuario admin con el password ya hasheado, asigna el plan de autoservicio y aplica el tope del código promo si existe; notifica a superadmins + correo de bienvenida (sin credenciales, el usuario eligió su contraseña). `POST /api/registration/resend` ({email}, @limiter 3/min, respuesta neutra). No hace auto-login: el usuario va a `/login` tras verificar (decisión del producto).
- **Plan de autoservicio** `_resolve_self_service_plan()`: 1) plan con `is_self_service_default:true`; 2) plan gratuito ("Free" o price 0); 3) el activo más económico. La óptica se crea con `is_active=true`, `billing_state="active"`, `signup_source="self_service"`, `promo_code` (atribución). Dunning NO afecta cuentas sin `stripe_subscription_id` (las gratuitas nunca se suspenden).
- **Códigos de promoción = tope de pacientes ampliado (NO monetario)**: `leads.py` `PromoCodeCreate/Update` +`patient_limit`. Al registrarse con un código válido con `patient_limit>0`, la óptica arranca con `patient_limit_override = patient_limit` (ej 200 en vez de 50); sin código o sin límite → usa el tope del plan (50). El Superadmin crea/edita el tope en Solicitudes → Códigos.
- **Al llegar al tope → flujo normal existente**: `patients.py::_check_patient_limit` ya bloquea con 403 usando el límite efectivo (`effective_max_patients`, respeta el override). `PatientsPage.js` ahora muestra un toast con acción "Actualizar plan" → `/my-plan` cuando se alcanza el tope.
- **Frontend**: NUEVO `SelfRegisterPage.jsx` (`/registro`, una pantalla, validación en vivo, contraseña + confirmar con show/hide, código promo precargable con `?codigo=`, honeypot, pantalla "Revisa tu correo" con reenvío, enlaces a `/login` y `/contacto`). NUEVO `VerifyRegistrationPage.jsx` (`/verificar-cuenta?token=`, estados loading/success/expired/error, useRef anti doble POST en StrictMode). `App.js`: `/registro`→SelfRegister, `/verificar-cuenta`→Verify, `/contacto` y `/solicitar-plan`→el formulario de solicitud original (PublicLeadFormPage). `LoginPage.js`: enlace "Crear cuenta gratis"→`/registro`. `LeadsAdminPage.jsx`: campo "Tope de pacientes gratis" al crear código + edición inline en la tabla (columna "Tope pacientes", vacío/0 = "por defecto (50)").
- **Config**: `backend/.env` `APP_URL` fijado a `https://www.cortexiaoptical.com` (enlaces de correo apuntan a la app; marketing vive en `web.cortexiaoptical.com` por separado). Índices nuevos: `pending_registrations.token` (unique), `.email`, `.created_at`. Env opcional `REGISTRATION_VERIFY_HOURS=48`.
- **Verificado**: curl E2E backend (submit→verify→login OK; idempotencia doble verify; 409 duplicado; 400 contraseña débil; promo `patient_limit=200`→`patient_limit_override=200`, Plan Free, billing active, signup self_service; resend neutro; 410 expirado; 400 inválido) + testing agent iteration_17 100% frontend (todos los flujos UI, validaciones, verificación vía token de Mongo, códigos con tope editable). Datos de prueba limpiados. Fase 2 pendiente: tope gratuito configurable por plan, panel Superadmin de registros por autoservicio, onboarding guiado.


### Control de Cobros y Suspensión por Impago — Fase 1 MVP (Jun 2026)
Sistema automático de cobros de la membresía (Stripe, USD): detecta pagos fallidos, da **3 días de gracia** con avisos escalonados, **suspende** (muro de pago) si no se regulariza, y **reactiva automáticamente** al confirmarse el pago. Cortesía = SIEMPRE exenta.
- **Backend `dunning.py` (NUEVO)**: motor de estados `billing_state` (active|grace|suspended). `process_company()` mapea el status de Stripe → estado interno: `active/trialing`→activo (reactiva si venía de gracia/suspensión); `past_due/unpaid/incomplete`→inicia gracia `BILLING_GRACE_DAYS`(=3) o suspende al vencer; `canceled/incomplete_expired`→suspende (NO baja a Free). `run_dunning_cycle()` (cron diario), `build_billing_snapshot()` (para login/me), `build_collections_panel()` (panel superadmin), `_check_amount()` (verificación de monto Stripe vs plan; marca+avisa, no suspende). Notificaciones in-app + correo a superadmins y al admin de la óptica en cada evento.
- **Backend `email_service.py`**: 4 plantillas nuevas — `render_payment_failed`, `render_grace_reminder`, `render_suspension_notice`, `render_payment_restored`.
- **Backend `routes/billing.py`**: `_sync_subscriptions_job` ahora delega en `run_dunning_cycle()`. `_apply_paid` limpia el estado de cobro (billing_state=active). Nuevos endpoints: `GET /api/billing/account-status` (auth; revalida en vivo con Stripe con timeout 8s si gracia/suspendido para reactivar sin esperar al cron) y `GET /api/billing/admin/collections` (superadmin; KPIs + listas).
- **Backend `auth_utils.py`**: `get_current_user` aplica el **muro de pago** — si `billing_state=='suspended'` (y no cortesía) y la ruta NO está en `_BILLING_WALL_ALLOWED` (`/api/auth/`, `/api/billing/`, `/api/plans`) → HTTP **402** `cuenta_suspendida`.
- **Backend `routes/auth.py`**: login y `/auth/me` incluyen `billing` = snapshot (state, grace_until, days_remaining, suspended_at/reason, subscription_status, has_subscription, amount_mismatch, is_exempt).
- **Campos Mongo en `companies`**: `billing_state`, `payment_failed_at`, `grace_until`, `suspended_at`, `suspended_reason`, `last_dunning_stage`, `amount_mismatch`, `amount_mismatch_detail`, `current_period_end`. Índice `billing_state`.
- **Frontend**: `PaymentWall.js` (muro suspendido: admin ve estado + "Actualizar método de pago"→portal + "Elegir plan"→/my-plan, auto-poll de reactivación cada 15s; no-admin ve "contacta a tu administrador"). `BillingBanner.js` (banner de gracia NO bloqueante + banner inline de suspensión en /my-plan). `CollectionsPage.js` (`/admin/cobros`, superadmin: 5 KPIs + 4 listas). `MainLayout.js` (menú "Cobros"; renderiza muro/banner según `user.billing`). `MyPlanPage.js` (alerta de estado + botón "Gestionar suscripción"→portal + refresca sesión tras pago). Ruta `/admin/cobros` en App.js.
- **Verificado**: pytest determinista `backend/tests/test_dunning_engine.py` 18/18 (gracia→suspensión→reactivación, cancelación, cortesía exenta, panel). Testing agent iteration_15: 100% (7 escenarios backend+frontend: collections 200/403, account-status, enforcement 402/whitelist 200, muro admin/vendedor, banner de gracia, menú Cobros). Empresa demo restaurada a activo.
- **Nota**: se probó sembrando estados en Mongo porque Stripe usa placeholder en preview; el flujo real se valida en producción con el cron diario `sync-subs`. Fases 2/3 (gracia configurable, historial de comprobantes, prórrogas, FEL/SAT) pendientes.


### Code quality pass: import circular + higiene de tests (Jun 2026)
- **Import circular resuelto**: se extrajo la función pura `_plan_amount_cents` a `backend/billing_utils.py`; `dunning.py` ya NO importa `routes.billing` (rompe el ciclo dunning↔billing). Verificado: imports OK + 18/18 tests del motor de cobros.
- **Secretos hardcodeados en tests**: los 5 archivos señalados (test_receipt_and_patient_limit, test_profitability_iter16, test_collections_and_wall, test_caja_egresos_iter9/10) ahora importan credenciales de `tests/_credentials.py` (basado en env vars, patrón ya usado en el repo).
- **Comparaciones `is` en tests**: convertidas a asserts truthy/falsy en los archivos señalados.
- **Variables indefinidas (#4)**: pyflakes NO encontró nombres indefinidos reales en backend (falso positivo del reporte).
- **Diferidos a propósito** (refactors amplios y riesgosos sobre código en producción ya probado; se harían incrementalmente con re-testing): refactor de `login()`/`get_current_user()` (auth crítico), split de componentes de 300-1000 líneas, deps de hooks React en masa, y simplificación del motor de dunning recién probado.


### Rentabilidad por productos + separación Flujo de caja vs Margen (Jun 2026)
Hallazgo (confirmado por code review): la "Utilidad neta" del módulo Finanzas se calculaba en BASE CAJA (cobros − pagos) sin descontar el costo de la mercadería vendida (COGS), y se confundía con margen. Fase 1 implementada:
- **`sales.py`**: cada línea de venta ahora **fotografía el costo** (`unit_cost` + `cost_source`) del producto al momento de vender (no cambia si el costo se edita después). Ítems sin producto de inventario → `cost_source="sin_costo"`. Solo aplica a ventas NUEVAS (históricas quedan sin costo).
- **`finance.py`**: nuevo `GET /api/finance/profitability` (admin) → base DEVENGADO por fecha de venta: `revenue_with_cost`, `cogs`, `gross_margin` (+%), `revenue_without_cost`/`items_without_cost` (transparencia), y `by_product` (unidades, ingreso, costo, margen, %). Excluye ventas `cancelada`.
- **UI**: `FinancePage` renombra "Utilidad"/"Utilidad neta" (caja) → **"Flujo de caja"/"Flujo de caja neto"** y agrega la tarjeta **"Rentabilidad por productos"** (`profitability-card`: KPIs + tabla por producto + aviso de ítems sin costo). `DashboardPage` y `ReportsPage` renombran a "Flujo de caja". `reports.py` (Excel) etiqueta explícito devengado vs base caja.
- **No existe endpoint de edición de venta** (solo crear/eliminar), así que no hay hueco de costo no capturado. Ventas eliminadas se borran en duro.
- **Verificado**: testing agent iteration_16 100% (backend 4/4 + frontend 10/10): venta nueva Ray-Ban (precio 850, costo 450, x2) → ingreso 1700, COGS 900, margen 800 (47.1%); superadmin 403; etiquetas renombradas; limpieza de datos QA. Fases 2/3 (descuentos globales prorrateados al margen, costo manual en ítems sin producto, margen histórico estimado) pendientes.


### Guía de usuario (PDF): sección de suscripción y cobros (Jun 2026)
`routes/user_guide.py`: nueva subsección admin **"3.7 Mi Plan, suscripción y cobros"** (membresía USD, suscribirse/checkout, cambio de plan inmediato con prorrateo, Portal de Stripe para tarjeta/facturas/cancelar, y flujo de impago: gracia 3 días → suspensión/muro de pago → reactivación automática; cortesía exenta) + entrada en la Tabla de Contenidos. Verificado con build directo (`_build_pdf`) y endpoint `GET /api/docs/user-guide.pdf` (200, PDF válido). Caché en memoria (TTL 5 min) se limpia al reiniciar/redeploy.


### Cambio de plan en el lugar con prorrateo — fix doble cobro (Jun 2026)
El cambio de plan in-app creaba una SEGUNDA suscripción en Stripe y dejaba la anterior activa (doble cobro + suscripción huérfana). Fix en `routes/billing.py`: si la empresa ya tiene `stripe_subscription_id`, `POST /api/billing/checkout` ahora llama a `_modify_subscription_plan()` → `stripe.Subscription.modify(sub_id, items=[{id, price}], proration_behavior="create_prorations")` sobre la MISMA suscripción, actualiza plan_id/billing_cycle de inmediato, registra `payment_transactions(mode="subscription_change")` + `plan_history`, y devuelve `{"changed": true, ...}` (sin checkout, sin redirección). La primera suscripción (sin sub activa) sigue usando Stripe Checkout. Frontend `MyPlanPage.js` maneja `{changed:true}` con toast de éxito + refresco. El Customer Portal del usuario tiene deshabilitado el cambio de plan a propósito (se hace desde Cortexia). Validación E2E del `modify` solo posible en producción (Stripe placeholder en preview).


### Fix Stripe BYOK: aceptar llaves restringidas (rk_) + separación preview/prod (Jun 2026)
La integración de Stripe (SDK nativo, BYOK) fallaba en producción con "Stripe aún no está configurado" aunque la llave estaba en Manage → Secrets. Causa raíz (confirmada por el desplegador): la llave del usuario es una **restricted key (`rk_...`)** — válida del lado del servidor — pero la validación exigía `sk_`. Fix en `routes/billing.py`: `_stripe_configured()` acepta `sk_` y `rk_` (rechaza `pk_` publicable y el placeholder `sk_test_emergent`); `_resolve_stripe_key()` prioriza `STRIPE_SECRET_KEY` y luego `STRIPE_API_KEY`, ignorando el placeholder, con respaldo de lectura de `backend/.env` (preview). Log de diagnóstico (solo prefijo). Aprendizaje: **Manage → Secrets aplica solo a producción (deploy)**; en **preview** el backend lee de `backend/.env`.


### Fix overlay "Script error." (cross-origin) en dev/preview (Jun 2026)
El overlay rojo "Uncaught runtime errors: Script error." que aparecía en el navegador es un error ENMASCARADO por CORS proveniente de un script cross-origin (barra de preview de Emergent / extensiones del navegador / widgets de terceros), NO del bundle de la app. Se confirmó: en un navegador limpio (headless) la app carga sin overlay y el único log es el 401 esperado de `/api/auth/me` antes del login. No ocurre en producción (ese overlay es solo de dev).
- **Frontend** `src/index.js`: se generalizó el manejador global (mismo patrón ya usado para el error benigno "ResizeObserver loop") para que también detenga el overlay ante "Script error." cross-origin. Detección segura: `message` contiene "Script error", `error` es null y sin `filename`/`lineno` — condiciones exclusivas de errores cross-origin no accionables. Los errores reales del bundle (que sí traen message/filename/lineno/objeto error) NO se suprimen.


### Membresía cobrada en USD (Jun 2026)
La moneda de cobro de la MEMBRESÍA (planes de suscripción) pasó de GTQ a **USD**. La moneda OPERATIVA de cada óptica (ventas, POS, caja, finanzas, reportes) **sigue en Quetzales (Q)** — sin cambios. Decisión del usuario: solo se cambió la moneda; los montos de cada plan los ajusta el superadmin en el panel de Planes. Anual = 10× mensual (2 meses gratis), sin cambios.
- **Backend**: `models.py` `PlanCreate.currency` default `GTQ`→`USD`; `server.py` planes seed con `currency: "USD"` + **migración idempotente al arranque** que convierte planes sin moneda o en GTQ → USD (no toca otras monedas); `billing.py` `_plan_amount` default de moneda `gtq`→`usd` (moneda enviada a Stripe Checkout); `plans.py` stats_summary default `GTQ`→`USD`. Fix lint: `my-transactions` ahora retorna `[serialize_doc(t) ...]`.
- **Frontend**: `MyPlanPage.js` `fmt` mapea USD→`$` (default USD); `PlansPage.js` helper `curSymbol` (USD→$, GTQ→Q) usado en tarjetas de plan, MRR/ARR por plan y StatCards (MRR/ARR/Ingresos 30d en `$`), label del form "Precio (USD/mes)"; `AdminOpticasPage.js` dropdown de plan y "Costo mensual actual" en `$`; `SuperAdminDashboard.js` KPI MRR y tooltip de Revenue en `$`.
- Verificado: `GET /api/plans` y `/api/plans/stats/summary` devuelven `currency: USD` (Free/Basic/Enterprise); migración aplicada (3 planes en USD); frontend compila. Números de precio sin cambios (los edita el superadmin).


### Revisión completa de la Guía de Usuario PDF (Jun 2026)
Revisión sección por sección de la guía (`routes/user_guide.py`) para dejarla al día con todas las funciones actuales (también sirve como material comercial vía enlace público). Sin rediseño visual ni cambios en los pasos del Inicio rápido (opción A: se dejan los 8 pasos). Solo contenido. Antes de documentar, se verificó en el código que cada función exista.
- **§1 Módulos**: agregados "Cuentas por Pagar" y "Estado de Resultados" a la tabla de módulos.
- **§3.3 Inventario/proveedores**: aclarado que un proveedor se vincula tanto a productos como a egresos/compras de Finanzas.
- **§3.4 Caja y finanzas** (mayor actualización, ahora 2 páginas): egresos integrados en el arqueo (solo efectivo resta del efectivo esperado), resumen del turno en vivo, botón "Registrar egreso" desde Caja (método+proveedor), "Imprimir cierre (PDF)" y "Descargar egresos del turno (Excel)", egreso con proveedor (obligatorio en categoría Proveedores), egresos a crédito → Cuentas por Pagar con abonos y vencimientos, anular movimiento con motivo (auditable), Estado de Resultados base caja vs utilidad bruta, y arrastre de cuentas por cobrar/pagar.
- **§3.5 Reportes/auditoría**: añadidos reportes de Finanzas (compras por proveedor, egresos por rango, Estado de Resultados) y nota de que las anulaciones quedan registradas en Auditoría.
- **§4.2 Ventas**: mención de "Imprimir recibo" y "Compartir por WhatsApp" del comprobante.
- **§4.3 Caja diaria**: botón Registrar egreso desde Caja, resumen del turno en vivo, Imprimir cierre (PDF), Descargar egresos (Excel), y que solo egresos en efectivo afectan el efectivo esperado.
- **§5.2 Recetas**: agregado bloque "Receta de lentes de contacto" (OD/OS: esfera, cilindro, eje, adición, diámetro, curva base; marca/reemplazo/vencimiento; PDF y WhatsApp). Sección renombrada a "Recetas de anteojos, contacto y médicas".
- **§6 Jornadas**: agregado modo offline (captura sin internet, datos cifrados en el dispositivo, sincronización automática) + tip del indicador de sincronización.
- **§7 Buenas prácticas**: 2 consejos nuevos ("Anula, no borres" y "Revisa Cuentas por Pagar y sus vencimientos").
- **TOC**: números de página corregidos a los valores reales (el PDF ahora tiene 21 páginas; el índice ocupa 2 páginas).
- Verificado: `_build_pdf()` genera 21 páginas válidas (%PDF), sin errores de encoding (ñ, acentos, −, P&L), y el endpoint en vivo `GET /api/docs/user-guide.pdf` responde 200 con admin (cookie httpOnly).


### Estado de Resultados mensual (P&L, base caja) (Jun 2026)
Vista y exportación del P&L (ingresos por categoría − egresos por categoría = utilidad neta) en Finanzas, usando el rango de fechas y sucursal seleccionados. **Base CAJA** (decisión del usuario): los ingresos ya son base caja (una entrada por pago real; los abonos a cuentas por cobrar generan su propia entrada), los egresos de contado cuentan por su fecha, y **los egresos a crédito cuentan SOLO por los abonos realmente pagados** (payments[] con fecha en el rango), NO por el total devengado. Excluye anulados. Coexiste con `/summary` (que sigue en base devengado para la vista de Movimientos).
- **Backend** `routes/finance.py`: `_compute_income_statement(...)`; `GET /api/finance/income-statement` (JSON), `/income-statement.xlsx` (`_render_pl_xlsx`, hoja INGRESOS/EGRESOS/UTILIDAD NETA) y `/income-statement.pdf` (`_render_pl_pdf`, reportlab). superadmin 403, branch_id inválido 400. Audit `FINANCE_INCOME_STATEMENT`.
- **Frontend** `FinancePage.js`: tarjeta `income-statement-card` (ingresos y egresos por categoría, totales, "Utilidad neta" verde/rojo, nota de base caja) + botones "Excel" (`export-pl-excel-btn`) y "PDF" (`export-pl-pdf-btn`). Se refresca con el rango/sucursal actuales.
- **Arrastre de cuentas (confirmado)**: las **cuentas por cobrar** (ventas con saldo>0) persisten hasta que los abonos dejan el saldo en 0 (o se cancela/revierte la venta); las **cuentas por pagar** (egresos a crédito con saldo>0) persisten en Cuentas por Pagar hasta quedar en 0 (status "pagado") o ser anuladas. Ambas se arrastran entre periodos/turnos; los abonos van reduciendo el saldo. (Comportamiento ya existente, sin cambios.)
- Verificado: pytest `test_income_statement_iter14.py` 16/16 (base caja: crédito cuenta abonos no total; divergencia con /summary devengado; xlsx/pdf; 403/400) + testing agent iteration_14 100% frontend (tarjeta + 2 exports 200). Datos QA limpiados.


### Reporte de Egresos por Rango a Excel (Jun 2026)
Exportar a Excel TODOS los egresos entre dos fechas (no solo por turno) para el cierre contable mensual.
- **Backend** `routes/finance.py`: `GET /api/finance/expenses-report.xlsx?date_from&date_to&branch_id` (admin/vendedor; superadmin 403; branch_id inválido 400). Filtra `type='egreso'` + `is_voided:{$ne:True}` + rango de fechas + sucursal. Excel (`_render_expenses_xlsx`, openpyxl) con 2 hojas: **Resumen** (TOTAL EGRESOS + "Por Categoria" + "Por Metodo de Pago") y **Detalle** (Fecha, Categoria, Proveedor, Descripcion, Metodo, Credito, Pagado, Saldo, Referencia, Monto). Etiquetas ES vía `_EXPENSE_CATEGORY_LABELS`/`_EXP_METHOD_LABELS`. Audit `FINANCE_EXPENSES_REPORT`.
- **Frontend** `FinancePage.js`: `handleExportExpenses()` y botón "Exportar egresos (Excel)" (`export-expenses-btn`) en la barra de filtros de fecha; usa el rango (date_from/date_to) y la sucursal seleccionados.
- Verificado: pytest `test_expenses_report_iter13.py` 7/7 (2 hojas, columnas, excluye anulado e ingreso, 403/400, regresión purchases-report) + testing agent iteration_13 100% frontend (botón dispara descarga 200 spreadsheet). Datos QA limpiados.


### Exportar Egresos del turno a Excel (Jun 2026)
Además del PDF de arqueo, se puede descargar los egresos del turno en Excel (conciliación contable).
- **Backend** `routes/cash_register.py`: `GET /api/cash-register/{register_id}/egresos.xlsx` (`_render_cierre_egresos_xlsx`, openpyxl). Si la caja está ABIERTA recalcula los egresos del turno en vivo con `_compute_close_totals` (excluye anulados); si está CERRADA usa el snapshot `egresos_detail`. Columnas: Fecha, Hora, Descripción, Proveedor, Categoría, Método, Crédito, Monto + filas TOTAL y "En efectivo". 403 superadmin, 400 id inválido, 404 otra empresa. Declarado ANTES de `/{register_id}`. Audit `CASH_REGISTER_EGRESOS_XLSX`.
- **Frontend** `CashRegisterPage.js`: `downloadEgresosExcel(id)`; botón "Excel" (`shift-egresos-excel-btn`) en la tarjeta "Egresos del turno" (caja abierta, usa `current._id`) y botón "Egresos (Excel)" (`detail-egresos-excel-btn`) junto a "Imprimir cierre (PDF)" en el modal de detalle (cierre cerrado, usa `detail._id`).
- Verificado: pytest `test_egresos_xlsx_iter12.py` 9/9 (open recalcula + closed snapshot, excluye anulados, 403/400/404, TOTAL/efectivo correctos) + testing agent iteration_12 100% frontend (ambos botones disparan descarga 200). Datos QA limpiados.
- Endurecido el silenciador del overlay dev benigno "ResizeObserver loop" en `index.js` (además de silenciar el error, oculta el overlay de webpack-dev-server que bloqueaba clics en el preview; solo dev, no afecta producción).


### Anular egreso/movimiento (soft-void) (Jun 2026)
Se puede ANULAR un movimiento financiero mal registrado (decisión del usuario: anular, no editar ni eliminar). Aplica a egresos e ingresos manuales.
- **Regla**: el movimiento anulado queda VISIBLE tachado en el historial (auditable, con badge "Anulado" + responsable) y DEJA DE CONTAR en totales, cuentas por pagar y en la caja. Motivo obligatorio. Irreversible.
- **Permisos**: puede anular el **admin** (cualquier movimiento de su óptica) o el **vendedor que lo creó** (created_by == user). Superadmin 403.
- **Backend** `routes/finance.py`: `POST /api/finance/{entry_id}/void` (body `{reason}`) → valida oid (400), existencia+tenant (404), autorización admin|creador (403), no-doble-anulación (400), motivo no vacío (400); setea `is_voided/voided_at/voided_by/voided_by_name/void_reason`; audita `FINANCE_ENTRY_VOIDED`. Exclusión `is_voided:{$ne:True}` añadida a `list_payables`, `payables/alerts`, `add_payable_payment` (find), `summary`, `purchases-report.xlsx` y `dashboard`. `GET /api/finance` SÍ sigue devolviendo los anulados (con el flag) para mostrarlos tachados.
- **Backend** `routes/cash_register.py`: `_compute_close_totals` filtra egresos `is_voided:{$ne:True}` (el arqueo ya no cuenta anulados) y `egresos_detail` incluye `created_by`.
- **Frontend**: (Finanzas `FinancePage.js`) columna "Acciones" con botón "Anular" (`void-btn-{id}`), filas anuladas tachadas + `voided-badge-{id}`, diálogo `void-dialog` (`void-reason-input`, `void-confirm-btn`); los totales por proveedor y el filtro excluyen anulados. (Caja `CashRegisterPage.js`) tarjeta "Egresos del turno" en vivo (`shift-egresos-list`) con botón Anular por fila (`shift-egreso-void-{i}`) y diálogo `shift-void-dialog`; al anular, el egreso desaparece y el Efectivo esperado se recalcula. El botón solo aparece si el usuario puede anular (admin o creador).
- Verificado: curl E2E de todos los edge cases (200/400 motivo vacío/400 doble/403 vendedor ajeno/403 superadmin/400 id inválido; caja expected 50→100 al anular; summary expense 50→0; listado muestra is_voided). Testing agent iteration_11: 100% frontend en Finanzas + Caja + permisos vendedor/admin. Datos QA limpiados.


### Egreso desde Caja + Detalle de Egresos en PDF (Jun 2026)
Dos features sobre la pantalla de Caja (`/cash-register`), continuación de la integración de egresos en caja:
- **Egreso desde Caja**: botón "Registrar egreso" (`register-egreso-btn`, visible solo con caja abierta) abre el diálogo `egreso-dialog` (monto, categoría, método de pago seleccionable —efectivo/tarjeta/transferencia/cheque/otro—, proveedor opcional/obligatorio solo si categoría=Proveedores, descripción). Usa el mismo `POST /api/finance` (type=egreso). Tras registrar, refresca un **resumen del turno en vivo** (`shift-summary`: Recaudado, Egresos, Fondo inicial, Efectivo esperado) que se carga con `GET /current/preview` cuando la caja está abierta. Data-testids: `register-egreso-btn`, `egreso-dialog`, `egreso-amount`, `egreso-category`, `egreso-method`, `egreso-supplier`, `egreso-description`, `egreso-submit`, `shift-summary`, `shift-egresos`, `shift-expected-cash`.
- **Detalle de Egresos en PDF** (ambos lugares):
  - (a) Reporte de rango (`GET /api/cash-register/report/pdf`): nueva sección "Detalle de egresos del periodo" que lista línea por línea (cierre, sucursal, descripción, proveedor, método, monto) todos los egresos de los cierres del periodo. `_build_report` ahora devuelve `egresos_detail` (lista plana).
  - (b) **PDF por cierre individual**: nuevo `GET /api/cash-register/{register_id}/pdf` (`_render_single_cierre_pdf`) → "Arqueo de Caja" de ESE cierre: fondo inicial, ventas por método, TOTAL recaudado, egresos del turno (efectivo/total), EFECTIVO ESPERADO, contado, diferencia, tabla de egresos línea por línea (hora/descripción/proveedor/método/monto), cuentas por cobrar generadas y notas de cierre. Botón "Imprimir cierre (PDF)" (`print-cierre-btn`) en el modal de detalle (solo cierres cerrados). Ruta declarada ANTES de `/{register_id}` para evitar colisión.
- Fix menor: suprimido el overlay dev benigno "ResizeObserver loop" en `index.js` (interrumpía clics con Selects/Dialogs en el preview; no afecta producción).
- Verificado: pytest `test_caja_egresos_iter10.py` 14/14 (per-cierre PDF 200/403/404/400 + contenido, range PDF con sección egresos, sin colisión con GET /{id} JSON, regresión finance). E2E frontend (iteration_10): egreso cash 40 → Efectivo esperado 60; egreso transfer 20 → Egresos total 60 pero esperado sigue 60; validación proveedor obligatorio; cierre → botón Imprimir cierre dispara PDF. Curl main agent: ambos PDFs 200 %PDF con descripciones dentro (pypdf). Datos QA limpiados.


### Egresos integrados en Caja (Apertura/Cierre) (Jun 2026)
Los egresos (compras/gastos de Finanzas) ahora se reflejan en el arqueo de caja del turno. Regla confirmada por el usuario: SOLO los egresos en efectivo restan del efectivo esperado; egresos por otros métodos suman al total de egresos del turno pero NO afectan el efectivo esperado. Para egresos a crédito, la salida de efectivo del turno es el abono inicial (`amount_paid`), no el total.
- **Backend** `routes/cash_register.py` `_compute_close_totals`: además de ventas, lee `db.finance_entries` (`type='egreso'`, `branch_id`, `created_at` en [opened_at, closed_at]), agrupa por `payment_method`, usa `amount_paid` si `is_credit` else `amount`. Devuelve `egresos_by_method`, `egresos_total`, `egresos_cash`, `egresos_count`, `egresos_detail`. `expected_cash = opening_amount + totals_by_method.cash - egresos_cash` (preview y cierre). El PDF de reporte incluye "Egresos del turno (efectivo)" y "(total)"; `/report` agrega `grand_egresos_total`/`grand_egresos_cash`.
- **Backend** `routes/finance.py`: nuevo helper `_resolve_branch_id(user)` — los admins sin `branch_id` ahora atribuyen sus egresos a la sucursal principal (misma lógica que la caja) para que SÍ se reflejen en su cierre (antes quedaban con `branch_id=None` y no cuadraban). También se corrigió el 500 de `GET /api/finance` serializando `payments[].created_by` (ObjectId→str).
- **Frontend** `pages/CashRegisterPage.js`: (1) el modal "Cerrar caja" hace `GET /current/preview` al abrir y muestra bloque `close-preview` (recaudado efectivo, egresos efectivo, Efectivo esperado ya con egresos restados) + diferencia en vivo al escribir `counted-cash`; (2) el modal "Detalle de caja" muestra sección `cash-egresos-section` con tabla (descripción/proveedor/método/monto) + línea resumen `detail-egresos-summary`. `METHOD_META` ahora incluye `check` (Cheque). Data-testids: `close-preview`, `close-preview-expected-cash`, `close-preview-egresos-cash`, `close-preview-egresos-note`, `close-preview-difference`, `cash-egresos-section`, `egreso-row-{i}`, `detail-egresos-summary`.
- Verificado: pytest `tests/test_caja_egresos_iter9.py` 10/10 (venta cash + egreso cash/transfer/crédito → preview → cierre → PDF → regresión finance list sin 500). E2E frontend (iteration_9): modal de cierre con Efectivo esperado Q25 y egresos -Q75, cierre, detalle con sección Egresos. Fix admin verificado por curl (expected_cash 60 = 100−40). Datos de prueba limpiados (0 QA, 0 cajas abiertas).


### Recordatorio de vencimiento de Cuentas por Pagar (Jun 2026)
Avisos in-app al admin cuando un egreso a crédito está por vencer o ya venció (base contable devengado; canal in-app, consistente con las alertas de plan/stock del Dashboard).
- **Backend** `routes/finance.py`: `GET /api/finance/payables/alerts?days=7&branch_id` → `{days, overdue:{count,total}, due_soon:{count,total}}` (vencidas = due_date < hoy; por vencer = hoy..hoy+days). `list_payables` ahora añade `days_until_due` e `is_due_soon` (≤7 días) por item.
- **Frontend**:
  - `DashboardPage.js`: tarjeta `payables-reminder-card` (roja si hay vencidas, ámbar si solo por vencer) con conteos + montos y enlace "Ver cuentas por pagar →".
  - `MainLayout.js`: insignia roja con el conteo (vencidas+por vencer) en el ítem "Cuentas por Pagar" (fetch a `/payables/alerts` solo para no-superadmin con módulo finanzas y permiso `payables`). `nav-badge-payables`.
  - `PayablesPage.js`: nuevo KPI "Por vencer" (próximos 7 días).
- Nota: la vista/menú Finanzas y Cuentas por Pagar requieren el módulo `finanzas` en el plan (el plan Basic demo no lo incluye; verificado habilitándolo temporalmente y revirtiendo). El umbral de "por vencer" es 7 días. No se agregó aviso por correo (posible mejora futura).
- Verificado E2E: alerts con 1 vencida (Q400) + 1 por vencer (Q250) y la lejana (+60d) excluida; tarjeta del Dashboard con montos correctos; insignia "2" en el menú (plan con finanzas); KPI "Por vencer" en la página. Datos de prueba y módulo del plan revertidos.

### Reporte de compras (Excel) + Cuentas por Pagar (Jun 2026)
Dos features sobre proveedores en Finanzas:

**Reporte de compras a Excel**
- `GET /api/finance/purchases-report.xlsx?date_from&date_to&branch_id` (admin/vendedor; superadmin 403). Agrupa egresos con proveedor del periodo. Genera xlsx en hilo (`_render_purchases_xlsx`, openpyxl) con 2 hojas: "Por Proveedor" (proveedor, nº egresos, total pagado, TOTAL) y "Detalle" (fecha, proveedor, categoría, descripción, referencia, monto). Encabezado navy #1B2A49.
- Frontend `FinancePage.js`: botón "Exportar a Excel" (`export-purchases-btn`) en la tarjeta "Egresos por Proveedor"; descarga con los filtros de fecha/sucursal actuales.

**Cuentas por Pagar (egresos a crédito, devengado)**
- Registro desde el modal "Nueva Entrada Financiera" (Egreso): checkbox "Egreso a crédito (cuenta por pagar)" + "Monto pagado ahora" (abono inicial) + "Fecha de vencimiento". Proveedor obligatorio para crédito.
- **Base contable: DEVENGADO** — el monto TOTAL del egreso cuenta como gasto desde el registro (aparece en el total de Egresos/Utilidad de inmediato). Los abonos SOLO bajan el saldo; NO crean nuevos movimientos. (Nota: los ingresos por ventas siguen siendo base caja; esta asimetría fue una decisión explícita del usuario para egresos.)
- Backend `routes/finance.py`: en `POST /api/finance`, si `is_credit` guarda `is_credit`, `amount_paid`, `balance`, `status` (pendiente/pagado), `due_date`, `payments[]` (abono inicial si aplica). `GET /api/finance/payables` (egresos crédito con balance>0: items + total_pending + count + by_supplier, con `days_pending` e `is_overdue`). `POST /api/finance/payables/{id}/payment?amount&method&note` (abono: valida no exceder saldo → 400; actualiza amount_paid/balance/status; push a payments).
- Frontend: nueva página `PayablesPage.js` (`/payables`) estilo "Cuentas por Cobrar": KPIs (saldo total por pagar, proveedores con deuda, vencidas), "Saldo por Proveedor", tabla (fecha, proveedor, concepto, vencimiento con badge "Vencida", total, pagado, saldo, antigüedad, botón "Abonar") y diálogo de abono (`PayableAbonoDialog`). Ítem de menú "Cuentas por Pagar" (icono Banknote) bajo módulo `finanzas`; agregado a `RolePermissionsSection` (key `payables`). Modelo `FinanceEntryCreate` +`is_credit/amount_paid/due_date`. Badge "Crédito · saldo" en la tabla de Movimientos.
- Verificado E2E: Excel con hojas Resumen+Detalle y totales correctos; crédito 1000 pagado 200 → balance 800; sin proveedor 400; payables list OK; abono 300 → 500; abono que excede → 400; summary incluye el total 1000 (devengado). Frontend: modal con bloque crédito, página con KPIs/tabla, diálogo de abono. Datos de prueba limpiados.


Tres mejoras sobre el proveedor en Finanzas (`FinancePage.js` + `routes/finance.py`):
- **Proveedor obligatorio en categoría "Proveedores"**: si el egreso es de categoría `suppliers` y no se elige proveedor, se bloquea. Frontend valida (toast) y muestra `*` en la etiqueta; backend devuelve 400 "Selecciona un proveedor para egresos de la categoria Proveedores.".
- **Filtro por proveedor en Movimientos**: select `supplier-filter` (poblado con los proveedores que aparecen en los movimientos del periodo) que filtra la tabla por `supplier_id` (client-side, junto al filtro de tipo).
- **Total por proveedor**: tarjeta "Egresos por Proveedor" (`supplier-totals-card`) que agrupa y suma los egresos con proveedor del periodo seleccionado, ordenados de mayor a menor, con barra proporcional.
- Verificado E2E: 400 sin proveedor en categoría Proveedores; tarjeta muestra totales correctos (Essilor Q500 / Optilab Q450); filtro por Optilab deja 2 filas. Datos de prueba limpiados.

### Proveedor en Egresos (Finanzas) (Jun 2026)
En "Nueva Entrada Financiera" (`FinancePage.js`), al elegir tipo **Egreso** aparece un campo **Proveedor** (select) poblado desde la lista de proveedores existente (`GET /api/suppliers`). Decisiones: solo visible en Egresos; **opcional**; si no hay proveedores muestra un enlace a `/suppliers` para agregarlos.
- **Backend**: `FinanceEntryCreate` +`supplier_id: Optional[str]`. `POST /api/finance` valida que el proveedor exista y pertenezca a la company (400 id inválido, 404 no encontrado) y guarda `supplier_id` (ObjectId) + `supplier_name` (resuelto en el servidor). El listado serializa el `supplier_id`.
- **Frontend**: fetch de proveedores al montar; select `entry-supplier` (con opción "Sin proveedor"); se limpia al cambiar a Ingreso; solo se envía `supplier_id` si es egreso. Nueva columna "Proveedor" en la tabla de Movimientos (muestra `supplier_name` o "—"). Data-testids: `supplier-field`, `entry-supplier`, `add-supplier-link`.
- Verificado E2E: egreso con proveedor guarda `supplier_name`+`supplier_id`; 400/404 en validación; UI muestra el select solo en Egresos (oculto en Ingresos) y la columna Proveedor. Datos de prueba limpiados.

### Onboarding: nuevo Paso 1 "Descarga la Guía de usuarios" (Jun 2026)
`OnboardingPage.js` — se agregó como **Paso 1** el paso "Descarga la Guía de usuarios" (icono BookOpen). Los 7 pasos previos pasan a 2–8 (mismo orden/textos). Total ahora **8 pasos**; el medidor y el texto muestran "X de 8".
- Botón "Descargar la guía" descarga `GET /api/docs/user-guide.pdf` (blob) y **auto-marca** el paso como completado (también editable a mano con el checkbox). `id='download_guide'` agregado a `ALLOWED_STEP_IDS` en `routes/onboarding.py`.
- `OnboardingWidget.js` (dashboard) refleja el total 8 automáticamente (importa `STEPS`).
- Guía PDF (`user_guide.py`): sección "Antes de empezar" actualizada de "7 pasos" → "8 pasos" y se menciona que el Paso 1 es descargar la Guía de usuarios.
- Verificado E2E: PUT status `download_guide` 200; guía contiene "8 pasos" (ya no "7 pasos"); UI muestra 8 cards, Paso 1 = descarga guía, renumeración correcta, botón descarga + auto-marca (2→3 de 8). Estado de prueba restaurado.


Dos mejoras sobre las cuentas de cortesía:
- **Filtro "Cortesía" (SuperAdmin)**: `AdminOpticasPage.js` — nueva pestaña de filtro `activation-filter-cortesia` (junto a Todas/Sin activar/Activas/Inactivas) que muestra solo las ópticas con `is_courtesy`. Cada card muestra además un badge verde "Cortesía" (`courtesy-badge-{id}`) para verlas de un vistazo. Filtrado client-side sobre el campo `is_courtesy` que ya devuelve `GET /companies`.
- **Exención de inactivación**: helper `db.is_billing_exempt(company)` → True para cortesías. `activation_task._process_deactivations` ahora excluye del pipeline las cuentas de cortesía (`company.is_courtesy: {$ne: True}`): NUNCA se desactivan automáticamente (por expiración de activación hoy, ni por futuras reglas de falta de pago). Docstring actualizado.
- Verificado: exención E2E (empresa creada hace 40 días con admin sin login: con cortesía queda `is_active=True`; sin cortesía se desactiva con `deactivated_reason=activation_expired`); filtro E2E (muestra 1/3, badge "Cortesía" en el card). Datos de prueba limpiados (0 cortesías activas).


El SuperAdmin puede marcar una óptica como "cuenta de cortesía" para que su costo mensual efectivo sea **Q0**, SIN cambiar plan, módulos ni límites. Pensado para regalar acceso a un grupo de optometristas. Óptica por óptica, a mano; permanente hasta que se quite; reversible; auditado.
- **Costo mensual efectivo**: helper `db.effective_monthly_cost(company, plan)` → Q0 si `company.is_courtesy`, si no `plan.price_monthly` (o `price`).
- **Backend**:
  - **NUEVO** `PUT /api/companies/{id}/courtesy` (SuperAdmin, CSRF). Body `{is_courtesy: bool}`. `true` setea `is_courtesy=True`; `false` hace `$unset`. Guarda `courtesy_updated_at/by`. Audita `COMPANY_COURTESY_GRANTED` / `COMPANY_COURTESY_REVOKED`. Devuelve `{ok, is_courtesy, effective_monthly_cost, plan_monthly_cost}`. 403 no-superadmin.
  - `GET /companies`: añade `is_courtesy`, `monthly_cost` (efectivo) y `plan_monthly_cost`.
  - `GET /plans/usage/{id}`: añade `is_courtesy`, `monthly_cost`, `plan_monthly_cost`.
  - `GET /plans/stats/summary`: el MRR ahora **excluye** las cuentas de cortesía (agrupa por `is_courtesy`; las de cortesía no suman a `companies_monthly/yearly`). Añade `companies_courtesy` por plan y `total_courtesy` global. La distribución (`total_companies`) sí las incluye.
- **Frontend**:
  - `AdminOpticasPage.js` (tab Info): sección "Cuenta de cortesía" con `Switch` (data-testid `courtesy-switch`), badge "Activa" (`courtesy-active-badge`) cuando está activa, y texto "Costo mensual actual: Q… (cortesía)". Actualiza `selectedCompany` + recarga listado.
  - `MyPlanPage.js`: la tarjeta "Plan actual" muestra una fila "Costo mensual" con el costo efectivo (`usage.monthly_cost`) — Q0.00 si es cortesía, sin ninguna etiqueta de cortesía (la óptica solo ve Q0). Data-testids `monthly-cost-row`, `monthly-cost-value`.
- Campo Mongo `companies.is_courtesy` (bool, opcional).
- **Reglas de inactivación por falta de pago**: no existen aún (se definirán con el módulo de pagos); cuando existan, deberán exentar `is_courtesy`.
- Verificado E2E: activar cortesía en óptica de plan Q699 → efectivo Q0; usage y listado reflejan Q0+is_courtesy; MRR bajó 998→299 (−699) y `total_courtesy=1`; quitar → vuelve a Q699; no-superadmin 403. Frontend: switch con badge "Activa" + toast + "Q0.00 (cortesía)"; "Mi Plan" muestra "Costo mensual Q 299.00" (no cortesía). Datos de prueba limpiados (0 cortesías activas).


El SuperAdmin puede subir el tope de pacientes de una óptica específica (p. ej. de 50 a 150) SIN cambiar su plan, precio ni módulos. Pensado como beneficio para ópticas que llegaron con código de promoción. Óptica por óptica, a mano; reversible; auditado.
- **Concepto "límite efectivo"**: helper `db.effective_max_patients(company, plan)` → devuelve `company.patient_limit_override` si está fijado (>0), si no `plan.max_patients`.
- **Backend**:
  - `routes/patients.py`: `_check_patient_limit` y `_notify_patient_limit` ahora usan el límite efectivo (el bloqueo 403 y los avisos "cerca del límite / límite alcanzado" respetan el override).
  - `routes/plans.py` `GET /plans/usage/{id}`: `max_patients` = efectivo; añade `patient_limit_override` y `plan_max_patients` a la respuesta.
  - `routes/companies.py` `GET /companies`: `max_patients` y `patients_warning` se calculan con el efectivo (el override ya viaja en el doc serializado).
  - **NUEVO** `PUT /api/companies/{id}/patient-limit` (SuperAdmin, CSRF). Body `{patient_limit_override: int|null}`. Valor >0 fija override; `null`/≤0 hace `$unset` (vuelve al plan). Guarda `patient_limit_updated_at/by`. Audita `COMPANY_PATIENT_LIMIT_SET` / `COMPANY_PATIENT_LIMIT_CLEARED` (old/new/plan_max/effective). Devuelve `{ok, patient_limit_override, effective_max_patients, plan_max_patients}`. 403 para no-superadmin.
- **Frontend** `AdminOpticasPage.js` (tab Info de la ficha de óptica): sección "Límite de pacientes" con input precargado en **150** (editable a cualquier número), botón "Fijar límite" y, si hay override, badge "Personalizado" + botón "Quitar límite personalizado". Muestra "Actual: N pacientes (personalizado/según su plan)". Actualiza `selectedCompany` y recarga el listado tras guardar. Data-testids: `patient-limit-section`, `patient-limit-input`, `patient-limit-save-btn`, `patient-limit-clear-btn`, `patient-limit-custom-badge`.
- Config: campo Mongo `companies.patient_limit_override` (int, opcional).
- Verificado E2E: set 150→efectivo 150 (plan 10000), usage/list reflejan 150+override, clear→vuelve al plan, no-superadmin 403; **enforcement real**: override=1 en óptica con 19 pacientes → crear paciente devuelve 403 "Limite alcanzado (1)", tras quitar override → 200. Frontend: control renderiza, toast, badge "Personalizado", contador 5/150, botón quitar. Datos de prueba limpiados (0 overrides activos).


Opción para imprimir/compartir un recibo de pago desde el POS principal (`/sales`).
- **Formato media carta horizontal** (8.5×5.5 in = 612×396pt, igual que las recetas). Diseño profesional en `_render_sale_receipt_pdf`: banda de encabezado navy (#1B2A49) con **logo de la óptica** a la izquierda, nombre/razón social/NIT/tel/email en blanco; título "RECIBO DE PAGO"; meta (Recibo #, Fecha, Cliente, Atendió); tabla de artículos (PRODUCTO/CANT/PRECIO/TOTAL); bloque "FORMA DE PAGO" a la izquierda y totales a la derecha (Subtotal, Descuento, TOTAL en navy, Pagado, SALDO PENDIENTE en ámbar); pie con "Gracias por su compra" + web.
- **Logo**: `_get_company_logo_bytes(company)` obtiene el logo desde Object Storage (`logo_storage_path`) o filesystem local (fallback) y se embebe con `ImageReader`. Si no hay logo, se omite sin romper.
- **Backend** `routes/sales.py`:
  - `GET /api/sales/{sale_id}/receipt.pdf` (admin/vendedor; superadmin 403; venta ajena/inexistente 404). Render en hilo vía `_build_sale_receipt_pdf` (resuelve empresa/cliente/vendedor/logo). Inline `recibo_XXXX.pdf`.
  - `GET /api/sales/{sale_id}/receipt-share-link` (auth): genera JWT firmado (`sub=sale-receipt`, sale_id, company_id, exp `RECEIPT_SHARE_HOURS`=720h/30d, jti). Devuelve `{path, token, expires_at, phone (normalizado +502), patient_name, message}` para compartir por WhatsApp.
  - `GET /api/sales/public/receipt?token=` (PÚBLICO, sin auth, `@limiter 20/min`): valida el JWT y sirve el mismo PDF (410 expirado, 403 inválido, 404 no encontrado). Multi-tenant por `company_id` del token.
- **Frontend** `SalesPage.js`: helpers `printReceipt(id)` (abre PDF blob en pestaña nueva) y `shareReceiptWhatsApp(id)` (pide share-link, arma `window.location.origin + path` y abre `wa.me/{phone}?text=mensaje+enlace`). Botones en 3 lugares: (1) diálogo post-venta "Venta registrada" (Imprimir + Enviar por WhatsApp + Cerrar), (2) Detalle de Venta (Imprimir + Enviar por WhatsApp), (3) ícono Printer por fila en el Historial. Data-testids: `sale-receipt-dialog`, `sale-receipt-print-btn`, `sale-receipt-whatsapp-btn`, `sale-receipt-close-btn`, `detail-print-receipt-btn`, `detail-whatsapp-receipt-btn`, `print-receipt-{id}`.
- Config env: `RECEIPT_SHARE_HOURS=720`.
- Verificado: curl E2E (receipt 200 %PDF con logo embebido / share-link con phone+message / público 200 sin auth / inválido 403), tamaño de página confirmado 612×396pt, render a imagen (logo + layout media carta correctos) y screenshots del frontend (botones Imprimir + WhatsApp visibles en detalle e historial).


Cuatro mejoras sobre el módulo de Solicitudes (leads), todas verificadas por API + navegador:
- **Guard de ruta admin**: nuevo `components/RequireSuperAdmin.jsx` (usa `useAuth().user.role`); envuelve `/admin/leads` y `/admin/correos` en App.js. Un no-superadmin es redirigido a `/dashboard` (antes solo veía toast + datos vacíos). Verificado: admin@cortexia.gt → redirigido.
- **Abrir cuenta desde una solicitud** (alta real): `POST /api/leads/{id}/create-account` (superadmin) crea empresa + usuario admin REUTILIZANDO el flujo existente (`hash_password`, mismos campos que `POST /api/companies`, `render_welcome_company` + `queue_email`). Genera contraseña temporal fuerte (`secrets`) si no se pasa una, la devuelve para compartir, encola el correo de bienvenida con credenciales, marca la solicitud `cuenta_creada` + `company_id`, y hace rollback de la empresa si el correo ya existe como usuario (409). Verificado E2E: la cuenta creada **inicia sesión correctamente**. 409 si ya fue convertida. NO se escribió auth nuevo (se reutilizó el flujo vetado existente). UI: botón "Abrir cuenta" + diálogo con datos precargados y contraseña opcional; pantalla de éxito con la contraseña temporal (copiar).
- **Aviso de nueva solicitud**: al enviar el formulario público, `_notify_superadmins_new_lead` encola (cola durable) un correo a todos los superadmins activos (fallback env `CORTEXIA_ALERTS_TO`/`ADMIN_EMAIL`) + crea notificación push. Best-effort (no rompe el submit). Verificado: 2 correos `tag=new_lead` encolados.
- **Estado de solicitud**: campo `status` (nueva/contactada/cuenta_creada, default "nueva"). `PATCH /api/leads/{id}/status` (superadmin). Filtro por estado en `GET /api/leads` y en la UI; columna Estado con selector inline (nueva/contactada) o badge "Cuenta creada"; columna Estado añadida al export XLSX. Menú renombrado a "Solicitudes".


### Formulario público "Solicita tu cuenta" + panel SuperAdmin (Jun 2026)
Formulario público compartible (sin login) para que ópticas soliciten abrir cuenta; datos SOLO para superadmin (global, sin tenant). Al enviar SOLO se registra la solicitud (el superadmin revisa y abre la cuenta manualmente — NO crea cuentas automáticamente).
- **Backend** `routes/leads.py` (colecciones `leads` y `promo_codes`; índices únicos `leads.email` y `promo_codes.code`):
  - `POST /api/leads` PÚBLICO (@limiter 5/min por IP, honeypot `website`, correo único global 409, WhatsApp normalizado +502, matchea solo códigos `is_active=True`, captura de origen desde `source`/`source_details`). Campos: name, optica_name (obligatorio), location "Ciudad/País" (obligatorio), whatsapp, email, promo_code (opcional), consent (obligatorio). Duplicado por WhatsApp permitido pero marcado (`is_possible_duplicate`).
  - SUPERADMIN: `GET /api/leads` (filtros promo_code incl. "sin_codigo", source, search, duplicates; paginado), `/stats`, `/grouped` (por código + grupo "Sin código", con miembros y conteo), `/sources`, `/export` (XLSX en hilo con columnas Nombre/Óptica/Ciudad-País/WhatsApp/Correo/Código/Origen/Duplicado/Consentimiento/Fecha), y códigos `GET/POST /codes` + `PATCH /codes/{id}` (activar/desactivar). Guard `role==superadmin` (403).
- **Frontend**: `PublicLeadFormPage.jsx` (ruta pública `/registro`, fuera de ProtectedRoute, axios propio, mobile-first, precarga `?codigo=`, valida en tiempo real, honeypot, pantalla de éxito). Título "Solicita tu cuenta", botón "Solicitar mi cuenta", consentimiento reescrito para apertura de cuenta. `LeadsAdminPage.jsx` (ruta `/admin/leads`, superadmin) con tabs Solicitudes/Agrupado/Códigos, tarjetas, filtros, búsqueda, export blob, enlaces wa.me click-to-chat, copiar enlace con código, gestión de códigos. Item de menú "Solicitudes" (icono UserPlus) solo superadmin.
- Verificado por API (todas las reglas de aceptación: submit con/sin código, óptica+ubicación obligatorias con mensajes ES, correo único 409, WhatsApp inválido 400, honeypot y no-consent no se guardan, rate-limit 429, grouped/sources/export, 403 admin) y por E2E navegador (iteration_6.json: 100% backend y frontend). Datos de prueba limpiados (colecciones en cero).
- **Pendiente menor (opcional)**: la ruta `/admin/leads` (y otras rutas admin) no redirige a usuarios no-superadmin; muestra toast "Acceso denegado" + datos vacíos (backend 403 correcto, sin fuga de datos, menú oculto). Patrón general de la app, no específico de esta feature.

### Panel de Correos para SuperAdmin (Jun 2026)
Vista para monitorear y reenviar la cola durable de correos (`email_queue`). Solo superadmin.
- **Backend** `routes/email_queue_admin.py` (registrado en server.py): `GET /api/email-queue/stats` (conteos por estado), `GET /api/email-queue?status=&tag=&search=&limit=&skip=` (listado paginado, proyeccion EXCLUYE `html` y `attachments.content` para no traer payloads pesados; anota `attachment_count`/`attachment_names`), `POST /api/email-queue/{id}/resend` (reencola: status->pending, attempts=0, next_attempt_at=now, limpia completed_at), `POST /api/email-queue/retry-failed` (reencola todos los fallidos). Guard `role == superadmin` (403 si no). Audit: EMAIL_QUEUE_RESEND / EMAIL_QUEUE_RETRY_ALL_FAILED.
- **Frontend** `pages/EmailQueuePage.jsx` + ruta `/admin/correos` + item de menu "Correos" (icono Mail) en la seccion superadmin de `MainLayout.js`. Tarjetas de estado (Total/Enviados/Pendientes/Enviando/Fallidos), tabs de filtro, busqueda por destinatario, tabla con badge de estado, tipo, intentos (n/max), ultimo error, adjunto (paperclip), fecha, y boton "Reenviar" por fila (un clic) + "Reintentar fallidos" (aparece si hay fallidos). Paginacion basica.
- Verificado por curl (stats/list/resend/403) + screenshot E2E (renderiza 6 filas, botones reenviar; el reenvio via API volvio a pending y el worker lo re-envio a sent). Sin fugas de html/adjuntos en el listado.

### Regresion completa post-cambios (Jun 2026)
Testing agent (iteration_5.json): 22/22 pruebas ejecutadas PASARON, 1 omitida (sin datos via ?type=eyeglass, PDFs de recetas ya verificados por separado), 0 fallos. CERO regresiones. Cubre: auth (login/me/refresh/logout/forgot-password), fix N+1 en consultas (64 filas con patient_name/professional_name), todos los PDFs/XLSX en hilo, cola durable de correos (email_queue: 6 docs todos 'sent'), y serialize_doc en listas. Frontend OK sin errores de compilacion. Observaciones menores del review (no bugs): list_consultations expone _id como string (consistencia, no fuga); CSRF rota en /auth/refresh (el interceptor del frontend ya lo maneja). Test file: backend/tests/test_regression_iter5.py.

### Revision de calidad de codigo — correcciones aplicadas (Jun 2026)
Se recibio un reporte automatico de calidad. Se aplicaron SOLO las correcciones reales y de bajo riesgo (la app esta en produccion, no se refactoriza codigo que funciona por metricas de estilo):
- **Secretos hardcodeados en tests (REAL, corregido)**: `tests/test_sessions.py`, `test_retention_dashboard.py` y `test_activation_tracking.py` hardcodeaban passwords de las cuentas seed. Ahora importan de `tests/_credentials.py` (lee SOLO de env vars, con `require()` que falla claro si faltan). La password del test que crea empresa temporal ahora es aleatoria (`uuid`).
- **Catch vacios (mejorado)**: se agrego `console.error` con contexto en los `catch {}` silenciosos senalados (`SupportTicketsPage`, `SalesPage`, `ReceivablesPage`, `OnboardingPage`) manteniendo el comportamiento best-effort.
- **NO aplicado (con justificacion)**: (a) `is` vs `==` (F632) = FALSA ALARMA, eran `is True/False/None` que es Python correcto (0 violaciones reales). (b) Refactor de `login()`/`get_current_user()` por complejidad = alto riesgo de romper el auth de todos los tenants en produccion; es metrica de estilo, no bug. (c) 74 deps faltantes de hooks React = agregar deps a ciegas suele causar loops de render/refetch; requiere analisis caso por caso. (d) Split de componentes grandes y type hints en `models.py` (ya tipado via Pydantic) = churn alto, valor bajo. Quedan como backlog opcional a abordar incrementalmente si aparece un bug concreto.


### Cola durable de correos (background queue) (Jun 2026)
Antes los correos se enviaban con `asyncio.create_task` (fire-and-forget): rapido pero fragil — si el pod se reiniciaba se perdian, sin reintentos y con riesgo de GC de la tarea. Se reemplazo por una cola durable respaldada en MongoDB, sin proceso worker aparte (compatible con el despliegue de 1 pod de Emergent).
- **`email_service.py`**: `queue_email(...)` ahora es `async` y PERSISTE cada correo en `db.email_queue` (status=pending) en vez de lanzar una tarea suelta. Soporta `attachments` (se guardan en base64 en el doc). Nuevas piezas: `_process_email_queue_once` (reclama docs de forma atomica pending->sending con `find_one_and_update`, envia via `send_email` en hilo, marca sent o reintenta con backoff 30s->30min hasta `EMAIL_MAX_ATTEMPTS=5`, luego failed), `_recover_stale_sending` (devuelve a pending los "sending" colgados > `EMAIL_STALE_SENDING_SEC=300s`), y `email_worker_loop` (poll cada `EMAIL_WORKER_INTERVAL=5s`, drena rapido si hay backlog).
- **`server.py`**: arranca `email_worker_loop()` en el startup (junto a `activation_task_loop`). Indices nuevos: `email_queue (status, next_attempt_at)` + TTL 7d en `completed_at` (purga enviados/fallidos; los pending/reintentando NO expiran). `completed_at` se guarda como `datetime` (BSON date) para que el TTL funcione.
- **Call sites actualizados a `await queue_email(...)`** (la funcion es async): `auth.py` (4), `activation_task.py` (3), `companies.py`, `superadmin_retention.py`, `support_tickets.py`, `security_reports.py`. Todos estaban ya en funciones async.
- **Cotizaciones (opcion a del usuario)**: `quotations.py::send_quotation_email` ahora ENCOLA el correo con el PDF adjunto y responde al instante (`"Cotizacion encolada para envio"`, ya no espera a Resend ni devuelve 502). El PDF se genera en hilo antes de encolar. Frontend `QuotationsPage.js`: toast "Cotizacion en camino ... (envio en segundo plano)".
- Config env: `EMAIL_MAX_ATTEMPTS`, `EMAIL_WORKER_INTERVAL`, `EMAIL_STALE_SENDING_SEC`, `EMAIL_WORKER_BATCH`.
- Verificado por curl + inspeccion directa de Mongo: (1) forgot-password encola -> worker envia (status=sent, id Resend real); (2) cotizacion encola con adjunto PDF (base64) -> enviado; (3) recipiente invalido -> status vuelve a pending, attempts=1, next_attempt_at +30s, last_error seteado (backoff OK). Sin warnings de "coroutine never awaited". `send_email` (envio directo con confirmacion) se conserva intacto.


### Optimizacion de rendimiento y capacidad (Jun 2026)
Respuesta a la pregunta del usuario sobre capacidad (cuantas opticas / usuarios simultaneos al 100%). Se corrigieron los 2 cuellos de botella detectados en el analisis:
- **N+1 en Consultas** (`routes/consultations.py::list_consultations`): antes hacia 1 `find_one` de paciente + 1 de profesional POR consulta dentro de un bucle (1+2N queries). Ahora usa batch `$in` -> 3 queries constantes.
- **Generacion de PDF/Excel bloqueante (CPU-bound)**: reportlab/openpyxl corrian sincronamente en el event loop ASGI, bloqueando a TODOS los usuarios ~200-400ms por documento. Se extrajo la parte de armado a funciones sync y se envolvio en `asyncio.to_thread(...)` en 10 endpoints: recetas anteojos/contacto/medica (`prescriptions.py`), cotizacion (`quotations.py`, `_build_quotation_pdf_bytes` ahora delega a `_render_quotation_pdf` en hilo), reporte de cierres de caja (`cash_register.py`), reporte jornada PDF + XLSX (`jornada_consignment.py`), ticket de venta de jornada (`jornada_ops.py`), guia de usuario (`user_guide.py`), manifiesto de seguridad (`security.py`) y exportacion completa de BD Excel (`data_export.py`, ahora hace todos los fetch async primero y arma el workbook en un hilo).
- Sin cambios funcionales: los PDFs/Excel salen identicos. Verificado por curl E2E que los 10 endpoints devuelven salida valida (%PDF / PK) y que `list_consultations` sigue poblando `patient_name`/`professional_name`.
- Capacidad estimada con la infraestructura actual (1 pod + pool Mongo max 200 + Redis Upstash): cientos de opticas registradas y ~150-250 usuarios concurrentes activos con carga fluida. Para >500 opticas o mayor concurrencia se activa la Fase 2 (uvicorn --workers, HPA multi-pod, cola Celery/RQ para PDFs/emails) documentada en la seccion de Escalabilidad.


### Nomenclatura ocular OD/OS (Jun 2026)
- Estandarizada la etiqueta del ojo izquierdo a **OS** (Oculus Sinister) en TODO lo visible; OD (ojo derecho) sin cambios. Ya no se usa "OI".
- Cambios de etiqueta (no de datos): formularios de recetas y consultas, tablas/listados, headings "Ojo Izquierdo (OS)", PDFs de recetas (`prescriptions.py`), exportaciones Excel/CSV (`data_export.py`), mensajes de WhatsApp (`PrescriptionsPage.js`), guia PDF (`user_guide.py`), y POS de jornada (`JornadaPOSTab.js`).
- Las claves internas de campo en MongoDB (`oi_sphere`, `va_*_oi`, `side:'oi'`, data-testids) se conservan intactas: sin migracion de datos.
- Fix colateral (linter ObjectId): endpoints de listado en `prescriptions.py`, `jornada_ops.py`, `support_tickets.py` ahora serializan explicitamente con `serialize_doc` en el patron reconocido (bucle o comprension en el return).

### Recetas lentes de contacto: orden completo + color OD/OS en PDF (Jun 2026)
- Tabla resumen de lentes de contacto muestra ahora los 6 valores en orden esfera/cilindro/eje/adicion/diametro/curva base (antes solo Esf/Cil/Eje).
- Mensaje de WhatsApp de lentes de contacto reordenado al mismo formato completo (antes Poder/BC/DIA incompleto).
- PDF de recetas (`prescriptions.py`): etiqueta OD en azul (#1D4ED8) y OS en verde (#15803D) en anteojos y lentes de contacto; header de contacto "B.C." -> "C.B.". Orden de columnas de contacto ya era ESF/CIL/EJE/ADD/DIA/CB.

### Reordenamiento del menu lateral (Jun 2026)
- `MainLayout.js`: `navItems` reordenado (lista unica filtrada por rol/modulo, mismo orden para todos los roles): Inicio rapido, Dashboard, Agenda, Pacientes, Consultas, Recetas, Punto de Venta, Cuentas por Cobrar, Cotizaciones, Inventario, Jornadas, Finanzas, Proveedores, Reportes, Configuracion. Consultas y Recetas se ubican tras Pacientes (eleccion del usuario). Finanzas/Proveedores solo aparecen si el plan incluye esos modulos, en su posicion (tras Jornadas / antes de Reportes).

### Color OD/OS en tablas de recetas en pantalla (Jun 2026)
- `PrescriptionsPage.js`: columnas OD (azul, text-blue-700) y OS (verde, text-green-700) en encabezados y celdas de las tablas de anteojos y de lentes de contacto, alineado con formularios y PDF.

### Recordatorio de reposicion de lentes de contacto (Jun 2026)
- Backend `GET /api/prescriptions/contact/replacement-reminders?days_ahead=5`: calcula el vencimiento desde la fecha de la receta segun el tipo de reemplazo (Diario=30, Quincenal=15, Mensual=30, Trimestral=90, Anual=365 dias). Deduplica por paciente (receta mas reciente), incluye vencidas + por vencer dentro de la ventana, y arma mensaje + enlace wa.me (con prefijo 502 si aplica). Envio manual (semi-automatico).
- Frontend `AgendaPage.js`: boton "Reposicion de lentes" con contador y modal que lista pacientes (vencidas en rojo, por vencer en cian) con boton "Enviar" por WhatsApp.

### Refraccion Actual en consultas + autorellenado de recetas (Jun 2026)
- Formulario de Consulta (`ConsultationsPage.js`): tras "Hallazgos" se agrego el area "Refraccion Actual" repetible (Agregar/Quitar). Cada refraccion tiene OD (azul) y OS (verde) con esfera/cilindro/eje/adicion + Observaciones. Se guarda como array `refractions` en la consulta.
- Backend `models.py`: clase `Refraction` + campo `refractions: Optional[List[Refraction]]` en ConsultationCreate y ConsultationUpdate. `routes/consultations.py` guarda/actualiza/devuelve `refractions`.
- Autorellenado: desde el detalle de la consulta, botones "Receta Anteojos" y "Receta Lentes de Contacto" abren el dialogo prellenado con refractions[0]. Con mas de una refraccion, `EyeglassRxDialog`/`ContactRxDialog` muestran botones "Refraccion N" (opcion B del usuario) para elegir cual cargar. Mapeo os_*->oi_* y esfera->power (contacto). Campos no aplicables (DP en anteojos; Diametro y Curva Base en contacto) quedan en blanco. Verificado E2E (iteration_4, 100%).

### Lensometria actual al usar lentes (Jun 2026)
- En "II. Historia Clinica > A. Antecedentes Oculares", al marcar el checkbox "Usa lentes" aparece "Lensometria actual" con OD (azul) y OS (verde) como texto libre (graduacion que usa el paciente actualmente).
- Backend `models.py`: campos `lensometry_od`/`lensometry_oi` en ConsultationCreate y ConsultationUpdate. `routes/consultations.py` los guarda (create), actualiza (all_fields) y devuelve. Se muestran tambien en el detalle de la consulta y en `ConsultationViewDialog`. Verificado (curl + screenshot).

### Correccion de la exportacion de base de datos (Jun 2026)
- `routes/data_export.py` (Configuracion > Exportacion de Base de Datos > Excel, `GET /api/data-export/full-database`, admin/superadmin):
  - Consultas: se corrigieron los campos mal mapeados (Tratamiento -> treatment_plan, Notas -> notes) y se completaron columnas: Tipo, Anamnesis, Hallazgos, Recomendaciones, Historia Clinica (usa lentes, lensometria OD/OS, cirugias, traumatismos, enfermedades), Antecedentes sistemicos y familiares, Agudeza Visual (lejos/cerca con y sin Rx, estenopeico, metodo) y Refracciones (serializadas legibles).
  - Recetas de Contacto: se corrigio la Esfera OD/OS (leia od_sphere en vez de od_power -> salia vacia) y se agrego Adicion OD/OS.
  - Recetas Oftalmicas: se agrego Adicion OD/OS y Armazon (frame_type).
  - Verificado descargando el Excel (openpyxl): columnas presentes y datos poblados. Pendiente por decision del usuario: hojas Jornadas, Cuentas por Cobrar/abonos, Cajas, Tickets, Notificaciones y Auditoria (opcion b, no solicitada aun).

### Modo offline global (captura sin internet) (Jun 2026)
- Objetivo: en jornadas/lugares sin senal, poder seguir CAPTURANDO datos; se guardan cifrados en el dispositivo y se sincronizan solos al volver la senal. Sin PIN, sin PWA (decision del usuario).
- Piezas nuevas:
  - `lib/offlineQueue.js`: cola en IndexedDB cifrada con AES-GCM usando una clave NO exportable guardada en IndexedDB (ni el JS lee sus bytes). Cada item se purga apenas se sincroniza.
  - `context/OfflineContext.js`: estado {online, pending, failed, syncing}; motor de sincronizacion FIFO (reintenta al volver online, evento `online` + polling 30s si hay pendientes); marca fallidos si el servidor rechaza (4xx).
  - `components/OfflineIndicator.js`: pastilla en el header — "Sin conexion · N sin sincronizar" / "Sincronizando… N" / "N por sincronizar" (+ boton Sincronizar) / "N con error"; toasts al perder/recuperar conexion y "Todo sincronizado".
  - `context/AuthContext.js`: interceptor de respuesta de axios encola peticiones mutantes (POST/PUT/PATCH/DELETE) cuando hay error de red y devuelve respuesta sintetica `{_offlineQueued:true}` (status 202) para que la UI continue. Denylist: /auth/, /data-export/, /search, .pdf, blobs, FormData. IMPORTANTE: el guard `!isAuthRoute` se mantiene en la logica de refresh 401 (sin el, /auth/refresh entra en bucle infinito y la app queda en "Cargando...").
  - `pages/JornadaPatientsTab.js`: al encolar offline muestra "Guardado en el dispositivo", agrega fila optimista con badge "Pendiente de sincronizar" y NO hace GET.
- Verificado E2E (Playwright offline real): registro offline -> badge/indicador -> reconecta -> auto-sync -> el paciente queda persistido en el backend (curl confirmado).
- Limitaciones honestas: la LECTURA de listas/datos existentes necesita conexion (no hay cache de lectura sin PWA); si cierran/recargan la app sin senal, no abre; algunos flujos que devuelven documento inmediato (ticket de venta) se completan tras sincronizar; la deteccion de duplicados no corre offline.
- Capacidad: sin limite fijo en la app; lo limita la cuota del navegador (medido ~977 MB en el entorno). Paciente ~289 B, venta ~431 B en texto; caben cientos de miles de registros. 100 expedientes = ~0.03 MB.
- Aviso de seguridad (`OfflineIndicator.js`): al cruzar cada bloque de pendientes (umbral 50, urgente 150) muestra un toast recordando buscar senal ("Tienes N registros sin sincronizar...") y la pastilla del indicador se pone ROJA con "· busca senal". Umbrales WARN_THRESHOLD=50 / URGENT_THRESHOLD=150. Verificado sembrando 52 pendientes cifrados (toast + pastilla roja) y limpiando la cola.


### Agenda - Proxima cita al terminar consulta + Recordatorios WhatsApp (Feb 2026)
- **Backend** `routes/appointments.py`: nuevo `GET /api/appointments/reminders?days_ahead=1` retorna las citas del dia objetivo con `patient_name`, `patient_phone`, `reminder_message` y `whatsapp_url` (link wa.me con mensaje pre-armado URL-encoded). Anade prefijo 502 automatico a telefonos de 8 digitos (Guatemala). Excluye status cancelada/completada/no_asistio. Multi-tenant por `company_id`. Rechaza superadmin (403) y `days_ahead` fuera de [0,30] (400).
- **Frontend** `ConsultationsPage.js`: al guardar consulta NUEVA (no edicion), abre modal "Agendar proxima cita" con fecha default a +6 meses, botones rapidos (1 semana / 1 mes / 3 meses / 6 meses / 1 ano) y POST a `/api/appointments` con patient_id + professional_id de la consulta. Opcion "Ahora no" para saltar.
- **Frontend** `AgendaPage.js`: boton "Recordatorios manana" en header (con contador badge) abre modal listando citas del dia siguiente. Cada item tiene boton verde WhatsApp que abre `wa.me/{phone}?text={message}` en nueva pestana. Mensaje personalizado con nombre del paciente, empresa, fecha y hora.
- **Testing**: 8/8 pytest tests + verificacion frontend end-to-end (`reminders_results.xml`).


### JORNADAS - Test de Aceptacion Completo (CA1..CA22) (Feb 2026)
- Test comprehensivo `test_jornadas_acceptance.py` (28 tests) validando 1:1 cada uno de los 22 criterios del spec + relaciones cross-collection (patients, sales, stock, inventory_movements).
- **Bugs encontrados y corregidos**:
  1. `serialize_doc` no serializaba listas de ObjectIds → `GET /api/patients` devolvia 500 cuando el paciente tenia `jornada_ids`. Fix en `db.py::serialize_doc` para manejar listas top-level de ObjectIds.
  2. `GET /jornadas/{jid}/cash` retornaba 200 con null cuando la jornada era de otra empresa (no validaba tenancy antes de consultar). Fix: usa `_get_jornada_active_or_400` que valida `company_id` primero. Igual para `/inventory`, `/sales`, `/patients`, `/excel/uploads`.
- **Resultado final**: **28/28 pasados**. Todos los CA1..CA22 verificados incluyendo: creacion, caja independiente, apertura+movimientos+arqueo+cierre, fuentes de inventario (branch/consignment/mixto), traslado descuenta stock de sucursal, consignacion NO afecta stock, Excel con header row detection + auto-map + preview + errores descargables + autocreacion + vinculacion, revert (con y sin ventas), pacientes en coleccion central con `jornada_ids` filtrable, vincular existente sin duplicar, POS restringido al inventario de la jornada, venta descuenta fuente correcta e ingresa a caja, cierre valida caja + devuelve remanente automaticamente, liquidacion (vendido/devuelto/faltante/a_pagar/utilidad), PDF+XLSX descargables, cerrada solo lectura + reopen solo superadmin auditado, aislamiento multi-tenant en TODOS los endpoints, consolidacion en `/api/sales` global con marca `jornada_id`.
- **Total tests modulo Jornadas**: 80 (17 + 14 + 13 + 8 + 28 acceptance).


### JORNADAS - Iteracion 3.1: POS encadenado (Consulta + Receta + Ticket) (Feb 2026)
- **Backend** en `jornada_ops.py` (extendido):
  - `POST /jornadas/{jid}/consultations` — consulta rapida con jornada_id + type='jornada' en `consultations`.
  - `POST /jornadas/{jid}/prescriptions/eyeglass` — receta con jornada_id + consultation_id opcional en `eyeglass_prescriptions`.
  - `GET /jornadas/{jid}/sales/{sale_id}/receipt.pdf` — ticket 80mm generado con `reportlab.pdfgen.canvas` (header empresa, jornada, items, totales, pagos, saldo pendiente).
  - `JSaleCreate` extendido con `consultation_id` y `prescription_id`, guardados como ObjectId en `sales`.
- **Frontend** `JornadaPOSTab.js`:
  - Botones "Consulta" y "Receta" aparecen al seleccionar paciente; pasan a verde "Consulta OK" / "Receta OK" al guardar.
  - Modal "Venta registrada" post-cobro con "Ver / Imprimir ticket" (abre PDF) y "Compartir por WhatsApp" (wa.me link) si el paciente tiene telefono.
  - Ventas recientes clickeables re-abren el modal para reimprimir el ticket.
- **Auditoria**: `JORNADA_CONSULTATION_CREATED`, `JORNADA_RX_CREATED`.
- **Testing**: `test_jornada_pos_ticket.py` — **8/8 passed** (consulta OK, rx OK, sale con refs + PDF, 404 sale ajena, multitenant isolation, gating jornada activa).
- **Total tests Jornadas**: 52 (17 + 14 + 13 + 8).


### JORNADAS - Iteracion 3: Consignacion Excel + Liquidacion + Reportes (Feb 2026)
- **Backend** nuevo `routes/jornada_consignment.py` (~900 lineas): carga por Excel, liquidacion y reportes.
- **Carga Excel** (`openpyxl`, colecciones `jornada_excel_uploads` + productos con `is_consignment_source=true`):
  - `POST /excel/preview` detecta fila de encabezados (skip logos/titulos), auto-sugiere mapeo por similitud de palabras, retorna preview de filas y estimacion total.
  - `POST /excel/import` con `mapping_json` (multipart): descripcion y cantidad obligatorios; autocrea productos o los vincula por SKU; consolida duplicados dentro del mismo archivo; hash SHA-256 para idempotencia (rechazo si mismo archivo dos veces); margen por defecto si no hay precio; agrega a `jornada_stock` con `source='consignment'`.
  - `GET /excel/uploads` historial. `POST /excel/{uid}/revert` elimina stock+productos autocreados solo si no hay ventas.
- **Liquidacion** (`GET /liquidation`): agrupa por proveedor con items desglosados: vendido/devuelto/faltante, costo, precio, a_pagar (sold*cost), ingreso (sold*price), utilidad. Totales globales.
- **Reportes finales** con `reportlab` (PDF) y `openpyxl` (Excel):
  - `GET /report.pdf` con secciones Ventas (metodos, categoria, marca, origen), Inventario (enviado/vendido/devuelto/faltante), Pacientes (nuevos, recurrentes, conversion, recetas), Caja (fondo, neto, egresos por categoria, diferencia arqueo), Liquidacion por proveedor, Meta comercial (% alcanzado), Utilidad bruta y neta.
  - `GET /report.xlsx` con hoja Resumen + hoja Liquidacion detallada.
- **Frontend**: nuevo `JornadaExcelImport.js` (wizard 3 pasos: subida -> mapeo con preview -> confirmacion con resumen). Nuevo `JornadaLiquidationTab.js` con KPIs, tarjetas por proveedor, tabla detallada, historial de cargas Excel con revert. Botones "Descargar PDF/Excel" en el header del panel (cuando cerrada/en_cierre) y en la tab Liquidacion. Nueva tab 'Liquidacion' en el panel (6 tabs total).
- **Testing**: `test_jornada_consignment.py` (13 tests): preview con fila titulo, gating consignment, oversize; import creates/vincula/idempotencia/mapping requerido; revert elimina; liquidation structure; PDF/XLSX magic bytes correctos; multi-tenant 404. **Resultado: 13/13 passed**.
- **Auditoria**: `JORNADA_EXCEL_IMPORT`, `JORNADA_EXCEL_REVERT`.
- **Modulo Jornadas COMPLETO**: 3 iteraciones cubriendo requerimiento completo del spec.


### JORNADAS - Iteracion 2: Operacion (Caja + Inventario + POS + Pacientes) (Feb 2026)
- **Backend** (`routes/jornada_ops.py`, ~600 lineas): endpoints operativos para caja, inventario, POS y pacientes de la jornada.
- **Caja de jornada** (usa `cash_registers` con `jornada_id`):
  - `POST /api/jornadas/{jid}/cash/open` (solo mode='own'), `GET /cash` (register + totals), `POST /cash/movements` (ingreso/egreso con category y descripcion), `POST /cash/close` (arqueo con conteo fisico, diff obligatorio si difiere, opcional traslado neto a caja de sucursal).
  - Compute totales: ventas de jornada por metodo, ingresos/egresos manuales, expected_cash, egresos_by_category.
- **Inventario** (colecciones nuevas `jornada_stock` + `jornada_transfers`):
  - `POST /inventory/transfer` desde sucursal (descuenta stock, upsert en jornada_stock, audita).
  - `GET /inventory` consolidado con initial/sold/adjusted/current qty + valor.
  - `POST /inventory/adjust` (delta +/-, motivo obligatorio, solo admin).
  - `POST /inventory/return` traslado inverso a sucursal fuente.
- **POS de jornada** (extiende `sales` con `jornada_id`):
  - `POST /{jid}/sales` valida stock en jornada_stock, requiere caja abierta si mode='own', crea venta multi-payment, descuenta stock e incrementa contadores agregados.
  - `GET /{jid}/sales` listado con paciente resuelto.
- **Pacientes** (extiende `patients` con `jornada_id_first` + `jornada_ids`):
  - `POST /patients/search` para deteccion de duplicados por DPI/telefono/nombre.
  - `POST /patients` crea nuevo o vincula existente (add jornada al historial).
  - `GET /patients` lista pacientes con flag `is_first_capture_here`.
- **Cierre con validacion** (`POST /jornadas/{jid}/close`):
  - Rechaza si hay caja abierta o ventas en borrador.
  - Devuelve automaticamente remanente `source='branch'` a la sucursal origen (traslado inverso).
- **Frontend**: `JornadaPanelPage.js` refactorizado con 5 tabs. 4 archivos nuevos: `JornadaCashTab.js`, `JornadaInventoryTab.js`, `JornadaPatientsTab.js`, `JornadaPOSTab.js`.
- **Indices Mongo nuevos**: `jornada_stock (company, jornada, product)`, `(company, jornada, source)`, `jornada_transfers (company, jornada, created_at)`, `cash_registers (company, jornada, status)`, `sales (company, jornada, _id)`, `patients (company, jornada_ids)`.
- **Auditoria**: JORNADA_CASH_OPENED/MOVEMENT/CLOSED, JORNADA_INV_TRANSFER/ADJUST/RETURN, JORNADA_SALE_CREATED, JORNADA_PATIENT_CREATED/LINKED.
- **Testing**: `test_jornada_ops.py` (14 tests). Resultado: **14 passed, 0 failed**.
- **Pendiente Iter 3**: Carga Excel consignacion, liquidacion, reporte PDF/Excel, inclusion en reportes de sucursal con filtro.


### JORNADAS - Iteracion 1: Cimientos (Feb 2026)
Modulo nuevo de brigadas visuales / eventos fuera de sucursal. Multi-tenant, opcional por plan.
- **Backend**: `routes/jornadas.py` (481 lineas), coleccion `jornadas`, modelos `JornadaCreate/Update/StatusChange/CashConfig/InventoryConfig` en `models.py`.
- **Ciclo de vida**: `planificada -> activa -> en_cierre -> cerrada` (+ `cancelada`). Endpoints:
  - `GET /api/jornadas` con filtros (status, branch_id, from_date, to_date, search) + paginacion.
  - `POST/PUT/DELETE /api/jornadas/{id}` (soft-delete via `is_deleted`).
  - `GET /api/jornadas/{id}` y `/{id}/summary` con KPIs (total_sold, patients_count, cash_balance, cumplimiento meta).
  - Transiciones: `/activate` (valida fuente de inventario) · `/start-closing` · `/close` · `/cancel` (motivo obligatorio, sin ventas/pacientes) · `/reopen` (solo superadmin, motivo obligatorio).
- **Gating de plan**: `_require_module()` valida que la empresa tenga `jornadas` en `plan.modules`. Free devuelve HTTP 402. Modulo agregado a seed Basic + Enterprise y migracion aplicada a planes existentes.
- **Auditoria completa**: `JORNADA_CREATED/UPDATED/DELETED/ACTIVATED/START_CLOSING/CLOSED/CANCELLED/REOPENED` con actor, target, metadata (from/to/reason).
- **Indices Mongo**: `(company_id, status, start_date)`, `(company_id, responsible_branch_id, start_date)`, `(company_id, is_deleted, start_date)`, `(company_id, name)`.
- **Frontend**: 3 paginas nuevas — `JornadasPage.js` (listado con filtros y cards), `JornadaFormPage.js` (creacion/edicion por 4 pasos), `JornadaPanelPage.js` (panel con KPIs, config, acciones de estado, modal de cancel/reopen).
- **Sidebar**: item "Jornadas" con icono Tent, visible solo si `hasModule('jornadas')`. Rutas: `/jornadas`, `/jornadas/new`, `/jornadas/:id`, `/jornadas/:id/edit`.
- **Permisos por rol**: agregado a `RolePermissionsSection.js` (`planKey: 'jornadas'`).
- **Testing**: `backend/tests/test_jornadas.py` (391 lineas, 19 tests). Resultado pytest: 17 passed, 2 skipped, 0 failed.
- **Pendiente en Iteraciones 2 y 3**: Caja propia, traslado desde sucursal, POS de la jornada, pacientes con indicador, carga Excel consignacion, cierre validado + liquidacion + reporte PDF/Excel.


### Bugfix Editar Plan + Migracion moneda Q (Feb 2026)
- **Bug "Plan no encontrado"**: cache de Redis compartida entre entornos servia plans con ObjectIds obsoletos que ya no existian en MongoDB.
  - Fix: namespace de cache ahora incluye `DB_NAME` (`cortexia:{db}:{ns}:{key}`) en `cache.py::_k()`.
  - Safety net: `PUT /api/plans/{id}` invalida `plans_cache` cuando el plan no existe.
  - Cache de plans purgada manualmente (una sola vez).
- **Moneda GTQ (Quetzales)**: defaults cambiados a `GTQ` en `models.py`, `routes/plans.py`, `routes/billing.py` (Stripe usa `gtq`).
- Frontend muestra `Q` en `PlansPage.js` (StatCards + distribucion) y `MyPlanPage.js` (`fmt()` traduce `GTQ` -> `Q`).
- Migracion aplicada: todos los planes en DB y `payment_transactions` reetiquetados a `GTQ`.

## Lo Implementado

### Security Audit Round 3 — IP Trust + Public Endpoint DoS Hardening (Feb 2026)
Tercera auditoria. Verdict: `CONDITIONAL PASS - NEEDS ATTENTION`. 0 criticos, 1 alto, 1 medio, 1 bajo. Todos resueltos y verificados E2E.

**SEC-001 (P1 HIGH - RESUELTO)**: IP spoofable via `X-Forwarded-For` leftmost.
- Bug: `get_real_ip` en `auth_utils.py` tomaba el primer valor de XFF, controlable por el cliente. Un anonimo podia mandar 10 CSP reports con `X-Forwarded-For: <victim-ip>` y auto-banear a la victima 24h (o cualquier IP compartida como oficina/NAT).
- Fix: `get_real_ip` ahora prioriza (1) `CF-Connecting-IP` de Cloudflare (imposible de spoofear), (2) rightmost de XFF (el hop del proxy trusted mas cercano), (3) `X-Real-IP`, (4) `request.client.host`. Nunca leftmost.
- Callers actualizados: `server.py` middleware auto-block, `security_reports.py` deteccion de spike + registro de IP en violaciones, `auth.py` (4 usos: brute force, password change alert, forgot password log, reset password alert), `superadmin_retention.py` (reset password token log).
- Verificado E2E: 10 CSP reports con `X-Forwarded-For: 1.2.3.4, 5.6.7.8` NO banean 1.2.3.4 ni 5.6.7.8. Registran el edge real (`34.160.127.70` en preview).

**SEC-002 (P2 MEDIUM - RESUELTO)**: DoS por PDF generation en endpoint publico sin rate limit.
- Bug: `/api/docs/public/user-guide?token=...` genera un PDF de 35KB con reportlab (~200-300ms CPU) sin rate limit per-endpoint. Un atacante con un token o rotando XFF podia hacer flooding.
- Fix 1 (rate limit): `@limiter.limit("10/minute")` en endpoint publico + `@limiter.limit("30/minute")` en endpoint autenticado (ambos keyed por IP via `slowapi`).
- Fix 2 (cache): cache in-memory por `hash(prospect_name)` con TTL 5min y max 50 entradas (LRU-like eviction). Segundo hit del mismo prospecto es ~2x mas rapido (415ms → 194ms).
- Env vars: `USER_GUIDE_CACHE_TTL=300`, `USER_GUIDE_CACHE_MAX=50`.
- Verificado E2E: 15 requests seguidos → 10x 200 + 5x 429 confirmando rate limit.

**SEC-003 (P3 LOW - RESUELTO)**: JWT del share link exponia `user_id` interno y no era revocable.
- Bug: el payload del JWT incluia `generated_by: <ObjectId>` que se filtraba al decodificar el JWT (base64) por el destinatario del link.
- Fix: quitado `generated_by`. Agregado `jti: str(uuid4())` unique per token para preparar futura revocacion via denylist. Solo el firmante (server) puede vincular jti → user_id via audit logs.
- Verificado E2E: JWT decodificado muestra solo `{sub, prospect, iat, exp, jti}` — sin datos sensibles internos.

### Guia de Usuario en PDF — Personalizacion + Share WhatsApp (Feb 2026)
- **Portada personalizada**: `GET /api/docs/user-guide.pdf?prospect={nombre}` estampa un banner morado en la portada con "PREPARADA ESPECIALMENTE PARA {nombre}" (max 80 chars, HTML-escaped). Verificado extrayendo el texto del PDF con pypdf.
- **Share link publico firmado**: `POST /api/docs/share-link` (admin/superadmin) recibe `{prospect_name, expires_hours}` y devuelve un JWT firmado con HS256 (`sub=guide-share`, exp 30d default / 90d max). Retorna `{path, token, expires_at, prospect_name}`. Frontend construye URL absoluto con `window.location.origin`.
- **Endpoint publico**: `GET /api/docs/public/user-guide?token={jwt}` (sin auth) valida el JWT y sirve el PDF personalizado inline. Errores: 410 si expirado, 403 si invalido.
- **Frontend `SettingsPage.js`**: nuevo boton verde "Compartir personalizada por WhatsApp" al lado de la descarga estandar. Abre `Dialog` con: input prospecto, botones "Generar enlace" y "Solo descargar" (descarga PDF personalizado localmente sin enlace publico). Al generar: muestra URL con boton "Copiar", input de telefono (autocompleta +502 si es GT 8 digitos), textarea mensaje opcional (con mensaje sugerido pre-armado si vacio), boton "Abrir WhatsApp" que abre `wa.me/{phone}?text=...` en pestana nueva.
- Data-testids: `share-user-guide-btn`, `share-guide-dialog`, `share-prospect-name-input`, `generate-share-link-btn`, `download-personalized-btn`, `share-link-result`, `copy-share-url-btn`, `share-phone-input`, `share-message-input`, `send-whatsapp-btn`.
- Config env: `USER_GUIDE_SHARE_HOURS=720` (30d default), `USER_GUIDE_SHARE_MAX_HOURS=2160` (90d max).
- Testing E2E: admin descarga personalizada 200 (35KB, "Optica Vision de Xela" verificado en PDF text extraction), share-link POST 200, endpoint publico 200 sin cookies, invalid token 403, vendedor 403 al intentar POST share-link.

### Guia de Usuario en PDF (Feb 2026)
- **Backend** `routes/user_guide.py` (708 lineas, reportlab platypus):
  - `GET /api/docs/user-guide.pdf` restringido a `admin` y `superadmin` (403 para vendedor/doctor).
  - Portada + TOC + 8 secciones: Introduccion, Primer ingreso, Guia Admin (6 subsecciones), Guia Vendedor (4), Guia Doctor (3), Jornadas, Buenas practicas, Soporte.
  - Header/footer con branding Cortexia, paginacion, tip boxes por color, tablas de modulos, listas estilizadas.
  - Genera PDF de ~35KB, 21 paginas.
- **Frontend** `SettingsPage.js`: nueva card "Documentacion" (data-testid=`documentation-card`) visible solo para admin y superadmin. Boton morado "Descargar Guia de Usuario (PDF)" (data-testid=`download-user-guide-btn`) llama a `/api/docs/user-guide.pdf` como blob y dispara download con filename desde `Content-Disposition`. Muestra 6 highlights del contenido y callout "Ideal para onboarding/venta".
- **Fix menor**: nombre de estilo `Bullet` colisionaba con default de reportlab. Renombrado a `BulletCX`.

## Lo Implementado

### Auto-block IP + Widget de IPs bloqueadas (Feb 2026)
Escalada del sistema CSP: cuando una IP individual supera un umbral en la ventana, se bloquea automaticamente en el rate limiter para detener el ataque en tiempo real.

**Backend `blocked_ips.py`** (modulo nuevo):
- Cache in-memory Set con refresh cada 30s + invalidacion on-write para checkeo O(1) desde el middleware.
- `is_ip_blocked(ip)`, `block_ip(ip, reason, metadata, hours)`, `unblock_ip(ip)`, `list_blocked_ips(limit)`.
- TTL: 24h por defecto (env `BLOCKED_IP_TTL_HOURS`). Auto-unblock via indice TTL de Mongo sobre `blocked_until`.
- Coleccion `db.blocked_ips` con indice unico en `ip` + TTL en `blocked_until`.

**Backend `server.py` middleware**:
- Chequeo temprano de `is_ip_blocked(client_ip)` para todo `/api/*`. Retorna 403 "IP bloqueada por comportamiento anomalo. Contacta soporte." antes de cualquier otra logica.
- Extrae IP desde `X-Forwarded-For` (primer valor, cortex de proxies).

**Backend `routes/security_reports.py`**:
- `_check_and_alert_spike()` ahora corre PRIMERO la deteccion por IP. Agrega violaciones agrupadas por IP en la ventana, si alguna supera `CSP_IP_BLOCK_THRESHOLD` (default 2x el global = 10), se bloquea automaticamente con razon `csp_spike_{count}_violations`.
- Crea notification push al SuperAdmin (`event_type=ip_auto_blocked`) por cada IP nueva.
- El email del spike ahora incluye la lista de IPs auto-bloqueadas en el `event_meta`.
- Nuevos endpoints (SuperAdmin only):
  - `GET /api/security/blocked-ips` — lista con `active` flag calculado.
  - `DELETE /api/security/blocked-ips/{ip}` — unblock manual. Audit `IP_UNBLOCKED`.
- `/api/security/csp-report` agregado a `_CSRF_EXEMPT_PATHS` (los navegadores envian reports automaticamente sin JS, no pueden setear X-CSRF-Token).

**Frontend `SuperAdminDashboard.js`**:
- Widget extendido con seccion "IPs auto-bloqueadas" cuando hay activas. Card completo cambia a borde rojo si hay IP bloqueadas.
- Cada IP muestra: direccion, razon, hora de expiracion, boton "Desbloquear" con confirmacion.
- Data-testids: `blocked-ip-{ip}`, `unblock-{ip}`.

**Testing E2E**:
- 10 CSP reports desde `203.0.113.99` → IP bloqueada automaticamente con razon `csp_spike_10_violations` y TTL 24h.
- Request desde IP bloqueada → 403 middleware.
- Request desde IP legitima → 401/200 (normal).
- Unblock manual funciona y la IP vuelve a poder acceder.

**Config env vars**:
- `CSP_IP_BLOCK_THRESHOLD=10` (default 2x global)
- `CSP_IP_BLOCK_HOURS=24`
- `BLOCKED_IP_TTL_HOURS=24`
- `BLOCKED_IP_CACHE_REFRESH=30`

### CSP Spike Alerts al equipo Cortexia (Feb 2026)
Alertas proactivas cuando se detectan picos anormales de violaciones CSP — signal fuerte de intento activo de XSS/inyeccion.

**Backend `routes/security_reports.py`**:
- Nueva funcion `_check_and_alert_spike()` que corre best-effort tras cada report guardado (no bloquea la respuesta HTTP).
- Umbrales configurables via env:
  - `CSP_SPIKE_THRESHOLD=5` (default) — cantidad minima de violaciones en la ventana para disparar alerta.
  - `CSP_SPIKE_WINDOW_MIN=15` (default) — ventana temporal.
  - `CSP_ALERT_COOLDOWN_MIN=60` (default) — periodo minimo entre alertas para evitar spam.
- Cuando se detecta pico:
  1. Agrega top 5 `violated_directive` y top 5 `blocked_uri` para dar contexto en el alerta.
  2. Envia email al equipo (`CORTEXIA_ALERTS_TO` o `ADMIN_EMAIL`) usando template `render_security_alert` con event_meta detallado (cantidad, umbral, directives, URIs).
  3. Crea push notification al SuperAdmin (`event_type=csp_spike`).
  4. Guarda doc en `db.csp_alerts` con `scope=global, last_alert_at, last_count, last_top_directives` (upsert).
  5. En el siguiente report dentro de `ALERT_COOLDOWN_MIN`, la funcion detecta la alerta reciente y NO envia otra.
- Colecccion `csp_alerts` sirve como state machine minimalista para dedup — no tiene TTL (borrado manual solo).

**Testing E2E**: 4 reports bajo umbral → sin alerta, 5to report (=umbral) → email + notification + doc creado, siguientes 5 reports → cooldown activo, sin duplicados. Verificado con curls.

### CSP + Report-To + Security Headers Telemetry (Feb 2026)
Defense-in-depth adicional para telemetria de intentos de XSS/inyeccion cross-site.

**Backend security headers** (`server.py` middleware, aplicado en todas las responses):
- **API responses (JSON, prefix `/api/`)**:
  - `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'` (bloquea absolutamente todo — APIs no cargan recursos)
  - `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- **HTML SPA responses**:
  - CSP moderno con `default-src 'self'`, allowlist para Stripe (`js.stripe.com`, `hooks.stripe.com`, `checkout.stripe.com`), Google Fonts (`fonts.googleapis.com`, `fonts.gstatic.com`), `frame-ancestors 'none'`, `object-src 'none'`, `upgrade-insecure-requests`.
  - `script-src 'self' 'unsafe-inline' 'unsafe-eval' https://js.stripe.com` (unsafe-inline necesario para CRA bootstrap; TODO nonce en v2).
  - `report-uri /api/security/csp-report` + `Report-To` header con el mismo endpoint.
  - Adicional: HSTS `max-age=31536000; includeSubDomains`.

**Backend `routes/security_reports.py`** (nuevo):
- `POST /api/security/csp-report`: publico, sin auth (asi lo envian los navegadores). Rate limited 60/min. Acepta ambos formatos: CSP Level 2 (`application/csp-report`) y Reporting API (`application/reports+json`). Extrae `violated_directive`, `blocked_uri`, `document_uri`, `source_file`, etc. Guarda en `db.csp_violations`.
- `GET /api/security/csp-violations` (superadmin only): retorna items + breakdown por directive + breakdown por blocked_uri, filtrado por hours (max 720).
- Indice TTL 30 dias sobre `created_at` para auto-purga.

**Frontend `SuperAdminDashboard.js`**:
- Nuevo widget `CspViolationsWidget` (data-testid=`csp-widget`) al final del dashboard SaaS.
- Muestra total 24h, pills con top directives (bg-amber), lista scrollable con las ultimas 10 violaciones (directive + blocked_uri + hora).
- Card cambia a borde amber cuando hay violaciones (>0); estado vacio muestra mensaje amigable.

**Testing**: Simulacion CSP report → guardado OK, GET violations retorna con breakdown correcto, widget muestra amber cuando hay violation, empty state correcto.

### Security Audit Round 2 + CSRF Double-Submit + Hardening (Feb 2026)
Segunda auditoria completa. 1 finding MEDIUM (P2) CSRF + varios P3. Verdict: **PASS - NO MATERIAL FUNCTIONAL ISSUES FOUND**.

**SEC-001 CSRF (P2 - RESUELTO)**: cookies con SameSite=None (forzado por Cloudflare proxy) permitirian ataques CSRF cross-site. Fix con patron CSRF Double-Submit Cookie:
- `routes/auth.py::_set_auth_cookies`: nuevo cookie `csrf_token` con `secrets.token_urlsafe(32)` (256-bit entropy), `httponly=False` (JS-readable), `samesite=none`, `secure=True`. Se envia cross-site pero atacante no puede LEER via JS (SOP).
- `server.py` middleware: para POST/PUT/PATCH/DELETE con auth cookie, exige header `X-CSRF-Token` que coincida con cookie. Sino → 403 "CSRF token invalido". Fallback Origin/Referer para transicion.
- Frontend `AuthContext.js`: axios request interceptor lee cookie via `document.cookie` y agrega header en todos los state-changing requests.
- `/auth/refresh` reemite csrf_token para mantener consistencia con access_token.
- Webhook Stripe `/api/webhook/stripe` en `_CSRF_EXEMPT_PATHS` (server-to-server, verificado via signature).
- Verificado: POST sin header → 403, con header incorrecto → 403, con header correcto → 200.

**SEC-002 Logout tokens sid-less (P3 - RESUELTO)**: logout ahora revoca la sesion actual Y (fallback) bumpea `password_changed_at` si el token no tiene sid (compatibilidad con tokens emitidos antes del deploy).

**SEC-003 Session existence disclosure (P3 - RESUELTO)**: `sessions::revoke_session` valida autorizacion ANTES del check de revoked → 404 uniforme sin filtrar existencia.

**P3 Hardenings adicionales (RESUELTOS)**:
- `auth_utils.get_current_user`: bloquea usuarios de ópticas inactivas (`company.is_active=False`) con 401 para no-superadmin. Antes staff podia seguir operando en optica desactivada.
- `email_service.py`: nuevo helper `_e()` (HTML-escape). Aplicado a interpolaciones de nombres/company/comentarios en TODOS los templates de email (render_welcome_company, render_activation_reminder, render_deactivation_notice, render_onboarding_tips, render_reactivation_notice, render_security_alert, render_support_ticket, render_quotation_email, render_password_reset).
- `routes/reactivation_feedback::submit_feedback`: precondition idempotente — 400 si `needs_reactivation_feedback` flag no esta seteado. Previene spam al SuperAdmin en recargas.
- Default `SameSite=lax` en cookies (previously `none`). CF sigue reescribiendo httpOnly cookies a None+Partitioned pero csrf_token se mantiene con la config correcta.

### Panel Sesiones Activas + Session-based JWT revocation (Feb 2026)

**Feature "Sesiones Activas"** - permite al admin ver todos los dispositivos logueados en su optica y revocar sesiones sospechosas con un click.

**Backend**:
- Nueva coleccion `sessions` con TTL 7d en `last_activity_at`:
  ```
  {session_id (uuid), user_id, company_id, user_email, user_name, user_role,
   ip (X-Forwarded-For aware), user_agent (raw, max 500), created_at,
   last_activity_at, revoked, revoked_at, revoked_by, revoked_reason}
  ```
- `auth_utils.create_access_token/create_refresh_token`: aceptan `session_id` opcional que va como claim `sid` en el JWT.
- `auth_utils.get_current_user`: valida que la sesion no este revocada (401 si lo esta) + refresca `last_activity_at` con throttling de 30s para reducir carga de escritura.
- `routes/auth.py::login`: inserta doc en `sessions` al login y emite JWT con `sid`.
- `routes/auth.py::refresh`: preserva `sid` en el nuevo access_token.
- `routes/auth.py::logout`: **CAMBIO** — antes invalidaba todas las sesiones via `password_changed_at`; ahora solo revoca la sesion actual. Habilita sesiones concurrentes de forma segura.
- Nueva ruta `routes/sessions.py`:
  - `GET /api/sessions` — Lista sesiones activas con RBAC: user/doctor ve las propias, admin ve todas de su company, superadmin ve todas.
  - `POST /api/sessions/{id}/revoke` — Revoca una sesion (403 si no tiene permiso; 400 si es la sesion actual). Audit `SESSION_REVOKED`.
  - `POST /api/sessions/revoke-all-mine` — Cierra todas mis otras sesiones. Audit `SESSION_REVOKE_ALL_MINE`.
- Indices Mongo: `session_id` unique, compound (user_id, revoked, last_activity_at), compound (company_id, revoked, last_activity_at), TTL 7d sobre `last_activity_at`.

**Frontend**:
- Nuevo componente `components/security/SessionsPanel.jsx` con detector de icono simple (`Smartphone/Tablet/Monitor/Globe` basado en user-agent).
- Card visual verde para la sesion actual con badge "Esta sesion" (no revocable).
- Boton rojo `<ShieldOff />` en las otras sesiones que abre `AlertDialog` de confirmacion.
- Boton "Cerrar mis otras sesiones (N)" cuando hay >0 sesiones propias adicionales.
- Warning cuando hay >10 sesiones activas.
- Formato de tiempo relativo: "hace segundos/X min/X h/X d".
- Integrado en `SettingsPage.js` como una nueva Card "Sesiones Activas" dentro de Configuracion. Admin ve titulo "Sesiones activas del equipo"; otros roles ven "Mis sesiones activas".
- Fix menor: `SettingsPage.js::fetchCompany` no muestra toast de error si 403 (permite a vendedores entrar a /settings para ver Sesiones Activas sin ver un mensaje confuso).

**Testing**: 15/15 tests backend PASS + frontend E2E OK.

### Security Audit + Hardening (Feb 2026)
Auditoria de seguridad completa (read-only) con 2 findings CRITICOS (P0) y varios P3. Todos los fixes de codigo aplicados y verificados.

**SEC-002 (P0 - RESUELTO)**: Privilege escalation via role mass-assignment.
- Bug: `POST /api/users` aceptaba `role: str` arbitrario. Un admin cliente podia crear `role=superadmin` y escalar a cross-tenant.
- Fix en `routes/users.py::create_user`: allowlist estricta:
  - Admin (cliente): solo puede crear `user`, `doctor`.
  - Superadmin: puede crear cualquier rol conocido.
  - Roles fuera de allowlist -> 403 (admin) / 400 (superadmin con rol invalido).
- PUT `/users/{id}` tambien incluye `doctor` en la lista de roles validos.
- Verificado via curl E2E: admin creando superadmin/admin -> 403; admin creando user/doctor -> 200.

**SEC-001 (P0 - RESUELTO EN PREVIEW)**: JWT_SECRET expuesto en historial de git.
- JWT_SECRET aparecia 3 veces en commits antiguos del historial (aunque `.env` ya estaba en `.gitignore` y no era trackeado actualmente).
- Rotado en preview con `secrets.token_urlsafe(64)` (86 chars). Nuevo valor aparece 0 veces en historial. Login funcional post-rotacion.
- **Accion pendiente del usuario**: rotar en produccion via Emergent Deployments env config los mismos secrets (JWT_SECRET, ADMIN_PASSWORD, MONGO_URL, RESEND_API_KEY, EMERGENT_LLM_KEY, REDIS_URL).

**SEC-003 (P3 - RESUELTO)**: ReDoS/regex injection en 8 search endpoints.
- Fix: todos los `$regex` con input del usuario ahora usan `re.escape(input[:100])`:
  - `server.py::global_search` (agregado `max_length=100`)
  - `routes/companies.py::list_companies`, `patients.py::list_patients`, `inventory.py::list_products`
  - `routes/suppliers.py::list_suppliers`, `jornadas.py::list_jornadas`
  - `routes/jornada_ops.py` (busqueda de productos + deteccion duplicados de pacientes)
  - `routes/audit_log.py::list_audit_logs`

**SEC-004 (P3 - RESUELTO)**: Onboarding step_id sin allowlist.
- Bug: `PUT /api/onboarding/status` construia clave `$set` a partir de input del usuario (`onboarding_progress.{step_id}`).
- Fix en `routes/onboarding.py`: `ALLOWED_STEP_IDS = {"company_data", "branches", "users", "inventory", "first_patient", "first_sale", "change_password"}`. Match exacto con los steps del `OnboardingPage.js` frontend.

**Hardening adicional (P3 - RESUELTO)**: `settings.py::update_my_company` bloqueaba `is_active` toggle self-service.
- `BLOCKED_FIELDS = {"is_active", "plan_id", "reactivated_at", "reactivated_by", "deactivated_reason", "deactivated_at", "needs_reactivation_feedback"}`. Solo SuperAdmin puede tocarlos desde `/admin/opticas`.

**Verdict final del auditor**: `CONDITIONAL PASS - NEEDS ATTENTION` — todos los fixes de codigo verificados; solo pendiente rotacion manual de secrets en produccion.

### Feedback rapido post-reactivacion + Nota de reglas de desactivacion (Feb 2026)

**Feedback rapido cuando se reactiva una optica**:
- **Backend `routes/reactivation_feedback.py`**: nuevo endpoint que captura por que el admin no ingreso la primera vez.
  - `POST /api/reactivation-feedback` (auth admin) — recibe {reason, comment, allow_contact}. Guarda en `reactivation_feedbacks`. Motivos validos: `sin_tiempo`, `no_supe_empezar`, `olvide_password`, `precio`, `no_lo_necesitaba`, `otro`. Crea notificacion push al SuperAdmin + audit `REACTIVATION_FEEDBACK_SUBMITTED`. Limpia el flag `companies.needs_reactivation_feedback` para no volver a mostrar el dialog.
  - `POST /api/reactivation-feedback/skip` — descarta el dialog sin enviar. Limpia el flag.
  - `GET /api/reactivation-feedback/list` (superadmin only) — retorna items + breakdown por reason + reason_labels.
- **`routes/superadmin_retention.py::reactivate_company`**: al reactivar setea `needs_reactivation_feedback: true`.
- **`routes/auth.py`**: `/login` y `/me` retornan `needs_reactivation_feedback: bool` en el user payload (solo si role=admin y el flag esta true).
- **Frontend `components/retention/ReactivationFeedbackDialog.jsx`**: dialog automatico que aparece con delay de 1.2s al cargar la app si `user.needs_reactivation_feedback == true`. Include: 6 radios de motivo, textarea opcional (max 1000 char), checkbox "Autoriza contacto", botones "Ahora no"/"Enviar feedback". Incluido en `MainLayout.js` para todas las paginas del admin. Refresca `checkAuth()` post-submit para limpiar el flag localmente.
- **Frontend `RetentionDashboard.jsx`**: nueva tab "Feedback (N)" (`tab-feedback`) con breakdown por motivo (pills purple) y lista de cards de feedback (`feedback-{id}`) con optica/admin/motivo/comment/badge autoriza-contacto/mailto para contactar.
- **Notificacion push al SuperAdmin** con `event_type=reactivation_feedback` al enviar cada feedback.

**IMPORTANTE - Regla de desactivacion aclarada (Feb 2026)**:
- El `activation_task._process_deactivations` (dia 30) **SOLO desactiva ópticas donde el admin NUNCA ha ingresado por primera vez** (`first_login_at is None`).
- Opticas ya activadas (con `first_login_at` establecido) NO se desactivan por inactividad — se muestran en Panel Retencion como "En riesgo" para contacto manual.
- Otras reglas de inactivacion (falta de pago Stripe, etc.) se definiran cuando el modulo de pagos este completamente operativo.
- Docstring de `_process_deactivations` actualizado con esta regla de negocio.

### Bienvenida Programada + Panel Retencion Opticas (Feb 2026)

**Bienvenida programada (dia 3)**:
- `activation_task.py::_process_welcome_tips`: nueva stage del loop que envia email amigable con 5 tips practicos + CTA "Inicio Rapido" al admin en dia 3-22 SOLO si aun no ha ingresado. Marcado con `users.welcome_tips_sent_at` para idempotencia. Se excluye si `days_since_created >= DEADLINE_DAYS-7` para no solapar con recordatorio de 7d.
- Nuevo template `email_service.py::render_onboarding_tips(admin_name, company_name, login_link)`: template con 5 tips (registrar 5 pacientes, configurar logo, cargar 10 armazones/5 lentes, venta de prueba, invitar equipo) y CTA gradient a `/onboarding`. Sin video (por decision del usuario).
- Config: `WELCOME_TIPS_DAY=3` (env override).

**Panel Retencion Opticas (SuperAdmin)**:
- Nueva ruta `/admin/retencion` con item sidebar 'Retencion' (icono Sparkles).
- **Backend `routes/superadmin_retention.py`**:
  - `GET /api/superadmin/retention`: retorna KPIs (total, active, inactive, never_activated, at_risk, expired, recently_activated, activation_rate) + thresholds (at_risk_days=15, deadline_days=30) + segmentos con lista de opticas (never_activated, at_risk, expired, recently_activated). Batch aggregation admin_activity + patients_count + plans + companies en O(4) queries constantes.
  - `POST /api/companies/{id}/reactivate`: reactiva optica + admins, genera password reset token (24h TTL, source='reactivation'), envia email al admin con link para nueva contrasena, resetea markers de activation_task (reminder_7d, reminder_2d, welcome_tips) para reiniciar el ciclo. Audit `COMPANY_REACTIVATED`. Solo superadmin (403 para otros roles).
- Nuevo template `render_reactivation_notice(admin_name, company_name, reset_link)`.
- **Frontend `RetentionDashboard.jsx`**: 6 stat cards con color-code (`kpi-{total|activation-rate|recently|never|at-risk|expired}`), 4 tabs (`tab-{never|at-risk|expired|recent}`), tabla por segmento con optica/admin/creada/estado/accion. Tab Expiradas tiene boton verde "Reactivar" que abre AlertDialog de confirmacion (`reactivate-dialog`) → llamada POST /reactivate → toast + refresh. Otros tabs tienen boton mailto con mensaje pre-armado por segmento.
- **Testing**: 19/19 tests backend PASS + frontend E2E OK. Fix menor aplicado: HTML hydration warning por `<ul>` dentro de `<AlertDialogDescription>` → separado en dos elementos.

### Agendar proxima cita + Tracking activacion admin (Feb 2026)
**Fix bug agenda**: El modal "Agendar proxima cita" al terminar consulta antes solo aparecia en `/consultations`. Ahora tambien aparece cuando la consulta se crea desde el card del paciente en `/patients`.
- Nuevo componente compartido `components/appointments/NextAppointmentDialog.jsx` (props: open, onOpenChange, patientId, professionalId, professionalName, onSaved). Fecha default = hoy+6 meses, botones rapidos 7/30/90/180/365 dias.
- `PatientsPage.js::handleCreateConsultation` y `ConsultationsPage.js::handleSave` disparan el modal via `setNextApptCtx()` con delay 300ms.

**Feature tracking de activacion del admin (Issue 2)**:
- **Backend `auth.py`**: cada login exitoso actualiza `users.last_login_at`. En el PRIMER login se setea `users.first_login_at`. Si el usuario es `role=admin` y es su primer login, se dispara:
  - Update `companies.admin_activated_at = now`.
  - Notificacion push al SuperAdmin (`event_type=admin_first_login`, titulo "Optica activada").
  - Audit log `ADMIN_FIRST_LOGIN`.
- **Backend `companies.py` `GET /api/companies`**: nueva aggregacion batch de users con role=admin. Cada company retorna: `admin_email`, `admin_name`, `admin_first_login_at`, `admin_last_login_at`, `admin_activated` (bool), `days_since_last_login`, `days_since_created`.
- **Backend `email_service.py`**: nuevos templates `render_activation_reminder(days_remaining)` y `render_deactivation_notice()`. `render_welcome_company` ahora incluye warning de 30 dias.
- **Backend `activation_task.py`** (nuevo, ~180 lineas): loop async que corre cada 12h (`ACTIVATION_CHECK_INTERVAL`). Umbral configurable `ACTIVATION_DEADLINE_DAYS=30`.
  - Dia 23 (7d restantes): envia recordatorio con `tag=reminder_7d`, marca `reminder_7d_sent_at`.
  - Dia 28 (2d restantes): envia recordatorio urgente `tag=reminder_2d`, marca `reminder_2d_sent_at`.
  - Dia 30+: desactiva company (`is_active=False`, `deactivated_reason=activation_expired`) + desactiva admin + envia email + notifica al superadmin + audit `COMPANY_DEACTIVATED_ACTIVATION_EXPIRED`.
  - Filtra admins con `$or:[{first_login_at:None},{exists:False}]` (robusto).
- **Backend `server.py` startup**: migracion idempotente de backfill — para todos los admins existentes sin `first_login_at`, se setea `first_login_at=$created_at`. Evita que ópticas antiguas se desactiven por error (bug detectado y corregido en la sesion: 5 opticas fueron desactivadas erroneamente y luego restauradas manualmente + backfill agregado).
- **Frontend `AdminOpticasPage.js`**:
  - Nuevo helper `getActivationBadge(company)` con logica de estados: `Activo` (login <=7d), `Hace Xd` (7-30d), `Inactivo` (>30d), `Sin activar` (nunca ingreso), `Por expirar` (dia 23-29), `Expirada` (dia 30+).
  - Filtros clickeables: `Todas / Sin activar / Activas / Inactivas` (data-testid=`activation-filter-{key}`).
  - Badge en cada card (data-testid=`activation-badge-{company_id}`).
  - Seccion "Activacion del Administrador" en tab Info del detalle: estado, admin name/email, primer login, ultimo acceso con "hace Xd".
- **Testing**: 6/6 tests backend PASS + validacion UI end-to-end del testing agent. Test en `/app/backend/tests/test_activation_tracking.py`.


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

### WhatsApp para Recetas (Feb 2026)

### Fix congruencia planes + submenu Configuracion (Feb 2026)
- **Bug SuperAdmin 'Plan no encontrado'**: `plans_cache.invalidate()` era sync fire-and-forget, dejaba Redis stale con `_ids` obsoletos. Fix: `create_plan`, `update_plan`, `delete_plan` ahora usan `await plans_cache.ainvalidate("all_plans")` (bloqueante, atomico).
- **Congruencia**: cualquier cambio del superadmin en planes es visible INMEDIATAMENTE en `/my-plan` del admin y en `/api/plans` sin esperar TTL.
- **UI submenu Configuracion (v2)**: reorganizacion completa del sidebar admin:
  - `Inicio rapido` movido al TOP del sidebar (primer item).
  - `Configuracion` ahora contiene 4 hijos: **Sucursales · Usuarios · Mi Plan · Soporte**.
  - Roles no-admin (user/doctor) siguen viendo `Soporte` a top-level (no tienen menu Configuracion).
  - `MainLayout.NavLink` soporta `children[]` con indentacion `border-l` y auto-expand cuando parent o child esta activo.
- **Testing agent: 18/18 tests OK** (backend cache coherency). UI de reorganizacion validada visualmente para admin y vendedor.

### Billing self-service con Stripe (Feb 2026)
- **Modelo**: suscripciones mensual y anual (anual = mensual x10, "2 meses gratis" -> ahorro 16%). Proracion la maneja Stripe internamente.
- **Aprobacion**: self-service — admin paga y su plan se actualiza automatico al confirmarse.
- **Backend** `routes/billing.py`:
  - `POST /api/billing/checkout` (admin only): valida plan, arma sesion Stripe Checkout con metadata (company_id, plan_id, cycle, user_id), registra en `payment_transactions`. Rechaza planes gratuitos con mensaje claro.
  - `GET /api/billing/status/{session_id}` (publico, para polling desde el redirect de Stripe).
  - `GET /api/billing/my-transactions` (admin y superadmin).
  - `POST /api/webhook/stripe` (endpoint webhook a nivel raiz, path completo). `_mark_paid_and_apply_plan` es idempotente: actualiza `companies.plan_id`, `billing_cycle`, `last_payment_at` y registra `plan_history`.
- **Integracion**: `emergentintegrations.payments.stripe.checkout` con `STRIPE_API_KEY=sk_test_emergent` (sandbox compartido). Guatemala no tiene sandbox propio.
- **Frontend** `MyPlanPage.js` en `/my-plan`, accesible desde el sidebar (solo admin):
  - Muestra plan actual con barras de uso (pacientes / sucursales).
  - Toggle mensual/anual con badge "Ahorra 16%".
  - Grid de 3+ planes con badge "Popular" en Pro, botones "Elegir plan" -> redirect a Stripe Checkout.
  - Polling automatico al volver con `?session_id=...` -> toast de exito.
  - Historial de pagos con estados (pagado / pendiente / fallido).
  - Banner explicativo del prorrateo.
- **Indices**: `payment_transactions.session_id` (unique), `company_id+_id`, `payment_status`.
- **Testing agent: 20/20 tests OK, 0 criticos.** Suite: `/app/backend/tests/test_billing.py`.

### Bugfix Caja: admin sin branch_id (Feb 2026)
- Backend: `list_eyeglass_prescriptions`, `list_contact_lens_prescriptions`, `list_medical_prescriptions` ahora hacen batch `$in` de pacientes con projection `{first_name, last_name, phone, whatsapp}` y enriquecen cada rx con `patient_name`, `patient_phone`, `patient_whatsapp` (siempre presentes, incluso si el paciente fue eliminado = orphan rx).
- Frontend `PrescriptionsPage.js`:
  - Handler `openWhatsAppFor(type, rx)` que arma mensaje distinto por tipo con resumen de la receta (grados, medicamentos, diagnostico) y firma "Gracias por confiar en Cortexia Optical".
  - Boton verde "WhatsApp" en cada fila de las 3 tablas junto a "PDF". Abre `https://wa.me/{numero}?text=...` en pestana nueva.
  - Muestra toast si el paciente no tiene telefono ni WhatsApp registrado.
- Verificado: testing agent 15/15 tests OK. Fix menor aplicado post-report: campos `patient_*` ahora siempre presentes en la respuesta (recetas huerfanas OK).

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
- Password del seed inicial se lee de env var `ADMIN_PASSWORD` (backend/.env). Evita characters especiales de shell (`$`, `!`) si vas a exportarlo sin comillas simples
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
