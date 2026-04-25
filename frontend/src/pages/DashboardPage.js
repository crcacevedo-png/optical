import React, { useState, useEffect } from 'react';
import { api, useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { 
  Users, Calendar, TrendingUp, TrendingDown, 
  AlertTriangle, Clock, DollarSign, ShoppingBag, CreditCard
} from 'lucide-react';
import { BranchFilter } from '../components/BranchFilter';

export default function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [alertDetails, setAlertDetails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [branchId, setBranchId] = useState('');

  useEffect(() => {
    fetchDashboard();
  }, [branchId]);

  const fetchDashboard = async () => {
    try {
      const params = branchId ? { branch_id: branchId } : {};
      const [dashRes, alertsRes] = await Promise.all([
        api.get('/api/reports/dashboard', { params }),
        api.get('/api/inventory/alerts', { params }).catch(() => ({ data: [] }))
      ]);
      setData(dashRes.data);
      setAlertDetails(alertsRes.data || []);
    } catch (error) {
      console.error('Error fetching dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount) => {
    return `Q ${(amount || 0).toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pine-900"></div>
      </div>
    );
  }

  const stats = [
    {
      title: 'Citas Hoy',
      value: data?.appointments_today || 0,
      icon: Calendar,
      color: 'bg-blue-50 text-blue-600',
      iconBg: 'bg-blue-100'
    },
    {
      title: 'Pacientes Nuevos',
      value: data?.new_patients || 0,
      icon: Users,
      color: 'bg-green-50 text-green-600',
      iconBg: 'bg-green-100',
      subtitle: 'Este mes'
    },
    {
      title: 'Ventas Hoy',
      value: data?.sales_count_today || 0,
      icon: ShoppingBag,
      color: 'bg-purple-50 text-purple-600',
      iconBg: 'bg-purple-100',
      subtitle: formatCurrency(data?.total_sales_today)
    },
    {
      title: 'Alertas Stock',
      value: data?.stock_alerts || 0,
      icon: AlertTriangle,
      color: 'bg-amber-50 text-amber-600',
      iconBg: 'bg-amber-100',
      subtitle: 'Productos bajos'
    }
  ];

  const financeStats = [
    {
      title: 'Ingresos',
      value: formatCurrency(data?.income),
      icon: TrendingUp,
      color: 'text-green-600',
      bgColor: 'bg-green-50'
    },
    {
      title: 'Egresos',
      value: formatCurrency(data?.expense),
      icon: TrendingDown,
      color: 'text-red-600',
      bgColor: 'bg-red-50'
    },
    {
      title: 'Utilidad',
      value: formatCurrency(data?.profit),
      icon: DollarSign,
      color: data?.profit >= 0 ? 'text-green-600' : 'text-red-600',
      bgColor: data?.profit >= 0 ? 'bg-green-50' : 'bg-red-50'
    }
  ];

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Dashboard</h1>
          <p className="text-slate-500 mt-1">Resumen de operaciones del dia</p>
        </div>
        <BranchFilter value={branchId} onChange={setBranchId} />
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, index) => (
          <Card key={index} className="border-slate-200/80" data-testid={`stat-card-${index}`}>
            <CardContent className="p-5">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{stat.title}</p>
                  <p className="font-heading text-3xl font-bold text-slate-900 mt-1">{stat.value}</p>
                  {stat.subtitle && (
                    <p className="text-xs text-slate-400 mt-1">{stat.subtitle}</p>
                  )}
                </div>
                <div className={`p-2.5 rounded-lg ${stat.iconBg}`}>
                  <stat.icon className={`w-5 h-5 ${stat.color.split(' ')[1]}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Finance Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {financeStats.map((stat, index) => (
          <Card key={index} className={`border-0 ${stat.bgColor}`} data-testid={`finance-card-${index}`}>
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-600">{stat.title}</p>
                  <p className={`font-heading text-2xl font-bold mt-1 ${stat.color}`}>{stat.value}</p>
                </div>
                <stat.icon className={`w-8 h-8 ${stat.color} opacity-50`} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Bottom Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upcoming Appointments */}
        <Card className="border-slate-200/80" data-testid="upcoming-appointments">
          <CardHeader className="pb-3">
            <CardTitle className="font-heading text-lg flex items-center gap-2">
              <Clock className="w-5 h-5 text-pine-700" />
              Próximas Citas
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data?.upcoming_appointments?.length > 0 ? (
              <div className="space-y-3">
                {data.upcoming_appointments.map((apt, index) => (
                  <div 
                    key={apt._id || index} 
                    className="flex items-center justify-between p-3 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-pine-100 flex items-center justify-center text-pine-700 font-medium text-sm">
                        {apt.patient_name?.split(' ').map(n => n[0]).join('').slice(0, 2) || 'P'}
                      </div>
                      <div>
                        <p className="font-medium text-slate-900 text-sm">{apt.patient_name || 'Paciente'}</p>
                        <p className="text-xs text-slate-500">{apt.type || 'Consulta'}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-medium text-slate-900 text-sm">{apt.time}</p>
                      <p className="text-xs text-slate-500">{apt.date}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-slate-500">
                <Calendar className="w-12 h-12 mx-auto mb-2 opacity-30" />
                <p>No hay citas próximas</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Stock Alerts */}
        <Card className="border-slate-200/80" data-testid="stock-alerts">
          <CardHeader className="pb-3">
            <CardTitle className="font-heading text-lg flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-500" />
              Alertas de Inventario
            </CardTitle>
          </CardHeader>
          <CardContent>
            {alertDetails.length > 0 ? (
              <div className="space-y-2">
                {alertDetails.slice(0, 5).map((a) => (
                  <div key={a.product_id} className="flex items-center justify-between p-3 rounded-lg bg-amber-50 border border-amber-100" data-testid={`dashboard-alert-${a.product_id}`}>
                    <div>
                      <p className="text-sm font-medium text-slate-900">{a.product_name}</p>
                      <p className="text-xs text-slate-500">{a.sku}</p>
                    </div>
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-800">
                      {a.current_stock} / {a.min_stock}
                    </span>
                  </div>
                ))}
                {alertDetails.length > 5 && (
                  <p className="text-xs text-amber-600 text-center pt-1">
                    y {alertDetails.length - 5} producto{alertDetails.length - 5 > 1 ? 's' : ''} mas
                  </p>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-slate-500">
                <AlertTriangle className="w-12 h-12 mx-auto mb-2 opacity-30" />
                <p>Sin alertas de inventario</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
