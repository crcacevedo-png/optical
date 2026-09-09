# Ampliar límite de pacientes por óptica (acción del SuperAdmin)

## Objetivo
Permitir que el SuperAdmin suba el límite de pacientes de una óptica específica
(por ejemplo, de 50 a 150) sin cambiarle el plan ni cobrarle nada. Pensado para
las ópticas que llegaron con un código de promoción, a quienes se les ofrece este
beneficio.

## Qué se construye
Un control, visible solo para el SuperAdmin dentro de la ficha de cada óptica, que
permite fijar un límite de pacientes personalizado para esa óptica. Cuando está
fijado, ese número reemplaza al límite que trae el plan.

- El campo viene precargado con **150** (valor sugerido del beneficio), pero el
  SuperAdmin puede escribir cualquier número. Así el mismo control sirve para
  futuros beneficios con otros límites.
- El plan de la óptica, su precio y sus módulos **no cambian**. Solo cambia el
  tope de pacientes.
- Es **reversible**: el SuperAdmin puede quitar el límite personalizado y la
  óptica vuelve al tope de su plan.
- Queda registrado quién hizo el cambio y cuándo (auditoría).

## Cómo se comporta
- El límite efectivo de una óptica pasa a ser: el personalizado si está fijado; si
  no, el del plan.
- El bloqueo al crear pacientes, los avisos de "cerca del límite / límite
  alcanzado" y el medidor de uso del plan respetan este límite efectivo. Es decir,
  una óptica con 150 podrá seguir registrando pacientes hasta 150.

## Decisiones tomadas (se pueden objetar)
- **Se aplica óptica por óptica, a mano.** El SuperAdmin entra a la óptica y le
  sube el límite. No se aplica de forma automática a todas las que usaron un código
  de promoción. Motivo: el pedido dice "únicamente por el superadmin" y da control
  caso por caso. Alternativa posible si se prefiere: aplicar el beneficio en bloque
  a todas las ópticas de un código dado.
- **Solo afecta el límite de pacientes**, no el de sucursales u otros topes.
- **No se muestra automáticamente qué código de promoción usó cada óptica.**
  Identificar a las beneficiarias queda a criterio del SuperAdmin. Nota: ese enlace
  solo existiría para ópticas creadas desde una solicitud con código; las creadas
  de otra forma no lo tendrían, por eso no es confiable como filtro.

## Fuera de alcance
- Cambios de precio, cobros o descuentos.
- Autoaplicación masiva por código de promoción.
- Ajuste de otros límites del plan (sucursales, módulos).
