// API service for the Green Means Go Backend

import { AssessmentRequest, AssessmentResult } from '@/types/assessment';
import { EnhancedAssessmentRequest, FertilizerApplication, PesticideApplication } from '@/types/enhanced-assessment';
import { COUNTRY_TO_REGION } from '@/lib/country-examples';
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
      // Stateless logout — clearing local tokens is what matters even if the call fails.
    } finally {
      clearSession();
    }
  }

  // --- workspace (saved assessments, farms, facilities) --------------------------

  async getMyAssessments(): Promise<{ assessments: AssessmentSummary[]; total: number }> {
    return this.fetchAPI('/me/assessments');
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
    opts?: { farmId?: string | null; title?: string | null }
  ): Promise<AssessmentResult> {
    // Transform enhanced assessment data to backend format
    const backendData = this.transformEnhancedAssessmentToBackend(data);
    if (opts?.farmId) backendData.farm_id = opts.farmId;
    if (opts?.title) backendData.title = opts.title;

    return this.fetchAPI('/assess', {
      method: 'POST',
      body: JSON.stringify(backendData),
    });
  }

  private transformEnhancedAssessmentToBackend(data: EnhancedAssessmentRequest): AssessmentRequest {
    // Map the UI country to the country the API accepts + the engine region. Canada is
    // sent as country "Global" + region "CA" (the engine has a CA region but no Canada
    // country). Sending region explicitly is also what makes Ghana->GH and Nigeria->NG
    // resolve reliably instead of being re-derived from the country string.
    const mapped = COUNTRY_TO_REGION[data.farmProfile.country as string]
      ?? { country: data.farmProfile.country, region: undefined };

    // Transform the comprehensive frontend data to backend format
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
      management_practices: {
        soil_management: {
          // Backend SoilType enum is space-less PascalCase (ClayLoam), the UI uses spaces
          // ("Clay Loam"); strip the space so multi-word soil types validate.
          soil_type: data.managementPractices.soilManagement.soilType?.replace(/ /g, ''),
          uses_compost: data.managementPractices.soilManagement.compostUse.usesCompost,
          compost_source: data.managementPractices.soilManagement.compostUse.compostsource,
          compost_application_rate: data.managementPractices.soilManagement.compostUse.applicationRate,
          conservation_practices: data.managementPractices.soilManagement.conservationPractices,
          soil_testing_frequency: data.managementPractices.soilManagement.soilTestingFrequency,
        },
        fertilization: {
          uses_fertilizers: data.managementPractices.fertilization.usesFertilizers,
          fertilizer_applications: data.managementPractices.fertilization.fertilizerApplications.map((app: FertilizerApplication) => ({
            fertilizer_type: app.fertilizerType,
            npk_ratio: app.npkRatio,
            application_rate: app.applicationRate,
            applications_per_season: app.applicationsPerSeason,
            cost: app.cost,
          })),
          soil_test_based: data.managementPractices.fertilization.soilTestBased,
          follows_nutrient_plan: data.managementPractices.fertilization.followsNutrientPlan,
        },
        water_management: {
          water_source: data.managementPractices.waterManagement.waterSource,
          irrigation_system: data.managementPractices.waterManagement.irrigationSystem,
          water_conservation_practices: data.managementPractices.waterManagement.waterConservationPractices,
        },
        pest_management: {
          management_approach: data.pestManagement.managementApproach,
          uses_ipm: data.pestManagement.usesIPM,
          pesticides_used: data.pestManagement.pesticides.map((pest: PesticideApplication) => ({
            pesticide_type: pest.pesticideType,
            active_ingredient: pest.activeIngredient,
            application_rate: pest.applicationRate,
            applications_per_season: pest.applicationsPerSeason,
            target_pests: pest.targetPests,
          })),
          monitoring_frequency: data.pestManagement.pestMonitoringFrequency,
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
        fuel_consumption: data.equipmentEnergy.fuelConsumption.map(fc => ({
          fuel_type: fc.fuelType,
          monthly_consumption: fc.monthlyConsumption,
          primary_use: fc.primaryUse,
          cost: fc.cost,
        })),
      } : undefined,
      foods: data.cropProductions.map((crop, index) => ({
        id: `crop_${index + 1}`,
        name: crop.cropName,
        quantity_kg: crop.annualProduction,
        category: crop.category,
        crop_type: crop.variety,
        origin_country: data.farmProfile.country,
        production_system: crop.productionSystem,
        seasonal_factor: crop.seasonality.season[0], // Use first season as primary
        variety: crop.variety,
        area_allocated: crop.areaAllocated,
        cropping_pattern: crop.croppingPattern,
        intercropping_partners: crop.intercroppingPartners,
        post_harvest_losses: crop.postHarvestLosses,
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
        management_practices: {
          soil_management: data.managementPractices.soilManagement,
          fertilization: data.managementPractices.fertilization,
          water_management: data.managementPractices.waterManagement,
          pest_management: data.pestManagement,
        },
      })),
    };

    return backendData;
  }

  async getAssessment(assessmentId: string): Promise<AssessmentResult> {
    return this.fetchAPI(`/assess/${assessmentId}`);
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