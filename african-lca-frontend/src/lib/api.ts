// API service for African LCA Backend

import { AssessmentRequest, AssessmentResult } from '@/types/assessment';
import { EnhancedAssessmentRequest, FertilizerApplication, PesticideApplication } from '@/types/enhanced-assessment';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Report types
export interface Report {
  report_id: string;
  generated_at: string;
  report_type: 'comprehensive' | 'executive' | 'farmer_friendly';
  assessment_id?: string;
  company_name?: string;
  country?: string;
  assessment_date?: string;
  sections: Record<string, string>;
  metadata?: {
    model_used?: string;
    generation_timestamp?: string;
    temperature?: number;
    chain_of_thought_enabled?: boolean;
    iso_14044_compliant?: boolean;
    data_quality_level?: string;
    validation_warnings?: string[];
    sections_generated?: number;
  };
}

class AssessmentAPI {
  private async fetchAPI(endpoint: string, options: RequestInit = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

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
      
      throw new Error(errorMessage);
    }

    return response.json();
  }

  async submitAssessment(data: AssessmentRequest): Promise<AssessmentResult> {
    return this.fetchAPI('/assess', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async submitComprehensiveAssessment(data: EnhancedAssessmentRequest): Promise<AssessmentResult> {
    // Transform enhanced assessment data to backend format
    const backendData = this.transformEnhancedAssessmentToBackend(data);
    
    return this.fetchAPI('/assess', {
      method: 'POST',
      body: JSON.stringify(backendData),
    });
  }

  private transformEnhancedAssessmentToBackend(data: EnhancedAssessmentRequest): AssessmentRequest {
    // Transform the comprehensive frontend data to backend format
    const backendData: AssessmentRequest = {
      company_name: `${data.farmProfile.farmerName} - ${data.farmProfile.farmName}`,
      country: data.farmProfile.country,
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
          soil_type: data.managementPractices.soilManagement.soilType,
          uses_compost: data.managementPractices.soilManagement.compostUse.usesCompost,
          compost_source: data.managementPractices.soilManagement.compostUse.compostsource,
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

  // Report Generation APIs
  async generateReport(
    assessmentId: string,
    reportType: 'comprehensive' | 'executive' | 'farmer_friendly' = 'comprehensive'
  ): Promise<Report> {
    return this.fetchAPI('/reports/generate', {
      method: 'POST',
      body: JSON.stringify({
        assessment_id: assessmentId,
        report_type: reportType
      })
    });
  }

  async getReport(reportId: string): Promise<Report> {
    return this.fetchAPI(`/reports/report/${reportId}`);
  }

  async listReportsForAssessment(assessmentId: string): Promise<{ assessment_id: string; reports: Report[]; total: number }> {
    return this.fetchAPI(`/reports/assessment/${assessmentId}/reports`);
  }

  async exportReportMarkdown(reportId: string): Promise<{ report_id: string; format: string; content: string }> {
    return this.fetchAPI(`/reports/report/${reportId}/export/markdown`);
  }

  async downloadReportPDF(reportId: string, assessmentId: string): Promise<Blob> {
    const url = `${API_BASE_URL}/reports/report/${reportId}/download/pdf?assessment_id=${assessmentId}`;

    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`Failed to download PDF: ${response.statusText}`);
    }

    return response.blob();
  }

  async exportReportJSON(reportId: string): Promise<Report> {
    return this.fetchAPI(`/reports/report/${reportId}/export/json`);
  }

  async checkReportHealth(): Promise<{ status: string; service: string; ai_enabled: boolean; reports_generated: number; supported_types: string[] }> {
    return this.fetchAPI('/reports/health');
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
      title: 'Excellent Performance',
      description: 'Your farm is in the top 10% for sustainability!',
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
      title: 'Good Performance',
      description: 'Your farm performs better than average in West Africa',
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