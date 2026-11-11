# Selección de moneda para Latinoamérica

Permite que cada óptica elija la moneda en la que trabaja (por nombre y país) y que esa moneda se muestre en todo el sistema.
Hoy la moneda está fija como Quetzal de Guatemala; esta función la vuelve configurable sin tocar las cifras ya registradas.

## Para quién es
Administradores de ópticas de distintos países de Latinoamérica que usan Cortexia y necesitan que ventas, precios, caja, cotizaciones, finanzas y reportes se muestren en su propia moneda local, no en Quetzales.

## Funcionalidad y experiencia principal
- **Selector de moneda** en Configuración (visible solo para el administrador), con una lista amplia de monedas latinoamericanas más el dólar estadounidense. Cada opción se muestra con su **nombre, país y símbolo** (por ejemplo: "Peso mexicano (México) — $", "Sol (Perú) — S/", "Quetzal (Guatemala) — Q", "Dólar (Ecuador/El Salvador/Panamá) — $").
- **Aplica a toda la óptica**: una sola moneda para todas las sucursales y usuarios del negocio.
- **Se refleja en todo el sistema**: cualquier lugar donde se muestre dinero adopta el símbolo y el formato de la moneda elegida — ventas y punto de venta, cotizaciones, caja (apertura/cierre, pagos, cuentas por cobrar), finanzas, cuentas por pagar y cobrar, inventario y precios, tablero/indicadores, reportes, jornadas, y los importes en comprobantes/PDF que incluyan montos.
- **Paso en el Inicio rápido**: la elección de moneda se agrega como uno de los primeros pasos del asistente de Inicio rápido (onboarding), para que cada óptica la defina al configurar su cuenta. El paso lleva directo a la configuración de moneda, se marca como completado y se puede editar después desde Configuración.
- **En el manual de usuario**: la función queda documentada en el manual (PDF), dentro de la sección de configuración inicial, explicando cómo elegir la moneda y que solo cambia la presentación (sin convertir cifras).
- **Sin conversión de cifras**: cambiar la moneda solo cambia el **símbolo y el formato** mostrado; los montos ya registrados (ventas pasadas, precios, saldos, reportes) conservan su número tal cual. Está pensado para fijar la moneda una vez, de preferencia al inicio.
- **Formato por país**: la separación de miles/decimales y la cantidad de decimales siguen la convención de cada moneda (por ejemplo, el peso chileno y el guaraní se muestran sin decimales; otras con dos decimales).
- **Valor inicial**: las ópticas actuales siguen viendo Quetzal hasta que el administrador decida cambiarlo, de modo que nada se altera para quienes ya usan el sistema.
- **Aviso al cambiar**: antes de guardar, se muestra una confirmación que aclara que solo cambia la presentación y que los montos históricos no se convierten.

## Flujo del usuario
1. El administrador entra a **Configuración** (o toca el paso **"Elige la moneda de tu óptica"** del Inicio rápido, que lleva al mismo lugar).
2. Abre la tarjeta **Moneda** y ve la moneda actual del negocio.
3. Elige en la lista la moneda deseada (identificada por nombre, país y símbolo).
4. Confirma el aviso de que solo cambia la presentación (sin convertir cifras).
5. Guarda; de inmediato, todas las pantallas que muestran dinero pasan a usar el símbolo y el formato de la nueva moneda, y el paso del Inicio rápido queda marcado como completado.

## Estética y sensación (UI/UX)
Consistente con la pantalla de Configuración actual de Cortexia: tarjeta limpia con acento verde (pine), un menú de selección con buscador para encontrar la moneda rápidamente, y cada opción mostrando nombre + país + símbolo. El paso del Inicio rápido mantiene el mismo estilo de tarjeta de los demás pasos. La función es exclusiva del rol administrador.

## Fases de implementación

**Fase 1 — MVP (se construye ahora)**
- Selector de moneda en Configuración (solo administrador) con lista amplia de Latinoamérica + dólar.
- Moneda única por óptica (todas las sucursales y usuarios).
- Aplicación del símbolo y formato de la moneda elegida en todas las pantallas y documentos donde se muestra dinero.
- Formato y decimales según la convención de cada moneda.
- Sin conversión de montos; Quetzal como valor inicial para las cuentas existentes.
- Aviso de confirmación al cambiar la moneda.
- **Nuevo paso "Elige la moneda de tu óptica" en el Inicio rápido**, que enlaza a la configuración de moneda y se puede marcar como completado.
- **Documentación de la moneda en el manual de usuario (PDF)**, dentro de la sección de configuración inicial, con el índice actualizado.

**Fase 2 — Claridad y documentos**
- Mostrar el código internacional de la moneda (p. ej. MXN, PEN, GTQ) junto a los montos en reportes y comprobantes, para evitar ambigüedad entre monedas que comparten el símbolo "$".
- Incluir la moneda en las exportaciones (Excel/PDF) y en los correos con importes.
- Opción de ajustar manualmente el símbolo o los decimales si una óptica lo necesita.

**Fase 3 — Casos avanzados**
- Herramienta opcional de conversión por tipo de cambio para reexpresar cifras históricas cuando un negocio realmente cambia de moneda.
- Moneda distinta por sucursal y reportes consolidados multimoneda.

## Supuestos
- **Alcance**: la moneda es única para toda la óptica (todas las sucursales y usuarios); la define el administrador.
- **Solo presentación**: cambiar la moneda no convierte ni recalcula montos; únicamente cambia símbolo y formato.
- **Valor inicial**: las ópticas actuales continúan en Quetzal (Guatemala) hasta que el administrador elija otra moneda.
- **Lista de monedas**: se incluye un conjunto amplio de Latinoamérica más el dólar estadounidense (p. ej. Quetzal–Guatemala, Peso–México, Dólar–EE. UU./Ecuador/El Salvador/Panamá, Sol–Perú, Peso–Colombia, Peso–Chile, Peso–Argentina, Boliviano–Bolivia, Guaraní–Paraguay, Peso–Uruguay, Lempira–Honduras, Córdoba–Nicaragua, Colón–Costa Rica, Real–Brasil, Bolívar–Venezuela). El conjunto final puede ajustarse sin cambiar la experiencia.
- **Formato por moneda**: el separador de miles/decimales y la cantidad de decimales siguen la convención de cada país.
- **Inicio rápido**: el paso de moneda se suma a los pasos existentes (el total de pasos del asistente aumenta) y se puede completar/editar; elegir la moneda también queda disponible siempre desde Configuración.
- **Manual de usuario**: la moneda se documenta dentro de la configuración inicial del manual (no es un capítulo nuevo); se actualiza el índice y la numeración de páginas.
- **Impuestos no incluidos**: elegir la moneda no cambia el régimen fiscal ni la facturación específica de Guatemala (IVA/FEL/SAT); eso es independiente y queda fuera de esta función.
- **Permiso**: la configuración de moneda es exclusiva del rol administrador de cada óptica.
