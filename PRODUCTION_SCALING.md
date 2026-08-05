# Cortexia Optical — Guía de Escalabilidad a Producción

Documento de referencia para escalar la plataforma a **1000 usuarios concurrentes** distribuidos en **500 ópticas**.

---

## Estado actual tras Quick Wins (Feb 2026)

### ✅ Aplicado en código (activo en preview + producción tras redeploy)

**Pool de conexiones MongoDB (`backend/db.py`):**
```
maxPoolSize          = 200   (env: MONGO_MAX_POOL_SIZE)
minPoolSize          = 20    (env: MONGO_MIN_POOL_SIZE)
maxIdleTimeMS        = 60000 (env: MONGO_MAX_IDLE_MS)
serverSelectionTimeoutMS = 5000
waitQueueTimeoutMS   = 3000
retryWrites          = True
```

**Object Storage compartido (`backend/object_storage.py`):**
- Usa Emergent Object Storage via `INTEGRATION_PROXY_URL` + `EMERGENT_LLM_KEY`.
- Migrado: `POST /api/settings/logo`, `GET /api/settings/logo`, `POST /api/companies/{id}/logo`, `GET /api/companies/{id}/logo`.
- Path convention: `cortexia-optical/logos/{company_id}.{ext}`.
- MongoDB campo `logo_storage_path` en `companies` = fuente de verdad para el path.
- Fallback filesystem si `EMERGENT_LLM_KEY` no esta seteado (dev only).

**Cache y Rate Limiter Redis-ready (`backend/cache.py`, `backend/rate_limiter.py`):**
- Si `REDIS_URL` esta seteado → Redis compartido (multi-pod safe).
- Si no → memoria in-process (dev/single-pod).
- `plans_cache` y `companies_cache` migrados a la API async con namespacing.
- `slowapi Limiter` usa `storage_uri=REDIS_URL` cuando esta disponible.

---

## Cambios pendientes en Emergent Deploy Pipeline

Estos cambios NO se pueden aplicar desde el preview (rompen hot-reload). Deben aplicarse en el pipeline de deployment.

### P0-1: Uvicorn workers y quitar --reload

**Comando actual (dev):**
```
uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1 --reload
```

**Comando recomendado (prod):**
```
uvicorn server:app --host 0.0.0.0 --port 8001 --workers 4 --no-access-log
```

O con gunicorn (más robusto):
```
gunicorn server:app -w 4 -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8001 --timeout 60 --graceful-timeout 30 \
  --max-requests 5000 --max-requests-jitter 500
```

Impacto: capacidad ~200 req/s → ~800 req/s en un solo pod.

### P0-2: Horizontal scaling (multi-pod)

Contactar **Emergent Support** para activar HPA con:
- Min replicas: 3
- Max replicas: 8
- Target CPU: 70%

Requisitos previos (deben estar hechos ANTES de multi-pod):
- P0-3 (S3 para logos) ✔ o los logos se pierden entre pods.
- P0-4 (Redis para cache + rate limit) ✔ o hay inconsistencias.

### P0-3: Object Storage para logos

Archivos actualmente en `backend/uploads/logos/` — sistema de archivos local del pod.

Rutas afectadas:
- `POST /api/settings/logo`
- `GET /api/settings/logo`
- `POST /api/companies/{id}/logo`
- `GET /api/companies/{id}/logo`

Migración: usar el playbook `integration_playbook_expert_v2` con "object storage" para obtener el bucket S3 gestionado por Emergent. Reemplazar `open(filepath, "wb")` por upload a S3 y servir vía URL firmada o pública.

### P0-4: Redis (rate limiter + cache compartido)

**Rate limiter (`slowapi`)** — cambiar en `backend/rate_limiter.py`:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=["120/minute"],
    storage_uri=os.environ.get("REDIS_URL"),  # <-- este cambio
)
```

**Cache (`backend/cache.py`)** — reemplazar LRU in-memory por `aiocache` con backend Redis. Endpoints principales:
- `/api/plans`
- `/api/companies` (superadmin)
- `/api/health-metrics`

### P0-5: Celery/RQ para tareas pesadas

Emails (Resend) y generación de PDFs actualmente usan `FastAPI BackgroundTasks`. Se pierden si el pod muere y no tienen retry.

Recomendado: `RQ` con broker Redis, un worker separado por pod tipo `celery-worker`. Colas:
- `emails` (welcome, quotations, alerts)
- `pdf` (quotations, cash reports)

### P0-6: Frontend en modo producción + CDN

Servir el build minificado (`yarn build`) desde CloudFront/Cloudflare, no `yarn start`.
Impacto: TTI en LATAM baja 40-60%.

---

## Roadmap sugerido

| Fase | Acciones | Capacidad resultante |
|---|---|---|
| **Hoy** | Pool Mongo tuneado (aplicado) | 100-300 usuarios |
| **+1 día** | P0-1 workers + P0-6 frontend CDN | 300-500 usuarios |
| **+3-5 días** | P0-2 multi-pod + P0-3 S3 + P0-4 Redis + P0-5 Celery | 1000-1500 usuarios |
| **+2 días** | APM (Sentry/Datadog) + load testing k6 | Validado en carga |

---

## Env vars para producción (recomendados)

```
# MongoDB pool
MONGO_MAX_POOL_SIZE=200
MONGO_MIN_POOL_SIZE=20
MONGO_MAX_IDLE_MS=60000

# Redis (cuando esté disponible)
REDIS_URL=redis://user:pass@host:port/0

# Object storage (cuando esté disponible)
S3_BUCKET=cortexia-uploads
S3_REGION=us-east-1

# Feature flags
ENABLE_REQUEST_CACHE=true
```

## Referencias en código
- `backend/db.py` — pool tuning
- `backend/rate_limiter.py` — slowapi (migrar a Redis)
- `backend/cache.py` — LRU (migrar a aiocache+Redis)
- `backend/routes/settings.py:61-84` — upload logo local
- `backend/routes/companies.py:149` — upload logo local
- `backend/email_service.py` — BackgroundTasks (migrar a RQ)
