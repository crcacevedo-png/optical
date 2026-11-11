"""Catalogo de monedas (LatAm + USD). Solo presentacion: simbolo y decimales.
Se usa en los generadores de PDF/Excel para reflejar la moneda de cada optica.
Debe mantenerse en sincronia con frontend/src/lib/currency.js.
"""

CURRENCIES = [
    {"code": "GTQ", "name": "Quetzal", "country": "Guatemala", "symbol": "Q", "decimals": 2},
    {"code": "USD", "name": "Dolar", "country": "EE.UU. / Ecuador / El Salvador / Panama", "symbol": "$", "decimals": 2},
    {"code": "MXN", "name": "Peso mexicano", "country": "Mexico", "symbol": "$", "decimals": 2},
    {"code": "COP", "name": "Peso colombiano", "country": "Colombia", "symbol": "$", "decimals": 2},
    {"code": "CLP", "name": "Peso chileno", "country": "Chile", "symbol": "$", "decimals": 0},
    {"code": "ARS", "name": "Peso argentino", "country": "Argentina", "symbol": "$", "decimals": 2},
    {"code": "PEN", "name": "Sol", "country": "Peru", "symbol": "S/", "decimals": 2},
    {"code": "BOB", "name": "Boliviano", "country": "Bolivia", "symbol": "Bs", "decimals": 2},
    {"code": "PYG", "name": "Guarani", "country": "Paraguay", "symbol": "\u20B2", "decimals": 0},
    {"code": "UYU", "name": "Peso uruguayo", "country": "Uruguay", "symbol": "$U", "decimals": 2},
    {"code": "HNL", "name": "Lempira", "country": "Honduras", "symbol": "L", "decimals": 2},
    {"code": "NIO", "name": "Cordoba", "country": "Nicaragua", "symbol": "C$", "decimals": 2},
    {"code": "CRC", "name": "Colon", "country": "Costa Rica", "symbol": "\u20A1", "decimals": 2},
    {"code": "DOP", "name": "Peso dominicano", "country": "Republica Dominicana", "symbol": "RD$", "decimals": 2},
    {"code": "BRL", "name": "Real", "country": "Brasil", "symbol": "R$", "decimals": 2},
    {"code": "VES", "name": "Bolivar", "country": "Venezuela", "symbol": "Bs.", "decimals": 2},
]

DEFAULT_CURRENCY = "GTQ"
_BY_CODE = {c["code"]: c for c in CURRENCIES}


def is_valid_currency(code) -> bool:
    return code in _BY_CODE


def get_currency(code):
    return _BY_CODE.get(code) or _BY_CODE[DEFAULT_CURRENCY]


def currency_symbol(code) -> str:
    return get_currency(code)["symbol"]


def format_amount(value, code="GTQ") -> str:
    """Formatea un monto con el simbolo y los decimales de la moneda. Agrupa con coma (estilo LatAm)."""
    c = get_currency(code)
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        n = 0.0
    num = f"{n:,.{c['decimals']}f}"
    return f"{c['symbol']} {num}"


def excel_number_format(code="GTQ") -> str:
    """Formato numerico de openpyxl con el simbolo de la moneda (0 decimales para CLP/PYG)."""
    c = get_currency(code)
    base = "#,##0.00" if c["decimals"] else "#,##0"
    return f'"{c["symbol"]} "{base}'


def company_currency(company) -> str:
    """Devuelve el codigo de moneda de la optica (default GTQ)."""
    code = (company or {}).get("currency")
    return code if code in _BY_CODE else DEFAULT_CURRENCY
