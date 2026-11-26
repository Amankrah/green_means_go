/**
 * result-cache.ts: browser-side cache of assessment results, keyed `assessment_<id>`.
 *
 * The backend is the source of truth; the cache only gives the results page an
 * instant first paint and survives backend restarts. Full payloads now carry the
 * engine inventory, the ISO report and per-crop detail, which can exceed the
 * browser's storage quota (about 5 MB per origin). So:
 *   1. heavy, re-fetchable sections are stripped before caching;
 *   2. a quota error evicts older cached assessments and retries once;
 *   3. a cache failure is never surfaced to the user (the server already has the result).
 */

const KEY_PREFIX = 'assessment_';
const LAST_KEY = 'lastAssessmentId';

/** Sections that are large and always re-fetched from the backend on the results page. */
const HEAVY_SECTIONS = [
  'engine_inventory',
  'engine_inventory_by_source',
  'inventory',
  'contribution_sankey',
  'iso_report',
  'sensitivity_analysis',
  'uncertainty',
  'method_variants',
] as const;

export function cacheKey(id: string): string {
  return `${KEY_PREFIX}${id}`;
}

function storage(): Storage | null {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null;
  } catch {
    return null;
  }
}

function isQuotaError(err: unknown): boolean {
  if (!(err instanceof DOMException)) return false;
  return (
    err.name === 'QuotaExceededError' ||
    err.name === 'NS_ERROR_DOM_QUOTA_REACHED' ||
    err.code === 22 ||
    err.code === 1014
  );
}

function slim<T extends object>(result: T): T {
  const copy: Record<string, unknown> = { ...(result as Record<string, unknown>) };
  for (const key of HEAVY_SECTIONS) delete copy[key];
  return copy as T;
}

/** Remove every cached assessment except the one being written. Oldest entries go first. */
function evictOthers(store: Storage, keep: string): number {
  const keys: string[] = [];
  for (let i = 0; i < store.length; i += 1) {
    const k = store.key(i);
    if (k && k.startsWith(KEY_PREFIX) && k !== keep) keys.push(k);
  }
  for (const k of keys) store.removeItem(k);
  return keys.length;
}

/**
 * Cache a result. Returns true when something was stored. Never throws.
 * `id` overrides the id inside the result (reruns navigate to the existing id).
 */
export function cacheAssessment(id: string, result: object): boolean {
  const store = storage();
  if (!store) return false;
  const key = cacheKey(id);
  const value = JSON.stringify({ ...slim(result), id });
  try {
    store.setItem(key, value);
    store.setItem(LAST_KEY, id);
    return true;
  } catch (err) {
    if (!isQuotaError(err)) return false;
  }
  try {
    evictOthers(store, key);
    store.setItem(key, value);
    store.setItem(LAST_KEY, id);
    return true;
  } catch {
    // Still too large for this browser: the results page will fetch from the backend.
    try {
      store.setItem(LAST_KEY, id);
    } catch {
      /* ignore */
    }
    return false;
  }
}

/** Read a cached result, or null when absent or unreadable. Never throws. */
export function readCachedAssessment<T = unknown>(id: string): T | null {
  const store = storage();
  if (!store) return null;
  try {
    const raw = store.getItem(cacheKey(id));
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export function clearCachedAssessment(id: string): void {
  const store = storage();
  if (!store) return;
  try {
    store.removeItem(cacheKey(id));
  } catch {
    /* ignore */
  }
}
