"""Utilidades puras de facturacion compartidas por `routes/billing.py` y `dunning.py`.

Vive fuera de ambos modulos para romper la dependencia circular: `dunning` necesitaba
`_plan_amount_cents` de `routes.billing`, mientras que `billing` importa `dunning`. Al
alojar aqui la logica pura (sin Stripe ni DB), ambos la importan sin ciclo.
"""


def _plan_amount_cents(plan: dict, cycle: str) -> tuple[int, str]:
    """Devuelve (unit_amount_en_centavos, intervalo). Anual = price_yearly o mensual x10."""
    if cycle == "yearly":
        amt = plan.get("price_yearly")
        if amt is None:
            base = float(plan.get("price_monthly") or plan.get("price", 0) or 0)
            amt = base * 10
        return int(round(float(amt) * 100)), "year"
    amt = plan.get("price_monthly")
    if amt is None:
        amt = float(plan.get("price", 0) or 0)
    return int(round(float(amt) * 100)), "month"
