import React, { useState, useEffect, useCallback, useRef } from 'react';
import { api, useAuth } from '../context/AuthContext';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { Bell, Building2, CreditCard, AlertTriangle, Check, CheckCheck } from 'lucide-react';

const EVENT_ICONS = {
  new_company: { icon: Building2, bg: 'bg-blue-50', color: 'text-blue-600' },
  plan_change: { icon: CreditCard, bg: 'bg-purple-50', color: 'text-purple-600' },
  limit_warning: { icon: AlertTriangle, bg: 'bg-amber-50', color: 'text-amber-600' },
  limit_reached: { icon: AlertTriangle, bg: 'bg-red-50', color: 'text-red-600' },
};

export function NotificationBell() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef(null);

  const fetchUnreadCount = useCallback(async () => {
    try {
      const res = await api.get('/api/notifications/unread-count');
      setUnreadCount(res.data.count || 0);
    } catch {}
  }, []);

  useEffect(() => {
    if (user?.role !== 'superadmin') return;
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 30000);
    return () => clearInterval(interval);
  }, [user, fetchUnreadCount]);

  useEffect(() => {
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const loadNotifications = async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/notifications?limit=20');
      setNotifications(res.data || []);
    } catch {}
    setLoading(false);
  };

  const toggleOpen = () => {
    if (!open) loadNotifications();
    setOpen(!open);
  };

  const markAsRead = async (id) => {
    await api.put(`/api/notifications/${id}/read`).catch(() => {});
    setNotifications(prev => prev.map(n => n._id === id ? { ...n, is_read: true } : n));
    setUnreadCount(prev => Math.max(0, prev - 1));
  };

  const markAllAsRead = async () => {
    await api.put('/api/notifications/read-all').catch(() => {});
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    setUnreadCount(0);
  };

  const timeAgo = (dateStr) => {
    if (!dateStr) return '';
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'ahora';
    if (mins < 60) return `${mins}m`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h`;
    const days = Math.floor(hours / 24);
    return `${days}d`;
  };

  if (user?.role !== 'superadmin') return null;

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={toggleOpen}
        className="relative p-2 rounded-lg hover:bg-slate-100 transition-colors"
        data-testid="notification-bell"
      >
        <Bell className="w-5 h-5 text-slate-600" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center px-1"
            data-testid="notification-badge">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-white rounded-xl border border-slate-200 shadow-xl z-50 overflow-hidden"
          data-testid="notification-dropdown">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
            <h3 className="font-semibold text-sm text-slate-900">Notificaciones</h3>
            {unreadCount > 0 && (
              <button onClick={markAllAsRead} className="text-[11px] text-pine-700 hover:underline flex items-center gap-1" data-testid="mark-all-read">
                <CheckCheck className="w-3 h-3" /> Marcar todas leidas
              </button>
            )}
          </div>

          {/* List */}
          <ScrollArea className="max-h-[360px]">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-pine-900"></div>
              </div>
            ) : notifications.length === 0 ? (
              <div className="py-8 text-center text-slate-400">
                <Bell className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">Sin notificaciones</p>
              </div>
            ) : (
              <div>
                {notifications.map(n => {
                  const ev = EVENT_ICONS[n.event_type] || EVENT_ICONS.new_company;
                  const Icon = ev.icon;
                  return (
                    <div
                      key={n._id}
                      className={`flex items-start gap-3 px-4 py-3 border-b border-slate-50 hover:bg-slate-50/80 transition-colors cursor-pointer ${
                        !n.is_read ? 'bg-blue-50/40' : ''
                      }`}
                      onClick={() => !n.is_read && markAsRead(n._id)}
                      data-testid={`notification-item-${n._id}`}
                    >
                      <div className={`mt-0.5 w-8 h-8 rounded-lg ${ev.bg} flex items-center justify-center flex-shrink-0`}>
                        <Icon className={`w-4 h-4 ${ev.color}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <p className={`text-sm leading-tight ${!n.is_read ? 'font-semibold text-slate-900' : 'text-slate-700'}`}>{n.title}</p>
                          {!n.is_read && <span className="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0 mt-1.5"></span>}
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{n.message}</p>
                        <p className="text-[10px] text-slate-400 mt-1">{timeAgo(n.created_at)}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </ScrollArea>
        </div>
      )}
    </div>
  );
}
