// Catalogo de monedas para Latinoamerica + dolar. Solo cambia simbolo/formato;
// NO convierte cifras. La moneda activa la fija AuthContext segun la optica.

export const CURRENCIES = [
  { code: 'GTQ', name: 'Quetzal', country: 'Guatemala', symbol: 'Q', decimals: 2 },
  { code: 'USD', name: 'Dolar', country: 'EE.UU. / Ecuador / El Salvador / Panama', symbol: '$', decimals: 2 },
  { code: 'MXN', name: 'Peso mexicano', country: 'Mexico', symbol: '$', decimals: 2 },
  { code: 'COP', name: 'Peso colombiano', country: 'Colombia', symbol: '$', decimals: 2 },
  { code: 'CLP', name: 'Peso chileno', country: 'Chile', symbol: '$', decimals: 0 },
  { code: 'ARS', name: 'Peso argentino', country: 'Argentina', symbol: '$', decimals: 2 },
  { code: 'PEN', name: 'Sol', country: 'Peru', symbol: 'S/', decimals: 2 },
  { code: 'BOB', name: 'Boliviano', country: 'Bolivia', symbol: 'Bs', decimals: 2 },
  { code: 'PYG', name: 'Guarani', country: 'Paraguay', symbol: '\u20B2', decimals: 0 },
  { code: 'UYU', name: 'Peso uruguayo', country: 'Uruguay', symbol: '$U', decimals: 2 },
  { code: 'HNL', name: 'Lempira', country: 'Honduras', symbol: 'L', decimals: 2 },
  { code: 'NIO', name: 'Cordoba', country: 'Nicaragua', symbol: 'C$', decimals: 2 },
  { code: 'CRC', name: 'Colon', country: 'Costa Rica', symbol: '\u20A1', decimals: 2 },
  { code: 'DOP', name: 'Peso dominicano', country: 'Republica Dominicana', symbol: 'RD$', decimals: 2 },
  { code: 'BRL', name: 'Real', country: 'Brasil', symbol: 'R$', decimals: 2 },
  { code: 'VES', name: 'Bolivar', country: 'Venezuela', symbol: 'Bs.', decimals: 2 },
];

export const DEFAULT_CURRENCY = 'GTQ';

const BY_CODE = Object.fromEntries(CURRENCIES.map((c) => [c.code, c]));

export function getCurrency(code) {
  return BY_CODE[code] || BY_CODE[DEFAULT_CURRENCY];
}

// Moneda activa (singleton). AuthContext la actualiza al cargar/cambiar de usuario.
let _active = DEFAULT_CURRENCY;
export function setActiveCurrency(code) {
  _active = (code && BY_CODE[code]) ? code : DEFAULT_CURRENCY;
}
export function getActiveCurrency() {
  return _active;
}

export function formatCurrency(amount, code) {
  const c = getCurrency(code || _active);
  const n = Number(amount) || 0;
  const num = n.toLocaleString('es-GT', {
    minimumFractionDigits: c.decimals,
    maximumFractionDigits: c.decimals,
  });
  return `${c.symbol} ${num}`;
}
