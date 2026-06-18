# Onboarding — Cortexia Optical

Guía paso a paso para incorporar una nueva óptica a la plataforma y dejarla operando productivamente. Está dividida en dos perspectivas: la del **SuperAdmin** (quien crea la óptica) y la del **Administrador de la óptica** (quien la opera).

---

## 1. Visión General del Flujo

```
┌──────────────────┐     ┌────────────────────┐     ┌─────────────────────┐
│  SuperAdmin crea │ ──> │ Email de bienvenida│ ──> │  Admin entra y      │
│  la óptica       │     │ automático (Resend)│     │  configura          │
└──────────────────┘     └────────────────────┘     └─────────────────────┘
                                                              │
                                                              ▼
                              ┌──────────────────────────────────────────┐
                              │  1. Datos de la óptica  2. Sucursales     │
                              │  3. Equipo de usuarios  4. Inventario    │
                              │  5. Primeros pacientes 6. Primera venta  │
                              └──────────────────────────────────────────┘
```

**Tiempo estimado**: 30-45 minutos hasta dejar la óptica operativa.

---

## 2. Onboarding del SuperAdmin (rol Cortexia)

### Paso 1 — Crear la nueva óptica

1. Accede como SuperAdmin a `https://cortexiaoptical.com`
2. Ve a **Administración → Ópticas** (`/admin/opticas`)
3. Clic en **"Nueva óptica"**
4. Completa el formulario:
   - **Nombre comercial** (ej: "Óptica Visión Clara")
   - **Razón social y NIT** (Guatemala)
   - **Dirección, teléfono y email** de la óptica
   - **Datos del administrador inicial**:
     - Nombre del admin (ej: "Dra. María González")
     - Email del admin (será su usuario de acceso)
     - Contraseña inicial (mínimo 8 caracteres, 1 mayúscula, 1 minúscula, 1 dígito)
   - **Plan de suscripción** (Free / Basic / Enterprise)
5. Clic en **"Crear óptica"**

**Qué pasa automáticamente:**
- Se crea la empresa con su `company_id`
- Se crea el usuario admin con `role: admin` ligado al `company_id`
- **Se envía un email de bienvenida** al admin (vía Resend) con:
  - Confirmación de su óptica registrada
  - Sus credenciales de acceso
  - Link al login
  - Guía de primeros pasos (5 pasos sugeridos)
- Se registra el evento `USER_CREATED` y la creación de empresa en el audit log

### Paso 2 — Validar acceso del admin

- Recomienda al admin verificar su inbox (y carpeta de **spam/promociones**)
- Asegúrate que pueda hacer login en `https://cortexiaoptical.com/login`
- Si el email no llegó, puedes resetear la contraseña desde **Administración → Usuarios**

---

## 3. Onboarding del Administrador de la Óptica

### Paso 1 — Primer ingreso

1. Recibe el email **"Bienvenido a Cortexia Optical - [Tu Óptica]"**
2. Clic en **"Ingresar a Cortexia"**
3. Login con el email y contraseña proporcionados
4. **Recomendación de seguridad**: cambia tu contraseña en tu primer ingreso
   - Menú superior derecho → ícono de usuario → **"Cambiar mi contraseña"**

### Paso 2 — Configurar datos de la óptica

Ve a **Configuración** (`/settings`) y completa:

1. **Datos generales**:
   - Logo de la óptica (sube imagen PNG/JPG)
   - Dirección completa, teléfono, email de contacto
   - Razón social y NIT (aparecerá en recetas y facturas)
2. **Estilos de receta** (opcional):
   - Colores y fuentes del PDF de recetas oftálmicas
   - Colores y fuentes del PDF de recetas médicas
3. **Guardar**

### Paso 3 — Crear sucursales (si tienes más de una)

1. Ve a **Sucursales** (`/branches`)
2. Clic en **"Nueva sucursal"**
3. Por cada sucursal completa: nombre, dirección, teléfono, email
4. Cada usuario que crees podrá ser asignado a una sucursal específica

> **Nota**: El plan Free permite 1 sucursal, Basic hasta 3, Enterprise sin límite.

### Paso 4 — Dar de alta al equipo

1. Ve a **Usuarios** (`/users`)
2. Clic en **"Nuevo usuario"** y crea uno por cada miembro del equipo:
   - **Admin**: gestión completa (vendedores + inventario + finanzas + recetas)
   - **Vendedor**: ventas, pacientes, inventario, cotizaciones (sin acceso a finanzas)
3. Cada usuario recibe sus credenciales del admin (no se envía email automático por defecto)

### Paso 5 — Cargar inventario inicial

1. Ve a **Inventario** (`/inventory`)
2. Crea los productos:
   - Monturas, lentes, accesorios
   - SKU, marca, categoría
   - Precio costo y precio de venta
   - Stock mínimo (alerta automática cuando se acerque al límite)
3. Asigna stock inicial por sucursal en cada producto

### Paso 6 — Registrar primer paciente

1. Ve a **Pacientes** (`/patients`)
2. Clic en **"Nuevo paciente"**
3. Completa: nombre, DPI, fecha nacimiento, teléfono, WhatsApp, email
4. Guarda

### Paso 7 — Realizar primera venta

1. Ve a **Ventas** (`/sales`) → **Nueva venta**
2. Selecciona paciente, sucursal, vendedor
3. Agrega productos del inventario
4. Aplica descuentos si corresponde
5. Selecciona método de pago
6. Confirma → se genera el comprobante automáticamente

---

## 4. Flujos Complementarios

### Restablecer contraseña (cualquier usuario)

1. En el login, clic en **"¿Olvidaste tu contraseña?"**
2. Ingresa tu email
3. Recibe un enlace por email (expira en **1 hora**)
4. Clic en el enlace → define nueva contraseña (mínimo 8 chars, mayúscula, minúscula, dígito)
5. Login con la nueva contraseña

### Descargar respaldo de tu base de datos

1. Ve a **Configuración → Exportación de Base de Datos**
2. Clic en **"Descargar Base de Datos (Excel)"**
3. Se descarga un `.xlsx` con 16 hojas: pacientes, citas, consultas, recetas, ventas, inventario, finanzas, etc.

### Ver el audit log (solo SuperAdmin)

1. Ve a **Auditoría** (`/admin/audit`)
2. Consulta todos los eventos críticos: logins, cambios de contraseña, eliminación de usuarios, cambios de rol, exportaciones, etc.
3. Filtra por tipo de evento o por email

### Recibir alertas de seguridad

Se envían automáticamente por email cuando:
- Hay **3+ intentos fallidos** de login en tu cuenta (con IP origen)
- Tu contraseña fue **cambiada** (notificación al titular)
- Tu contraseña fue **restablecida** vía email (confirmación)

---

## 5. Checklist Final del Onboarding

Al terminar, el admin debe tener:

- [ ] Login funcional con su email
- [ ] Contraseña cambiada (no la inicial)
- [ ] Datos de la óptica configurados (logo, dirección, NIT)
- [ ] Al menos 1 sucursal creada
- [ ] Al menos 1 usuario adicional creado (vendedor)
- [ ] Al menos 10 productos en inventario
- [ ] Al menos 1 paciente registrado
- [ ] Al menos 1 venta de prueba ejecutada
- [ ] Descarga de respaldo Excel completada para verificar datos

---

## 6. Soporte

- **Email general**: info@cortexiagt.com
- **Reportes de seguridad**: info@cortexiagt.com
- **Documentación adicional**: ver `/app/memory/PRD.md` para detalles técnicos

---

_Versión del documento: 1.0 — Junio 2026_
