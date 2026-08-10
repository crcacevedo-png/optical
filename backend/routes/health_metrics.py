"""Endpoint de metricas de salud del sistema (solo SuperAdmin).
Ayuda a decidir cuando activar Fase 2 de escalabilidad (multi-pod, Redis, S3).
"""
import os
import time
import psutil
from fastapi import APIRouter, HTTPException, Depends

from db import db, client
from auth_utils import get_current_user
from cache import plans_cache, companies_cache

router = APIRouter(prefix="/health", tags=["Health Metrics"])

# Coleccciones "core" que revisamos para stats
_CORE_COLLECTIONS = [
    "companies", "users", "branches",
    "patients", "products", "stock", "sales", "appointments",
    "optical_consultations", "eyeglass_prescriptions",
    "contact_lens_prescriptions", "medical_prescriptions",
    "finance_entries", "quotations", "inventory_movements",
    "audit_log", "notifications", "announcements", "suppliers",
    "login_attempts", "plans",
]


@router.get("/metrics")
async def health_metrics(user: dict = Depends(get_current_user)):
    """Metricas operativas del sistema. Solo SuperAdmin."""
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    # ─── Ping a MongoDB ───────────────────────────────────────────────
    t0 = time.perf_counter()
    ping_ok = True
    try:
        await client.admin.command("ping")
    except Exception:
        ping_ok = False
    mongo_ping_ms = round((time.perf_counter() - t0) * 1000, 2)

    # ─── Conteo por coleccion (paralelo) ──────────────────────────────
    counts = {}
    for name in _CORE_COLLECTIONS:
        try:
            counts[name] = await db[name].estimated_document_count()
        except Exception:
            counts[name] = None

    # ─── Server stats (dbStats) ───────────────────────────────────────
    db_stats_summary = {}
    try:
        stats = await db.command("dbStats", scale=1024 * 1024)  # MB
        db_stats_summary = {
            "collections": stats.get("collections"),
            "objects_total": stats.get("objects"),
            "data_size_mb": round(stats.get("dataSize", 0), 2),
            "storage_size_mb": round(stats.get("storageSize", 0), 2),
            "index_size_mb": round(stats.get("indexSize", 0), 2),
            "total_size_mb": round(stats.get("totalSize", 0), 2),
        }
    except Exception as e:
        db_stats_summary = {"error": str(e)}

    # ─── Memoria y CPU del proceso backend ───────────────────────────
    proc = psutil.Process(os.getpid())
    mem_info = proc.memory_info()
    process_stats = {
        "pid": proc.pid,
        "rss_mb": round(mem_info.rss / 1024 / 1024, 2),
        "vms_mb": round(mem_info.vms / 1024 / 1024, 2),
        "cpu_percent": proc.cpu_percent(interval=0.1),
        "threads": proc.num_threads(),
        "open_fds": proc.num_fds() if hasattr(proc, "num_fds") else None,
        "uptime_seconds": round(time.time() - proc.create_time()),
    }

    # ─── Sistema (host / pod) ─────────────────────────────────────────
    # En Kubernetes `psutil.virtual_memory()` y `psutil.disk_usage("/")` reportan
    # el NODO completo (compartido con decenas de otros pods). Para conocer el
    # uso REAL de nuestro contenedor leemos los limites de cgroup v2.
    def _read_int(path):
        try:
            with open(path) as f:
                v = f.read().strip()
            return int(v) if v.isdigit() else None
        except Exception:
            return None

    cg_mem_limit = _read_int("/sys/fs/cgroup/memory.max")  # cgroups v2
    cg_mem_used = _read_int("/sys/fs/cgroup/memory.current")
    if cg_mem_limit is None:
        # cgroups v1 fallback
        cg_mem_limit = _read_int("/sys/fs/cgroup/memory/memory.limit_in_bytes")
        cg_mem_used = _read_int("/sys/fs/cgroup/memory/memory.usage_in_bytes")

    vm = psutil.virtual_memory()
    # Si tenemos cgroup y no es "sin limite" (valores absurdamente grandes), lo usamos.
    if cg_mem_limit and cg_mem_used and cg_mem_limit < (1 << 62):
        mem_total_bytes = cg_mem_limit
        mem_used_bytes = cg_mem_used
        mem_source = "cgroup"
    else:
        mem_total_bytes = vm.total
        mem_used_bytes = vm.used
        mem_source = "host"
    mem_percent = round((mem_used_bytes / mem_total_bytes) * 100, 1) if mem_total_bytes else 0

    disk_path = "/app" if os.path.isdir("/app") else "/"
    disk = psutil.disk_usage(disk_path)
    system_stats = {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "cpu_count": psutil.cpu_count(),
        "memory_source": mem_source,
        "memory_total_mb": round(mem_total_bytes / 1024 / 1024, 2),
        "memory_used_mb": round(mem_used_bytes / 1024 / 1024, 2),
        "memory_percent": mem_percent,
        "disk_path": disk_path,
        "disk_used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
        "disk_total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
        "disk_percent": disk.percent,
        "disk_is_shared_node": disk.total > 50 * 1024 * 1024 * 1024,  # >50GB = disco compartido del nodo
        "app_data_mb": round(db_stats_summary.get("total_size_mb", 0), 2),
    }

    # ─── Cache stats ──────────────────────────────────────────────────
    cache_stats = {
        "plans_cache": plans_cache.stats(),
        "companies_cache": companies_cache.stats(),
    }

    # ─── Activity (ultimos 24h) ───────────────────────────────────────
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    day_ago_iso = (now - timedelta(hours=24)).isoformat()
    activity = {
        "logins_24h": await db.audit_log.count_documents({"action": "LOGIN_OK", "created_at": {"$gte": day_ago_iso}}),
        "failed_logins_24h": await db.audit_log.count_documents({"action": "LOGIN_FAILED", "created_at": {"$gte": day_ago_iso}}),
        "audit_events_24h": await db.audit_log.count_documents({"created_at": {"$gte": day_ago_iso}}),
        "new_users_24h": await db.users.count_documents({"created_at": {"$gte": day_ago_iso}}),
        "sales_24h": await db.sales.count_documents({"created_at": {"$gte": day_ago_iso}}),
    }

    # ─── Health tier signals (semaforo simple para Fase 2) ────────────
    signals = []
    if system_stats["memory_percent"] > 80:
        signals.append({"level": "warning", "msg": "Uso de memoria del pod > 80%"})
    # Solo alertar por disco cuando el nodo esta realmente critico (>95%).
    # En Kubernetes el disco es compartido con otros pods; el uso "normal"
    # oscila naturalmente entre 60-85%.
    if system_stats["disk_percent"] > 95:
        signals.append({"level": "warning", "msg": "Disco del nodo K8s > 95% (compartido con otros pods, contacta soporte)"})
    if db_stats_summary.get("total_size_mb", 0) > 5000:
        signals.append({"level": "info", "msg": "BD > 5GB — considera archivar audit_log manualmente"})
    if counts.get("companies", 0) > 500:
        signals.append({"level": "info", "msg": ">500 opticas — evalua activar Fase 2 (Redis + multi-pod)"})
    if mongo_ping_ms > 200:
        signals.append({"level": "warning", "msg": f"Ping a MongoDB alto ({mongo_ping_ms}ms)"})
    if not ping_ok:
        signals.append({"level": "critical", "msg": "MongoDB no responde"})

    return {
        "timestamp": now.isoformat(),
        "mongo": {"ping_ms": mongo_ping_ms, "reachable": ping_ok, **db_stats_summary},
        "collection_counts": counts,
        "process": process_stats,
        "system": system_stats,
        "cache": cache_stats,
        "activity_24h": activity,
        "signals": signals,
    }
