'use client';

import React, { Suspense, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2, Sprout, Users, Factory } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { UserRole } from '@/lib/auth-storage';

export const dynamic = 'force-dynamic';

const ROLES: { value: UserRole; label: string; blurb: string; icon: React.ElementType }[] = [
  {
    value: 'farmer',
    label: 'Farmer or farm organization',
    blurb: 'Assess and track the sustainability of your own farm.',
    icon: Sprout,
  },
  {
    value: 'extension_officer',
    label: 'Agricultural extension officer',
    blurb: 'Run and manage assessments for many farmers you support.',
    icon: Users,
  },
  {
    value: 'processor',
    label: 'Industrial processor',
    blurb: 'Assess the footprint of your food processing facilities.',
    icon: Factory,
  },
];

function SignupForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get('next') || '/dashboard';
  const { signup } = useAuth();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [organization, setOrganization] = useState('');
  const [role, setRole] = useState<UserRole>('farmer');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    setSubmitting(true);
    try {
      await signup({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        role,
        organization: organization.trim() || undefined,
      });
      router.push(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create your account. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-paper flex flex-col items-center justify-center px-4 py-12">
      <Link href="/" className="flex items-center space-x-3 mb-8">
        <Image src="/logo.svg" alt="Green Means Go" width={44} height={44} />
        <span className="text-xl font-bold text-gray-900">Green Means Go</span>
      </Link>

      <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
        <h1 className="text-2xl font-bold text-gray-900">Create your account</h1>
        <p className="mt-1 text-sm text-gray-500">Start measuring and improving sustainability.</p>

        <form onSubmit={onSubmit} className="mt-6 space-y-5">
          <div>
            <span className="block text-sm font-medium text-gray-700 mb-2">I am a…</span>
            <div className="grid gap-2">
              {ROLES.map((r) => {
                const Icon = r.icon;
                const active = role === r.value;
                return (
                  <button
                    type="button"
                    key={r.value}
                    onClick={() => setRole(r.value)}
                    className={`flex items-start gap-3 text-left rounded-xl border px-4 py-3 transition-colors ${
                      active
                        ? 'border-moss bg-moss/10 ring-2 ring-moss/25'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <Icon className={`w-5 h-5 mt-0.5 ${active ? 'text-moss' : 'text-gray-400'}`} />
                    <span>
                      <span className="block font-medium text-gray-900">{r.label}</span>
                      <span className="block text-sm text-gray-500">{r.blurb}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label htmlFor="fullName" className="block text-sm font-medium text-gray-700">Full name</label>
              <input
                id="fullName"
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-gray-900 focus:border-moss focus:ring-2 focus:ring-moss/30 outline-none"
              />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="organization" className="block text-sm font-medium text-gray-700">
                Organization <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <input
                id="organization"
                type="text"
                value={organization}
                onChange={(e) => setOrganization(e.target.value)}
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-gray-900 focus:border-moss focus:ring-2 focus:ring-moss/30 outline-none"
              />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">Email</label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-gray-900 focus:border-moss focus:ring-2 focus:ring-moss/30 outline-none"
              />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">Password</label>
              <input
                id="password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-gray-900 focus:border-moss focus:ring-2 focus:ring-moss/30 outline-none"
              />
              <p className="mt-1 text-xs text-gray-400">At least 8 characters.</p>
            </div>
          </div>

          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full flex items-center justify-center gap-2 rounded-lg bg-spruce px-4 py-2.5 font-medium text-white hover:bg-ink disabled:opacity-60 transition-colors"
          >
            {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
            {submitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="mt-6 text-sm text-gray-600 text-center">
          Already have an account?{' '}
          <Link href="/login" className="font-semibold text-moss hover:text-spruce">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={null}>
      <SignupForm />
    </Suspense>
  );
}
