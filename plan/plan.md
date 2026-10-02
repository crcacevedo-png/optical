# Refracciones en la consulta: captura y receta imprimible

En la pantalla de consulta, la persona registra una o varias refracciones justo después del plan de tratamiento y, con un clic, convierte cualquiera de ellas en una receta imprimible de anteojos o de lentes de contacto.
La receta queda guardada en el historial del paciente y se descarga lista para entregar o imprimir, con el logo y la plantilla de la óptica.

## Para quién es
- Optómetras y profesionales de salud visual que atienden la consulta y entregan la graduación al paciente.
- Staff de la óptica que imprime o comparte la receta al final de la atención.

## Funcionalidad principal y experiencia
- **Área de refracción reubicada:** aparece después de "Plan / Tratamiento" dentro de la consulta (hoy está antes del diagnóstico).
- **Varias refracciones:** se puede agregar y quitar más de una refracción (por ejemplo, la refracción final y una comparativa). Cada refracción tiene, por ojo (OD / OS): Esfera, Cilindro, Eje, Adición y una nota.
- **Imprimir como receta, por refracción:** cada refracción muestra dos acciones claras: "Imprimir como anteojos" e "Imprimir como lentes de contacto".
- **Paso rápido para completar:** al elegir una opción se abre una ventana con los valores ya precargados desde esa refracción. La persona completa solo lo que la refracción no incluye:
  - Anteojos: D.P. (distancia pupilar) y, opcionalmente, tipo de lente y armazón.
  - Lentes de contacto: curva base, diámetro, marca y tipo de reemplazo.
  - En ambos casos, un campo de observaciones.
- **Guardar + imprimir:** al confirmar, la receta se guarda en el historial de recetas del paciente y se genera el PDF (media carta, con logo y plantilla de la óptica) para descargar o imprimir. Puede reimprimirse después.
- **Funciona desde el formulario**, aun sin haber guardado la consulta. Solo requiere que haya un paciente seleccionado.

## Flujo del usuario
1. En la consulta, después de llenar "Plan / Tratamiento", la persona registra una o más refracciones.
2. Para una refracción, elige "Imprimir como anteojos" o "Imprimir como lentes de contacto".
3. Se abre el paso rápido con los datos precargados; completa los campos específicos del tipo de receta y confirma.
4. La receta se guarda en el historial del paciente y se abre el PDF listo para imprimir o compartir.
5. Puede repetir con otra refracción, o imprimir la misma refracción también como el otro tipo de receta.

## Sensación UI/UX
- Coherente con la consulta actual: estética sobria y profesional, OD en azul y OS en verde, rejilla clara por ojo.
- Acciones de impresión evidentes en cada refracción; la ventana para completar datos es breve y enfocada.
- El PDF conserva la identidad de la óptica (logo, encabezado, plantilla) ya existente.

## Fases de implementación

**Fase 1 — MVP (se construye ahora)**
- Reubicar el área de refracción para que aparezca después de "Plan / Tratamiento".
- Conservar el registro de varias refracciones (agregar/quitar).
- En cada refracción, acciones "Imprimir como anteojos" e "Imprimir como lentes de contacto".
- Paso rápido precargado para completar los datos específicos de cada tipo de receta.
- Guardar la receta en el historial del paciente y generar el PDF para imprimir.
- Que funcione desde el formulario, con solo tener un paciente seleccionado.

**Fase 2 — Más adelante**
- Elegir cualquiera de las refracciones desde la vista de la consulta ya guardada y reimprimir.
- Mostrar, junto a cada receta ya generada dentro de la consulta, un botón visible para descargar/imprimir su PDF.
- Enviar la receta al paciente por WhatsApp o correo.

**Fase 3 — Futuro**
- Comparar refracciones lado a lado y marcar una como "final".
- Copiar automáticamente la lensometría o la agudeza visual a una refracción nueva.
- Plantillas de receta adicionales.

## Suposiciones (decisiones tomadas sin volver a preguntar)
- La refracción mantiene sus campos actuales (OD/OS: Esfera, Cilindro, Eje, Adición + nota). Para lentes de contacto, el "poder" se toma de la esfera y el resto se completa en el paso rápido.
- El área de refracción se coloca después del bloque "Plan / Tratamiento" y "Recomendaciones", antes de "Observaciones".
- Al imprimir desde una consulta nueva aún sin guardar, la receta se guarda bajo el paciente y queda vinculada a la consulta cuando esta ya existe (consulta guardada o en edición).
- Se requiere un paciente seleccionado para imprimir; si no hay, se muestra un aviso.
- Se reutiliza el sistema actual de recetas de anteojos y de lentes de contacto y su PDF (plantilla, logo, tamaño media carta); no se crea un formato de receta nuevo.
- Se mantienen también los botones actuales de la consulta para generar recetas; las nuevas acciones por refracción se suman a lo existente.
- El PDF se descarga/abre para imprimir; no hay impresión automática silenciosa.
- Idioma español. La receta médica no cambia.
