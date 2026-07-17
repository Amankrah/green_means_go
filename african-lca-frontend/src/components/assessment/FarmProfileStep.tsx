'use client';

import React from 'react';
import { useFormContext } from 'react-hook-form';
import { motion } from 'framer-motion';
import { 
  User, 
  MapPin, 
  TrendingUp, 
  Award,
  AlertCircle,
  Info,
  Globe
} from 'lucide-react';

import { 
  FarmType, 
  FarmingSystem, 
  CertificationType 
} from '@/types/enhanced-assessment';
import {
  EnhancedAssessmentFormData,
  REGIONS_BY_COUNTRY
} from '@/lib/enhanced-assessment-schema';
import {
  COUNTRY_EXAMPLES,
  EXAMPLE_FARM_NAMES,
  EXAMPLE_FARMER_NAMES,
  isExampleIdentity,
} from '@/lib/country-examples';

export default function FarmProfileStep() {
  const {
    register,
    formState: { errors },
    watch,
    setValue,
    reset,
    getValues
  } = useFormContext<EnhancedAssessmentFormData>();

  const selectedCountry = watch('farmProfile.country');
  const countryField = register('farmProfile.country');

  // When the user picks a country, load that country's example farm (from the validated
  // case studies) so agronomic defaults reflect a real farm for the region. Custom
  // farmer/farm names are preserved — only empty or known demo placeholders are replaced.
  const onCountryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    countryField.onChange(e);                       // keep react-hook-form in sync
    const example = COUNTRY_EXAMPLES[e.target.value];
    if (example) {
      const current = getValues();
      const keepFarmer = !isExampleIdentity(current.farmProfile?.farmerName, EXAMPLE_FARMER_NAMES);
      const keepFarm = !isExampleIdentity(current.farmProfile?.farmName, EXAMPLE_FARM_NAMES);
      reset({
        ...current,
        ...example,
        farmProfile: {
          ...example.farmProfile,
          farmerName: keepFarmer
            ? current.farmProfile.farmerName
            : example.farmProfile.farmerName,
          farmName: keepFarm
            ? current.farmProfile.farmName
            : example.farmProfile.farmName,
          country: e.target.value as EnhancedAssessmentFormData['farmProfile']['country'],
        },
      } as EnhancedAssessmentFormData);
    }
  };
  const totalFarmSize = watch('farmProfile.totalFarmSize');

  // Auto-select farm type based on size
  React.useEffect(() => {
    if (totalFarmSize) {
      if (totalFarmSize < 2) {
        setValue('farmProfile.farmType', FarmType.SMALLHOLDER);
      } else if (totalFarmSize <= 5) {
        setValue('farmProfile.farmType', FarmType.SMALL_SCALE);
      } else if (totalFarmSize <= 20) {
        setValue('farmProfile.farmType', FarmType.MEDIUM_SCALE);
      } else {
        setValue('farmProfile.farmType', FarmType.COMMERCIAL);
      }
    }
  }, [totalFarmSize, setValue]);

  const farmTypeOptions = [
    { value: FarmType.SMALLHOLDER, label: '🏠 Smallholder (<2 hectares)', description: 'Family farm for subsistence and local markets' },
    { value: FarmType.SMALL_SCALE, label: '🌱 Small Scale (2-5 hectares)', description: 'Small commercial farm with some market sales' },
    { value: FarmType.MEDIUM_SCALE, label: '🚜 Medium Scale (5-20 hectares)', description: 'Commercial farm with regular market engagement' },
    { value: FarmType.COMMERCIAL, label: '🏭 Commercial (>20 hectares)', description: 'Large-scale commercial farming operation' },
    { value: FarmType.COOPERATIVE, label: '🤝 Cooperative', description: 'Member of a farming cooperative' },
    { value: FarmType.MIXED_LIVESTOCK, label: '🐄 Mixed Livestock & Crops', description: 'Integrated crop-livestock farming system' }
  ];

  const farmingSystemOptions = [
    { value: FarmingSystem.SUBSISTENCE, label: '🏠 Subsistence', description: 'Mainly for household food security' },
    { value: FarmingSystem.SEMI_COMMERCIAL, label: '💰 Semi-commercial', description: 'Mix of subsistence and market sales' },
    { value: FarmingSystem.COMMERCIAL, label: '💼 Commercial', description: 'Primarily for market sales and profit' },
    { value: FarmingSystem.ORGANIC, label: '🌿 Organic', description: 'Certified or practicing organic farming' },
    { value: FarmingSystem.AGROECOLOGICAL, label: '🌍 Agroecological', description: 'Sustainable, ecological farming practices' },
    { value: FarmingSystem.CONVENTIONAL, label: '⚡ Conventional', description: 'Standard modern farming with synthetic inputs' },
    { value: FarmingSystem.INTEGRATED_FARMING, label: '🔄 Integrated System', description: 'Multiple enterprises (crops, livestock, fish, etc.)' }
  ];

  const certificationOptions = [
    { value: CertificationType.ORGANIC, label: '🌿 Organic Certification' },
    { value: CertificationType.FAIRTRADE, label: '🤝 Fair Trade' },
    { value: CertificationType.RAINFOREST_ALLIANCE, label: '🌳 Rainforest Alliance' },
    { value: CertificationType.GLOBAL_GAP, label: '✅ GlobalGAP' },
    { value: CertificationType.NONE, label: '❌ No Certifications' }
  ];

  const sustainabilityPrograms = [
    'Climate Smart Agriculture',
    'Conservation Agriculture',
    'Sustainable Intensification',
    'Organic Farming Program',
    'Agroforestry Initiative',
    'Water Conservation Program',
    'Soil Health Program',
    'Integrated Pest Management',
    'Farmer Field School',
    'Agricultural Extension Program'
  ];

  return (
    <div className="space-y-8">
      {/* Basic Farm Information */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="gmg-section"
      >
        <div className="flex items-center space-x-3 mb-6">
          <div className="w-10 h-10 bg-moss/10 rounded-lg flex items-center justify-center">
            <User className="w-5 h-5 text-moss" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-ink">Basic Information</h3>
            <p className="text-sm text-muted">Tell us about yourself and your farm</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-ink mb-2">
              Farmer/Owner Name *
            </label>
            <input
              {...register('farmProfile.farmerName')}
              placeholder="e.g., Kwame Asante"
              className="gmg-input"
            />
            {errors.farmProfile?.farmerName && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.farmProfile.farmerName.message}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-ink mb-2">
              Farm Name *
            </label>
            <input
              {...register('farmProfile.farmName')}
              placeholder="e.g., Green Valley Farm"
              className="gmg-input"
            />
            {errors.farmProfile?.farmName && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.farmProfile.farmName.message}
              </p>
            )}
          </div>
        </div>
      </motion.section>

      {/* Location Information */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="gmg-section"
      >
        <div className="flex items-center space-x-3 mb-6">
          <div className="w-10 h-10 bg-moss/10 rounded-lg flex items-center justify-center">
            <MapPin className="w-5 h-5 text-moss" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-ink">Location Details</h3>
            <p className="text-sm text-muted">Help us understand your farming environment</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-ink mb-2">
              <Globe className="w-4 h-4 inline mr-1" />
              Country *
            </label>
            <select
              {...countryField}
              onChange={onCountryChange}
              className="gmg-input"
            >
              <option value="">Select your country</option>
              <option value="Ghana">🇬🇭 Ghana</option>
              <option value="Nigeria">🇳🇬 Nigeria</option>
              <option value="Canada">🇨🇦 Canada</option>
            </select>
            {errors.farmProfile?.country && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.farmProfile.country.message}
              </p>
            )}
            <p className="mt-1 text-xs text-muted">
              Choosing a country loads a matching example farm you can then edit.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-ink mb-2">
              Region/State *
            </label>
            <select
              {...register('farmProfile.region')}
              className="gmg-input"
            >
              <option value="">Select your region/state</option>
              {selectedCountry && REGIONS_BY_COUNTRY[selectedCountry]?.map((region) => (
                <option key={region} value={region}>
                  {region}
                </option>
              ))}
            </select>
            {errors.farmProfile?.region && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.farmProfile.region.message}
              </p>
            )}
          </div>
        </div>
      </motion.section>

      {/* Farm Size & Experience */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="gmg-section"
      >
        <div className="flex items-center space-x-3 mb-6">
          <div className="w-10 h-10 bg-moss/10 rounded-lg flex items-center justify-center">
            <TrendingUp className="w-5 h-5 text-moss" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-ink">Farm Scale & Experience</h3>
            <p className="text-sm text-muted">Size of your operation and farming background</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-ink mb-2">
              Total Farm Size (hectares) *
            </label>
            <input
              type="number"
              step="0.1"
              {...register('farmProfile.totalFarmSize', { valueAsNumber: true })}
              placeholder="e.g., 2.5"
              className="gmg-input"
            />
            {errors.farmProfile?.totalFarmSize && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.farmProfile.totalFarmSize.message}
              </p>
            )}
            {totalFarmSize && (
              <p className="mt-1 text-sm text-moss">
                <Info className="w-4 h-4 inline mr-1" />
                {totalFarmSize < 2 ? 'Smallholder farm' : 
                 totalFarmSize <= 5 ? 'Small-scale farm' :
                 totalFarmSize <= 20 ? 'Medium-scale farm' : 'Commercial-scale farm'}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-ink mb-2">
              Years of Farming Experience *
            </label>
            <input
              type="number"
              {...register('farmProfile.farmingExperience', { valueAsNumber: true })}
              placeholder="e.g., 15"
              className="gmg-input"
            />
            {errors.farmProfile?.farmingExperience && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.farmProfile.farmingExperience.message}
              </p>
            )}
          </div>
        </div>
      </motion.section>

      {/* Farm Type & System */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.3 }}
        className="gmg-section"
      >
        <div className="flex items-center space-x-3 mb-6">
          <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
            <TrendingUp className="w-5 h-5 text-purple-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-ink">Farming System</h3>
            <p className="text-sm text-muted">What type of farming operation do you run?</p>
          </div>
        </div>

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-ink mb-3">
              Farm Type *
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {farmTypeOptions.map((option) => (
                <label key={option.value} className="relative">
                  <input
                    type="radio"
                    {...register('farmProfile.farmType')}
                    value={option.value}
                    className="sr-only"
                  />
                  <div className={`
                    border-2 rounded-lg p-4 cursor-pointer transition-all
                    ${watch('farmProfile.farmType') === option.value
                      ? 'border-moss bg-moss/10'
                      : 'border-line hover:border-line'
                    }
                  `}>
                    <div className="font-medium text-ink mb-1">{option.label}</div>
                    <div className="text-sm text-muted">{option.description}</div>
                  </div>
                </label>
              ))}
            </div>
            {errors.farmProfile?.farmType && (
              <p className="mt-2 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.farmProfile.farmType.message}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-ink mb-3">
              Primary Farming System *
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {farmingSystemOptions.map((option) => (
                <label key={option.value} className="relative">
                  <input
                    type="radio"
                    {...register('farmProfile.primaryFarmingSystem')}
                    value={option.value}
                    className="sr-only"
                  />
                  <div className={`
                    border-2 rounded-lg p-4 cursor-pointer transition-all
                    ${watch('farmProfile.primaryFarmingSystem') === option.value
                      ? 'border-moss bg-moss/10'
                      : 'border-line hover:border-line'
                    }
                  `}>
                    <div className="font-medium text-ink mb-1">{option.label}</div>
                    <div className="text-sm text-muted">{option.description}</div>
                  </div>
                </label>
              ))}
            </div>
            {errors.farmProfile?.primaryFarmingSystem && (
              <p className="mt-2 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.farmProfile.primaryFarmingSystem.message}
              </p>
            )}
          </div>
        </div>
      </motion.section>

      {/* Certifications & Programs */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.4 }}
        className="gmg-section"
      >
        <div className="flex items-center space-x-3 mb-6">
          <div className="w-10 h-10 bg-amber/10 rounded-lg flex items-center justify-center">
            <Award className="w-5 h-5 text-amber" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-ink">Certifications & Programs</h3>
            <p className="text-sm text-muted">Any certifications or sustainability programs you participate in</p>
          </div>
        </div>

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-ink mb-3">
              Current Certifications (select all that apply)
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {certificationOptions.map((option) => (
                <label key={option.value} className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    {...register('farmProfile.certifications')}
                    value={option.value}
                    className="rounded border-line text-moss focus:ring-moss"
                  />
                  <span className="text-sm text-ink">{option.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-ink mb-3">
              Sustainability Programs (select all that apply)
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {sustainabilityPrograms.map((program) => (
                <label key={program} className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    {...register('farmProfile.participatesInPrograms')}
                    value={program}
                    className="rounded border-line text-moss focus:ring-moss"
                  />
                  <span className="text-sm text-ink">{program}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
      </motion.section>

      {/* Info Box */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="bg-moss/10 border border-line rounded-lg p-4"
      >
        <div className="flex items-start space-x-3">
          <Info className="w-5 h-5 text-moss mt-0.5" />
          <div className="text-sm text-spruce">
            <strong>Why we need this information:</strong> Your farm profile helps us select appropriate 
            environmental impact factors and benchmarks specific to your farming system and location. 
            This ensures more accurate sustainability assessment results.
          </div>
        </div>
      </motion.div>
    </div>
  );
}