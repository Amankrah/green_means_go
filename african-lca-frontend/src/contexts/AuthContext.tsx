'use client';

// AuthContext — the single source of truth for who is signed in on the client.
//
// It mirrors the localStorage-backed session (see lib/auth-storage) into React state,
// exposes sign-up / sign-in / sign-out, and re-reads storage whenever the API client
// refreshes a token or forces a sign-out (via the AUTH_CHANGED event or another tab).

import React, { createContext, useContext, useCallback, useEffect, useMemo, useState } from 'react';
import { assessmentAPI, SignupRequest } from '@/lib/api';
import {
  AUTH_CHANGED_EVENT,
  AuthUser,
  getAccessToken,
  getStoredUser,
} from '@/lib/auth-storage';

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  // True until the first client-side read of stored session completes, so guards can
  // avoid redirecting before we know whether someone is signed in.
  loading: boolean;
  login: (email: string, password: string) => Promise<AuthUser>;
  signup: (data: SignupRequest) => Promise<AuthUser>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Hydrate from storage on mount, and stay in sync with token refreshes / other tabs.
  useEffect(() => {
    const sync = () => {
      const token = getAccessToken();
      setUser(token ? getStoredUser() : null);
    };
    sync();
    setLoading(false);
    window.addEventListener(AUTH_CHANGED_EVENT, sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener(AUTH_CHANGED_EVENT, sync);
      window.removeEventListener('storage', sync);
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const resp = await assessmentAPI.login(email, password);
    setUser(resp.user);
    return resp.user;
  }, []);

  const signup = useCallback(async (data: SignupRequest) => {
    const resp = await assessmentAPI.signup(data);
    setUser(resp.user);
    return resp.user;
  }, []);

  const logout = useCallback(async () => {
    await assessmentAPI.logout();
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const me = await assessmentAPI.getMe();
      setUser(me);
    } catch {
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isAuthenticated: !!user, loading, login, signup, logout, refreshUser }),
    [user, loading, login, signup, logout, refreshUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
