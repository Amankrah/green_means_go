'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useForm, FormProvider } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

// Force dynamic rendering for this page
export const dynamic = 'force-dynamic';
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
  MaintenanceFrequency,
  ProductionSystem,
  CroppingPattern,
  SeasonType,
  SoilType,
  TestingFrequency,
  SoilConservationPractice,
  FertilizerType,
  WaterSource,
  IrrigationSystem,
  PestManagementApproach,
  PesticideType,
  IPMPractice,
  MonitoringFrequency,
  EquipmentType,
  PowerSource,
  EnergyType,
  FuelType,
  StorageFacilityType,
  RoadAccessType,
  TransportMode,
  Currency
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
        farmerName: 'Kwame Mensah',
        farmName: 'Mensah Family Farms',
        country: 'Ghana',
        region: 'Ashanti',
        totalFarmSize: 8.5,
        farmingExperience: 18,
        farmType: FarmType.MEDIUM_SCALE,
        primaryFarmingSystem: FarmingSystem.SEMI_COMMERCIAL,
        certifications: [],
        participatesInPrograms: ['Climate Smart Agriculture', 'Farmer Field School']
      },
      cropProductions: [
        {
          cropId: 'crop_maize_001',
          cropName: 'Maize',
          localName: 'Aburo',
          category: 'Cereals',
          variety: 'Oba Super 2',
          areaAllocated: 5.0,
          annualProduction: 9500,
          productionSystem: ProductionSystem.RAINFED,
          croppingPattern: CroppingPattern.INTERCROPPING,
          seasonality: {
            plantingMonths: [4, 5],
            harvestingMonths: [8, 9],
            growingPeriod: 120,
            cropsPerYear: 2,
            season: [SeasonType.WET_SEASON]
          },
          isIntercropped: true,
          intercroppingPartners: ['Cowpea'],
          intercroppingRatio: {},
          rotationSequence: ['Maize', 'Cowpea', 'Groundnuts'],
          rotationDuration: 2,
          averageYieldPerHectare: 1900,
          postHarvestLosses: 12
        },
        {
          cropId: 'crop_cassava_001',
          cropName: 'Cassava',
          localName: 'Bankye',
          category: 'Roots',
          variety: 'Bankye Hemaa',
          areaAllocated: 3.5,
          annualProduction: 31500,
          productionSystem: ProductionSystem.RAINFED,
          croppingPattern: CroppingPattern.MONOCULTURE,
          seasonality: {
            plantingMonths: [3, 4],
            harvestingMonths: [12, 1],
            growingPeriod: 270,
            cropsPerYear: 1,
            season: [SeasonType.WET_SEASON, SeasonType.DRY_SEASON]
          },
          isIntercropped: false,
          intercroppingPartners: [],
          intercroppingRatio: {},
          rotationSequence: ['Cassava', 'Vegetables'],
          rotationDuration: 2,
          averageYieldPerHectare: 9000,
          postHarvestLosses: 15
        }
      ],
      managementPractices: {
        soilManagement: {
          soilType: SoilType.LOAM,
          soilpH: 6.2,
          organicMatterContent: 3.5,
          soilTestingFrequency: TestingFrequency.EVERY_2_3_YEARS,
          conservationPractices: [
            SoilConservationPractice.CONTOUR_PLOWING,
            SoilConservationPractice.MULCHING,
            SoilConservationPractice.MINIMUM_TILL
          ],
          coverCrops: ['Mucuna', 'Cowpea'],
          compostUse: {
            usesCompost: true,
            compostsource: CompostSource.FARM_MADE,
            applicationRate: 8,
            applicationTiming: "Before planting"
          }
        },
        fertilization: {
          usesFertilizers: true,
          fertilizerApplications: [
            {
              fertilizerType: FertilizerType.NPK_COMPOUND,
              brandName: 'Yara NPK 15-15-15',
              npkRatio: '15-15-15',
              applicationRate: 250,
              applicationsPerSeason: 1,
              cost: 185,
              currency: Currency.GHS
            },
            {
              fertilizerType: FertilizerType.UREA,
              brandName: 'Wienco Urea',
              npkRatio: '46-0-0',
              applicationRate: 100,
              applicationsPerSeason: 2,
              cost: 120,
              currency: Currency.GHS
            }
          ],
          applicationMethod: ApplicationMethod.BAND_PLACEMENT,
          timingStrategy: TimingStrategy.SPLIT_APPLICATION,
          soilTestBased: true,
          followsNutrientPlan: true
        },
        waterManagement: {
          waterSource: [WaterSource.RAINFALL, WaterSource.RIVER_STREAM],
          irrigationSystem: IrrigationSystem.NONE,
          drainageSystem: true,
          waterConservationPractices: []
        }
      },
      pestManagement: {
        primaryPests: ['Fall armyworm', 'Stemborer', 'Cassava green mite'],
        primaryDiseases: ['Maize leaf blight', 'Cassava mosaic disease'],
        managementApproach: PestManagementApproach.INTEGRATED_IPM,
        pesticides: [
          {
            pesticideType: PesticideType.INSECTICIDE,
            activeIngredient: 'Emamectin benzoate',
            brandName: 'Lancer 2.5 EC',
            applicationRate: 0.5,
            applicationsPerSeason: 3,
            targetPests: ['Fall armyworm', 'Stemborer'],
            cost: 45,
            currency: Currency.GHS,
            safetyPrecautions: []
          },
          {
            pesticideType: PesticideType.INSECTICIDE,
            activeIngredient: 'Lambda-cyhalothrin',
            brandName: 'Karate 5EC',
            applicationRate: 0.3,
            applicationsPerSeason: 2,
            targetPests: ['Cassava green mite'],
            cost: 38,
            currency: Currency.GHS,
            safetyPrecautions: []
          }
        ],
        usesIPM: true,
        ipmPractices: [
          IPMPractice.CROP_ROTATION,
          IPMPractice.COMPANION_PLANTING,
          IPMPractice.RESISTANT_VARIETIES,
          IPMPractice.CULTURAL_CONTROLS
        ],
        biologicalControls: ['Neem extract', 'Trichogramma wasps'],
        pestMonitoringFrequency: MonitoringFrequency.WEEKLY,
        usesEconomicThresholds: true
      },
      equipmentEnergy: {
        equipment: [
          {
            equipmentType: EquipmentType.MEDIUM_TRACTOR,
            powerSource: PowerSource.DIESEL,
            age: 8,
            hoursPerYear: 320,
            fuelEfficiency: 12.5
          },
          {
            equipmentType: EquipmentType.SPRAYER,
            powerSource: PowerSource.PETROL,
            age: 3,
            hoursPerYear: 85,
            fuelEfficiency: 2.8
          },
          {
            equipmentType: EquipmentType.WATER_PUMP,
            powerSource: PowerSource.PETROL,
            age: 5,
            hoursPerYear: 120,
            fuelEfficiency: 3.2
          }
        ],
        energySources: [
          {
            energyType: EnergyType.DIESEL_GENERATOR,
            monthlyConsumption: 145,
            primaryUse: 'Tractor operations (plowing, planting, transport)',
            cost: 320,
            currency: Currency.GHS
          },
          {
            energyType: EnergyType.GRID_ELECTRICITY,
            monthlyConsumption: 85,
            primaryUse: 'Lighting, phone charging, small tools',
            cost: 65,
            currency: Currency.GHS
          }
        ],
        infrastructure: {
          storageCapacity: 12000,
          storageFacilities: [
            StorageFacilityType.TRADITIONAL_GRANARY,
            StorageFacilityType.HERMETIC_STORAGE
          ],
          transportAccess: {
            roadAccess: RoadAccessType.GRAVEL_ROAD,
            distanceToMarket: 18,
            transportMode: [TransportMode.PICKUP_TRUCK, TransportMode.MOTORCYCLE],
            transportCost: 45
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

      // Debug: Check if fuelConsumption is being populated
      const fuelConsumptionDebug = {
        hasEquipmentEnergy: !!apiData.equipmentEnergy,
        fuelConsumptionLength: apiData.equipmentEnergy?.fuelConsumption?.length || 0,
        fuelConsumptionData: apiData.equipmentEnergy?.fuelConsumption,
        energySourcesLength: apiData.equipmentEnergy?.energySources?.length || 0,
        energySourcesData: apiData.equipmentEnergy?.energySources
      };

      console.log('=== FUEL CONSUMPTION DEBUG ===');
      console.log('Equipment Energy Data:', apiData.equipmentEnergy);
      console.log('Fuel Consumption Array LENGTH:', fuelConsumptionDebug.fuelConsumptionLength);
      console.log('Fuel Consumption Array:', fuelConsumptionDebug.fuelConsumptionData);
      console.log('Energy Sources Array:', fuelConsumptionDebug.energySourcesData);
      console.log('==============================');

      // Store in localStorage so we can check it later
      localStorage.setItem('lastFuelDebug', JSON.stringify(fuelConsumptionDebug, null, 2));

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
        // Extract fuel consumption from energy sources
        // Convert energy sources like "Diesel Generator" to fuel consumption entries
        fuelConsumption: data.equipmentEnergy.energySources
          ?.filter(energy => {
            const energyTypeStr = typeof energy.energyType === 'string'
              ? energy.energyType
              : String(energy.energyType);

            return energyTypeStr.includes('Diesel') ||
                   energyTypeStr.includes('diesel') ||
                   energyTypeStr.includes('Petrol') ||
                   energyTypeStr.includes('Gasoline') ||
                   energyTypeStr.includes('gasoline');
          })
          .map(energy => {
            const energyTypeStr = typeof energy.energyType === 'string'
              ? energy.energyType
              : String(energy.energyType);

            // Determine fuel type based on energy type
            let fuelType = FuelType.DIESEL;
            if (energyTypeStr.includes('Diesel') || energyTypeStr.includes('diesel')) {
              fuelType = FuelType.DIESEL;
            } else if (energyTypeStr.includes('Petrol') || energyTypeStr.includes('Gasoline')) {
              fuelType = FuelType.PETROL;
            }

            return {
              fuelType,
              monthlyConsumption: energy.monthlyConsumption || 0,
              primaryUse: energy.primaryUse || 'Farm operations',
              cost: energy.cost || 0
            };
          }) || [],
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
      <div className="min-h-screen bg-gradient-to-br from-green-50 via-emerald-50/50 to-teal-50 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-center mb-12"
          >
            <motion.div 
              className="w-20 h-20 bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-xl"
              whileHover={{ scale: 1.05, rotate: 5 }}
              transition={{ duration: 0.3 }}
            >
              <Sprout className="w-10 h-10 text-white" />
            </motion.div>
            <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4 leading-tight">
              Comprehensive Farm Sustainability Assessment
            </h1>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
              Get detailed environmental impact analysis with actionable recommendations tailored for African farming systems
            </p>
          </motion.div>

          {/* Progress Bar */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="mb-12 bg-white/80 backdrop-blur-sm rounded-2xl p-6 shadow-lg border border-white"
          >
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-green-100 rounded-xl flex items-center justify-center">
                  <Clock className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <div className="text-sm font-medium text-gray-900">
                    Estimated time: {currentStepInfo?.estimatedTime}
                  </div>
                  <div className="text-xs text-gray-500">Save and continue anytime</div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-green-600">
                  {FORM_STEPS.findIndex(s => s.id === currentStep) + 1}/{FORM_STEPS.length}
                </div>
                <div className="text-xs text-gray-500 font-medium">Steps</div>
              </div>
            </div>
            
            <div className="relative w-full bg-gray-200 rounded-full h-3 overflow-hidden">
              <motion.div
                className="absolute top-0 left-0 h-full bg-gradient-to-r from-green-500 via-emerald-500 to-teal-500 rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.8, ease: "easeOut" }}
              />
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-pulse" />
            </div>
            <div className="mt-2 text-right text-xs font-semibold text-green-600">
              {Math.round(progress)}% Complete
            </div>
          </motion.div>

          {/* Step Navigation */}
          <div className="mb-12 px-2 sm:px-0 overflow-x-auto">
            <div className="flex items-center justify-between min-w-max sm:min-w-0">
              {FORM_STEPS.map((step, index) => {
                const Icon = stepIcons[step.id];
                const isActive = step.id === currentStep;
                const isCompleted = FORM_STEPS.findIndex(s => s.id === currentStep) > index;
                
                return (
                  <div
                    key={step.id}
                    className={`flex items-center ${index < FORM_STEPS.length - 1 ? 'flex-1' : ''}`}
                  >
                    <motion.div 
                      className="relative"
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ duration: 0.4, delay: index * 0.1 }}
                    >
                      <motion.div 
                        className={`
                          w-14 h-14 rounded-2xl flex items-center justify-center border-2 shadow-lg transition-all duration-300
                          ${isActive 
                            ? 'bg-gradient-to-br from-green-500 to-emerald-600 border-green-400 text-white scale-110 shadow-green-200' 
                            : isCompleted 
                              ? 'bg-gradient-to-br from-green-100 to-emerald-50 border-green-400 text-green-600'
                              : 'bg-white border-gray-300 text-gray-400'
                          }
                        `}
                        whileHover={{ scale: isActive ? 1.15 : 1.05 }}
                        whileTap={{ scale: 0.95 }}
                      >
                        {isCompleted ? (
                          <motion.div
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            transition={{ type: "spring", stiffness: 500, damping: 15 }}
                          >
                            <CheckCircle className="w-7 h-7" />
                          </motion.div>
                        ) : (
                          <Icon className="w-7 h-7" />
                        )}
                      </motion.div>
                      <div className="absolute top-16 left-1/2 transform -translate-x-1/2 text-center w-24">
                        <div className={`text-xs font-semibold ${isActive ? 'text-green-600' : isCompleted ? 'text-green-500' : 'text-gray-500'}`}>
                          {step.title.split(' ')[0]}
                        </div>
                        <div className={`text-[10px] ${isActive ? 'text-green-500' : 'text-gray-400'}`}>
                          {step.title.split(' ').slice(1).join(' ')}
                        </div>
                      </div>
                    </motion.div>
                    
                    {index < FORM_STEPS.length - 1 && (
                      <div className="flex-1 h-1 mx-3 mt-2 relative">
                        <div className="absolute inset-0 bg-gray-200 rounded-full" />
                        <motion.div 
                          className="absolute inset-0 bg-gradient-to-r from-green-400 to-emerald-500 rounded-full"
                          initial={{ scaleX: 0 }}
                          animate={{ scaleX: isCompleted ? 1 : 0 }}
                          transition={{ duration: 0.5, delay: index * 0.1 }}
                          style={{ transformOrigin: 'left' }}
                        />
                      </div>
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
            transition={{ duration: 0.6, delay: 0.4 }}
            className="bg-white rounded-3xl shadow-2xl overflow-hidden border border-gray-100"
          >
            <div className="relative bg-gradient-to-br from-green-500 via-emerald-500 to-teal-600 px-8 py-8">
              {/* Background Pattern */}
              <div className="absolute inset-0 opacity-10">
                <div className="absolute top-0 right-0 w-32 h-32 bg-white rounded-full blur-3xl"></div>
                <div className="absolute bottom-0 left-0 w-40 h-40 bg-white rounded-full blur-3xl"></div>
              </div>
              
              <div className="relative z-10">
                <div className="flex items-center space-x-3 mb-3">
                  {(() => {
                    const Icon = stepIcons[currentStep];
                    return <Icon className="w-7 h-7 text-white" />;
                  })()}
                  <span className="px-3 py-1 bg-white/20 backdrop-blur-sm rounded-full text-xs font-semibold text-white">
                    Step {FORM_STEPS.findIndex(s => s.id === currentStep) + 1} of {FORM_STEPS.length}
                  </span>
                </div>
                <h2 className="text-3xl font-bold text-white mb-2">
                  {currentStepInfo?.title}
                </h2>
                <p className="text-green-50 text-lg leading-relaxed">
                  {currentStepInfo?.description}
                </p>
              </div>
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
              <div className="bg-gradient-to-r from-gray-50 to-green-50/30 px-8 py-6 flex flex-col sm:flex-row justify-between items-center gap-4 border-t border-gray-200">
                <motion.button
                  type="button"
                  onClick={handlePreviousStep}
                  disabled={currentStep === FormStep.FARM_PROFILE}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="flex items-center space-x-2 px-8 py-3.5 border-2 border-gray-300 rounded-xl text-gray-700 font-semibold hover:bg-white hover:border-gray-400 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm"
                >
                  <ChevronLeft className="w-5 h-5" />
                  <span>Previous</span>
                </motion.button>

                <div className="text-sm text-center">
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
                      <motion.div 
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex items-center space-x-2 text-red-600 bg-red-50 px-4 py-2 rounded-lg border border-red-200"
                      >
                        <AlertTriangle className="w-5 h-5" />
                        <span className="font-medium">Please fix errors to continue</span>
                      </motion.div>
                    ) : null;
                  })()}
                </div>

                <motion.button
                  type="button"
                  onClick={handleNextStep}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="flex items-center space-x-2 bg-gradient-to-r from-green-600 to-emerald-600 text-white px-8 py-3.5 rounded-xl font-semibold hover:from-green-700 hover:to-emerald-700 transition-all shadow-lg hover:shadow-xl"
                >
                  <span>Next Step</span>
                  <ChevronRight className="w-5 h-5" />
                </motion.button>
              </div>
            )}
          </motion.div>

          {/* Submit Result */}
          {submitResult && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 25 }}
              className={`mt-8 max-w-2xl mx-auto text-center p-8 rounded-3xl shadow-2xl ${
                submitResult.success 
                  ? 'bg-gradient-to-br from-green-50 to-emerald-50 border-2 border-green-300' 
                  : 'bg-gradient-to-br from-red-50 to-orange-50 border-2 border-red-300'
              }`}
            >
              <div className="flex flex-col items-center space-y-4">
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 500, damping: 20, delay: 0.2 }}
                  className={`w-20 h-20 rounded-full flex items-center justify-center ${
                    submitResult.success ? 'bg-green-500' : 'bg-red-500'
                  }`}
                >
                  {submitResult.success ? (
                    <CheckCircle className="w-12 h-12 text-white" />
                  ) : (
                    <AlertTriangle className="w-12 h-12 text-white" />
                  )}
                </motion.div>
                <div>
                  <h3 className={`text-2xl font-bold mb-2 ${
                    submitResult.success ? 'text-green-900' : 'text-red-900'
                  }`}>
                    {submitResult.success ? 'Success!' : 'Error'}
                  </h3>
                  <p className={`text-lg ${
                    submitResult.success ? 'text-green-700' : 'text-red-700'
                  }`}>
                    {submitResult.message}
                  </p>
                </div>
                {submitResult.success && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.5 }}
                    className="flex items-center space-x-2 text-green-600 bg-green-100 px-4 py-2 rounded-full"
                  >
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    <span className="text-sm font-medium">Redirecting to comprehensive results page...</span>
                  </motion.div>
                )}
              </div>
            </motion.div>
          )}

          {/* Help Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.6 }}
            className="mt-10 bg-gradient-to-br from-blue-50 to-cyan-50 border-2 border-blue-200 rounded-3xl p-8 shadow-lg"
          >
            <div className="flex items-start space-x-4">
              <div className="w-12 h-12 bg-blue-500 rounded-2xl flex items-center justify-center flex-shrink-0 shadow-lg">
                <Info className="w-7 h-7 text-white" />
              </div>
              <div className="flex-1">
                <h3 className="text-2xl font-bold text-blue-900 mb-3">
                  Why This Detailed Assessment?
                </h3>
                <p className="text-blue-800 mb-5 leading-relaxed text-lg">
                  This comprehensive assessment follows international LCA standards (ISO 14040/14044) 
                  to provide you with accurate, scientifically-backed sustainability insights specific 
                  to African farming systems.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[
                    { title: 'More Accurate Results', desc: 'Detailed inputs provide precise environmental impact calculations' },
                    { title: 'Specific Recommendations', desc: 'Tailored advice based on your actual practices' },
                    { title: 'Benchmark Comparisons', desc: 'See how you compare to similar farms' },
                    { title: 'Improvement Pathways', desc: 'Clear steps to reduce environmental impact' }
                  ].map((item, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.4, delay: 0.7 + (idx * 0.1) }}
                      className="bg-white/60 backdrop-blur-sm rounded-xl p-4 border border-blue-100"
                    >
                      <div className="flex items-start space-x-2">
                        <div className="w-6 h-6 bg-green-500 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                          <CheckCircle className="w-4 h-4 text-white" />
                        </div>
                        <div>
                          <div className="font-bold text-blue-900 mb-1">{item.title}</div>
                          <div className="text-sm text-blue-700 leading-relaxed">{item.desc}</div>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </Layout>
  );
}