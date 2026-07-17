// Small localStorage-backed token/user store, shared by the API client (which attaches
// the access token and refreshes it) and the AuthContext (which mirrors it into React
// state). Kept as a plain module so api.ts and the context don't import each other.

export type UserRole = 'extension_officer' | 'farmer' | 'processor' | 'researcher';

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  organization?: string | null;
  phone?: string | null;
  country?: string | null;
  is_active: boolean;
  email_verified: boolean;
  created_at: string;
}

const ACCESS_KEY = 'gmg_access_token';
const REFRESH_KEY = 'gmg_refresh_token';
const USER_KEY = 'gmg_user';

const isBrowser = () => typeof window !== 'undefined';

// Notifies the AuthContext when tokens/user change from outside React (e.g. a refresh
// or a forced sign-out inside the API client), so the UI can react in the same tab.
export const AUTH_CHANGED_EVENT = 'gmg-auth-changed';

function emitAuthChanged() {
  if (isBrowser()) window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
}

export function getAccessToken(): string | null {
  return isBrowser() ? window.localStorage.getItem(ACCESS_KEY) : null;
}

export function getRefreshToken(): string | null {
  return isBrowser() ? window.localStorage.getItem(REFRESH_KEY) : null;
}

export function getStoredUser(): AuthUser | null {
  if (!isBrowser()) return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function setSession(tokens: { access_token: string; refresh_token: string }, user: AuthUser): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(ACCESS_KEY, tokens.access_token);
  window.localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  emitAuthChanged();
}

export function setAccessToken(token: string): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(ACCESS_KEY, token);
}

export function setStoredUser(user: AuthUser): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  emitAuthChanged();
}

export function clearSession(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
  window.localStorage.removeItem(USER_KEY);
  // Also drop cached assessment results so a shared browser doesn't leak the previous
  // user's data (results are re-fetched from the ownership-scoped backend on demand).
  for (let i = window.localStorage.length - 1; i >= 0; i -= 1) {
    const key = window.localStorage.key(i);
    if (key && (key.startsWith('assessment_') || key === 'lastAssessmentId' || key === 'lastFuelDebug')) {
      window.localStorage.removeItem(key);
    }
  }
  emitAuthChanged();
}
