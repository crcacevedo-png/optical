# Cuentas de cortesía (sin costo mensual) — acción del SuperAdmin

## Objetivo
Permitir que el SuperAdmin marque una óptica como "cuenta de cortesía" para que su
costo mensual quede en Q0, sin cambiarle el plan ni los módulos. Pensado para un
grupo de optometristas a quienes se les regala el acceso.

## Qué se construye
Un control, visible únicamente para el SuperAdmin dentro de la ficha de cada
óptica, que activa o desactiva la cortesía de esa óptica.

- Cuando la cortesía está activa, el costo mensual efectivo de esa óptica es **Q0**.
- El plan asignado, sus módulos y sus límites **no cambian**. Solo se elimina el
  cobro mensual.
- Es **reversible**: el SuperAdmin puede quitar la cortesía y la óptica vuelve al
  precio de su plan.
- Queda registrado quién activó/quitó la cortesía y cuándo (auditoría).

## Cómo se comporta (decisiones confirmadas por el usuario)
- **Se aplica óptica por óptica, a mano.** El SuperAdmin entra a cada óptica del
  grupo y le activa la cortesía. No hay aplicación en bloque.
- **Cortesía = costo mensual en Q0 (waiver total).** No es un precio personalizado
  arbitrario.
- **La cortesía es permanente hasta que el SuperAdmin la quite.** Sin fecha de
  vencimiento automática.
- **La óptica ve simplemente Q0** como su costo mensual, sin ninguna etiqueta de
  "cortesía".
- **Solo afecta el costo mensual.** No toca módulos, límites ni el plan.

## Dónde se refleja
- El costo mensual efectivo (Q0 si es cortesía, si no el del plan) se muestra en la
  vista "Mi Plan" de la óptica y en el panel del SuperAdmin.
- Las cuentas de cortesía aportan Q0 a los totales de ingresos del SuperAdmin.
- Si en el futuro se activan reglas de inactivación por falta de pago, las cuentas
  de cortesía quedan exentas.

## Fuera de alcance
- Cobros reales, pasarela de pago o facturación (no se procesa dinero).
- Aplicación masiva a un grupo con un clic.
- Precios personalizados distintos de Q0 (descuentos parciales).
- Cambios de plan, módulos o límites de la óptica.
