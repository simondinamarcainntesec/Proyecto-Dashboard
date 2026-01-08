# Opciones de Seguridad JWT para Portales Desacoplados

Una guía completa para elegir la arquitectura de autenticación más segura y práctica entre dos portales independientes.

## Contexto del Problema

Tenemos dos portales web completamente separados:
- **Portal A (Django)**: Servidor central de autenticación y lógica de negocio
- **Portal B (Next.js)**: Aplicación frontend independiente que necesita acceder a los datos de Portal A

El desafío es que están en **dominios distintos** (ejemplo: `portal-a.com` y `portal-b.com`), lo cual genera limitaciones técnicas importantes debido a las políticas de seguridad del navegador.

### Requisitos principales
1. **Seguridad**: Proteger contra XSS, CSRF y robo de tokens
2. **Escalabilidad**: Si Portal A falla, Portal B debe seguir funcionando con datos en caché
3. **Usabilidad**: El usuario no debe perder su sesión al refrescar la página
4. **Mantenibilidad**: La solución debe ser relativamente simple de mantener

---

## Comparativa General de Opciones

| Opción | Seguridad XSS | CSRF | Funciona entre dominios | Resiste refresh | Complejidad |
|--------|---------------|------|---------|--------------|-------------|
| **localStorage** | ❌ Vulnerable | ✅ Resistente | ✅ Funciona | ✅ Persiste | Muy Baja |
| **sessionStorage** | ❌ Vulnerable | ✅ Resistente | ✅ Funciona | ❌ Se pierde | Muy Baja |
| **HttpOnly Cookie** | ✅ Muy seguro | ⚠️ Complejo | ❌ NO funciona | ✅ Persiste | Media |
| **Memoria** | ✅ Muy seguro | ✅ Resistente | ✅ Funciona | ❌ Se pierde | Baja-Media |
| **Híbrida (Recomendada)** | ✅ Muy seguro | ✅ Resistente | ✅ Funciona | ✅ Persiste | Media-Alta |

---

## Opción 1: localStorage

### Descripción
Token JWT se guarda en `localStorage` del navegador.

### Ventajas
- ✅ Simple de implementar
- ✅ Funciona entre dominios
- ✅ Persiste al refrescar página
- ✅ No requiere configuración de servidor

### Desventajas
- ❌ **Vulnerable a XSS**: Si se inyecta JS malicioso, pueden robar el token
- ❌ Accesible desde cualquier script JS

### Implementación

**Next.js:**
```javascript
// Login
const response = await fetch('https://portal-django.com/api/auth/login/', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({username, password})
});

const {access, refresh} = await response.json();

localStorage.setItem('access_token', access);
localStorage.setItem('refresh_token', refresh);

// Uso
const token = localStorage.getItem('access_token');
fetch(url, {
  headers: {'Authorization': `Bearer ${token}`}
});
```

### Cuándo usar
- Desarrollo rápido
- Aplicaciones con bajo riesgo de XSS
- Equipos con buenas prácticas de sanitización

---

## Opción 2: sessionStorage

### Descripción

SessionStorage es similar a localStorage, pero con una diferencia crítica: **se borra automáticamente cuando el usuario cierra la pestaña o el navegador**. Es útil para sesiones que deberían terminar cuando termina la sesión del navegador.

### ¿Cómo funciona?

El funcionamiento es idéntico a localStorage en cuanto a acceso desde JavaScript. La única diferencia es que JavaScript puede borrar automáticamente el token al detectar que el navegador se está cerrando, y lo hace con más predictibilidad.

### Ventajas

- **Más seguro que localStorage en ciertos escenarios**: Si los usuarios comparten computadora, al cerrar la pestaña se borra automáticamente
- **Simpleza similar a localStorage**: Misma sintaxis, misma complejidad
- **Funciona entre dominios**: Sin problemas de CORS
- **Sesión limitada**: El usuario no puede quedarse "eternamente" en sesión (aunque es limitación débil)

### Desventajas (GRAVES)

- **Sigue siendo vulnerable a XSS**: Los mismos riesgos que localStorage
- **Sesión incómoda**: Si el usuario tiene multiple pestañas abiertas y cierra una, pierde autenticación en esa pestaña
- **Peor experiencia de usuario**: "Refrescar" la página cierra la sesión
- **Confusión**: Los usuarios no entienden por qué se cierran sus sesiones tras eventos normales

### El problema con sessionStorage

Aunque sessionStorage se borra al cerrar, esto no lo hace más seguro contra XSS. Un atacante que inyecta JavaScript puede robar el token **antes** de que se cierre la sesión, y usarlo en otro navegador.

Además, con el flujo normal de una SPA (Single Page Application), los usuarios raramente "cierran" la sesión naturalmente. Generalmente es cuando cierra el navegador, que es mucho tiempo después del robo potencial.

### Cuándo usar sessionStorage

Solo en casos muy específicos:

1. **Kioscos públicos**: Donde cada usuario debe "empezar de nuevo" al cerrar la pestaña
2. **Sesiones de demostración**: Pruebas temporales donde la persistencia es una molestia
3. **Acuerdos de cumplimiento**: Si tu regulación requiere "limpiar sesión al cerrar navegador"

Para la mayoría de aplicaciones, sessionStorage es un compromiso que no resuelve problemas de seguridad pero empeora la experiencia.

### Implementación básica (solo referencia)

```javascript
sessionStorage.setItem('access_token', token);
const token = sessionStorage.getItem('access_token');
```

---

## Opción 3: HttpOnly Cookie (NO recomendada para tu caso)

---

## Opción 3: HttpOnly Cookie (NO recomendada para 2 dominios)

### Descripción

HttpOnly es una **bandera de cookie** que impide que JavaScript acceda al valor guardado. Solo el navegador (a nivel HTTP) puede enviar la cookie en requests. Esta es la forma más segura contra XSS si la aplicación está en el **mismo dominio**.

### ¿Cómo funciona?

Cuando Django establece una cookie HttpOnly, le dice al navegador:
- "Esta cookie es solo para HTTP, no para JavaScript"
- "Cuando hagas requests HTTP, envía esta cookie automáticamente"
- "No permitas que JavaScript lea el contenido de esta cookie"

Esto significa que incluso si hay una vulnerabilidad XSS y se inyecta JavaScript malicioso, el código inyectado **NO PUEDE** leer el token.

### Ventajas (muy grandes)

- **Máxima protección contra XSS**: JavaScript no puede acceder, punto
- **Envío automático**: El navegador envía la cookie automáticamente en cada request
- **Estándar de la industria**: Usado por Google, Facebook, Amazon, etc.
- **No requiere intervención del usuario**: Transparente

### Desventajas (CRÍTICA para tu caso)

- **NO funciona entre dominios**: Esta es la limitación que mata la opción para ti
  - Django en `portal-a.com` establece cookie
  - Next.js en `portal-b.com` hace request
  - La cookie `portal-a.com` **NO se envía** a `portal-b.com` (es una política de seguridad del navegador)

### Por qué no funciona entre dominios

Las cookies están vinculadas al dominio que las creó. Es una política de seguridad fundamental del navegador llamada **Same Origin Policy**. Un sitio no puede acceder a las cookies de otro sitio porque:

1. **Previene CSRF**: Si `evil.com` pudiera acceder a cookies de `bank.com`, podría transferir dinero
2. **Aislamiento de datos**: Cada sitio tiene su propia "bóveda" de cookies

Aunque Django establezca `Set-Cookie: refresh_token=...; SameSite=Lax` para permitir ciertos cross-site requests, la cookie **aún así no se envía** entre dominios distintos en los navegadores modernos.

### Alternativa: Usar HttpOnly con Same-Origin

Si ambas aplicaciones estuvieran en el **mismo dominio** (ej: `portal.com/api/` y `portal.com/app/`), entonces HttpOnly sería perfecto. Pero en tu caso con dominios distintos, es imposible.

### Cuándo usar HttpOnly

- Cuando la API y el frontend están en el mismo dominio
- Cuando tu Django renderiza las páginas HTML (server-side rendering)
- Cuando no necesitas integración con portales externos

En tu caso, **no aplica**.

### Implementación (solo referencia, no la uses)

```python
# Django - NO LO HAGAS en tu caso
response.set_cookie(
    'access_token',
    token,
    httponly=True,   # JavaScript no puede leer
    secure=True,     # Solo HTTPS
    samesite='Strict',
)

# Problema: La cookie de portal-a.com NO se envía a portal-b.com
```

---

## Opción 4: Memoria (Token en variable JavaScript)

---

## Opción 4: Memoria (Token en variable)

### Descripción

En lugar de guardar el token en storage (localStorage, sessionStorage o cookies), se mantiene únicamente en una **variable JavaScript en memoria**. Cuando la página se refrescar, la variable se pierde.

### ¿Cómo funciona?

```
┌─────────────────────────────────────────────────┐
│  Memoria (RAM del navegador - variable JS)      │
│  let accessToken = "eyJ0eXAi..."               │
│  Accesible solo mientras la pestaña está abierta│
└─────────────────────────────────────────────────┘
```

Cuando el usuario abre la página, el token solo existe en la variable. Si presiona F5 (refresh), esa variable se pierde.

### Ventajas (seguridad máxima)

- **No vulnerable a XSS causado por lectura de storage**: El token no está en localStorage, así que XSS no puede robarlo de ahí
- **Funciona entre dominios**: Sin problemas de CORS, es JavaScript puro
- **Limpio**: No requiere cookies ni almacenamiento persistente
- **Ideal para tokens corta vida**: Si el token dura 15 minutos, la pérdida al refrescar es menor problema

### Desventajas (problemas significativos)

- **Se pierde al refrescar**: Cuando presionas F5, la sesión se cierra
- **Se pierde si la pestaña se bloquea**: Un crash del navegador o de la pestaña = re-login
- **Se pierde si cambias de pestaña y vuelves**: Aunque sea la misma sesión del navegador, cada pestaña tiene su propia memoria
- **Problemas en mobile**: Apps con múltiples ventanas, widgets flotantes, etc.

### El problema real

Aunque en teoría es seguro contra XSS, en práctica **obliga al usuario a re-autenticarse constantemente**. Los desarrolladores típicamente lo "solucionan" guardando el token en localStorage de todas formas, lo cual anula el beneficio de seguridad.

### Caso de uso específico

Podría tener sentido en:
- Operaciones financieras críticas donde se accede a una sola página
- Formularios de un solo paso sin necesidad de navegar
- Aplicaciones de altísima seguridad donde el usuario acepta re-autenticarse al refrescar

### Cuándo usar memoria pura

Para la mayoría de aplicaciones web modernas, esto es **demasiado restrictivo**. Los usuarios esperan que su sesión persista al refrescar la página.

Sin embargo, puedes combinarla con refresh tokens para resolver el problema (ver Opción 5 - Híbrida).

---

## Opción 5: Híbrida - Arquitectura Recomendada para Tu Caso

### El Concepto

La opción híbrida combina lo mejor de dos mundos:

1. **Access Token en Memoria**: Dura 15 minutos, se guarda en una variable JavaScript
   - Si se inyecta XSS, el atacante no puede robar del storage (porque no está en storage)
   - Si el navegador se refrescar, se pierde, pero...

2. **Refresh Token en HttpOnly Cookie**: Dura 7 días, se guarda en una cookie HttpOnly
   - JavaScript no puede acceder (seguro contra XSS)
   - Se envía automáticamente en requests
   - El navegador puede usarlo para obtener un nuevo access token sin que el usuario haga nada

### Flujo Detallado

```
┌─────────────────────────────────────────────┐
│  Portal Next.js (portal-b.com)              │
│  - Access token en MEMORIA (15 min)         │
│  - Se renueva automáticamente cada 15 min   │
└─────────────────────────────────────────────┘
         ↓ POST /api/auth/login/
         ↓ (credentials: include)
┌─────────────────────────────────────────────┐
│  Portal Django (portal-a.com)               │
│  - Devuelve access token en JSON            │
│  - Guarda refresh en HttpOnly cookie        │
│    Set-Cookie: refresh_token=...; HttpOnly  │
└─────────────────────────────────────────────┘
```

### Implementación

#### Backend Django

**settings.py:**
```python
from datetime import timedelta

INSTALLED_APPS = [
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    ...
]

# CORS para Next.js
CORS_ALLOWED_ORIGINS = [
    "https://portal-nextjs.com",
    "https://localhost:3000",  # desarrollo
]
CORS_ALLOW_CREDENTIALS = True

# JWT Config
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),  # Corta vida
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': settings.SECRET_KEY,
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
}
```

**home/api/serializers.py:**
```python
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Agregar datos al token
        token['tenant_id'] = user.tenant.id if user.tenant else None
        token['tenant_name'] = user.tenant.name if user.tenant else None
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Agregar info del usuario
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'tenant': {
                'id': self.user.tenant.id if self.user.tenant else None,
                'name': self.user.tenant.name if self.user.tenant else None,
            } if self.user.tenant else None,
        }
        return data
```

**home/api/views.py:**
```python
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.http import JsonResponse

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        # Extraer refresh token
        refresh = response.data.get('refresh')
        
        # Guardarlo en HttpOnly cookie
        response.set_cookie(
            'refresh_token',
            refresh,
            httponly=True,      # ⭐ JS no puede acceder
            secure=not settings.DEBUG,  # Solo HTTPS en producción
            samesite='Lax',     # Permite cross-site pero seguro
            max_age=7*24*60*60, # 7 días
        )
        
        # Eliminar refresh del JSON (ya está en cookie)
        response.data.pop('refresh', None)
        
        return response

class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        # Leer refresh token desde cookie
        refresh = request.COOKIES.get('refresh_token')
        
        if not refresh:
            return JsonResponse({'detail': 'Refresh token not found'}, status=401)
        
        # Agregar al request para que TokenRefreshView lo procese
        request.data['refresh'] = refresh
        
        response = super().post(request, *args, **kwargs)
        return response
```

**home/api/urls.py:**
```python
from django.urls import path
from .views import CustomTokenObtainPairView, CustomTokenRefreshView

urlpatterns = [
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('auth/refresh/', CustomTokenRefreshView.as_view(), name='refresh'),
]
```

#### Frontend Next.js

**lib/auth.ts:**
```typescript
let accessToken: string | null = null;  // ⭐ EN MEMORIA

const API_URL = 'https://portal-django.com/api';

export async function login(username: string, password: string) {
  const response = await fetch(`${API_URL}/auth/login/`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    credentials: 'include',  // ⭐ Envía y recibe cookies
    body: JSON.stringify({username, password})
  });

  if (!response.ok) {
    throw new Error('Login failed');
  }

  const data = await response.json();
  
  // ⭐ Access token en MEMORIA
  accessToken = data.access;
  
  // Guardar info de usuario (no sensible)
  localStorage.setItem('user', JSON.stringify(data.user));
  
  return data;
}

export async function getAccessToken(): Promise<string | null> {
  if (!accessToken) {
    // Token se perdió (refresh de página), renovar
    return await refreshAccessToken();
  }

  // Verificar si está a punto de expirar
  try {
    const payload = JSON.parse(atob(accessToken.split('.')[1]));
    const exp = payload.exp * 1000;
    
    // Si expira en menos de 1 minuto, renovar
    if (exp < Date.now() + 60000) {
      return await refreshAccessToken();
    }
  } catch (e) {
    return await refreshAccessToken();
  }

  return accessToken;
}

export async function refreshAccessToken(): Promise<string | null> {
  try {
    const response = await fetch(`${API_URL}/auth/refresh/`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      credentials: 'include',  // ⭐ Envía refresh_token cookie
      body: JSON.stringify({})
    });

    if (!response.ok) {
      throw new Error('Refresh failed');
    }

    const data = await response.json();
    
    // ⭐ Actualizar token en memoria
    accessToken = data.access;
    return accessToken;
    
  } catch (e) {
    // Refresh falló, hacer logout
    logout();
    return null;
  }
}

export function logout() {
  accessToken = null;
  localStorage.removeItem('user');
  
  // Opcional: llamar al backend para invalidar cookie
  fetch(`${API_URL}/auth/logout/`, {
    method: 'POST',
    credentials: 'include'
  });
}

export function getCurrentUser() {
  const user = localStorage.getItem('user');
  return user ? JSON.parse(user) : null;
}

export function getCurrentTenant() {
  const user = getCurrentUser();
  return user?.tenant || null;
}
```

**lib/api.ts:**
```typescript
import { getAccessToken } from './auth';

export async function fetchAPI(
  endpoint: string,
  options: RequestInit = {}
): Promise<any> {
  const token = await getAccessToken();

  if (!token) {
    throw new Error('No access token available');
  }

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
    ...options.headers,
  };

  const response = await fetch(
    `https://portal-django.com/api${endpoint}`,
    {
      ...options,
      headers,
    }
  );

  if (!response.ok) {
    if (response.status === 401) {
      // Token expirado, intentar refresh automático
      const newToken = await getAccessToken();
      if (newToken) {
        // Reintentar con nuevo token
        headers['Authorization'] = `Bearer ${newToken}`;
        const retryResponse = await fetch(
          `https://portal-django.com/api${endpoint}`,
          { ...options, headers }
        );
        return retryResponse.json();
      }
    }
    throw new Error(`API error: ${response.statusText}`);
  }

  return response.json();
}
```

**Uso en componentes:**
```typescript
'use client';

import { useEffect, useState } from 'react';
import { fetchAPI } from '@/lib/api';
import { getCurrentTenant } from '@/lib/auth';

export default function BlacklistPage() {
  const [blacklist, setBlacklist] = useState([]);
  const tenant = getCurrentTenant();

  useEffect(() => {
    async function loadData() {
      const data = await fetchAPI('/blacklist/');
      setBlacklist(data);
    }
    loadData();
  }, []);

  return (
    <div>
      <h1>Blacklist - Tenant: {tenant?.name}</h1>
      <ul>
        {blacklist.map(ip => (
          <li key={ip.ip}>{ip.ip}</li>
        ))}
      </ul>
    </div>
  );
}
```

### Protecciones adicionales

**1. Content Security Policy (CSP):**
```python
# settings.py
SECURE_CONTENT_SECURITY_POLICY = {
    "default-src": ["'self'"],
    "script-src": ["'self'"],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:", "https:"],
}
```

**2. Rate Limiting:**
```bash
pip install django-ratelimit
```

```python
from django_ratelimit.decorators import ratelimit

class CustomTokenObtainPairView(TokenObtainPairView):
    @ratelimit(key='ip', rate='5/m', method='POST')
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
```

**3. Sanitización en Next.js:**
```bash
npm install dompurify
```

```typescript
import DOMPurify from 'dompurify';

const safeHTML = DOMPurify.sanitize(userInput);
```

### Cuándo usar
- ✅ **Recomendado para tu caso**: Portales desacoplados con máxima seguridad
- Aplicaciones enterprise
- Datos sensibles (credenciales, finanzas, salud)

---

## Tabla Resumen - ¿Cuál elegir?

| Requisito | Opción recomendada |
|-----------|-------------------|
| Desarrollo rápido, bajo riesgo | localStorage |
| Sesión temporal | sessionStorage |
| Mismo dominio (Django renderiza frontend) | HttpOnly Cookie |
| Máxima seguridad, misma pestaña | Memoria |
| **Portales desacoplados + Máxima seguridad** | **Híbrida** |

---

## Instalación de dependencias

### Backend Django
```bash
pip install djangorestframework
pip install djangorestframework-simplejwt
pip install django-cors-headers
pip install django-ratelimit  # Opcional
```

### Frontend Next.js
```bash
npm install jwt-decode  # Para decodificar tokens
npm install dompurify   # Para sanitización
```

---

## Checklist de seguridad

- [ ] HTTPS en producción (SECURE_SSL_REDIRECT=True)
- [ ] CORS configurado correctamente
- [ ] Access token vida corta (15 min)
- [ ] Refresh token en HttpOnly
- [ ] Rate limiting en login
- [ ] Content Security Policy (CSP)
- [ ] Sanitización de inputs
- [ ] Logging de intentos fallidos
- [ ] Rotación de SECRET_KEY periódica
- [ ] Monitoreo de tokens robados (opcional: JWT blacklist)

---

## Recursos adicionales

- [JWT.io](https://jwt.io) - Decodificador de tokens
- [OWASP Top 10](https://owasp.org/www-project-top-ten/) - Vulnerabilidades comunes
- [Django REST Framework JWT](https://django-rest-framework-simplejwt.readthedocs.io/)
- [Next.js Security](https://nextjs.org/docs/advanced-features/security-headers)

---

**Fecha:** 8 de enero de 2026  
**Proyecto:** Portal Dashboard - Inntesec  
**Arquitectura:** Django (Backend) + Next.js (Frontend desacoplado)
