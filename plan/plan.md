# Control de Cobros y Suspensión por Impago — Cortexia Optical

Sistema automático de gestión de cobros para las membresías de las ópticas: detecta pagos fallidos en Stripe, da 3 días de gracia con avisos, suspende el acceso si no se regulariza y reactiva solo cuando se paga. Incluye alertas al superadmin y a la óptica, más un panel de cobros para el superadmin.

## Para quién es
- **Superadmin (dueño de la plataforma):** supervisa el estado de cobro de todas las ópticas, recibe alertas y actúa sobre morosos.
- **Admin de cada óptica:** recibe avisos de impago y regulariza su pago desde la app.
- **Vendedores y otros roles de la óptica:** solo se ven afectados por el bloqueo; no participan del cobro.
- Las cuentas marcadas como **cortesía** quedan siempre exentas (sin costo ni suspensión).

## Funcionalidades y experiencia
1. **Detección automática de impago.** El sistema reconoce cuando Stripe marca un pago como fallido y arranca el reloj de gracia.
2. **Periodo de gracia de 3 días** desde el fallo del pago. Durante la gracia la óptica sigue operando con normalidad, pero ve avisos claros de que debe regularizar.
3. **Recordatorios escalonados a la óptica** (in-app + correo): al fallar el pago, durante los días de gracia y al momento del bloqueo.
4. **Suspensión con "muro de pago".** Al terminar la gracia sin pago, la cuenta se suspende: el **admin** solo puede entrar a una pantalla que muestra su estado de cuenta y el enlace para pagar/actualizar su tarjeta; el resto de la app queda bloqueado. Los demás usuarios de esa óptica ven un aviso de "cuenta suspendida, contacta a tu administrador".
5. **Reactivación automática.** En cuanto el pago se regulariza (Stripe confirma el cobro), la cuenta recupera su plan y el acceso completo, sin intervención manual.
6. **Alertas al superadmin** (in-app + correo) cuando una óptica cae en impago y cuando se suspende.
7. **Panel de Cobros del superadmin.** Un tablero para ver de un vistazo: renovaciones próximas, pagos fallidos / en gracia (con días restantes), cuentas suspendidas, e ingresos mensuales en riesgo. Desde ahí se abre la ficha de cada óptica.
8. **Verificación de monto vs. plan contratado.** El sistema compara lo que Stripe está cobrando contra el precio vigente del plan de esa óptica (mensual/anual). Si no coinciden, marca la cuenta y avisa al superadmin (sin suspender por esta causa).

## Flujo de uso
**Impago (óptica):**
Pago falla en Stripe → **Día 0:** aviso al admin y al superadmin + banner de gracia con cuenta regresiva de 3 días (sigue operando) → **Días 1–2:** recordatorios de gracia → **Día 3 sin pago:** suspensión + muro de pago → el admin paga o actualiza su tarjeta → **reactivación automática** y recuperación del plan.

**Superadmin:**
Entra al panel de Cobros → ve quién está por renovar, quién falló, quién está en gracia (y cuántos días le quedan), quién está suspendido y qué cuentas tienen discrepancia de monto → abre la ficha de la óptica para más detalle.

**Verificación de monto:**
El sistema revisa periódicamente que el cargo activo de cada suscripción coincida con el precio del plan contratado; ante una diferencia, marca la cuenta y notifica al superadmin.

## Sensación de UI/UX
- Consistente con la estética actual (Shadcn UI, azul navy de Cortexia).
- Código de color claro: **verde** = al día, **ámbar** = en gracia / por renovar, **rojo** = vencido / suspendido.
- Durante la gracia, banners visibles pero no bloqueantes; al suspender, un muro de pago simple y directo con un único llamado a la acción ("Pagar ahora").
- Panel de cobros tipo tablero: tarjetas de indicadores arriba + listas filtrables abajo.

## Fases de implementación

**Fase 1 — MVP (se construye ahora)**
- Detección de impago vía Stripe y gracia de 3 días desde el fallo.
- Recordatorios a la óptica (in-app + correo) al fallar, durante la gracia y al bloquear.
- Suspensión con muro de pago (admin ve estado + enlace de pago; otros usuarios ven aviso).
- Reactivación automática al regularizar el pago.
- Alertas al superadmin (in-app + correo) en fallo y en suspensión.
- Panel de Cobros del superadmin: renovaciones próximas, fallidos/en gracia con días restantes, suspendidos e ingresos en riesgo.
- Verificación de que el monto cobrado corresponde al plan contratado + alerta de discrepancia.

**Fase 2**
- Periodo de gracia y cadencia de recordatorios **configurables** por el superadmin (días y textos de los mensajes).
- Historial de pagos y comprobantes por óptica (descargables).
- Recordatorios **proactivos antes** del vencimiento (tarjeta por expirar, próximo cargo).
- Reportes de recuperación de pagos y de bajas por impago (churn).

**Fase 3**
- Gestión avanzada: prórrogas manuales del superadmin, pagos parciales, cupones/descuentos.
- Enganche con facturación fiscal de Guatemala (FEL/SAT) al momento del cobro.
- Multi-moneda y ajuste fino de los reintentos de cobro.

## Supuestos
- Todas las cuentas de pago usan Stripe; **cortesía = exenta** (sin cobro ni suspensión).
- La gracia de 3 días la controla la plataforma desde que Stripe marca el pago como fallido, independientemente de la ventana de reintentos propia de Stripe; si Stripe recupera el pago más tarde, la cuenta se reactiva sola.
- "Bloquear" significa **suspender**: el admin de la óptica solo accede al muro de pago (estado + enlace); vendedores y otros roles quedan sin operar y ven "cuenta suspendida, contacta a tu administrador".
- La **cancelación voluntaria** de la suscripción (al llegar a fin de periodo) también lleva a suspensión, no a un plan gratuito; no hay uso gratuito para cuentas que dejan de pagar (salvo cortesía).
- Recordatorios durante la gracia: uno al fallar (día 0), uno en cada día de gracia (días 1 y 2) y uno al suspender (día 3). Ajustable si se prefieren menos correos.
- La reactivación es automática al confirmarse el pago; el superadmin no necesita intervenir (podrá hacerlo manualmente solo en casos especiales, en fases posteriores).
- La verificación de monto compara el cargo activo de Stripe contra el precio vigente del plan (mensual/anual); una discrepancia se marca y se avisa, pero **no** suspende por sí sola.
- Las membresías se siguen cobrando en **USD** (la operación de la óptica permanece en Quetzales), como ya está definido.
- Las alertas usan los canales ya existentes de la plataforma (avisos in-app + correos).
