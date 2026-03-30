import React, { useState, useEffect } from 'react';
import { api } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { 
  Users, Calendar, Receipt, TrendingUp, TrendingDown, 
  AlertTriangle, Clock, DollarSign, ShoppingBag
} from 'lucide-react';

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const { data } = await api.get('/api/reports/dashboard');
      setData(data);
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
      title: 'Ventas',
      value: data?.sales_count || 0,
      icon: ShoppingBag,
      color: 'bg-purple-50 text-purple-600',
      iconBg: 'bg-purple-100',
      subtitle: 'Este mes'
    },
    {
      title: 'Recetas',
      value: data?.prescriptions_count || 0,
      icon: Receipt,
      color: 'bg-amber-50 text-amber-600',
      iconBg: 'bg-amber-100',
      subtitle: 'Recientes'
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
      <div>
        <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900">Dashboard</h1>
        <p className="text-slate-500 mt-1">Resumen de operaciones del día</p>
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
            {data?.stock_alerts > 0 ? (
              <div className="p-4 rounded-lg bg-amber-50 border border-amber-200">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-amber-800">
                      {data.stock_alerts} producto{data.stock_alerts !== 1 ? 's' : ''} con stock bajo
                    </p>
                    <p className="text-sm text-amber-700 mt-1">
                      Revise el inventario para evitar faltantes.
                    </p>
                  </div>
                </div>
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
