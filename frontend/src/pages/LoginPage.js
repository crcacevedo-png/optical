import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, formatApiErrorDetail } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Eye, EyeOff, Glasses } from 'lucide-react';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || 'Error al iniciar sesión');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" data-testid="login-page">
      {/* Left Side - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-white">
        <div className="w-full max-w-md">
          {/* Logo */}
          <div className="flex items-center justify-center mb-8">
            <img 
              src="https://customer-assets.emergentagent.com/job_eyecare-erp/artifacts/80lobcqc_logo%20cortexia%20optical%20transparente.png" 
              alt="Cortexia Optical" 
              className="h-60 object-contain"
            />
          </div>

          <Card className="border-0 shadow-none">
            <CardHeader className="px-0">
              <CardTitle className="font-heading text-2xl">Bienvenido</CardTitle>
              <CardDescription>Ingrese sus credenciales para acceder al sistema</CardDescription>
            </CardHeader>
            <CardContent className="px-0">
              <form onSubmit={handleSubmit} className="space-y-4">
                {error && (
                  <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm" data-testid="login-error">
                    {error}
                  </div>
                )}

                <div className="space-y-2">
                  <Label htmlFor="email">Correo electrónico</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="correo@ejemplo.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    data-testid="login-email-input"
                    className="h-11"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password">Contraseña</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      data-testid="login-password-input"
                      className="h-11 pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    >
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                </div>

                <Button
                  type="submit"
                  className="w-full h-11 bg-pine-900 hover:bg-pine-700 text-white font-medium"
                  disabled={loading}
                  data-testid="login-submit-button"
                >
                  {loading ? 'Iniciando sesión...' : 'Iniciar Sesión'}
                </Button>
              </form>

              {/* Demo credentials */}
              <div className="mt-6 p-4 rounded-lg bg-slate-50 border border-slate-200">
                <p className="text-xs font-medium text-slate-500 mb-2">CREDENCIALES DE DEMOSTRACIÓN</p>
                <div className="space-y-1 text-sm text-slate-600">
                  <p><span className="font-medium">Admin:</span> admin@visionclara.gt / Demo123!</p>
                  <p><span className="font-medium">Usuario:</span> vendedor@visionclara.gt / Demo123!</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Right Side - Image */}
      <div 
        className="hidden lg:flex flex-1 relative"
        style={{
          backgroundImage: 'url(https://images.pexels.com/photos/2078266/pexels-photo-2078266.jpeg)',
          backgroundSize: 'cover',
          backgroundPosition: 'center'
        }}
      >
        <div className="absolute inset-0 bg-pine-900/80 flex items-center justify-center p-12">
          <div className="max-w-lg text-center">
            <h2 className="font-heading text-4xl font-semibold text-white mb-4">
              Gestione su óptica de manera eficiente
            </h2>
            <p className="text-pine-100 text-lg leading-relaxed">
              Control total de pacientes, inventario, ventas y finanzas en una sola plataforma diseñada para ópticas en Guatemala.
            </p>
            
            {/* Testimonial card */}
            <div className="mt-8 p-6 rounded-xl bg-white/10 backdrop-blur-md border border-white/20">
              <p className="text-white/90 italic mb-4">
                "OptiSaaS transformó la manera en que administramos nuestra óptica. Ahora tenemos control total de todo."
              </p>
              <div className="flex items-center justify-center gap-3">
                <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center text-white font-medium">
                  CM
                </div>
                <div className="text-left">
                  <p className="text-white font-medium text-sm">Carlos Mendoza</p>
                  <p className="text-white/70 text-xs">Óptica Visión Clara</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
