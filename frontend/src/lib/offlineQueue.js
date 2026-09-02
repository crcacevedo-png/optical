// Cola de escritura offline cifrada (IndexedDB + Web Crypto AES-GCM).
// - Guarda peticiones mutantes (POST/PUT/PATCH/DELETE) cuando no hay conexion.
// - La clave AES es NO exportable y vive en IndexedDB: ni siquiera el JS puede
//   leer sus bytes; solo se usa para cifrar/descifrar dentro de este origen.
// - Cada item se purga apenas se sincroniza correctamente.

const DB_NAME = 'cortexia_offline';
const DB_VERSION = 1;
const STORE_OUTBOX = 'outbox';
const STORE_META = 'meta';
const KEY_ID = 'aes_key';

let _dbPromise = null;
function openDB() {
  if (_dbPromise) return _dbPromise;
  _dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_OUTBOX)) {
        db.createObjectStore(STORE_OUTBOX, { keyPath: 'id', autoIncrement: true });
      }
      if (!db.objectStoreNames.contains(STORE_META)) {
        db.createObjectStore(STORE_META, { keyPath: 'k' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return _dbPromise;
}

function _store(db, name, mode) {
  return db.transaction(name, mode).objectStore(name);
}
function _p(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// ---- Clave AES-GCM (no exportable) ----
let _keyPromise = null;
async function getKey() {
  if (_keyPromise) return _keyPromise;
  _keyPromise = (async () => {
    const db = await openDB();
    const existing = await _p(_store(db, STORE_META, 'readonly').get(KEY_ID));
    if (existing && existing.key) return existing.key;
    const key = await crypto.subtle.generateKey(
      { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']
    );
    await _p(_store(db, STORE_META, 'readwrite').put({ k: KEY_ID, key }));
    return key;
  })();
  return _keyPromise;
}

async function encryptJSON(obj) {
  const key = await getKey();
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const bytes = new TextEncoder().encode(JSON.stringify(obj));
  const cipher = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, bytes);
  return { iv: Array.from(iv), cipher: Array.from(new Uint8Array(cipher)) };
}
async function decryptJSON(payload) {
  const key = await getKey();
  const iv = new Uint8Array(payload.iv);
  const cipher = new Uint8Array(payload.cipher);
  const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, cipher);
  return JSON.parse(new TextDecoder().decode(plain));
}

function _changed() {
  try { window.dispatchEvent(new Event('cortexia:queue-changed')); } catch { /* noop */ }
}

// ---- API publica ----
export async function enqueue(item) {
  // item: { method, url, data, createdAt, label }
  const db = await openDB();
  const payload = await encryptJSON(item);
  await _p(_store(db, STORE_OUTBOX, 'readwrite').add({
    payload, createdAt: item.createdAt || Date.now(), status: 'pending',
  }));
  _changed();
}

export async function getAll() {
  const db = await openDB();
  const rows = await _p(_store(db, STORE_OUTBOX, 'readonly').getAll());
  const out = [];
  for (const row of rows) {
    try {
      const data = await decryptJSON(row.payload);
      out.push({ id: row.id, status: row.status, error: row.error, createdAt: row.createdAt, ...data });
    } catch { /* item corrupto: se ignora */ }
  }
  return out;
}

export async function remove(id) {
  const db = await openDB();
  await _p(_store(db, STORE_OUTBOX, 'readwrite').delete(id));
  _changed();
}

export async function markFailed(id, errorMsg) {
  const db = await openDB();
  const st = _store(db, STORE_OUTBOX, 'readwrite');
  const row = await _p(st.get(id));
  if (row) {
    row.status = 'failed';
    row.error = String(errorMsg || 'Error');
    await _p(st.put(row));
    _changed();
  }
}

export async function clearFailed() {
  const db = await openDB();
  const rows = await _p(_store(db, STORE_OUTBOX, 'readonly').getAll());
  const st = _store(db, STORE_OUTBOX, 'readwrite');
  for (const row of rows) {
    if (row.status === 'failed') await _p(st.delete(row.id));
  }
  _changed();
}

export async function count() {
  const db = await openDB();
  return _p(_store(db, STORE_OUTBOX, 'readonly').count());
}
