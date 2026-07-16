'use client';

// Client-side route guard. Wrap any page/section that requires a signed-in user.
// While the session is still hydrating it shows a spinner; if there's no user it
// redirects to /login?next=<current path> so the user returns here after signing in.
// Optionally restrict to specific roles.

import React, { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { UserRole } from '@/lib/auth-storage';

export default function RequireAuth({
  children,
  roles,
}: {
  children: React.ReactNode;
  roles?: UserRole[];
}) {
  const { user, isAuthenticated, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading) return;
    if (!isAuthenticated) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [loading, isAuthenticated, pathname, router]);

  if (loading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-moss" />
      </div>
    );
  }

  if (roles && user && !roles.includes(user.role)) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="max-w-md text-center">
          <h1 className="text-xl font-semibold text-gray-900">This area isn&apos;t available for your account</h1>
          <p className="mt-2 text-gray-600">
            Your account type doesn&apos;t have access to this page. Head back to your dashboard.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
