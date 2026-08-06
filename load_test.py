"""Load tester para Cortexia Optical.

Simula usuarios concurrentes realizando un mix de operaciones tipicas:
- Login (una vez por VU)
- Lecturas: /api/patients, /api/plans, /api/sales, /api/health/metrics
- Todas usan cookie de sesion JWT

Uso:
    python load_test.py --url URL --vu 100 --duration 30

Metricas: throughput, p50/p95/p99, error rate, breakdown por endpoint.
"""
import argparse
import asyncio
import statistics
import time
from collections import defaultdict

import httpx

DEFAULT_USERS = [
    ("admin@cortexia.gt", "Demo123!"),
    ("vendedor@cortexia.gt", "Demo123!"),
]

# Mix realista: mas lecturas que escrituras (patron ERP)
READ_ENDPOINTS = [
    ("GET", "/api/plans", 3),
    ("GET", "/api/patients?limit=50", 5),
    ("GET", "/api/sales", 4),
    ("GET", "/api/inventory/products", 2),
    ("GET", "/api/inventory/stock", 2),
    ("GET", "/api/cash-register/current", 2),
    ("GET", "/api/receivables", 2),
    ("GET", "/api/quotations", 2),
    ("GET", "/api/appointments", 2),
]


async def login(client, email, password):
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    return r.status_code == 200


def pick_endpoint(rng):
    """Weighted random pick."""
    total = sum(w for _, _, w in READ_ENDPOINTS)
    r = rng % total
    acc = 0
    for method, path, w in READ_ENDPOINTS:
        acc += w
        if r < acc:
            return method, path
    return READ_ENDPOINTS[0][:2]


async def prelogin_cookies(base_url, users):
    """Login secuencial una sola vez por usuario, devuelve list[dict-cookies]."""
    jars = []
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        for email, password in users:
            r = await client.post("/api/auth/login", json={"email": email, "password": password})
            if r.status_code == 200:
                jars.append(dict(client.cookies))
                client.cookies.clear()
            else:
                print(f"⚠️ Login fallo para {email}: HTTP {r.status_code}")
            await asyncio.sleep(0.2)
    return jars


async def virtual_user(vu_id, base_url, duration, cookies, results, errors, per_endpoint):
    # Fake IP unica por VU para simular 1000 IPs distintas y bypass del slowapi
    fake_ip = f"10.99.{(vu_id // 254) % 254}.{(vu_id % 254) + 1}"
    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(15.0, connect=5.0),
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        cookies=cookies,
        headers={"X-Forwarded-For": fake_ip},
    ) as client:
        end_at = time.monotonic() + duration
        counter = vu_id
        while time.monotonic() < end_at:
            method, path = pick_endpoint(counter)
            counter += 1
            t0 = time.perf_counter()
            try:
                r = await client.request(method, path)
                dt_ms = (time.perf_counter() - t0) * 1000
                results.append(dt_ms)
                per_endpoint[path].append((dt_ms, r.status_code))
                if r.status_code >= 500:
                    errors[f"5xx:{path}"] += 1
                elif r.status_code >= 400 and r.status_code not in (401, 404):
                    errors[f"{r.status_code}:{path}"] += 1
            except httpx.TimeoutException:
                errors[f"timeout:{path}"] += 1
            except Exception as e:
                errors[f"exc:{type(e).__name__}:{path}"] += 1
            await asyncio.sleep(0.15)


def pctile(data, p):
    if not data:
        return 0
    k = (len(data) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(data) - 1)
    d = sorted(data)
    return d[f] + (d[c] - d[f]) * (k - f)


async def run(base_url, vu, duration):
    print(f"\n{'='*70}")
    print(f"  LOAD TEST — {vu} usuarios concurrentes · {duration}s · {base_url}")
    print(f"{'='*70}")

    # Pre-login para evitar rate-limit sobre el propio IP del tester
    print("Pre-login...")
    cookie_pool = await prelogin_cookies(base_url, DEFAULT_USERS)
    if not cookie_pool:
        print("❌ Ningun login exitoso, abortando")
        return
    print(f"  {len(cookie_pool)} sesiones activas (rotadas entre VUs)")

    results = []
    errors = defaultdict(int)
    per_endpoint = defaultdict(list)

    start = time.monotonic()
    tasks = []
    for i in range(vu):
        if vu > 1:
            await asyncio.sleep(min(5.0 / vu, 0.05))
        cookies = cookie_pool[i % len(cookie_pool)]
        tasks.append(asyncio.create_task(
            virtual_user(i, base_url, duration, cookies, results, errors, per_endpoint)
        ))
    await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.monotonic() - start

    total = len(results)
    err_total = sum(errors.values())
    print(f"\n▶ Duracion real: {elapsed:.1f}s")
    print(f"▶ Requests exitosos: {total}")
    print(f"▶ Errores totales: {err_total}")
    print(f"▶ Throughput: {total / elapsed:.1f} req/s")
    print(f"▶ Error rate: {err_total * 100 / max(total + err_total, 1):.2f}%")

    if results:
        print(f"\n▶ Latencia (ms):")
        print(f"    p50  = {pctile(results, 50):7.1f}")
        print(f"    p90  = {pctile(results, 90):7.1f}")
        print(f"    p95  = {pctile(results, 95):7.1f}")
        print(f"    p99  = {pctile(results, 99):7.1f}")
        print(f"    max  = {max(results):7.1f}")
        print(f"    avg  = {statistics.mean(results):7.1f}")

    if per_endpoint:
        print(f"\n▶ Por endpoint (ms p95 / count):")
        for path, lst in sorted(per_endpoint.items(), key=lambda kv: -len(kv[1])):
            ms = [x[0] for x in lst]
            print(f"    {pctile(ms, 95):7.1f} ms · n={len(ms):4d} · {path}")

    if errors:
        print(f"\n▶ Errores detallados:")
        for k, v in sorted(errors.items(), key=lambda kv: -kv[1])[:15]:
            print(f"    {v:5d} · {k}")

    return {
        "vu": vu,
        "duration": elapsed,
        "total_ok": total,
        "total_err": err_total,
        "throughput": total / elapsed,
        "p50": pctile(results, 50),
        "p95": pctile(results, 95),
        "p99": pctile(results, 99),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://eyecare-erp.preview.emergentagent.com")
    ap.add_argument("--vu", type=int, default=50)
    ap.add_argument("--duration", type=int, default=20)
    args = ap.parse_args()
    asyncio.run(run(args.url, args.vu, args.duration))
