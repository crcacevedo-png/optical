"""Emergent Object Storage service.

Sustituye el almacenamiento local de logos y archivos por Object Storage
compartido, requisito para escalar a multi-pod.

Fallback: si EMERGENT_LLM_KEY no esta disponible, cae de vuelta al filesystem
local (compatibilidad con dev/tests). En produccion multi-pod DEBE estar la env.
"""
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger("object_storage")

APP_NAME = "cortexia-optical"
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")

_storage_key: Optional[str] = None

MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "pdf": "application/pdf",
}


def is_enabled() -> bool:
    return bool(EMERGENT_KEY)


def init_storage(force: bool = False) -> Optional[str]:
    """Init una unica vez por proceso; devuelve la storage_key.
    force=True para regenerar tras 404 (key expirada)."""
    global _storage_key
    if not EMERGENT_KEY:
        return None
    if _storage_key and not force:
        return _storage_key
    try:
        resp = requests.post(
            f"{STORAGE_URL}/init",
            json={"emergent_key": EMERGENT_KEY},
            timeout=30,
        )
        resp.raise_for_status()
        _storage_key = resp.json()["storage_key"]
        logger.info("Object storage initialized OK")
        return _storage_key
    except Exception as e:
        logger.error(f"Object storage init failed: {e}")
        return None


def put_object(path: str, data: bytes, content_type: str) -> dict:
    """Sube un objeto y devuelve {path, size, etag}."""
    key = init_storage()
    if not key:
        raise RuntimeError("Object storage no inicializado (falta EMERGENT_LLM_KEY)")
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    if resp.status_code == 404:
        # key stale -> regenerar y reintentar una vez
        key = init_storage(force=True)
        if not key:
            resp.raise_for_status()
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str) -> tuple[bytes, str]:
    """Descarga un objeto. Retorna (bytes, content_type)."""
    key = init_storage()
    if not key:
        raise RuntimeError("Object storage no inicializado")
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=60,
    )
    if resp.status_code == 404:
        key = init_storage(force=True)
        if key:
            resp = requests.get(
                f"{STORAGE_URL}/objects/{path}",
                headers={"X-Storage-Key": key},
                timeout=60,
            )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


def build_logo_path(company_id: str, ext: str) -> str:
    """Convencion de path para logos por empresa."""
    return f"{APP_NAME}/logos/{company_id}.{ext.lower()}"


def content_type_for(ext: str) -> str:
    return MIME_TYPES.get(ext.lower(), "application/octet-stream")
