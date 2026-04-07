import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../context/AuthContext';
import { Dialog, DialogContent } from './ui/dialog';
import { Input } from './ui/input';
import { Search, User, Package, Eye, Command } from 'lucide-react';

const typeConfig = {
  patient: { icon: User, color: 'text-blue-600 bg-blue-50', label: 'Paciente', path: '/patients' },
  product: { icon: Package, color: 'text-amber-600 bg-amber-50', label: 'Producto', path: '/inventory' },
  consultation: { icon: Eye, color: 'text-pine-600 bg-pine-50', label: 'Consulta', path: '/consultations' },
};

export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(0);
  const inputRef = useRef(null);
  const navigate = useNavigate();
  const timerRef = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery('');
      setResults([]);
      setSelected(0);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  const doSearch = useCallback(async (q) => {
    if (q.length < 2) { setResults([]); return; }
    setLoading(true);
    try {
      const { data } = await api.get('/api/search', { params: { q } });
      setResults(data);
      setSelected(0);
    } catch { setResults([]); }
    finally { setLoading(false); }
  }, []);

  const handleChange = (e) => {
    const v = e.target.value;
    setQuery(v);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => doSearch(v), 250);
  };

  const handleSelect = (item) => {
    const cfg = typeConfig[item.type];
    setOpen(false);
    navigate(cfg.path);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelected(s => Math.min(s + 1, results.length - 1)); }
    if (e.key === 'ArrowUp') { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)); }
    if (e.key === 'Enter' && results[selected]) { handleSelect(results[selected]); }
    if (e.key === 'Escape') { setOpen(false); }
  };

  return (
    <>
      <button onClick={() => setOpen(true)} data-testid="global-search-trigger"
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-500 text-sm transition-colors border border-slate-200">
        <Search className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">Buscar...</span>
        <kbd className="hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-slate-200 text-[10px] font-mono text-slate-500 ml-2">
          <Command className="w-2.5 h-2.5" />K
        </kbd>
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="p-0 max-w-lg gap-0 overflow-hidden" data-testid="global-search-dialog">
          <div className="flex items-center gap-3 px-4 py-3 border-b">
            <Search className="w-4 h-4 text-slate-400 flex-shrink-0" />
            <Input ref={inputRef} value={query} onChange={handleChange} onKeyDown={handleKeyDown}
              placeholder="Buscar pacientes, productos, consultas..."
              className="border-0 shadow-none focus-visible:ring-0 h-8 text-sm px-0" data-testid="global-search-input" />
          </div>
          <div className="max-h-[320px] overflow-y-auto">
            {loading && (
              <div className="flex justify-center py-6">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-pine-700" />
              </div>
            )}
            {!loading && query.length >= 2 && results.length === 0 && (
              <div className="text-center py-8 text-slate-400 text-sm">
                Sin resultados para "{query}"
              </div>
            )}
            {!loading && results.length > 0 && (
              <div className="py-1">
                {results.map((item, idx) => {
                  const cfg = typeConfig[item.type];
                  const Icon = cfg.icon;
                  return (
                    <button key={`${item.type}-${item.id}`}
                      onClick={() => handleSelect(item)}
                      onMouseEnter={() => setSelected(idx)}
                      className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                        idx === selected ? 'bg-pine-50' : 'hover:bg-slate-50'
                      }`} data-testid={`search-result-${item.type}-${item.id}`}>
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${cfg.color}`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-900 truncate">{item.title}</p>
                        <p className="text-xs text-slate-500 truncate">{item.subtitle}</p>
                      </div>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 flex-shrink-0">{cfg.label}</span>
                    </button>
                  );
                })}
              </div>
            )}
            {!loading && query.length < 2 && (
              <div className="text-center py-8 text-slate-400 text-sm">
                Escriba al menos 2 caracteres para buscar
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
