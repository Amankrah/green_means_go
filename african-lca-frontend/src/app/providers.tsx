'use client';

// Client-side provider tree mounted once in the root layout. Currently just auth;
// future cross-cutting providers (theme, toasts) compose here.

import { AuthProvider } from '@/contexts/AuthContext';

export default function Providers({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}
