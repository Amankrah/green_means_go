// API service for the Green Means Go Backend

import { AssessmentRequest, AssessmentResult, FertilizerApplicationMethodPayload } from '@/types/assessment';
import { RecommendationsResponse } from '@/types/recommendations';
import {
  ApplicationMethod,
  EnhancedAssessmentRequest,
  FertilizerType,
  StorageFacilityType,
  isRiceCrop,
  isKnownAnnualCrop,
} from '@/types/enhanced-assessment';
import { COUNTRY_TO_REGION } from '@/lib/country-examples';
import { FARM_FUEL_DEFAULT_UNIT } from '@/lib/enhanced-assessment-schema';
import {
  AuthUser,
  UserRole,
  getAccessToken,
  getRefreshToken,
  setAccessToken,
  setSession,
  clearSession,
} from '@/lib/auth-storage';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Chat types
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

// A live progress event streamed from the /assess/stream (SSE) endpoints. `stage` is one of
// prepare | inventory | match | solve | characterize | report.
export interface AssessmentProgressEvent {
  stage: string;
  detail?: string;
  index?: number | null;
  total?: number | null;
}

// Auth payloads
export interface SignupRequest {
  email: string;
  password: string;
  full_name: string;
  role: UserRole;
  organization?: string;
  phone?: string;
  country?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: AuthUser;
}

// Saved-assessment summary rows returned by the dashboard/list endpoints.
export interface AssessmentSummary {
  id: string;
  type?: 'farm' | 'processing';
  title?: string | null;
  company_name?: string | null;
  country?: string | null;
  region?: string | null;
  farm_id?: string | null;
  facility_id?: string | null;
  single_score?: number | null;
  status?: string;
  assessment_date?: string | null;
  created_at?: string | null;
  /** True when the server stored the original submit payload for edit/re-run. */
  can_rerun?: boolean;
}

export interface AssessmentRequestArchive {
  id: string;
  type: 'farm' | 'processing' | string;
  title?: string | null;
  farm_id?: string | null;
  facility_id?: string | null;
  api: Record<string, unknown> | null;
  form: Record<string, unknown> | null;
}

export interface Farm {
  id: string;
  name: string;
  country?: string | null;
  region?: string | null;
  location?: string | null;
  size_ha?: number | null;
  notes?: string | null;
  farmer_name?: string | null;
  farmer_contact?: string | null;
  created_at: string;
}

export interface Facility {
  id: string;
  name: string;
  facility_type?: string | null;
  country?: string | null;
  region?: string | null;
  location?: string | null;
  notes?: string | null;
  created_at: string;
}

/** Thrown on any non-OK response; carries the HTTP status so callers can special-case 401. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

class AssessmentAPI {
  // Serialize concurrent refresh attempts so a burst of 401s triggers one refresh.
  private refreshInFlight: Promise<boolean> | null = null;

  private authHeaders(): Record<string, string> {
    const token = getAccessToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  /** Exchange the refresh token for a new access token. Returns false (and signs the
   *  user out) if there's no refresh token or it's rejected. Deduplicated. */
  private async refreshAccessToken(): Promise<boolean> {
    if (this.refreshInFlight) return this.refreshInFlight;
    this.refreshInFlight = (async () => {
      const refresh_token = getRefreshToken();
      if (!refresh_token) return false;
      try {
        const resp = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token }),
        });
        if (!resp.ok) {
          clearSession();
          return false;
        }
        const data = await resp.json();
        setAccessToken(data.access_token);
        return true;
      } catch {
        return false;
      } finally {
        this.refreshInFlight = null;
      }
    })();
    return this.refreshInFlight;
  }

  // Returns parsed JSON, whose shape is the caller's responsibility (each public method
  // annotates its own return type), so the body is intentionally dynamic here.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private async fetchAPI(endpoint: string, options: RequestInit = {}, retryOn401 = true): Promise<any> {
    const url = `${API_BASE_URL}${endpoint}`;

    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...this.authHeaders(),
        ...options.headers,
      },
    });

    // Transparently refresh once on an expired access token, then retry.
    if (response.status === 401 && retryOn401) {
      const refreshed = await this.refreshAccessToken();
      if (refreshed) return this.fetchAPI(endpoint, options, false);
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));

      let errorMessage = `API Error: ${response.status} ${response.statusText}`;

      if (errorData.detail) {
        if (Array.isArray(errorData.detail)) {
          errorMessage = errorData.detail.map((err: { msg?: string; message?: string; loc?: string[] }) =>
            err.msg || err.message || err.loc?.join('.') + ': ' + err.msg || JSON.stringify(err)
          ).join(', ');
        } else if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail;
        } else {
          errorMessage = JSON.stringify(errorData.detail);
        }
      }

      throw new ApiError(errorMessage, response.status);
    }

    // 204 No Content (e.g. DELETE) has no JSON body.
    if (response.status === 204) return null;
    return response.json();
  }

  // --- auth ----------------------------------------------------------------------

  async signup(data: SignupRequest): Promise<TokenResponse> {
    const resp: TokenResponse = await this.fetchAPI('/auth/signup', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    setSession(resp, resp.user);
    return resp;
  }

  async login(email: string, password: string): Promise<TokenResponse> {
    const resp: TokenResponse = await this.fetchAPI('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setSession(resp, resp.user);
    return resp;
  }

  async getMe(): Promise<AuthUser> {
    return this.fetchAPI('/auth/me');
  }

  async logout(): Promise<void> {
    try {
      await this.fetchAPI('/auth/logout', { method: 'POST' });
    } catch {
      // Stateless logout: clearing local tokens is what matters even if the call fails.
    } finally {
      clearSession();
    }
  }

  // --- workspace (saved assessments, farms, facilities) --------------------------

  async getMyAssessments(): Promise<{ assessments: AssessmentSummary[]; total: number }> {
    return this.fetchAPI('/me/assessments');
  }

  async getAssessmentRequest(id: string): Promise<AssessmentRequestArchive> {
    return this.fetchAPI(`/me/assessments/${id}/request`);
  }

  async deleteAssessment(id: string): Promise<void> {
    await this.fetchAPI(`/me/assessments/${id}`, { method: 'DELETE' });
  }

  /** Scenario compare: patch archived request, re-solve, return deltas. */
  async createScenario(
    id: string,
    patch: {
      name?: string;
      yield_scale?: number;
      n_rate_scale?: number;
      diesel_scale?: number;
    }
  ): Promise<{
    baseline_id: string;
    scenario_id: string;
    title: string;
    patch: Record<string, number>;
    delta_midpoints: Record<string, { value: number; unit?: string; baseline?: number; scenario?: number }>;
    delta_single_score: number | null;
    scenario: AssessmentResult;
  }> {
    return this.fetchAPI(`/assess/${id}/scenarios`, {
      method: 'POST',
      body: JSON.stringify(patch),
    });
  }

  /** Recharacterize with an alternate LCIA method; caches method_variants. */
  async recharacterizeAssessment(
    id: string,
    lcia_method: string,
    apply_as_primary = false
  ): Promise<AssessmentResult> {
    return this.fetchAPI(`/assess/${id}/recharacterize`, {
      method: 'POST',
      body: JSON.stringify({ lcia_method, apply_as_primary }),
    });
  }

  /** Run pedigree screening Monte Carlo on a saved assessment. */
  async runAssessmentUncertainty(id: string): Promise<AssessmentResult> {
    return this.fetchAPI(`/assess/${id}/uncertainty`, { method: 'POST' });
  }

  /** Download SI-ready research export (JSON, or a tidy CSV section). Triggers a file save.
   * CSV `section` selects the rectangular table: 'impacts' (default), 'matches', or
   * 'contributions'. Honors the server's Content-Disposition filename when present. */
  async downloadAssessmentExport(
    id: string,
    format: 'json' | 'csv' = 'json',
    section?: 'impacts' | 'matches' | 'contributions'
  ): Promise<void> {
    const token = getAccessToken();
    const query = format === 'csv' && section ? `?section=${section}` : '';
    const res = await fetch(`${API_BASE_URL}/me/assessments/${id}/export.${format}${query}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      throw new ApiError(`Export failed: ${res.status}`, res.status);
    }
    const disposition = res.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    const suffix = format === 'csv' && section ? `_${section}` : '';
    const filename = match?.[1] || `assessment_${id}${suffix}.${format}`;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  /** Create a read-only share token for assessment results. */
  async createShareLink(id: string): Promise<{ token: string; share_path: string }> {
    return this.fetchAPI(`/me/assessments/${id}/share`, { method: 'POST' });
  }

  async rerunFarmAssessment(
    id: string,
    data: EnhancedAssessmentRequest,
    opts?: { farmId?: string; title?: string; formSnapshot?: unknown }
  ): Promise<AssessmentResult> {
    const backendData = this.transformEnhancedAssessmentToBackend(data);
    if (opts?.farmId) backendData.farm_id = opts.farmId;
    if (opts?.title) backendData.title = opts.title;
    if (opts?.formSnapshot !== undefined) backendData.form_snapshot = opts.formSnapshot;
    return this.fetchAPI(`/assess/${id}/rerun`, {
      method: 'POST',
      body: JSON.stringify(backendData),
    });
  }

  async rerunProcessingAssessment(
    id: string,
    data: Record<string, unknown>
  ): Promise<AssessmentResult> {
    return this.fetchAPI(`/processing/assess/${id}/rerun`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getFarms(): Promise<Farm[]> {
    return this.fetchAPI('/farms');
  }

  async getFarm(id: string): Promise<Farm> {
    return this.fetchAPI(`/farms/${id}`);
  }

  async createFarm(data: Partial<Farm> & { name: string }): Promise<Farm> {
    return this.fetchAPI('/farms', { method: 'POST', body: JSON.stringify(data) });
  }

  async updateFarm(id: string, data: Partial<Farm>): Promise<Farm> {
    return this.fetchAPI(`/farms/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
  }

  async deleteFarm(id: string): Promise<void> {
    await this.fetchAPI(`/farms/${id}`, { method: 'DELETE' });
  }

  async getFacilities(): Promise<Facility[]> {
    return this.fetchAPI('/facilities');
  }

  async getFacility(id: string): Promise<Facility> {
    return this.fetchAPI(`/facilities/${id}`);
  }

  async createFacility(data: Partial<Facility> & { name: string }): Promise<Facility> {
    return this.fetchAPI('/facilities', { method: 'POST', body: JSON.stringify(data) });
  }

  async updateFacility(id: string, data: Partial<Facility>): Promise<Facility> {
    return this.fetchAPI(`/facilities/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
  }

  async deleteFacility(id: string): Promise<void> {
    await this.fetchAPI(`/facilities/${id}`, { method: 'DELETE' });
  }

  // Processing assessment (processor accounts). Sends the request shape the backend
  // /processing/assess endpoint expects; most operations fields have server defaults.
  async submitProcessingAssessment(data: Record<string, unknown>): Promise<AssessmentResult> {
    return this.fetchAPI('/processing/assess', { method: 'POST', body: JSON.stringify(data) });
  }

  async submitAssessment(data: AssessmentRequest): Promise<AssessmentResult> {
    return this.fetchAPI('/assess', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async submitComprehensiveAssessment(
    data: EnhancedAssessmentRequest,
    opts?: { farmId?: string | null; title?: string | null; formSnapshot?: unknown }
  ): Promise<AssessmentResult> {
    // Transform enhanced assessment data to backend format
    const backendData = this.transformEnhancedAssessmentToBackend(data);
    if (opts?.farmId) backendData.farm_id = opts.farmId;
    if (opts?.title) backendData.title = opts.title;
    if (opts?.formSnapshot !== undefined) backendData.form_snapshot = opts.formSnapshot;

    return this.fetchAPI('/assess', {
      method: 'POST',
      body: JSON.stringify(backendData),
    });
  }

  // --- Streaming (SSE) assessment submit -------------------------------------------------
  // Same result as the plain submit methods, but consumes the /assess/stream endpoints and
  // calls onProgress for each live engine stage. Returns the final result once the stream's
  // terminal `result` event arrives (throws on an `error` event).
  private async streamAssess(
    endpoint: string,
    body: unknown,
    onProgress?: (e: AssessmentProgressEvent) => void,
    retryOn401 = true,
  ): Promise<AssessmentResult> {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...this.authHeaders() },
      body: JSON.stringify(body),
    });

    if (response.status === 401 && retryOn401) {
      const refreshed = await this.refreshAccessToken();
      if (refreshed) return this.streamAssess(endpoint, body, onProgress, false);
    }
    if (!response.ok || !response.body) {
      const errorData = await response.json().catch(() => ({}));
      const detail = errorData?.detail;
      throw new ApiError(
        typeof detail === 'string' ? detail : `API Error: ${response.status} ${response.statusText}`,
        response.status,
      );
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let result: AssessmentResult | undefined;
    let streamError: string | undefined;

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep: number;
      // SSE frames are separated by a blank line.
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const dataLine = frame.split('\n').find((l) => l.startsWith('data:'));
        if (!dataLine) continue;
        let evt: { type?: string; data?: AssessmentResult; message?: string } & AssessmentProgressEvent;
        try {
          evt = JSON.parse(dataLine.slice(5).trim());
        } catch {
          continue;
        }
        if (evt.type === 'progress') onProgress?.(evt);
        else if (evt.type === 'result') result = evt.data;
        else if (evt.type === 'error') streamError = evt.message || 'Assessment failed';
      }
    }

    if (streamError) throw new ApiError(streamError, 500);
    if (!result) throw new ApiError('The assessment stream ended without a result.', 500);
    return result;
  }

  async submitProcessingAssessmentStream(
    data: Record<string, unknown>,
    onProgress?: (e: AssessmentProgressEvent) => void,
  ): Promise<AssessmentResult> {
    return this.streamAssess('/processing/assess/stream', data, onProgress);
  }

  async submitComprehensiveAssessmentStream(
    data: EnhancedAssessmentRequest,
    opts?: { farmId?: string | null; title?: string | null; formSnapshot?: unknown },
    onProgress?: (e: AssessmentProgressEvent) => void,
  ): Promise<AssessmentResult> {
    const backendData = this.transformEnhancedAssessmentToBackend(data);
    if (opts?.farmId) backendData.farm_id = opts.farmId;
    if (opts?.title) backendData.title = opts.title;
    if (opts?.formSnapshot !== undefined) backendData.form_snapshot = opts.formSnapshot;
    return this.streamAssess('/assess/stream', backendData, onProgress);
  }

  private transformEnhancedAssessmentToBackend(data: EnhancedAssessmentRequest): AssessmentRequest {
    return transformEnhancedAssessmentToBackend(data);
  }

  async getAssessment(assessmentId: string): Promise<AssessmentResult> {
    return this.fetchAPI(`/assess/${assessmentId}`);
  }

  // Processing assessments live in their own namespace; /assess/{id} filters to farm
  // assessments and 404s on a processing id.
  async getProcessingAssessment(assessmentId: string): Promise<AssessmentResult> {
    return this.fetchAPI(`/processing/assess/${assessmentId}`);
  }

  // Deterministic, costed, sequenced recommendations for a saved assessment. Farm and
  // processing live in separate namespaces, mirroring getAssessment/getProcessingAssessment.
  async getRecommendations(assessmentId: string, isProcessing = false): Promise<RecommendationsResponse> {
    const base = isProcessing ? '/processing/assess' : '/assess';
    return this.fetchAPI(`${base}/${assessmentId}/recommendations`);
  }

  async getAssessments(): Promise<{ assessments: AssessmentResult[]; total: number }> {
    return this.fetchAPI('/assessments');
  }

  async getFoodCategories(): Promise<{ categories: string[] }> {
    return this.fetchAPI('/food-categories');
  }

  async getSupportedCountries(): Promise<{ countries: string[]; default: string }> {
    return this.fetchAPI('/countries');
  }

  async getImpactCategories(): Promise<{ midpoint: string[]; endpoint: string[] }> {
    return this.fetchAPI('/impact-categories');
  }

  async checkHealth(): Promise<{ status: string; timestamp: string }> {
    return this.fetchAPI('/health');
  }

  // Plain-language results chat (streaming SSE). Bypasses fetchAPI because it reads a
  // token stream rather than a single JSON body. Calls onChunk for each text delta.
  async streamChat(
    messages: ChatMessage[],
    opts: {
      assessmentData?: AssessmentResult;
      assessmentId?: string | null;
      onChunk: (text: string) => void;
      signal?: AbortSignal;
    },
    retryOn401 = true
  ): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...this.authHeaders() },
      body: JSON.stringify({
        messages,
        assessment_data: opts.assessmentData,
        assessment_id: opts.assessmentId ?? undefined,
      }),
      signal: opts.signal,
    });

    if (response.status === 401 && retryOn401) {
      const refreshed = await this.refreshAccessToken();
      if (refreshed) return this.streamChat(messages, opts, false);
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const detail = errorData.detail;
      throw new Error(typeof detail === 'string' ? detail : `Chat failed: ${response.status}`);
    }
    if (!response.body) throw new Error('No response stream from the server.');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by a blank line; keep any incomplete trailing event.
      const events = buffer.split('\n\n');
      buffer = events.pop() ?? '';

      for (const evt of events) {
        let eventType = 'message';
        const dataLines: string[] = [];
        for (const line of evt.split('\n')) {
          if (line.startsWith('event:')) eventType = line.slice(6).trim();
          else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
        }
        if (!dataLines.length) continue;
        const dataStr = dataLines.join('\n');

        if (eventType === 'error') {
          let msg = 'The chat ran into an error.';
          try { msg = JSON.parse(dataStr).error || msg; } catch { /* keep default */ }
          throw new Error(msg);
        }
        if (eventType === 'done') return;
        try {
          const parsed = JSON.parse(dataStr);
          if (parsed.delta) opts.onChunk(parsed.delta as string);
        } catch { /* ignore keep-alives / partial frames */ }
      }
    }
  }
}

export const assessmentAPI = new AssessmentAPI();

// The engine models ONE delivery leg to market: take the most motorised mode the farmer ticked
// (foot / bicycle only -> no transport emissions).
const MARKET_MODE_PRIORITY = ['Large truck', 'Pickup truck', 'Public transport', 'Motorcycle', 'Bicycle', 'On foot/Head carrying'];
// UI mode -> the keyword engine/inputs.py MARKET_TRANSPORT_MATCH / ZERO_EMISSION_MODES keys on.
// "Pickup truck" must not contain "truck": the engine checks "truck" (lorry) before "pickup"
// (light commercial vehicle).
const MARKET_MODE_TO_ENGINE: Record<string, string> = {
  'Large truck': 'Large truck',
  'Pickup truck': 'Pickup',
  'Public transport': 'Public transport',
  'Motorcycle': 'Motorcycle',
  'Bicycle': 'Bicycle',
  'On foot/Head carrying': 'On foot',
};
export function pickMarketMode(modes?: string[]): string | undefined {
  if (!modes || modes.length === 0) return undefined;
  const mode = MARKET_MODE_PRIORITY.find((m) => modes.includes(m)) ?? modes[0];
  return MARKET_MODE_TO_ENGINE[mode] ?? mode;
}

const FERTILIZER_METHOD_TO_API: Record<ApplicationMethod, FertilizerApplicationMethodPayload> = {
  [ApplicationMethod.BROADCAST]: 'broadcast',
  [ApplicationMethod.BAND_PLACEMENT]: 'band_placement',
  [ApplicationMethod.SIDE_DRESSING]: 'side_dressing',
  [ApplicationMethod.FOLIAR_SPRAY]: 'foliar',
  [ApplicationMethod.FERTIGATION]: 'fertigation',
  [ApplicationMethod.PRECISION_APPLICATION]: 'band_placement',
};

const cleanList = (items?: string[]) => (items ?? []).map((s) => s.trim()).filter(Boolean);
const trimmedOrUndefined = (s?: string) => (s && s.trim() ? s.trim() : undefined);
const finiteOrUndefined = (n: unknown) =>
  typeof n === 'number' && Number.isFinite(n) ? n : undefined;
const validMonths = (months?: Array<number | string>) =>
  [...new Set((months ?? []).map(Number).filter((m) => Number.isInteger(m) && m >= 1 && m <= 12))].sort((a, b) => a - b);

/**
 * Stable wire id per crop: the wizard's cropId (so crop_ids on fertiliser / pesticide / lime /
 * compost rows keep pointing at the same crop after reordering), deduplicated and capped at the
 * API's 64 characters; `crop_<n>` when the form has no id.
 */
export function foodIdsForCrops(crops: Array<{ cropId?: string }>): string[] {
  const used = new Set<string>();
  return crops.map((c, i) => {
    let id = (c.cropId || '').trim().slice(0, 64) || `crop_${i + 1}`;
    if (used.has(id)) {
      let n = 2;
      while (used.has(`${id.slice(0, 58)}_${n}`)) n++;
      id = `${id.slice(0, 58)}_${n}`;
    }
    used.add(id);
    return id;
  });
}

// Utility functions for the frontend
export const formatScore = (score: number): string => {
  return (score * 100).toFixed(1) + '%';
};

export const getScoreInterpretation = (score: number) => {
  if (score < 0.3) {
    return {
      category: 'excellent',
      title: 'Low Impact',
      description: 'Low environmental footprint per kg of product.',
      color: 'text-green-700 bg-green-50 border-green-200',
      recommendations: [
        'Share your practices with other farmers',
        'Consider becoming a sustainability demonstration farm',
        'Document your methods for extension services'
      ]
    };
  } else if (score < 0.45) {
    return {
      category: 'good',
      title: 'Lower than typical',
      description: 'Lower environmental footprint per kg than a typical product.',
      color: 'text-blue-700 bg-blue-50 border-blue-200',
      recommendations: [
        'Small improvements can make you a sustainability leader',
        'Focus on water efficiency opportunities',
        'Consider climate-smart agriculture practices'
      ]
    };
  } else if (score < 0.55) {
    return {
      category: 'typical',
      title: 'Typical Performance',
      description: 'Your farm has average environmental impact',
      color: 'text-yellow-700 bg-yellow-50 border-yellow-200',
      recommendations: [
        'Several improvement opportunities available',
        'Focus on the specific recommendations below',
        'Consider joining farmer sustainability programs'
      ]
    };
  } else if (score < 0.7) {
    return {
      category: 'above-average',
      title: 'Above Average Impact',
      description: 'Your farm needs improvement',
      color: 'text-orange-700 bg-orange-50 border-orange-200',
      recommendations: [
        'Focus on high-impact improvements first',
        'Potential to reduce environmental impact by 20-30%',
        'Seek support from agricultural extension officers'
      ]
    };
  } else {
    return {
      category: 'high-impact',
      title: 'High Environmental Impact',
      description: 'Immediate action recommended',
      color: 'text-red-700 bg-red-50 border-red-200',
      recommendations: [
        'Significant improvements needed',
        'Extension officer support strongly recommended',
        'Consider transitioning to more sustainable practices'
      ]
    };
  }
};

/**
 * Map the wizard's camelCase form data to the exact snake_case request the API accepts.
 * Exported so the contract can be unit-tested without the API client.
 */
export function transformEnhancedAssessmentToBackend(data: EnhancedAssessmentRequest): AssessmentRequest {
  // Map the UI country to the country the API accepts + the engine region. Canada is
  // sent as country "Global" + region "CA" (the engine has a CA region but no Canada
  // country). Sending region explicitly is also what makes Ghana->GH and Nigeria->NG
  // resolve reliably instead of being re-derived from the country string.
  const mapped = COUNTRY_TO_REGION[data.farmProfile.country as string]
    ?? { country: data.farmProfile.country, region: undefined };

  const foodIds = foodIdsForCrops(data.cropProductions);
  const foodIdByCropId = new Map<string, string>();
  data.cropProductions.forEach((c, i) => {
    if (c.cropId && !foodIdByCropId.has(c.cropId)) foodIdByCropId.set(c.cropId, foodIds[i]);
  });
  // [] means "all crops" on the API; ids of removed crops are dropped (the form refuses them).
  const toFoodIds = (ids?: string[]) =>
    [...new Set((ids ?? []).map((id) => foodIdByCropId.get(id)).filter((id): id is string => !!id))];

  const soil = data.managementPractices.soilManagement;
  const fert = data.managementPractices.fertilization;
  const water = data.managementPractices.waterManagement;
  const pest = data.pestManagement;
  // Rows of type "None" or with no product rate carry no inventory; never send them.
  const fertRows = (fert.fertilizerApplications ?? []).filter(
    (a) => String(a.fertilizerType).toLowerCase() !== FertilizerType.NONE.toLowerCase()
      && Number(a.applicationRate) > 0,
  );
  const infra = data.equipmentEnergy?.infrastructure;
  const storageFacilities = cleanList(infra?.storageFacilities);
  const hasCold = storageFacilities.includes(StorageFacilityType.COLD_STORAGE);
  const storageCapacity = finiteOrUndefined(infra?.storageCapacity);

  const backendData: AssessmentRequest = {
    company_name: `${data.farmProfile.farmerName} - ${data.farmProfile.farmName}`,
    country: mapped.country as AssessmentRequest['country'],
    region: mapped.region,
    farm_profile: {
      farmer_name: data.farmProfile.farmerName,
      farm_name: data.farmProfile.farmName,
      total_farm_size: data.farmProfile.totalFarmSize,
      farming_experience: data.farmProfile.farmingExperience,
      farm_type: data.farmProfile.farmType,
      primary_farming_system: data.farmProfile.primaryFarmingSystem,
      certifications: data.farmProfile.certifications,
      participates_in_programs: data.farmProfile.participatesInPrograms,
    },
    run_uncertainty: data.assessmentParameters?.includeUncertaintyAnalysis ?? true,
    study_meta: { admin_region: trimmedOrUndefined(data.farmProfile.region) },
    management_practices: {
      soil_management: {
        // Backend SoilType enum is space-less PascalCase (ClayLoam), the UI uses spaces
        // ("Clay Loam"); strip the space so multi-word soil types validate.
        soil_type: soil.soilType?.replace(/ /g, ''),
        uses_compost: soil.compostUse.usesCompost,
        compost_source: soil.compostUse.compostsource,
        compost_application_rate: soil.compostUse.applicationRate,
        compost_crop_ids: soil.compostUse.usesCompost ? toFoodIds(soil.compostUse.cropIds) : [],
        conservation_practices: soil.conservationPractices,
        soil_testing_frequency: soil.soilTestingFrequency,
        soil_ph: finiteOrUndefined(soil.soilpH),
        organic_matter_pct: finiteOrUndefined(soil.organicMatterContent),
        cover_crops: !!soil.usesCoverCrops,
        practices_adopted_years_ago: finiteOrUndefined(soil.practicesAdoptedYearsAgo),
        lime_applications: (soil.limeApplications ?? [])
          .filter((l) => l.rateTPerHaPerYear > 0)
          .map((l) => ({
            material: l.material,
            rate_t_per_ha_per_year: l.rateTPerHaPerYear,
            crop_ids: toFoodIds(l.cropIds),
          })),
      },
      fertilization: {
        uses_fertilizers: fert.usesFertilizers && fertRows.length > 0,
        fertilizer_applications: fertRows.map((app) => {
          const method = app.applicationMethod ?? fert.applicationMethod;
          return {
            fertilizer_type: app.fertilizerType,
            npk_ratio: trimmedOrUndefined(app.npkRatio),
            application_rate: app.applicationRate,
            applications_per_season: app.applicationsPerSeason,
            application_method: method ? FERTILIZER_METHOD_TO_API[method] : undefined,
            brand_name: trimmedOrUndefined(app.brandName),
            crop_ids: toFoodIds(app.cropIds),
            cost: app.cost,
          };
        }),
        soil_test_based: fert.soilTestBased,
        follows_nutrient_plan: fert.followsNutrientPlan,
        timing_strategy: fert.timingStrategy || undefined,
      },
      water_management: {
        water_source: water.waterSource,
        irrigation_system: water.irrigationSystem,
        irrigation_water_m3: water.irrigationWaterM3 ?? undefined,
        water_conservation_practices: water.waterConservationPractices ?? [],
        drainage_system: water.drainageSystem ? 'present' : 'none',
      },
      // Key names must match app/production/models.py exactly: the API rejects unknown
      // keys (it used to drop `pesticides_used` silently, losing every pesticide).
      pest_management: {
        management_approach: pest.managementApproach,
        uses_ipm: pest.usesIPM,
        pesticides: pest.pesticides.map((p) => ({
          pesticide_type: p.pesticideType,
          active_ingredient: p.activeIngredient,
          application_rate: p.applicationRate,
          applications_per_season: p.applicationsPerSeason,
          active_ingredient_content: p.activeIngredientContent ?? undefined,
          target_pests: cleanList(p.targetPests),
          brand_name: trimmedOrUndefined(p.brandName),
          crop_ids: toFoodIds(p.cropIds),
        })),
        pest_monitoring_frequency: pest.pestMonitoringFrequency,
        primary_pests: cleanList(pest.primaryPests),
        primary_diseases: cleanList(pest.primaryDiseases),
        ipm_practices: cleanList(pest.ipmPractices),
        biological_controls: cleanList(pest.biologicalControls),
        uses_economic_thresholds: !!pest.usesEconomicThresholds,
      },
    },
    // Include equipment_energy if provided (convert to snake_case and strip infrastructure field)
    equipment_energy: data.equipmentEnergy ? {
      equipment: data.equipmentEnergy.equipment.map(eq => ({
        equipment_type: eq.equipmentType,
        power_source: eq.powerSource,
        age: eq.age,
        hours_per_year: eq.hoursPerYear,
        fuel_efficiency: eq.fuelEfficiency,
      })),
      energy_sources: data.equipmentEnergy.energySources.map(es => ({
        energy_type: es.energyType,
        monthly_consumption: es.monthlyConsumption,
        primary_use: es.primaryUse,
        cost: es.cost,
        currency: es.currency,
      })),
      fuel_consumption: (data.equipmentEnergy.fuelConsumption ?? []).map(fc => ({
        fuel_type: fc.fuelType,
        monthly_consumption: fc.monthlyConsumption,
        // Always sent: without it the engine reads LPG cylinders (kg) as litres.
        unit: fc.unit ?? FARM_FUEL_DEFAULT_UNIT[fc.fuelType] ?? 'L',
        primary_use: fc.primaryUse,
        cost: fc.cost,
      })),
      storage: (storageFacilities.length > 0 || storageCapacity !== undefined) ? {
        facilities: storageFacilities,
        capacity_tonnes: storageCapacity,
        refrigerant: hasCold ? trimmedOrUndefined(infra?.refrigerant) : undefined,
        refrigerant_charge_kg: hasCold ? finiteOrUndefined(infra?.refrigerantChargeKg) : undefined,
      } : undefined,
    } : undefined,
    logistics: data.equipmentEnergy ? {
      packaging_material: data.equipmentEnergy.infrastructure?.packagingMaterial?.trim() || undefined,
      packaging_kg_per_tonne: data.equipmentEnergy.infrastructure?.packagingKgPerTonne ?? undefined,
      distance_to_market_km: data.equipmentEnergy.infrastructure?.transportAccess?.distanceToMarket ?? undefined,
      market_transport_mode: pickMarketMode(data.equipmentEnergy.infrastructure?.transportAccess?.transportMode),
      input_transport_km: data.equipmentEnergy.infrastructure?.inputTransportKm ?? undefined,
    } : undefined,
    foods: data.cropProductions.map((crop, index) => {
      const rice = isRiceCrop(crop.cropName);
      const luc = crop.landUseChange;
      const years = finiteOrUndefined(luc?.yearsSinceConversion);
      // Annual crops never carry establishment (the API refuses it with a 422).
      const est = isKnownAnnualCrop(crop) ? undefined : crop.establishment;
      const establishment = {
        ...(finiteOrUndefined(est?.immatureYears) !== undefined && { immature_years: est!.immatureYears }),
        ...(finiteOrUndefined(est?.productiveYears) !== undefined && est!.productiveYears! > 0 && { productive_years: est!.productiveYears }),
        ...(finiteOrUndefined(est?.inputShare) !== undefined && { input_share: est!.inputShare }),
      };
      return {
        id: foodIds[index],
        name: crop.cropName,
        quantity_kg: crop.annualProduction,
        category: crop.category,
        crop_type: crop.variety,
        origin_country: data.farmProfile.country,
        production_system: crop.productionSystem,
        // Only an explicit override; blank lets the engine derive wet/dry from the planting
        // months and the admin region's rainy season.
        seasonal_factor: crop.seasonality.seasonOverride || undefined,
        variety: crop.variety,
        area_allocated: crop.areaAllocated,
        cropping_pattern: crop.croppingPattern,
        intercropping_partners: crop.intercroppingPartners ? cleanList(crop.intercroppingPartners) : undefined,
        post_harvest_losses: finiteOrUndefined(crop.postHarvestLosses),
        seed_rate_kg_per_ha: crop.seedRateKgPerHa ?? undefined,
        crops_per_year: Math.min(4, Math.max(1, Math.round(Number(crop.seasonality.cropsPerYear) || 1))),
        growing_period_days: finiteOrUndefined(crop.seasonality.growingPeriod),
        planting_months: validMonths(crop.seasonality.plantingMonths),
        harvest_months: validMonths(crop.seasonality.harvestingMonths),
        rotation_sequence: cleanList(crop.rotationSequence),
        water_regime: rice && crop.waterRegime ? crop.waterRegime : undefined,
        preseason_water_status: rice && crop.preseasonWaterStatus ? crop.preseasonWaterStatus : undefined,
        // Years are required with a previous land use (the form refuses a blank); never 0 by default.
        land_use_change: luc?.previousLandUse && years !== undefined
          ? { previous_land_use: luc.previousLandUse, years_since_conversion: Math.round(years) }
          : undefined,
        residue_management: (crop.residueManagement?.fractionRemoved != null || crop.residueManagement?.fractionBurnt != null)
          ? { fraction_removed: crop.residueManagement?.fractionRemoved ?? 0,
              fraction_burnt: crop.residueManagement?.fractionBurnt ?? 0,
              // Only meaningful when some residue actually leaves the field.
              removed_residue_use: (crop.residueManagement?.fractionRemoved ?? 0) > 0
                && crop.residueManagement?.removedResidueUse
                ? crop.residueManagement.removedResidueUse : undefined }
          : undefined,
        establishment: Object.keys(establishment).length ? establishment : undefined,
      };
    }),
  };

  return backendData;
}
