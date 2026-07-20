'use client';

import React, { Suspense, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2, Sprout, Users, Factory, FlaskConical } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useAuth } from '@/contexts/AuthContext';
import { UserRole } from '@/lib/auth-storage';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';

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
  {
    value: 'researcher',
    label: 'Researcher',
    blurb: 'Run both farm and processing assessments for research and analysis.',
    icon: FlaskConical,
  },
];

const signupSchema = z.object({
  fullName: z.string().min(2, 'Full name is required'),
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  organization: z.string().optional(),
  role: z.enum(['farmer', 'extension_officer', 'processor', 'researcher']),
});

type SignupFormData = z.infer<typeof signupSchema>;

function SignupForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get('next') || '/dashboard';
  const { signup } = useAuth();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<SignupFormData>({
    resolver: zodResolver(signupSchema),
    defaultValues: {
      role: 'farmer',
      organization: '',
    },
  });

  const selectedRole = watch('role');

  const onSubmit = async (data: SignupFormData) => {
    setSubmitError(null);
    try {
      await signup({
        full_name: data.fullName.trim(),
        email: data.email.trim(),
        password: data.password,
        role: data.role,
        organization: data.organization?.trim() || undefined,
      });
      router.push(next);
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : 'Could not create your account. Please try again.'
      );
    }
  };

  return (
    <div className="min-h-screen bg-paper flex flex-col items-center justify-center px-4 py-12">
      <Link href="/" className="flex items-center space-x-3 mb-8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-moss/80 rounded-md">
        <Image src="/logo.svg" alt="Green Means Go" width={44} height={44} aria-hidden="true" />
        <span className="text-xl font-bold text-gray-900">Green Means Go</span>
      </Link>

      <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
        <h1 className="text-2xl font-bold text-gray-900">Create your account</h1>
        <p className="mt-1 text-sm text-gray-500">Start measuring and improving sustainability.</p>

        <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-6">
          <div>
            <span className="block text-sm font-medium text-gray-700 mb-2">I am a…</span>
            <div className="grid gap-2">
              {ROLES.map((r) => {
                const Icon = r.icon;
                const active = selectedRole === r.value;
                return (
                  <button
                    type="button"
                    key={r.value}
                    onClick={() => setValue('role', r.value, { shouldValidate: true })}
                    className={`flex items-start gap-3 text-left rounded-xl border px-4 py-3 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-moss/80 ${
                      active
                        ? 'border-moss bg-moss/10 ring-2 ring-moss/25'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <Icon className={`w-5 h-5 mt-0.5 transition-colors ${active ? 'text-moss' : 'text-gray-400'}`} />
                    <span>
                      <span className="block font-medium text-gray-900">{r.label}</span>
                      <span className="block text-sm text-gray-500">{r.blurb}</span>
                    </span>
                  </button>
                );
              })}
            </div>
            {errors.role && <p className="mt-1.5 text-sm text-red-600 font-medium">{errors.role.message}</p>}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2 space-y-1.5">
              <Label htmlFor="fullName">Full name</Label>
              <Input
                id="fullName"
                placeholder="Jane Doe"
                {...register('fullName')}
                aria-invalid={!!errors.fullName}
                className={errors.fullName ? 'border-red-500 focus-visible:ring-red-500' : ''}
              />
              {errors.fullName && <p className="text-sm text-red-600 font-medium">{errors.fullName.message}</p>}
            </div>

            <div className="sm:col-span-2 space-y-1.5">
              <Label htmlFor="organization">
                Organization <span className="text-gray-400 font-normal">(optional)</span>
              </Label>
              <Input
                id="organization"
                placeholder="Green Farms Ltd."
                {...register('organization')}
                aria-invalid={!!errors.organization}
                className={errors.organization ? 'border-red-500 focus-visible:ring-red-500' : ''}
              />
              {errors.organization && <p className="text-sm text-red-600 font-medium">{errors.organization.message}</p>}
            </div>

            <div className="sm:col-span-2 space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="jane@example.com"
                {...register('email')}
                aria-invalid={!!errors.email}
                className={errors.email ? 'border-red-500 focus-visible:ring-red-500' : ''}
              />
              {errors.email && <p className="text-sm text-red-600 font-medium">{errors.email.message}</p>}
            </div>

            <div className="sm:col-span-2 space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                {...register('password')}
                aria-invalid={!!errors.password}
                className={errors.password ? 'border-red-500 focus-visible:ring-red-500' : ''}
              />
              {errors.password ? (
                <p className="text-sm text-red-600 font-medium">{errors.password.message}</p>
              ) : (
                <p className="text-xs text-gray-500">At least 8 characters.</p>
              )}
            </div>
          </div>

          {submitError && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-sm font-medium text-red-700">
              {submitError}
            </div>
          )}

          <Button
            type="submit"
            disabled={isSubmitting}
            className="w-full h-11 text-base bg-spruce hover:bg-ink text-white"
          >
            {isSubmitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {isSubmitting ? 'Creating account…' : 'Create account'}
          </Button>
        </form>

        <p className="mt-6 text-sm text-gray-600 text-center">
          Already have an account?{' '}
          <Link href="/login" className="font-semibold text-moss hover:text-spruce focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-moss/80 rounded-sm">
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
