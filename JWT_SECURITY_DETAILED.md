# Guía Completa: Seguridad JWT para Portales Desacoplados

Una explicación profunda sobre cómo proteger autenticación entre dos portales independientes.

---

## El Problema que Resolvemos

Tienes:
- **Portal A (Django)**: Sistema central con autenticación, base de datos de usuarios, gestión de tenants
- **Portal B (Next.js)**: Aplicación frontend completamente independiente

Ambos están en **dominios distintos** (ejemplo: `portal-a.com` y `portal-b.com`).

### Desafíos específicos:

1. **Seguridad**: Los hackers buscan robar credenciales. ¿Cómo guardamos tokens sin exponerlos?

2. **Entre dominios**: Las cookies de `portal-a.com` NO se envían automáticamente a `portal-b.com` (política de seguridad del navegador)

3. **Experiencia de usuario**: Si el usuario presiona F5, ¿pierde su sesión?

4. **Independencia**: Si Portal A falla, ¿Portal B sigue funcionando?

---

## Opciones de Almacenamiento de Tokens

Existen 5 formas principales de guardar un JWT en el navegador. Cada una tiene tradeoffs.

### Opción 1: localStorage

**¿Qué es?**

Un almacén de texto simple en el navegador que persiste entre sesiones. Es como guardar un archivo de texto en la computadora del usuario.

```javascript
localStorage.setItem('token', 'eyJ0eXAi...');
const token = localStorage.getItem('token');
```

**Ventajas:**
- ✅ Súper simple de implementar
- ✅ Funciona perfecto entre dominios
- ✅ El usuario no pierde sesión al refrescar
- ✅ Sin configuración de servidor especial

**Desventajas:**
- ❌ **Vulnerable a XSS (Cross-Site Scripting)**
  - Si un atacante inyecta JavaScript en tu página, puede leer localStorage
  - Ejemplo: `const token = localStorage.getItem('token')`
  - El atacante puede enviar el token a su servidor malicioso
  
**¿Cuándo es válido usar localStorage?**

Solo si:
1. Tu equipo tiene prácticas de seguridad muy fuertes (sanitización de inputs)
2. Actualizas librerías regularmente (muchas vulnerabilidades XSS vienen de librerías)
3. Implementas Content Security Policy (CSP) fuerte
4. No tienes datos ultra-sensibles (no son credenciales de banco)

Para un MVP rápido o aplicación interna sin datos sensibles, localStorage es pragmático.

---

### Opción 2: sessionStorage

**¿Qué es?**

Como localStorage, pero se borra cuando cierras la pestaña/navegador.

```javascript
sessionStorage.setItem('token', 'eyJ0eXAi...');
```

**Ventajas:**
- ✅ Igual de simple que localStorage
- ✅ Se borra solo automáticamente
- ✅ Funciona entre dominios

**Desventajas:**
- ❌ Sigue siendo vulnerable a XSS (igual que localStorage)
- ❌ Mala experiencia: Usuario presiona F5 → Pierde sesión
- ❌ Si tiene múltiples pestañas abiertas, cada una pierde su sesión al cerrar

**¿Cuándo usar sessionStorage?**

Casi nunca. Es lo peor de ambos mundos: inseguro Y inconveniente.

Único caso: Kioscos públicos donde quieres que cada usuario "empiece de cero".

---

### Opción 3: HttpOnly Cookie

**¿Qué es?**

Una cookie con la bandera `httponly=True`. Le dice al navegador: "Esta cookie es solo para HTTP, JavaScript no puede leerla".

```python
# Django
response.set_cookie('token', token, httponly=True)
```

**¿Cómo funciona?**

1. Django establece: `Set-Cookie: token=eyJ0eXA...; HttpOnly; Secure; SameSite=Strict`
2. Navegador almacena la cookie
3. JavaScript intenta: `const token = document.cookie` → ❌ Retorna vacío (no ve HttpOnly cookies)
4. Cuando el navegador hace una petición HTTP a Django, automáticamente envía la cookie

**Ventajas:**
- ✅ **Máxima protección contra XSS**: JavaScript no puede leerla
- ✅ Envío automático: No necesitas código JS para enviarla
- ✅ Estándar de la industria: Google, Facebook, Amazon lo usan

**Desventajas (CRÍTICA para tu caso):**
- ❌ **NO funciona entre dominios**
  - Django establece cookie para `portal-a.com`
  - Next.js en `portal-b.com` hace request a Django
  - Navegador dice: "Esta cookie es de otro dominio, NO la envío"
  - Request falla sin autenticación

Es una política de seguridad fundamental del navegador (Same Origin Policy). Es imposible evitarlo.

**¿Cuándo usar HttpOnly?**

Solo cuando API y frontend están en el **MISMO dominio**:
- `portal-a.com/api/` (Django)
- `portal-a.com/app/` (Next.js renderizado)

O cuando Django renderiza las páginas (server-side rendering).

Para tu caso con dominios distintos, **no funciona**.

---

### Opción 4: Memoria (Variable JavaScript)

**¿Qué es?**

Guardar el token en una variable JavaScript normal, que existe solo mientras la página está abierta.

```javascript
let accessToken = null;

function login(token) {
  accessToken = token;  // Guardado en memoria
}

function getToken() {
  return accessToken;  // Recuperar
}
```

**Ventajas:**
- ✅ **Muy seguro contra XSS**: No está en storage, la variable es local
- ✅ Funciona entre dominios
- ✅ Limpio: No contamina localStorage ni cookies

**Desventajas:**
- ❌ **Se pierde cuando refrescas la página**
  - Usuario presiona F5 → Variable se reinicia → Token se pierde
  - Siguiente petición falla sin autenticación
  - Usuario debe re-hacer login
  
- ❌ Se pierde al cambiar de pestaña
- ❌ Mala experiencia de usuario

**¿Cuándo usar memoria pura?**

Casi nunca en aplicaciones web modernas. Los usuarios esperan que su sesión persista al refrescar.

Podría tener sentido en operaciones financieras críticas donde cada acción es única y el usuario acepta re-autentificarse.

---

### Opción 5: Híbrida (RECOMENDADA)

**La idea central:**

No almacena TODO en un solo lugar. Separa:

1. **Access Token** (lo que necesitas ahora)
   - Dura 15 minutos
   - Se guarda en MEMORIA (variable JavaScript)
   - Se usa para hacer requests a la API

2. **Refresh Token** (para renovar)
   - Dura 7 días
   - Se guarda en HttpOnly cookie
   - No es accesible desde JavaScript
   - SOLO se usa para obtener nuevos access tokens

**¿Por qué funciona?**

Combina las ventajas de cada una:

```
Opción 1 (localStorage):
- Pro: Funciona entre dominios, persiste al refrescar
- Contra: Vulnerable a XSS por 7 días

Opción 5 (Híbrida):
- Pro: Funciona entre dominios
- Pro: Persiste al refrescar (el refresh token renueva automáticamente)
- Pro: Vulnerable a XSS solo 15 minutos (access expira rápido)
- Pro: Refresh token NO se puede robar (está en HttpOnly)
```

**Flujos principales:**

1. **Primer login:**
   - Usuario ingresa usuario/contraseña
   - Django devuelve:
     - Access token en JSON (15 min) → Se guarda en memoria
     - Refresh token en HttpOnly cookie → Se guarda automáticamente
   - Usuario redirecciona a dashboard

2. **Usuario navega normalmente:**
   - Hace clic en "Ver datos"
   - Código obtiene el access token de memoria
   - Envía: `Authorization: Bearer [token]`
   - Django valida y devuelve datos
   - Usuario ni se da cuenta

3. **Usuario presiona F5:**
   - JavaScript se reinicia, access token desaparece
   - Portal B detecta: "No tengo token, necesito refrescar"
   - Envía el refresh token (en la cookie)
   - Django devuelve nuevo access token
   - Todo es transparente, usuario no ve popup

4. **Access token está a punto de expirar:**
   - Cada X segundos, Portal B chequea
   - Si va a expirar en menos de 1 minuto, renueva automáticamente
   - Sin que el usuario haga nada

5. **Atacante intenta robar:**
   - XSS intenta leer localStorage → Vacío (el token está en memoria)
   - XSS intenta leer documento.cookie → HttpOnly (no accesible)
   - XSS podría hace requests, pero token expira en 15 minutos
   - Comparado con localStorage (7 días), la ventana es MUCHO más pequeña

**Ventajas:**
- ✅ Funciona entre dominios
- ✅ Usuario no pierde sesión al refrescar
- ✅ Seguro contra XSS (access en memoria, refresh en HttpOnly)
- ✅ Renovación transparente
- ✅ Escalable a múltiples portales
- ✅ Sigue funcionando si Portal A falla (datos en caché)

**Desventajas:**
- ⚠️ Implementación más compleja que localStorage
- ⚠️ Requiere CORS bien configurado
- ⚠️ Más código en el frontend

---

## Tabla Comparativa Final

| Aspecto | localStorage | sessionStorage | HttpOnly | Memoria | Híbrida |
|---------|--------------|---|---------|---------|---------|
| **Seguridad XSS** | ❌ Muy vulnerable | ❌ Muy vulnerable | ✅ Seguro | ✅ Seguro | ✅ Muy seguro |
| **Entre dominios** | ✅ Funciona | ✅ Funciona | ❌ NO funciona | ✅ Funciona | ✅ Funciona |
| **Persiste refresh** | ✅ Automático | ❌ Se pierde | ✅ Automático | ❌ Se pierde | ✅ Automático |
| **Experiencia UX** | ✅ Perfecta | ❌ Mala | ✅ Perfecta | ❌ Mala | ✅ Perfecta |
| **Complejidad** | Muy baja | Muy baja | Baja | Baja-Media | Media |
| **Recomendado para** | MVPs rápidos | Nunca | Mismo dominio | Altísima seguridad | Tu caso ✅ |

---

## ¿Cuál elegir?

### Para tu caso específico:

**Recomendación: Opción 5 - Híbrida**

Por qué:
1. ✅ Datos sensibles (credenciales de usuarios)
2. ✅ Dos dominios distintos (localStorage sería vulnerable, HttpOnly no funciona)
3. ✅ UX moderna (usuario no pierde sesión)
4. ✅ Escalable (podrías agregar más portales)
5. ✅ Regulación (GDPR, CCPA: tokens sensibles no persisten sin cifrar)

### Si insisten en "algo más simple":

Usa localStorage CON protecciones muy fuertes:

1. **Content Security Policy (CSP)**: Bloquea inyección de scripts
2. **Sanitización**: Valida TODO input de usuario con DOMPurify
3. **Rate limiting**: Máx 5 intentos de login por IP por minuto
4. **HTTPS obligatorio**: No servir HTTP nunca
5. **CORS estricto**: Solo portales autorizados
6. **Validación backend**: Nunca confíes en el cliente

Pero: localStorage seguirá siendo vulnerable si hay XSS que no se detecta.

---

## Consideraciones de Seguridad

### XSS (Cross-Site Scripting)

XSS es cuando un atacante inyecta JavaScript en tu aplicación. Hay dos tipos:

**Stored XSS:**
```
1. Atacante comenta en tu sitio: "<script>robar token</script>"
2. Comentario se guarda en BD sin validar
3. Otro usuario ve el comentario → JavaScript se ejecuta
4. Token se roba
```

**Reflected XSS:**
```
1. Atacante envía link: "portal-b.com?q=<script>robar</script>"
2. Tu app muestra la búsqueda sin sanitizar
3. JavaScript se ejecuta
4. Token se roba
```

**Cómo se mitiga:**

1. **Sanitización**: Valida todo input de usuario
2. **Content Security Policy**: Bloquea scripts maliciosos
3. **Actualización de librerías**: Muchas XSS vienen de librerías viejas

**Cómo afecta cada opción:**

```
localStorage: XSS → const token = localStorage.getItem('token') → ROBO
             Ventana: 7 días

Híbrida (access en memoria): XSS → const token = window.accessToken → FAIL
                                    localStorage no tiene token
                                    HttpOnly no es accesible desde JS
                             Ventana: 0 (no puede robar)
                             
                             XSS → fetch('/api/transfer') → Funciona pero...
                                    Tokenexpira en 15 min, entonces queda bloqueado
                             Ventana: 15 minutos
```

### CSRF (Cross-Site Request Forgery)

CSRF es cuando un atacante hace que TU navegador haga requests sin tu permiso.

```
1. Abres http://evil.com
2. evil.com tiene:
   <img src="https://banco.com/transfer?amount=1000&account=attacker" />
3. Tu navegador automáticamente hace ese GET (porque estás logged en)
4. Se transfiere dinero

Defensa:
- CORS: evil.com NO puede hacer fetch() directo a banco.com
- SameSite: Cookies no se envían a evil.com
- CSRF token: Token adicional que evil.com no conoce
```

La Opción Híbrida maneja todo esto con CORS + SameSite.

---

## Flujo de Seguridad Detallado (Opción Híbrida)

### Primer acceso (Usuario no autenticado)

```
Usuario abre portal-b.com

↓

Página no tiene token (memoria vacía, no hay cookie)

↓

Detecta: "Usuario no autenticado"

↓

Redirige a /login
```

### Proceso de login

```
Usuario ingresa usuario/contraseña

↓

Portal B hace: POST portal-a.com/api/auth/login/
{
  "username": "usuario@example.com",
  "password": "password123"
}

↓

Portal A:
1. Verifica usuario en BD (TenantUser)
2. Verifica contraseña
3. Si es válido, devuelve:
   - access_token: "eyJ0eXA..." (válido 15 min)
   - access_token: "eyJ0eXA..." (válido 7 días)

↓

Response:
{
  "access": "eyJ0eXAi...",
  "user": {
    "id": 1,
    "username": "usuario@example.com",
    "tenant": {"id": 5, "name": "Empresa X"}
  }
}
Set-Cookie: refresh_token=eyJ0eXAi...; HttpOnly; Secure; SameSite=Lax

↓

Portal B:
1. Recibe access token en JSON
2. Guarda en variable en memoria: `accessToken = "eyJ0eXAi..."`
3. Cookie se guarda automáticamente en el navegador
4. Guarda user info en localStorage (no sensible)
5. Redirige a /dashboard

↓

Usuario ve el dashboard
```

### Durante uso normal (15 minutos)

```
Usuario hace clic en "Ver blacklist"

↓

Componente llama: fetchAPI('/api/blacklist/')

↓

fetchAPI() hace:
1. Obtiene token de memoria: `const token = accessToken;`
2. GET /api/blacklist/
   Headers: {
     "Authorization": "Bearer eyJ0eXAi...",
     "Content-Type": "application/json"
   }

↓

Portal A:
1. Lee header Authorization
2. Extrae token: "eyJ0eXAi..."
3. Decodifica y valida:
   - Firma es correcta
   - Token no ha expirado
   - Usuario existe en BD
   - Usuario tiene permiso
4. Devuelve datos JSON

↓

Portal B recibe datos

↓

Componente renderiza

↓

Usuario ve blacklist
```

### Cuando se presiona F5 (refrescada)

```
Usuario presiona F5

↓

Página se recarga
- Todo JavaScript se reinicia
- Variable accessToken = null (se perdió)
- localStorage permanece
- Cookies permanecen

↓

Componente intenta: fetchAPI('/api/data/')

↓

fetchAPI() hace:
1. Obtiene token de memoria: `const token = accessToken;`
2. Es null
3. Detecta: "Necesito refrescar"

↓

Llama: refreshAccessToken()

↓

refreshAccessToken() hace:
POST /api/auth/refresh/
credentials: include  ← IMPORTANTE: Envía cookies

↓

Navegador envía:
- Request POST
- Cookie HttpOnly refresh_token (automáticamente)

↓

Portal A:
1. Recibe POST
2. Lee cookie
3. Valida refresh token:
   - Firma correcta
   - No ha expirado (< 7 días)
   - Usuario existe
4. Devuelve nuevo access token

↓

Response:
{
  "access": "eyJ0eXAi..." (nuevo, válido 15 min)
}

↓

Portal B:
1. Recibe nuevo token
2. Lo guarda en memoria: `accessToken = "nuevo token"`
3. Reintenta la petición original
4. Continúa normalmente

↓

Usuario sigue navegando
(NO vio popup, NO tuvo que re-loguear, fue TRANSPARENTE)
```

### Token expirando (después de 14 minutos)

```
Cada 30 segundos, Portal B ejecuta:

```javascript
if (token_va_a_expirar_en_menos_de_1_minuto) {
  refreshAccessToken();  // Renovar antes de que expire
}
```

```
↓

Si SÍ va a expirar:
- Renueva con refresh token (en cookie)
- Obtiene nuevo access token
- Lo guarda en memoria
- Continúa sin interrupciones

↓

Si NO va a expirar:
- No hace nada
- Continúa usando el token actual

↓

Resultado: El usuario NUNCA ve un token expirado
```

### Refresh token expira (después de 7 días)

```
Usuario no usa la aplicación por 8 días

↓

Vuelve y abre portal-b.com

↓

Intenta hacer una petición: fetchAPI('/api/data/')

↓

Portal B intenta refrescar con la cookie

↓

POST /api/auth/refresh/
Cookie: refresh_token=eyJ0eXAi...

↓

Portal A:
1. Lee cookie
2. Valida refresh token
3. Descubre: "Este token expiró hace 1 día"
4. Rechaza con 401 Unauthorized

↓

Portal B detecta 401

↓

Portal B limpia memoria y localStorage

↓

Redirige a /login

↓

Usuario debe ingresar nuevamente
(Es aceptable después de 7 días)
```

### Atacante intenta robar

```
Atacante inyecta JavaScript malicioso en portal-b.com
(podría ser un comentario, búsqueda, header HTTP, etc)

↓

Código malicioso intenta 4 cosas:

1. Leer de localStorage:
   const token = localStorage.getItem('access_token');
   ❌ Retorna null (no está guardado ahí)

2. Leer de window:
   const token = window.accessToken;
   ❌ Acceso denegado (variable local de la librería)

3. Leer de documento:
   const token = document.innerHTML.match(/Bearer (.*)/);
   ❌ El token nunca aparece en HTML

4. Leer cookies:
   const token = document.cookie;
   ❌ HttpOnly = cookies no aparecen en document.cookie

↓

Resultado: Atacante NO PUEDE ROBAR el token

↓

¿Qué SÍ puede hacer?
Hacer requests: fetch('/api/transfer-money')

↓

Pero:
1. Sin acceso token válido, request falla
2. Aunque logre copiar un token que vio en memoria:
   - Token dura 15 minutos
   - Después expira automáticamente
   - Atacante queda bloqueado

Comparar con localStorage (7 días): MUCHO MÁS SEGURO
```

---

## Conclusión

Para tu caso específico (dos portales desacoplados, datos sensibles), la **Opción Híbrida es la opción profesional**.

Ofrece:
- ✅ Máxima seguridad contra XSS
- ✅ Funciona entre dominios
- ✅ UX moderna (sin re-logins)
- ✅ Escalable
- ✅ Cumple regulación

El costo es implementación un poco más compleja, que vale completamente la pena.

---

**Próximos pasos:** Ver el documento `JWT_SECURITY_OPTIONS.md` para el código específico de implementación.
