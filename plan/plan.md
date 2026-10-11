# Ingreso Masivo de Pacientes (Importación desde Excel/CSV)

Una herramienta para que el administrador de la óptica cargue muchos pacientes de una sola vez desde una hoja de cálculo, en lugar de registrarlos uno por uno.
Incluye descargar una plantilla, subir el archivo, ver una vista previa y recibir un reporte claro de qué se creó, qué se actualizó y qué falló.

## Para quién es
Administradores de óptica que están empezando con Cortexia o que migran desde papel, Excel propio u otro sistema, y necesitan cargar su base de pacientes (y su historial básico de recetas) rápidamente.

## Funcionalidad y experiencia principal
- **Plantilla descargable** (Excel y CSV) con las columnas correctas y una fila de ejemplo, para que el administrador sepa exactamente cómo llenar sus datos.
- **Carga de archivo** en formato Excel (.xlsx) o CSV, desde el menú de Configuración.
- **Vista previa** antes de confirmar: cuántas filas se detectaron y una muestra de los primeros registros.
- **Columnas de paciente**: Nombre completo (obligatorio), Teléfono (obligatorio), WhatsApp, Correo electrónico, Fecha de nacimiento, Sexo y Dirección.
- **Historial de receta de anteojos / evaluación** (opcional, por fila): graduación OD y OS (Esfera, Cilindro, Eje, Adición) y una nota de observaciones. Si estas columnas vienen llenas, se guarda una receta de anteojos ligada a ese paciente como su historial inicial.
- **Pacientes repetidos**: si un paciente del archivo ya existe en la óptica (mismo correo o, en su defecto, mismo teléfono), se **actualizan sus datos** con la información del archivo en lugar de duplicarlo.
- **Tope de pacientes**: en cuentas con límite (plan gratis o código promocional), se importan pacientes nuevos **hasta llenar el tope disponible** y se informa cuántos quedaron fuera. Las actualizaciones a pacientes existentes no consumen cupo.
- **Manejo de errores por fila**: las filas válidas se importan igual; las que tienen datos faltantes o mal formados se omiten y se listan con el motivo, para corregirlas y volver a subir solo esas.
- **Reporte final**: resumen con cantidades de creados, actualizados, omitidos por tope y con error (incluyendo el detalle fila por fila).

## Flujo del usuario
1. El administrador entra a **Configuración** y abre la tarjeta **Ingreso masivo de pacientes**.
2. Descarga la **plantilla** (Excel o CSV) y la llena con sus pacientes.
3. Sube el archivo; el sistema muestra una **vista previa** con el total de filas detectadas y una muestra.
4. Confirma la importación.
5. Ve el **reporte**: creados, actualizados, omitidos por tope y filas con error (con el motivo de cada una).
6. Si hubo errores o pacientes fuera de tope, corrige su archivo y repite el proceso solo con esos.

## Estética y sensación (UI/UX)
Consistente con la pantalla de Configuración actual de Cortexia: tarjeta limpia con acento verde (pine), íconos de hoja de cálculo/subida, zona de "arrastrar o hacer clic" para el archivo, tabla de vista previa compacta y un resumen final con contadores de colores (verde = creados, azul = actualizados, ámbar = fuera de tope, rojo = errores). Visible únicamente para el rol administrador.

## Fases de implementación

**Fase 1 — MVP (se construye ahora)**
- Tarjeta "Ingreso masivo de pacientes" en el menú de Configuración (solo administrador).
- Plantilla descargable en Excel y CSV con columnas de paciente + columnas opcionales de receta de anteojos/evaluación.
- Carga de archivo Excel/CSV con vista previa y confirmación.
- Validación por fila (nombre y teléfono obligatorios; formatos de fecha/graduación).
- Crear pacientes nuevos y actualizar los existentes por coincidencia (correo, luego teléfono).
- Respetar el tope de pacientes: importar hasta el cupo disponible y avisar del resto.
- Crear una receta de anteojos por fila cuando vengan las columnas de graduación.
- Reporte final: creados, actualizados, omitidos por tope, y errores con motivo por fila.

**Fase 2 — Historial ampliado y flexibilidad**
- Varias recetas/evaluaciones por paciente (más de una fila de historial por persona).
- Importación de recetas de lentes de contacto y de evaluaciones de consulta completas.
- Mapeo manual de columnas para archivos que no usen la plantilla.
- Bitácora de importaciones (historial de cargas realizadas).

**Fase 3 — Automatización y control**
- Revisión de duplicados antes de confirmar (elegir fila por fila qué actualizar).
- Deshacer la última importación.
- Importaciones programadas/recurrentes desde un archivo recurrente.

## Supuestos
- **Nombre completo**: se usa una sola columna "Nombre completo"; el sistema separa el primer término como nombre y el resto como apellidos (el modelo de paciente guarda nombre y apellidos por separado).
- **Teléfono obligatorio**: por consistencia con el registro manual actual, cada fila debe tener teléfono; WhatsApp es opcional y, si se omite, se usa el teléfono.
- **Detección de repetidos**: se hace dentro de la misma óptica, por correo electrónico y, si no hay correo, por teléfono (no se incluye columna de documento/DPI porque no fue seleccionada).
- **Historial en el MVP**: cada fila puede traer **una** receta de anteojos (graduación OD/OS + observaciones). El historial con múltiples recetas por paciente y las recetas de lentes de contacto/medicamentos quedan para la Fase 2.
- **Formato de datos**: fechas en formato AAAA-MM-DD, sexo como M/F, y graduaciones numéricas (se acepta "plano"/"pl" como 0.00).
- **Límite de tamaño**: el archivo tendrá un tope razonable de filas/peso por carga (similar a la importación de inventario existente) para proteger el rendimiento.
- **Permisos**: la función es exclusiva del rol administrador de cada óptica.
- **Aislamiento multiempresa**: todos los pacientes importados quedan ligados a la óptica y sucursal del administrador que realiza la carga.
