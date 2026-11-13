# Evaluación y múltiples recetas — Cortexia Optical

Un rediseño del módulo clínico que separa con claridad la evaluación del paciente, la refracción final validada y la preparación de una o varias recetas por examen.
Una evaluación puede generar cero, una o muchas recetas (anteojos, lentes de contacto y esclerales), cada una con su propio uso, estado y documento imprimible.

## Para quién es
Ópticas y profesionales de la salud visual (optometristas y oftalmólogos) que hoy usan Cortexia para registrar exámenes y emitir recetas. El objetivo es que un mismo examen soporte varias recetas del mismo o distinto tipo, con control de estados, versionado y entrega al paciente, sin reconstruir la aplicación ni perder registros anteriores.

## Funciones y experiencia principales
Todo esto se integra sobre los módulos actuales (Consultas y Recetas). No se duplican módulos, no se eliminan funciones y no se tocan los registros históricos.

**Nomenclatura de ojos: OD y OS en todo el sistema**
- Ojo derecho = OD y ojo izquierdo = OS, siempre explícitos y en ese orden.
- La etiqueta "OI" se reemplaza por "OS" en todas las pantallas clínicas (evaluación, lensometría, refracciones, refracción final, adaptaciones, editor y panel de recetas), en los PDF, en los mensajes de WhatsApp y correo, y en las exportaciones.
- Los datos ya guardados del ojo izquierdo se conservan y se muestran como OS; no se pierde ni se recalcula ningún valor.

**Espacio de trabajo por examen (nuevo diseño)**
- Encabezado con paciente, identificador, examen, fecha, profesional y estado.
- Secuencia visible en 4 pasos: Evaluación → Refracción final → Preparar recetas → Imprimir.
- Dos columnas en escritorio: a la izquierda evaluación, refracción final y editor de receta; a la derecha "Recetas del paciente" e impresión múltiple.
- En tablet y móvil los bloques se apilan y las recetas se abren en un panel independiente.
- Se conserva el logo, el menú y la identidad de marca ya configurada por cada óptica.

**Evaluación clínica (organizada, no recortada)**
- GENERAL: motivo y síntomas; antecedentes oculares, generales y familiares; cirugías, medicamentos y alergias; corrección habitual y necesidades visuales; biomicroscopía y superficie ocular; PIO por ojo con método y hora; fondo de ojo; evaluación binocular y acomodativa; estudios y archivos adjuntos.
- REFRACCIÓN: lensometría habitual, refracción objetiva, subjetiva, cicloplejia y refracción final, mantenidas como secciones separadas; esfera, cilindro, eje, adición, prisma y base por ojo, con agudeza visual (escala, distancia y condiciones).
- DIAGNÓSTICO Y PLAN: diagnósticos y lateralidad, interpretación, conducta e indicaciones, referencia y próximo control.
- No se autocompleta "normal". Se distingue entre no registrado, no realizado, no indicado y resultado negativo.
- Los campos clínicos completos se mantienen mediante pestañas o secciones desplegables.

**Bloque "Refracción final" (destacado, antes del editor de recetas)**
- Por OD y OS: esfera, cilindro, eje, adición, prisma horizontal y vertical con sus bases, y agudeza visual mejor corregida.
- Distancia de trabajo usada para evaluar la adición, observaciones clínicas, profesional responsable, estado y fecha de validación, y versión.
- Es el resultado clínico de referencia; NO equivale automáticamente a las recetas que se emitan.
- Acción explícita "Copiar refracción subjetiva" que el profesional debe revisar y validar.
- Guardar la evaluación nunca emite recetas por sí solo.

**Adaptaciones de lentes de contacto y esclerales (registro clínico, separado de la receta)**
- Documentación de adaptación con los hallazgos del proceso (hábitos y cuidados, queratometría/superficie, lentes de prueba, centrado/cobertura/movimiento/rotación, sobrerrefracción y agudeza, comodidad, hallazgos tras retiro, decisión y seguimiento; en esclerales además clearance central/mínimo/limbal con ubicación y método, apoyo/compresión/blanqueamiento/borde por sectores, burbujas/residuos/empañamiento, parámetros solicitados/recibidos/aceptados).
- Se admiten múltiples pruebas por ojo y múltiples consultas por adaptación.
- Una adaptación tiene estado "aceptada". La receta de contacto o escleral se prepara a partir de una adaptación aceptada, no de la refracción de anteojos ni de un lente de prueba.
- Sin umbrales universales que aprueben automáticamente un lente; sin cálculo automático de potencia a partir de la sobrerrefracción.

**Editor "Preparar receta" (los tres tipos)**
- Nombre descriptivo, tipo (anteojos / contacto / escleral), uso o finalidad, examen de origen, campos clínicos propios del tipo, indicaciones propias, control recomendado y vigencia.
- Acciones: Guardar borrador / Validar y emitir.
- Para anteojos: botón "Usar refracción final" que copia los valores de la versión validada, registra la procedencia, permite ajustes propios de esa receta, no modifica la refracción final y pide confirmación antes de sobrescribir campos ya editados.
- No se suma automáticamente la adición a la esfera; cualquier asistencia de cálculo es explícita, muestra qué cambia y requiere revisión. Se diferencia receta de lejos con ADD (multifocales) de potencia final de cerca (monofocal).
- Campos por tipo: anteojos (esf/cil/eje por ojo, adición, prisma/base, uso, distancia de trabajo, indicaciones, control; DP, alturas y armazón quedan en dispensación, identificados aparte de los resultados refractivos); contacto (fabricante/marca/modelo/material, potencia, cil/eje/adición según diseño, curva base, diámetro, diseño, modalidad y frecuencia de reemplazo, cuidados, control/vigencia; parámetros distintos por ojo); esclerales (laboratorio/diseño/código, potencia y componentes ópticos, diámetro, profundidad sagital con unidad y diámetro de referencia, zona limbal, háptica por sector, material/espesor, tratamiento superficial, modificaciones especiales, uso/llenado/limpieza/desinfección, control/vigencia; admite parámetros propios del fabricante).

**Panel "Recetas del paciente"**
- Por defecto muestra las recetas del examen abierto, con contador y botón "Agregar receta".
- Filtro separado para ver el historial del paciente.
- Cada receta muestra nombre, tipo, uso, fecha, versión, estado, resumen por ojo y casilla de selección para imprimir.
- Acciones según estado y permisos: ver, editar borrador, duplicar como nuevo borrador (con identificador propio, sin firma ni estado "emitida"), crear nueva versión, imprimir y anular con motivo. Una receta emitida no se edita como si fuera borrador.

**Estados y versionado (completo)**
- Estados diferenciados visualmente: borrador, emitida, sustituida y anulada.
- Una receta de anteojos solo se emite desde una refracción final validada; contacto y esclerales desde una adaptación aceptada; el profesional valida además los valores particulares de cada receta.
- La firma del examen completo y la emisión de recetas son estados distintos y coherentes.
- Al modificar una refracción validada se crea una revisión: se conserva la versión previa, las recetas ya emitidas quedan intactas y se indica si una receta proviene de una versión anterior.
- Una receta emitida conserva una instantánea de valores, indicaciones y datos de emisión; reimprimir reproduce esa instantánea.

**Impresión múltiple y entrega**
- Seleccionar una o varias recetas emitidas del mismo paciente para: imprimir seleccionadas, descargar un PDF conjunto, descargar cada PDF por separado y elegir cantidad de copias por receta.
- Una receta por página por defecto; cada documento conserva su propio encabezado, identificador, fecha y profesional aunque vaya en un PDF conjunto; no se mezclan pacientes.
- Los borradores no entran en la impresión de entrega; si se imprime un borrador para revisión interna, se marca claramente "BORRADOR · SIN VALIDEZ".
- El PDF reutiliza el mecanismo de marca, impresión y envío actuales e incluye: datos de la óptica, identificación del paciente, fecha de examen y emisión, identificador de receta, prescripción final por ojo, uso e indicaciones, control y vigencia, y el profesional con su línea de firma como hoy. No se inventan firmas, credenciales ni vencimientos, y no aparecen menús ni controles de la app.
- El envío por WhatsApp/correo usa la receta emitida seleccionada y el flujo actual; nunca se envía al guardar.

**Validaciones y seguridad**
- OD y OS siempre explícitos (nunca "OI"); se diferencia campo vacío de cero o plano; unidades visibles; eje obligatorio cuando el cilindro no es cero; convención de cilindro identificada; validaciones según tipo y diseño; sin valores "normales" por defecto; sin bloqueos por rangos arbitrarios.
- Permisos verificados en el servidor; aislamiento entre organizaciones; validación de paciente, examen y organización al emitir y exportar; auditoría de cambios, validaciones, emisiones y anulaciones; sin datos clínicos sensibles en registros de depuración.

## Flujo del usuario
1. El profesional abre o crea el examen de un paciente y completa la evaluación clínica por secciones.
2. Registra las refracciones y, cuando corresponde, copia la subjetiva a la refracción final, la revisa y la valida.
3. Para contacto o esclerales, documenta la adaptación (una o varias pruebas/consultas) y la marca como aceptada.
4. Prepara una o varias recetas: elige tipo y uso, parte de la refracción final validada (anteojos) o de la adaptación aceptada (contacto/escleral), ajusta valores propios, agrega indicaciones y guarda como borrador.
5. Valida y emite cada receta cuando está lista; la receta emitida queda congelada.
6. En el panel de recetas selecciona las emitidas que quiere entregar, define copias y genera la impresión o el PDF (individual o conjunto), o lo envía por el flujo actual.
7. Si más adelante cambia la refracción, crea una revisión sin alterar las recetas ya emitidas.

## Sensación de la interfaz
- Fondo claro, tarjetas blancas y acentos teal, siguiendo la imagen de referencia como guía de organización (no como lista exhaustiva de campos).
- Barra de pasos 1-2-3-4 siempre visible; la refracción final se presenta como bloque destacado antes del editor.
- Estados con color y etiqueta claros (borrador, emitida, sustituida, anulada) y avisos explícitos cuando una acción sobrescribe datos o depende de una validación.
- Tablas legibles, navegación por teclado y, en pantallas pequeñas, apilado con panel independiente para las recetas.
- La identidad visual actual y el logo configurado se conservan; el PDF mantiene el aspecto de marca ya existente.

## Fases de implementación

**Fase 1 — Flujo clínico completo (se construye ahora)**
Incluye, de forma funcional de punta a punta: el espacio de trabajo por examen con los 4 pasos y diseño responsivo; la evaluación clínica organizada por secciones; el bloque de refracción final validada con versión; las adaptaciones de contacto y esclerales con estado "aceptada"; el editor "Preparar receta" para los tres tipos (anteojos, contacto, escleral) con sus campos propios y "Usar refracción final"; el panel "Recetas del paciente" con todas sus acciones; estados y versionado completos (instantánea al emitir, revisiones de refracción, nueva versión, sustituida/anulada); impresión múltiple con copias, PDF conjunto o separado y marca de borrador; reutilización del PDF, WhatsApp y correo actuales; y las validaciones, aislamiento y auditoría descritos. Compatible con recetas y exámenes históricos, que se conservan y se pueden consultar e imprimir.

**Fase 2 — Refinamientos de impresión y documentación (posterior)**
Vista previa de impresión con reordenamiento y miniaturas; diseños de PDF dedicados por tipo de receta (en especial esclerales y contacto con todos sus parámetros); informe clínico completo del examen como documento separado; línea de tiempo de la adaptación; recordatorios de control y vigencia conectados a los nuevos campos.

**Fase 3 — Historial y productividad (posterior)**
Comparación lado a lado de versiones de refracción; tableros de historial por paciente; exportaciones por lote; diseñador de plantillas por tipo de receta; y, si se decide entonces, firma electrónica o credencial del profesional en el documento.

## Supuestos
- El nuevo espacio de trabajo se integra como la vista de detalle/edición del examen en el módulo de Consultas actual; la página global de Recetas se mantiene como listado entre pacientes para consulta e impresión.
- Las recetas y exámenes ya existentes se conservan tal cual: siguen visibles e imprimibles como "emitidas (históricas)" y no se reclasifican automáticamente como refracción final ni se les exige, de forma retroactiva, una refracción validada o una adaptación aceptada.
- El cambio de "OI" a "OS" es solo de nomenclatura visible: los registros históricos del ojo izquierdo se leen y se muestran como OS sin migraciones destructivas.
- Las recetas médicas (medicamentos) se mantienen como están hoy; el rediseño se centra en anteojos, contacto y esclerales.
- La firma en el PDF se mantiene como hoy (línea de firma y nombre del profesional); la identidad de quién emite y cuándo se registra en la auditoría, sin agregar credenciales nuevas en esta entrega.
- "Validar y emitir" lo puede hacer el profesional responsable y los perfiles con permiso de emisión ya existentes; la anulación requiere motivo. Los límites exactos siguen los roles actuales del sistema.
- El PDF conjunto usa el formato media carta y el estilo de marca actuales, una receta por página.
- La guía visual de la imagen se respeta en organización y acentos, pero se corrige la incoherencia de mostrar una refracción pendiente junto a recetas emitidas: una receta de anteojos solo puede emitirse desde una refracción final validada.
