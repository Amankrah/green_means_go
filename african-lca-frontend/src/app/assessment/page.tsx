'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useForm, FormProvider } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { 
  ChevronLeft, 
  ChevronRight, 
  CheckCircle,
  Sprout,
  User,
  Settings,
  Shield,
  Zap,
  BarChart3,
  AlertTriangle,
  Info,
  Clock
} from 'lucide-react';

import Layout from '@/components/Layout';
import { assessmentAPI } from '@/lib/api';
import { 
  enhancedAssessmentSchema, 
  type EnhancedAssessmentFormData,
  FORM_STEPS,
  getStepProgress,
  getNextStep,
  getPreviousStep
} from '@/lib/enhanced-assessment-schema';
import { 
  FormStep, 
  EnhancedAssessmentRequest, 
  FarmType, 
  FarmingSystem,
  CompostSource,
  FunctionalUnit,
  SystemBoundary,
  ApplicationMethod,
  TimingStrategy,
  TillageSystem,
  HarvestingMethod,
  MechanizationLevel,
  LaborIntensity,
  PostHarvestHandling,
  MaintenanceFrequency
} from '@/types/enhanced-assessment';
import { FoodCategory } from '@/types/assessment';

// Import individual step components
import FarmProfileStep from '@/components/assessment/FarmProfileStep';
import CropDetailsStep from '@/components/assessment/CropDetailsStep';
import ManagementPracticesStep from '@/components/assessment/ManagementPracticesStep';
import PestManagementStep from '@/components/assessment/PestManagementStep';
import EquipmentEnergyStep from '@/components/assessment/EquipmentEnergyStep';
import ReviewSubmitStep from '@/components/assessment/ReviewSubmitStep';

const stepIcons = {
  [FormStep.FARM_PROFILE]: User,
  [FormStep.CROP_DETAILS]: Sprout,
  [FormStep.MANAGEMENT_PRACTICES]: Settings,
  [FormStep.PEST_MANAGEMENT]: Shield,
  [FormStep.EQUIPMENT_ENERGY]: Zap,
  [FormStep.REVIEW_SUBMIT]: BarChart3,
};

export default function ComprehensiveAssessmentPage() {
  const [currentStep, setCurrentStep] = useState<FormStep>(FormStep.FARM_PROFILE);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{
    success: boolean;
    message: string;
    assessmentId?: string;
  } | null>(null);

  const methods = useForm({
    resolver: zodResolver(enhancedAssessmentSchema), // Will be overridden for specific steps
    defaultValues: {
      farmProfile: {
        farmerName: '',
        farmName: '',
        country: 'Ghana',
        region: '',
        totalFarmSize: 0,
        farmingExperience: 0,
        farmType: FarmType.SMALLHOLDER,
        primaryFarmingSystem: FarmingSystem.SUBSISTENCE,
        certifications: [],
        participatesInPrograms: []
      },
      cropProductions: [],
      managementPractices: {
        soilManagement: {
          soilType: undefined,
          soilTestingFrequency: undefined,
          conservationPractices: [],
          coverCrops: [],
                  compostUse: {
          usesCompost: false,
          compostsource: CompostSource.NONE,
          applicationTiming: "Before planting"
        }
        },
        fertilization: {
          usesFertilizers: false,
          fertilizerApplications: [],
          soilTestBased: false,
          followsNutrientPlan: false
        },
        waterManagement: {
          waterSource: [],
          irrigationSystem: undefined,
          drainageSystem: false,
          waterConservationPractices: []
        }
      },
      pestManagement: {
        primaryPests: [],
        primaryDiseases: [],
        managementApproach: undefined,
        pesticides: [],
        usesIPM: false,
        ipmPractices: [],
        biologicalControls: [],
        pestMonitoringFrequency: undefined,
        usesEconomicThresholds: false
      },
      equipmentEnergy: {
        equipment: [],
        energySources: [],
        infrastructure: {
          storageCapacity: 0,
          storageFacilities: [],
          transportAccess: {
            roadAccess: undefined,
            distanceToMarket: 0,
            transportMode: [],
            transportCost: undefined
          }
        }
      },
      assessmentParameters: {
        functionalUnit: FunctionalUnit.PER_KG_PRODUCT, // Default to most common LCA functional unit
        systemBoundary: SystemBoundary.CRADLE_TO_GATE, // Default to production-focused boundary
        assessmentPeriod: 1,
        includeUncertaintyAnalysis: true,
        includeSensitivityAnalysis: true,
        benchmarkComparison: true
      }
    },
    mode: 'onSubmit'
  });

  const { handleSubmit, trigger, formState: { errors } } = methods;

  const handleNextStep = async () => {
    // Only validate the current step fields
    let currentStepValid = false;
    
    switch (currentStep) {
      case FormStep.FARM_PROFILE:
        currentStepValid = await trigger(['farmProfile']);
        break;
      case FormStep.CROP_DETAILS:
        currentStepValid = await trigger(['cropProductions']);
        break;
      case FormStep.MANAGEMENT_PRACTICES:
        currentStepValid = await trigger(['managementPractices']);
        break;
      case FormStep.PEST_MANAGEMENT:
        currentStepValid = await trigger(['pestManagement']);
        break;
      case FormStep.EQUIPMENT_ENERGY:
        currentStepValid = await trigger(['equipmentEnergy', 'assessmentParameters']);
        break;
      case FormStep.REVIEW_SUBMIT:
        currentStepValid = await trigger(); // Validate everything for final step
        break;
      default:
        currentStepValid = true;
    }
    
    if (currentStepValid) {
      const nextStep = getNextStep(currentStep);
      if (nextStep) {
        setCurrentStep(nextStep);
      }
    }
  };

  const handlePreviousStep = () => {
    const previousStep = getPreviousStep(currentStep);
    if (previousStep) {
      setCurrentStep(previousStep);
    }
  };

  const onSubmit = async (data: EnhancedAssessmentFormData) => {
    setIsSubmitting(true);
    setSubmitResult(null);

    try {
      // Transform enhanced form data to API format
      const apiData = transformToAPIFormat(data);
      
      // Submit comprehensive assessment to backend
      console.log('Submitting comprehensive assessment:', apiData);
      
      const result = await assessmentAPI.submitComprehensiveAssessment(apiData);
      
      setSubmitResult({
        success: true,
        message: 'Comprehensive assessment completed successfully!',
        assessmentId: result.id,
      });

      // Redirect to results page after a short delay
      setTimeout(() => {
        window.location.href = `/results?id=${result.id}`;
      }, 2000);

    } catch (error) {
      console.error('Assessment submission error:', error);
      
      let errorMessage = 'Assessment failed. Please try again.';
      
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'object' && error !== null) {
        // Handle API validation errors
        if ('response' in error && error.response) {
          const response = error.response as { data?: { detail?: string | Array<{ msg?: string; message?: string }> } };
          if (response.data && response.data.detail) {
            errorMessage = Array.isArray(response.data.detail) 
              ? response.data.detail.map((err: { msg?: string; message?: string }) => err.msg || err.message || JSON.stringify(err)).join(', ')
              : response.data.detail;
          }
        }
      }
      
      setSubmitResult({
        success: false,
        message: errorMessage,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const transformToAPIFormat = (data: EnhancedAssessmentFormData): EnhancedAssessmentRequest => {
    // Transform to the complete enhanced assessment format expected by the API
    return {
      farmProfile: {
        farmerName: data.farmProfile.farmerName,
        farmName: data.farmProfile.farmName,
        country: data.farmProfile.country,
        region: data.farmProfile.region,
        coordinates: data.farmProfile.coordinates,
        totalFarmSize: data.farmProfile.totalFarmSize,
        farmingExperience: data.farmProfile.farmingExperience,
        farmType: data.farmProfile.farmType,
        primaryFarmingSystem: data.farmProfile.primaryFarmingSystem,
        certifications: data.farmProfile.certifications,
        participatesInPrograms: data.farmProfile.participatesInPrograms
      },
      cropProductions: data.cropProductions.map((crop, index) => ({
        cropId: crop.cropId || `crop_${index + 1}`,
        cropName: crop.cropName,
        localName: crop.localName,
        category: crop.category as FoodCategory, // Form validation ensures this is a valid FoodCategory
        variety: crop.variety,
        areaAllocated: crop.areaAllocated,
        annualProduction: crop.annualProduction,
        productionSystem: crop.productionSystem,
        croppingPattern: crop.croppingPattern,
        seasonality: crop.seasonality,
        isIntercropped: crop.isIntercropped,
        intercroppingPartners: crop.intercroppingPartners,
        intercroppingRatio: crop.intercroppingRatio,
        rotationSequence: crop.rotationSequence,
        rotationDuration: crop.rotationDuration,
        averageYieldPerHectare: crop.averageYieldPerHectare,
        postHarvestLosses: crop.postHarvestLosses,
        qualityGrades: [] // Default to empty array, can be enhanced later
      })),
      managementPractices: {
        soilManagement: {
          ...data.managementPractices.soilManagement,
          soilpH: data.managementPractices.soilManagement.soilpH || 6.5, // Default pH if not provided
          organicMatterContent: data.managementPractices.soilManagement.organicMatterContent || 2.0 // Default organic matter
        },
        fertilization: {
          ...data.managementPractices.fertilization,
          fertilizerApplications: data.managementPractices.fertilization.fertilizerApplications?.map(fert => ({
            ...fert,
            cost: fert.cost || 0 // Provide default cost
          })) || [],
          applicationMethod: data.managementPractices.fertilization.applicationMethod || ApplicationMethod.BROADCAST,
          timingStrategy: data.managementPractices.fertilization.timingStrategy || TimingStrategy.AT_PLANTING
        },
        waterManagement: {
          ...data.managementPractices.waterManagement,
          waterUseEfficiency: [], // Default to empty, can be enhanced later
          waterConservationPractices: [] // Default to empty enum array, can be enhanced later
        },
        pestManagement: {
          primaryPests: data.pestManagement?.primaryPests || [],
          primaryDiseases: data.pestManagement?.primaryDiseases || [],
          managementApproach: data.pestManagement?.managementApproach || 'INTEGRATED_IPM',
          pesticides: data.pestManagement?.pesticides?.map(pest => ({
            ...pest,
            cost: pest.cost || 0,
            safetyPrecautions: [] // Add missing required field
          })) || [],
          usesIPM: data.pestManagement?.usesIPM || false,
          ipmPractices: data.pestManagement?.ipmPractices || [],
          biologicalControls: data.pestManagement?.biologicalControls || [],
          pestMonitoringFrequency: data.pestManagement?.pestMonitoringFrequency || 'MONTHLY',
          usesEconomicThresholds: data.pestManagement?.usesEconomicThresholds || false
        },
        tillageSystem: TillageSystem.CONVENTIONAL_TILLAGE, // Default tillage system
        harvestingMethods: {
          primaryMethod: HarvestingMethod.MANUAL_HARVESTING,
          secondaryMethods: [],
          mechanizationLevel: MechanizationLevel.FULLY_MANUAL,
          laborIntensity: LaborIntensity.HIGH,
          postHarvestHandling: [PostHarvestHandling.FIELD_DRYING]
        }
      },
      pestManagement: {
        primaryPests: data.pestManagement?.primaryPests || [],
        primaryDiseases: data.pestManagement?.primaryDiseases || [],
        managementApproach: data.pestManagement?.managementApproach || 'INTEGRATED_IPM',
        pesticides: data.pestManagement?.pesticides?.map(pest => ({
          ...pest,
          cost: pest.cost || 0,
          safetyPrecautions: [] // Add missing required field
        })) || [],
        usesIPM: data.pestManagement?.usesIPM || false,
        ipmPractices: data.pestManagement?.ipmPractices || [],
        biologicalControls: data.pestManagement?.biologicalControls || [],
        pestMonitoringFrequency: data.pestManagement?.pestMonitoringFrequency || 'MONTHLY',
        usesEconomicThresholds: data.pestManagement?.usesEconomicThresholds || false
      },
      equipmentEnergy: {
        equipment: data.equipmentEnergy.equipment?.map(eq => ({
          ...eq,
          maintenanceFrequency: MaintenanceFrequency.MONTHLY // Add missing required field
        })) || [],
        energySources: data.equipmentEnergy.energySources?.map(energy => ({
          ...energy,
          cost: energy.cost || 0 // Provide default cost
        })) || [],
        fuelConsumption: [], // Default to empty, can be enhanced later
        infrastructure: {
          ...data.equipmentEnergy.infrastructure,
          processingFacilities: [], // Add missing required field
          transportAccess: {
            ...data.equipmentEnergy.infrastructure.transportAccess,
            transportCost: data.equipmentEnergy.infrastructure.transportAccess?.transportCost || 0 // Provide default cost
          }
        }
      },
      assessmentParameters: data.assessmentParameters
    };
  };

  const renderCurrentStep = () => {
    switch (currentStep) {
      case FormStep.FARM_PROFILE:
        return <FarmProfileStep />;
      case FormStep.CROP_DETAILS:
        return <CropDetailsStep />;
      case FormStep.MANAGEMENT_PRACTICES:
        return <ManagementPracticesStep />;
      case FormStep.PEST_MANAGEMENT:
        return <PestManagementStep />;
      case FormStep.EQUIPMENT_ENERGY:
        return <EquipmentEnergyStep />;
      case FormStep.REVIEW_SUBMIT:
        return <ReviewSubmitStep onSubmit={handleSubmit(onSubmit)} isSubmitting={isSubmitting} onPrevious={handlePreviousStep} />;
      default:
        return <FarmProfileStep />;
    }
  };

  const currentStepInfo = FORM_STEPS.find(step => step.id === currentStep);
  const progress = getStepProgress(currentStep);

  return (
    <Layout>
      <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-50 py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-center mb-8"
          >
            <div className="w-16 h-16 bg-gradient-to-r from-green-500 to-emerald-500 rounded-full flex items-center justify-center mx-auto mb-4">
              <Sprout className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-3xl md:text-4xl font-bold text-gray-900 mb-2">
              Comprehensive Farm Sustainability Assessment
            </h1>
            <p className="text-lg text-gray-600 max-w-3xl mx-auto">
              Get detailed environmental impact analysis with actionable recommendations tailored for African farming systems
            </p>
          </motion.div>

          {/* Progress Bar */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mb-12"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-2">
                <Clock className="w-5 h-5 text-gray-500" />
                <span className="text-sm text-gray-600">
                  Estimated time: {currentStepInfo?.estimatedTime}
                </span>
              </div>
              <div className="text-sm text-gray-600">
                Step {FORM_STEPS.findIndex(s => s.id === currentStep) + 1} of {FORM_STEPS.length}
              </div>
            </div>
            
            <div className="w-full bg-gray-200 rounded-full h-2">
              <motion.div
                className="bg-gradient-to-r from-green-500 to-emerald-500 h-2 rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.5 }}
              />
            </div>
          </motion.div>

          {/* Step Navigation */}
          <div className="mb-12 px-4 sm:px-0">
            <div className="flex items-center justify-between">
              {FORM_STEPS.map((step, index) => {
                const Icon = stepIcons[step.id];
                const isActive = step.id === currentStep;
                const isCompleted = FORM_STEPS.findIndex(s => s.id === currentStep) > index;
                
                return (
                  <div
                    key={step.id}
                    className={`flex items-center ${index < FORM_STEPS.length - 1 ? 'flex-1' : ''}`}
                  >
                    <div className="relative">
                      <div className={`
                        w-10 h-10 rounded-full flex items-center justify-center border-2
                        ${isActive 
                          ? 'bg-green-500 border-green-500 text-white' 
                          : isCompleted 
                            ? 'bg-green-100 border-green-500 text-green-600'
                            : 'bg-white border-gray-300 text-gray-400'
                        }
                      `}>
                        {isCompleted ? (
                          <CheckCircle className="w-5 h-5" />
                        ) : (
                          <Icon className="w-5 h-5" />
                        )}
                      </div>
                      <div className="absolute top-12 left-1/2 transform -translate-x-1/2 text-xs text-center">
                        <div className={`font-medium ${isActive ? 'text-green-600' : 'text-gray-500'}`}>
                          {step.title}
                        </div>
                      </div>
                    </div>
                    
                    {index < FORM_STEPS.length - 1 && (
                      <div className={`
                        flex-1 h-0.5 mx-4 mt-2
                        ${isCompleted ? 'bg-green-300' : 'bg-gray-200'}
                      `} />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Form Content */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="bg-white rounded-2xl shadow-xl overflow-hidden"
          >
            <div className="bg-gradient-to-r from-green-500 to-emerald-500 px-8 py-6">
              <h2 className="text-2xl font-bold text-white">
                {currentStepInfo?.title}
              </h2>
              <p className="text-green-100 mt-1">
                {currentStepInfo?.description}
              </p>
            </div>

            <FormProvider {...methods}>
              <div className="p-8">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={currentStep}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.3 }}
                  >
                    {renderCurrentStep()}
                  </motion.div>
                </AnimatePresence>
              </div>
            </FormProvider>

            {/* Navigation Footer */}
            {currentStep !== FormStep.REVIEW_SUBMIT && (
              <div className="bg-gray-50 px-8 py-6 flex justify-between items-center">
                <button
                  type="button"
                  onClick={handlePreviousStep}
                  disabled={currentStep === FormStep.FARM_PROFILE}
                  className="flex items-center space-x-2 px-6 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                  <span>Previous</span>
                </button>

                <div className="text-sm text-gray-500">
                  {(() => {
                    // Only show errors for current step
                    let hasCurrentStepErrors = false;
                    
                    if (currentStep === FormStep.FARM_PROFILE) {
                      hasCurrentStepErrors = !!errors.farmProfile;
                    } else if (currentStep === FormStep.CROP_DETAILS) {
                      hasCurrentStepErrors = !!errors.cropProductions;
                    } else if (currentStep === FormStep.MANAGEMENT_PRACTICES) {
                      hasCurrentStepErrors = !!errors.managementPractices;
                    } else if (currentStep === FormStep.PEST_MANAGEMENT) {
                      hasCurrentStepErrors = !!errors.pestManagement;
                    } else if (currentStep === FormStep.EQUIPMENT_ENERGY) {
                      hasCurrentStepErrors = !!errors.equipmentEnergy || !!errors.assessmentParameters;
                    } else if (currentStep === FormStep.REVIEW_SUBMIT) {
                      hasCurrentStepErrors = Object.keys(errors).length > 0;
                    }
                    
                    return hasCurrentStepErrors ? (
                      <div className="flex items-center space-x-2 text-red-600">
                        <AlertTriangle className="w-4 h-4" />
                        <span>Please fix errors to continue</span>
                      </div>
                    ) : null;
                  })()}
                </div>

                <button
                  type="button"
                  onClick={handleNextStep}
                  className="flex items-center space-x-2 bg-green-600 text-white px-6 py-3 rounded-lg hover:bg-green-700 transition-colors"
                >
                  <span>Next</span>
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </motion.div>

          {/* Submit Result */}
          {submitResult && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className={`mt-6 max-w-md mx-auto text-center p-6 rounded-lg ${
                submitResult.success 
                  ? 'bg-green-50 text-green-800 border border-green-200' 
                  : 'bg-red-50 text-red-800 border border-red-200'
              }`}
            >
              <div className="flex items-center justify-center space-x-2 mb-2">
                {submitResult.success ? (
                  <CheckCircle className="w-6 h-6" />
                ) : (
                  <AlertTriangle className="w-6 h-6" />
                )}
                <span className="font-medium">{submitResult.message}</span>
              </div>
              {submitResult.success && (
                <p className="text-sm text-green-600">
                  Redirecting to comprehensive results page...
                </p>
              )}
            </motion.div>
          )}

          {/* Help Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="mt-8 bg-blue-50 border border-blue-200 rounded-xl p-6"
          >
            <div className="flex items-start space-x-3">
              <Info className="w-6 h-6 text-blue-600 mt-0.5" />
              <div>
                <h3 className="text-lg font-semibold text-blue-900 mb-2">
                  Why This Detailed Assessment?
                </h3>
                <p className="text-blue-700 mb-3">
                  This comprehensive assessment follows international LCA standards (ISO 14040/14044) 
                  to provide you with accurate, scientifically-backed sustainability insights specific 
                  to African farming systems.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-blue-600">
                  <div>
                    <strong>✓ More Accurate Results:</strong> Detailed inputs provide precise environmental impact calculations
                  </div>
                  <div>
                    <strong>✓ Specific Recommendations:</strong> Tailored advice based on your actual practices
                  </div>
                  <div>
                    <strong>✓ Benchmark Comparisons:</strong> See how you compare to similar farms
                  </div>
                  <div>
                    <strong>✓ Improvement Pathways:</strong> Clear steps to reduce environmental impact
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </Layout>
  );
}