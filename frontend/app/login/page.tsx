'use client';

import { useState } from 'react';
import { useAuth } from '@/lib/auth-context';
import { useRouter } from 'next/navigation';
import { Mail, Lock, User, ArrowRight, Stethoscope, Users } from 'lucide-react';

export default function LoginPage() {
  const [isSignup, setIsSignup] = useState(false);
  const [role, setRole] = useState<'patient' | 'supervisor' | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login, signup } = useAuth();
  const router = useRouter();

  const handleRoleSelect = (selectedRole: 'patient' | 'supervisor') => {
    setRole(selectedRole);
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      if (isSignup) {
        if (!name.trim()) {
          setError('Name is required');
          return;
        }
        await signup(email, password, name, role!);
      } else {
        await login(email, password, role!);
      }
      router.push(isSignup && role === 'patient' ? '/dashboard/profile?onboarding=1' : '/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  // Role selection screen
  if (!role) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background via-background to-primary/5 flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          {/* Header */}
          <div className="mb-12 text-center">
            <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-primary/60">
              <span className="text-2xl font-bold text-white">N</span>
            </div>
            <h1 className="text-3xl font-bold text-foreground mb-2">NutriLoop</h1>
            <p className="text-foreground/60">AI-Driven Diet Management</p>
          </div>

          {/* Role Selection Cards */}
          <div className="space-y-4">
            <button
              onClick={() => handleRoleSelect('patient')}
              className="group relative w-full rounded-2xl border-2 border-primary/20 bg-background/40 backdrop-blur-sm p-6 text-left transition-all duration-300 hover:border-primary/60 hover:bg-primary/5"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/20 group-hover:bg-primary/30 transition-colors">
                    <Users className="h-6 w-6 text-primary" />
                  </div>
                  <h3 className="text-lg font-semibold text-foreground mb-1">Patient Login</h3>
                  <p className="text-sm text-foreground/60">Track your nutrition & health metrics</p>
                </div>
                <ArrowRight className="h-5 w-5 text-primary/40 group-hover:text-primary group-hover:translate-x-1 transition-all" />
              </div>
            </button>

            <button
              onClick={() => handleRoleSelect('supervisor')}
              className="group relative w-full rounded-2xl border-2 border-accent/20 bg-background/40 backdrop-blur-sm p-6 text-left transition-all duration-300 hover:border-accent/60 hover:bg-accent/5"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-lg bg-accent/20 group-hover:bg-accent/30 transition-colors">
                    <Stethoscope className="h-6 w-6 text-accent" />
                  </div>
                  <h3 className="text-lg font-semibold text-foreground mb-1">Supervisor Login</h3>
                  <p className="text-sm text-foreground/60">Manage patients & approve meal plans</p>
                </div>
                <ArrowRight className="h-5 w-5 text-accent/40 group-hover:text-accent group-hover:translate-x-1 transition-all" />
              </div>
            </button>
          </div>

          {/* Demo Credentials */}
          <div className="mt-8 rounded-xl border border-primary/10 bg-primary/5 p-4">
            <p className="text-xs font-semibold text-foreground/60 uppercase tracking-wide mb-2">Demo Credentials</p>
            <div className="space-y-2 text-sm">
              <div>
                <p className="text-foreground font-medium">Patient:</p>
                <code className="text-primary/80">patient@nutriloop.com / patient123</code>
              </div>
              <div>
                <p className="text-foreground font-medium">Supervisor:</p>
                <code className="text-accent/80">supervisor@nutriloop.com / supervisor123</code>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Login/Signup form screen
  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-primary/5 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Header with back button */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-foreground">
              {isSignup ? 'Create Account' : 'Welcome Back'}
            </h2>
            <p className="text-sm text-foreground/60 mt-1">
              {role === 'patient' ? 'Patient' : 'Supervisor'} Account
            </p>
          </div>
          <button
            onClick={() => {
              setRole(null);
              setError('');
              setEmail('');
              setPassword('');
              setName('');
            }}
            className="text-foreground/40 hover:text-foreground/70 transition-colors"
          >
            ← Back
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Signup Name Field */}
          {isSignup && (
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-foreground mb-2">
                Full Name
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-foreground/40" />
                <input
                  id="name"
                  type="text"
                  placeholder="Enter your full name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-lg border border-primary/20 bg-background/40 backdrop-blur-sm pl-10 pr-4 py-2.5 text-foreground placeholder-foreground/40 focus:border-primary/60 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                  required={isSignup}
                />
              </div>
            </div>
          )}

          {/* Email Field */}
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-foreground mb-2">
              Email Address
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-foreground/40" />
              <input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-primary/20 bg-background/40 backdrop-blur-sm pl-10 pr-4 py-2.5 text-foreground placeholder-foreground/40 focus:border-primary/60 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                required
              />
            </div>
          </div>

          {/* Password Field */}
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-foreground mb-2">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-foreground/40" />
              <input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-primary/20 bg-background/40 backdrop-blur-sm pl-10 pr-4 py-2.5 text-foreground placeholder-foreground/40 focus:border-primary/60 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                required
              />
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3">
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isLoading}
            className="w-full rounded-lg bg-gradient-to-r from-primary to-primary/80 px-4 py-2.5 font-medium text-white hover:shadow-lg hover:shadow-primary/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300"
          >
            {isLoading ? (
              <span className="flex items-center justify-center gap-2">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                {isSignup ? 'Creating account...' : 'Signing in...'}
              </span>
            ) : isSignup ? (
              'Create Account'
            ) : (
              'Sign In'
            )}
          </button>

          {/* Toggle Login/Signup */}
          <div className="text-center pt-2">
            <p className="text-sm text-foreground/60">
              {isSignup ? 'Already have an account?' : "Don&apos;t have an account?"}{' '}
              <button
                type="button"
                onClick={() => {
                  setIsSignup(!isSignup);
                  setError('');
                  setName('');
                }}
                className="font-medium text-primary hover:text-primary/80 transition-colors"
              >
                {isSignup ? 'Sign In' : 'Sign Up'}
              </button>
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}
