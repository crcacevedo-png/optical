import React, { useState, useEffect } from 'react';
import { api } from '../context/AuthContext';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Building2 } from 'lucide-react';

export function BranchFilter({ value, onChange, className = '' }) {
  const [branches, setBranches] = useState([]);

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await api.get('/api/branches');
        setBranches(data || []);
      } catch (e) {
        console.error('Error loading branches:', e);
      }
    };
    load();
  }, []);

  if (branches.length <= 1) return null;

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <Building2 className="w-4 h-4 text-slate-400 flex-shrink-0" />
      <Select value={value || 'todas'} onValueChange={(v) => onChange(v === 'todas' ? '' : v)}>
        <SelectTrigger className="w-[200px] h-9" data-testid="branch-filter">
          <SelectValue placeholder="Todas las sucursales" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="todas">Todas las sucursales</SelectItem>
          {branches.map((b) => (
            <SelectItem key={b._id} value={b._id}>{b.name}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
