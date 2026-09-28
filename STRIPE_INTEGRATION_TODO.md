# Stripe — Suscripciones recurrentes (Cortexia Optical)

Esta app cobra la **membresía** con **Stripe Checkout en modo suscripción** (recurrente,
mensual/anual, moneda USD). Se usa el **SDK nativo de Stripe** (la librería de pagos único
no soporta suscripciones). Documento = fuente única de pasos pendientes.

## Valores a reemplazar / configurar

**Archivos con la lógica:**
- [backend/routes/billing.py](backend/routes/billing.py) — checkout, status, portal, sync
- [backend/.env](backend/.env) — llaves/secretos

| Campo | Valor actual | Qué poner |
|-------|--------------|-----------|
| `STRIPE_API_KEY` | `sk_test_emergent` (placeholder, NO funciona con el SDK nativo) | **Tu llave secreta de Stripe** de "Cortexia Technologies LLC". Usa `sk_test_...` para probar y `sk_live_...` para producción. Agrégala en **Manage → Secrets** (no en el código). |
| `line_items[].price` | Se genera solo | El backend crea/actualiza el **Price recurrente** de cada plan por `lookup_key` (`cortexia_<plan_id>_<ciclo>`). No hay que tocar IDs a mano. |
| `success_url` / `cancel_url` | `<<origin>>/my-plan?...` | Ya son reales (usan el dominio del frontend). |
| `mode` | `subscription` | Fijo (cobro recurrente). |

## Parámetros configurados (Stripe Checkout Studio → `fixed_by_ui`)

**Archivo:** [backend/routes/billing.py](backend/routes/billing.py) (`_create_subscription_session`)

| Parámetro | Valor |
|-----------|-------|
| `mode` | `subscription` |
| `billing_address_collection` | `auto` |
| `phone_number_collection.enabled` | `false` |
| `automatic_tax.enabled` | `false` |
| `allow_promotion_codes` | `false` |
| `payment_method_collection` | `always` |

> El SDK inicializa sin fijar versión de API (se usa la de la cuenta).

## Qué debes hacer TÚ (pasos pendientes)

1. **Agregar tu llave secreta de Stripe** en **Manage → Secrets** como `STRIPE_API_KEY`
   (primero la de **Test** `sk_test_...`; luego la de **Live** `sk_live_...` para producción).
   No la pegues en el chat ni en el código.
2. Avísale al agente para hacer la **prueba de punta a punta** en preview
   (tarjeta de prueba `4242 4242 4242 4242`, cualquier fecha futura, cualquier CVC).
3. Para producción: publica/redeploya la app con la llave **Live** en Secrets.

## Cómo funciona el flujo

1. Frontend → `POST /api/billing/checkout {plan_id, billing_cycle, origin_url}`.
2. Backend asegura Product + Price recurrente del plan, crea/reutiliza el Customer de la óptica,
   y crea la **Checkout Session (mode=subscription)**. Devuelve `checkout_url`.
3. El usuario paga en la página **hosted** de Stripe y regresa a `/my-plan?session_id=...`.
4. El frontend hace polling a `GET /api/billing/status/{session_id}`; el backend consulta a Stripe
   y **activa el plan** en la empresa en cuanto la suscripción queda pagada (idempotente).
5. Gestión/cancelación: `POST /api/billing/portal` abre el **Billing Portal** de Stripe.

## Ciclo de vida (renovaciones, impagos, cancelaciones)

Sin webhooks. Un **cron diario** (`.emergent/crons.yml` → `POST /api/cron/sync-subscriptions`,
protegido con `WEBHOOK_CRON_SECRET`) consulta a Stripe cada suscripción y:
- `active` / `trialing` → mantiene el plan y actualiza `last_payment_at`.
- `past_due` / `incomplete` → mantiene el plan (periodo de gracia) y marca el estado.
- `canceled` / `unpaid` / `incomplete_expired` → **baja la óptica al plan Free** y registra el cambio.

## Pruebas

- Tarjeta OK: `4242 4242 4242 4242`. Requiere autenticación: `4000 0025 0000 3155`. Rechazada: `4000 0000 0000 9995`.
- Todo en modo Test no genera cobros reales.

## Recursos

- https://docs.stripe.com/billing/subscriptions/overview
- https://docs.stripe.com/api/checkout/sessions/create
- https://support.stripe.com
