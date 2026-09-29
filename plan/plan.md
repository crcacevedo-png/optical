# Autoservicio de registro — Plan Básico (Cortexia Optical)

Permite que un interesado se inscriba solo desde la web, verifique su correo y entre de inmediato a usar el Plan Básico, sin esperar aprobación manual. La meta es eliminar la fricción inicial: de "solicitar y esperar" a "crear cuenta y empezar hoy".

## Para quién es
- Dueños o administradores de ópticas en Latinoamérica que quieren probar Cortexia sin trámites ni contacto previo con ventas.
- El Superadmin, que deja de crear cuentas Básicas a mano y solo atiende solicitudes de planes superiores.

## Funcionalidad principal y experiencia
- **Registro público en una pantalla** (reemplaza el formulario actual de solicitud en `/registro`): la persona ingresa nombre del responsable, nombre de la óptica, correo, contraseña, WhatsApp, ciudad/país, código promocional (opcional) y acepta el consentimiento.
- **Verificación de correo obligatoria**: al enviar el formulario se manda un correo con un enlace seguro. La cuenta se crea y se activa recién cuando la persona hace clic en ese enlace. Hasta entonces no puede entrar. Incluye botón para reenviar el correo.
- **Provisión 100% automática**: al verificar, el sistema crea sola la óptica (empresa) y al usuario como Admin, le asigna el Plan Básico y lo deja listo para iniciar sesión. Sin intervención del Superadmin.
- **Plan Básico gratuito hasta 50 pacientes**: la cuenta funciona sin costo mientras no supere los 50 pacientes activos.
- **Al llegar al límite, "flujo normal"**: cuando la óptica alcanza su tope de pacientes, el sistema le impide agregar más y le muestra un aviso claro para actualizar de plan y pagar por Stripe (esto ya existe en la app y se reutiliza).
- **Código promocional con beneficio (límite de pacientes ampliado)**: los códigos ya existen hoy en el área de Solicitudes de cuenta del Superadmin. El beneficio **no es monetario**: es un **límite de pacientes ampliado en el plan gratis**. Cada código tiene un límite de pacientes que el **Superadmin puede modificar en el área de códigos**. Si la persona ingresa un código válido durante el registro, su cuenta arranca con ese tope gratuito (por ejemplo 200 pacientes en lugar de 50). Un código sin límite configurado queda registrado para atribución de campaña y usa el tope por defecto (50), como hoy.
- **Planes superiores siguen por solicitud**: quien necesite un plan mayor verá un enlace tipo "¿Necesitas un plan superior? Contáctanos" que abre el formulario de solicitud actual y sigue llegando al CRM del Superadmin.

## Flujo del usuario
1. Desde tu sitio de marketing (`web.cortexiaoptical.com`) hace clic en "Crear cuenta gratis", que lo lleva a la página de registro de la app (`www.cortexiaoptical.com/registro`).
2. Llena el formulario de registro (incluye contraseña propia y, si tiene, código promocional) y acepta el consentimiento.
3. Recibe un correo de verificación y hace clic en el enlace.
4. El sistema crea su óptica y su usuario Admin con Plan Básico y lo lleva a iniciar sesión.
5. Entra y empieza a cargar pacientes, inventario y ventas de inmediato.
6. Al acercarse/llegar a 50 pacientes (o al tope ampliado por su código), ve el aviso para actualizar de plan y pagar por Stripe.

## Sensación UI/UX
- Coherente con la identidad actual de Cortexia (azul profundo profesional, estética limpia y sobria de la app).
- Registro de mínima fricción: una sola pantalla, campos claros, validación en vivo, mensajes de error entendibles y señales de confianza ("sin tarjeta", "empieza gratis hasta 50 pacientes").
- Estados explícitos: "revisa tu correo para verificar", "correo verificado, ya puedes entrar", "límite alcanzado, actualiza tu plan".

## Conexión con el sitio web
- **Sitio de marketing:** `web.cortexiaoptical.com` (WordPress u otra plataforma), separado y sin cambios.
- **App Cortexia (producción):** `www.cortexiaoptical.com`, con su propia dirección. No hay conflicto: marketing en `web.` y app en `www.`.
- La conexión es por **enlace**: en tu sitio de marketing (`web.cortexiaoptical.com`) agregas un botón "Crear cuenta gratis" que apunta a `https://www.cortexiaoptical.com/registro`. Ese botón lo configuras tú con tus accesos a la web; del lado de la app yo construyo la página de registro.
- Los enlaces del correo de verificación se arman desde la variable `APP_URL`, fijada a `https://www.cortexiaoptical.com`, para que apunten a la app y no al sitio de marketing.

## Fases de implementación
**Fase 1 — MVP (se construye ahora)**
- Nueva pantalla de autoservicio en `/registro` (reemplaza el formulario de solicitud para el Plan Básico).
- Verificación de correo por enlace seguro con expiración y reenvío.
- Provisión automática de óptica + Admin con Plan Básico al verificar.
- Nuevo campo "límite de pacientes" en cada código promocional, editable por el Superadmin en el área de códigos existente (Solicitudes de cuenta).
- Aplicación del límite ampliado del código al registrarse: la cuenta arranca con el tope del código en lugar de 50.
- Aviso/upsell al alcanzar el límite gratuito, reutilizando el control de pacientes y el pago existente por Stripe.
- Enlace "Contáctanos" hacia el formulario de solicitud actual para planes superiores.

**Fase 2 — Más adelante**
- Tope gratuito configurable por plan (no fijo en 50).
- Panel del Superadmin para ver registros por autoservicio, estados de verificación y expiraciones.
- Onboarding de bienvenida más guiado tras el primer ingreso.

**Fase 3 — Futuro**
- Página pública de marketing con tabla de precios y botón por plan.
- Correos de seguimiento a registros abandonados (no verificados).
- Analítica del embudo de registro (visitas → registros → verificados → activos).

## Suposiciones (decisiones tomadas sin preguntar)
- El autoservicio **reemplaza** el formulario de solicitud en la ruta pública `/registro` para el Plan Básico; el formulario/CRM actual se conserva solo para planes superiores, accesible desde un enlace "Contáctanos".
- La persona **define su propia contraseña** durante el registro (no se envía contraseña temporal). El correo de verificación solo confirma el correo y activa la cuenta.
- La cuenta y la empresa se **crean al hacer clic en el enlace de verificación** (no antes); el enlace expira a las 48 horas y puede reenviarse.
- El Plan Básico es el plan marcado como predeterminado de autoservicio; si no hay uno marcado, se usa el plan gratuito con tope de 50 pacientes; en su defecto, el plan más económico.
- El tope gratuito por defecto es **50 pacientes activos** (coincide con el valor por defecto actual del sistema).
- El beneficio del código promocional es **exclusivamente un límite de pacientes ampliado en el plan gratis** (no monetario). El número lo configura y edita el Superadmin en el área de códigos ya existente. Se aplica sobre la nueva cuenta como límite efectivo de pacientes al registrarse.
- Se mantiene el consentimiento obligatorio y las protecciones anti-spam (honeypot + límite de intentos) del formulario actual.
- La verificación de correo usa el servicio de correo ya integrado (Resend); no se requiere una integración nueva.
- Las operaciones de la óptica siguen en GTQ; los cobros de membresía siguen en USD por Stripe, sin cambios.
- La app vive en `www.cortexiaoptical.com` y el sitio de marketing en `web.cortexiaoptical.com`; son dominios distintos, sin conflicto. `APP_URL` se fija a `https://www.cortexiaoptical.com` para los enlaces de la app y del correo de verificación.
- El botón "Crear cuenta gratis" en el sitio de marketing lo agregas tú (WordPress/plataforma actual); del lado de la app solo se entrega la ruta pública de registro (`/registro`) a la que enlazar.
