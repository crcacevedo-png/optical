# Agregar "Descarga la Guía de usuarios" como Paso 1 en Inicio rápido

## Objetivo
Añadir en "Inicio rápido" un paso nuevo para descargar la Guía de usuarios,
ubicado como **Paso 1** (el primero de la lista). Los pasos actuales se recorren
un lugar (el actual Paso 1 "Cambia tu contraseña inicial" pasa a ser Paso 2, y así
sucesivamente). Además, se actualiza el contenido de la Guía de usuarios para que
sea coherente con este cambio.

## Qué se construye
1. **Nuevo Paso 1 en Inicio rápido**:
   - Título: "Descarga la Guía de usuarios".
   - Descripción breve invitando a descargar la guía para conocer la plataforma.
   - Botón que descarga la Guía de usuarios en PDF (la guía oficial que la
     plataforma ya genera hoy).
   - Casilla para marcarlo como completado, igual que los demás pasos.
   - Se marca como completado automáticamente al descargar la guía (también se
     puede marcar/desmarcar a mano).
2. **Renumeración y progreso**:
   - La lista pasa de 7 a **8 pasos**. El nuevo es el Paso 1; los 7 actuales pasan
     a ser 2–8, conservando su orden y textos.
   - El Paso 1 cuenta para el progreso: el medidor y el texto pasan a "X de 8
     pasos completados".
3. **Actualización de la Guía de usuarios**:
   - En la sección "Antes de empezar: Primer ingreso", donde hoy dice que el
     onboarding tiene "7 pasos", se actualiza a "8 pasos".
   - Se agrega, como primer paso del onboarding descrito en la guía, el de
     descargar la Guía de usuarios, para que la guía coincida con lo que el
     usuario ve en pantalla.

## Decisiones tomadas (se pueden objetar)
1. **Posición y numeración**: el nuevo va como Paso 1 y el resto se recorre a 2–8
   (confirmado por el usuario).
2. **Cuenta para el progreso**: sí; el total visible pasa a 8 pasos.
3. **Marcado automático al descargar**: sí, además del marcado manual.
4. **Guía a descargar**: la Guía de usuarios oficial existente (no se crea una
   guía nueva; solo se ajusta el texto indicado arriba).

## Fuera de alcance
- Reescribir o rediseñar el resto del contenido de la Guía de usuarios (solo el
  ajuste de "7 → 8 pasos" y la mención del nuevo primer paso).
- Cambiar el orden o los textos de los pasos existentes.
- Agregar el paso en vistas fuera de "Inicio rápido".
