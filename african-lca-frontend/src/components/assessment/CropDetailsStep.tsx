'use client';

import React, { useState } from 'react';
import { useFormContext, useFieldArray } from 'react-hook-form';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Sprout, 
  Plus, 
  Trash2, 
  AlertCircle,
  Info,
  Calendar,
  Layers,
  Target
} from 'lucide-react';

import { 
  ProductionSystem,
  CroppingPattern,
  SeasonType 
} from '@/types/enhanced-assessment';
import { 
  EnhancedAssessmentFormData,
  COMMON_CROPS_BY_REGION,
  calculateEstimatedYield,
  getCropVarieties,
  calculateAreaPercentage,
  validateTotalAllocation,
  sumAllocatedArea,
  remainingFarmArea,
} from '@/lib/enhanced-assessment-schema';

const foodCategories = [
  { value: 'Cereals', label: '🌾 Cereals (Maize, Rice, Millet, Sorghum)' },
  { value: 'Legumes', label: '🫘 Legumes (Beans, Groundnuts, Cowpea, Soybeans)' },
  { value: 'Roots', label: '🥔 Roots & Tubers (Cassava, Yam, Potato, Cocoyam)' },
  { value: 'Vegetables', label: '🥬 Vegetables (Tomato, Onion, Pepper, Okra)' },
  { value: 'Fruits', label: '🍌 Fruits (Plantain, Mango, Orange, Pineapple)' },
  { value: 'Oils', label: '🫒 Oil Crops (Palm Oil, Groundnut, Sunflower)' },
  { value: 'Other', label: '🌿 Other Crops' },
];

const productionSystems = [
  { value: ProductionSystem.RAINFED, label: '🌧️ Rainfed', description: 'Relies on natural rainfall' },
  { value: ProductionSystem.IRRIGATED, label: '💧 Irrigated', description: 'Uses irrigation systems' },
  { value: ProductionSystem.INTENSIVE, label: '🏭 Intensive', description: 'High input, high output farming' },
  { value: ProductionSystem.EXTENSIVE, label: '🌾 Extensive', description: 'Low input, larger area farming' },
  { value: ProductionSystem.SMALLHOLDER, label: '👨‍🌾 Smallholder', description: 'Small-scale family farming' },
  { value: ProductionSystem.AGROFORESTRY, label: '🌳 Agroforestry', description: 'Integrated with trees' },
  { value: ProductionSystem.ORGANIC, label: '🌿 Organic', description: 'Organic farming methods' },
  { value: ProductionSystem.CONVENTIONAL, label: '🚜 Conventional', description: 'Standard farming practices' }
];

const croppingPatterns = [
  { value: CroppingPattern.MONOCULTURE, label: '🌱 Monoculture', description: 'Single crop grown alone' },
  { value: CroppingPattern.INTERCROPPING, label: '🌿🌾 Intercropping', description: 'Multiple crops grown together' },
  { value: CroppingPattern.RELAY_CROPPING, label: '🔄 Relay Cropping', description: 'Sequential planting of crops' },
  { value: CroppingPattern.AGROFORESTRY, label: '🌳🌾 Agroforestry', description: 'Crops integrated with trees' },
  { value: CroppingPattern.CROP_ROTATION, label: '🔄 Crop Rotation', description: 'Different crops in sequence' }
];


const months = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

export default function CropDetailsStep() {
  const { 
    register, 
    control,
    formState: { errors }, 
    watch, 
    setValue,
    getValues
  } = useFormContext<EnhancedAssessmentFormData>();

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'cropProductions'
  });

  const [showIntercroppingDetails, setShowIntercroppingDetails] = useState<Record<string, boolean>>({});
  const [areaPercentages, setAreaPercentages] = useState<Record<number, number>>({});

  const farmProfile = watch('farmProfile');
  const region = farmProfile?.region || '';
  const country = farmProfile?.country || '';
  const totalFarmSize = farmProfile?.totalFarmSize || 0;
  const allCrops = watch('cropProductions') || [];
  const totalAllocated = sumAllocatedArea(allCrops);
  const remainingHa = remainingFarmArea(allCrops, totalFarmSize);
  const canAddCrop = totalFarmSize <= 0 || remainingHa >= 0.01;

  // Get common crops for the region
  const getCommonCrops = () => {
    if (country === 'Ghana' && region?.includes('Northern')) {
      return COMMON_CROPS_BY_REGION['Ghana-Northern'] || [];
    } else if (country === 'Ghana') {
      return COMMON_CROPS_BY_REGION['Ghana-Southern'] || [];
    } else if (country === 'Nigeria' && ['Kaduna', 'Kano', 'Katsina', 'Sokoto'].includes(region)) {
      return COMMON_CROPS_BY_REGION['Nigeria-Northern'] || [];
    } else if (country === 'Nigeria' && ['Benue', 'Plateau', 'Niger', 'Kwara'].includes(region)) {
      return COMMON_CROPS_BY_REGION['Nigeria-Middle Belt'] || [];
    } else if (country === 'Nigeria') {
      return COMMON_CROPS_BY_REGION['Nigeria-Southern'] || [];
    } else if (country === 'Canada' && ['Saskatchewan', 'Alberta', 'Manitoba'].includes(region)) {
      return COMMON_CROPS_BY_REGION['Canada-Prairies'] || [];
    } else if (country === 'Canada' && ['Ontario', 'Quebec'].includes(region)) {
      return COMMON_CROPS_BY_REGION['Canada-Central'] || [];
    } else if (country === 'Canada') {
      return COMMON_CROPS_BY_REGION['Canada'] || [];
    }
    return [];
  };

  const addNewCrop = () => {
    if (!canAddCrop) return;
    const leftover = remainingFarmArea(getValues('cropProductions') || [], totalFarmSize);
    append({
      cropId: `crop_${Date.now()}`,
      cropName: '',
      localName: '',
      category: '',
      variety: '',
      // Prefill with what's left so the next crop cannot silently overshoot.
      areaAllocated: leftover > 0 ? leftover : 0,
      annualProduction: 0,
      productionSystem: ProductionSystem.RAINFED,
      croppingPattern: CroppingPattern.MONOCULTURE,
      seasonality: {
        plantingMonths: [],
        harvestingMonths: [],
        growingPeriod: 120,
        cropsPerYear: 1,
        season: [SeasonType.WET_SEASON]
      },
      isIntercropped: false,
      intercroppingPartners: [],
      intercroppingRatio: {},
      rotationSequence: [],
      rotationDuration: 1,
      averageYieldPerHectare: 0,
      postHarvestLosses: 10
    });
  };

  const handleCroppingPatternChange = (index: number, pattern: CroppingPattern) => {
    setValue(`cropProductions.${index}.croppingPattern`, pattern);
    
    if (pattern === CroppingPattern.INTERCROPPING) {
      setValue(`cropProductions.${index}.isIntercropped`, true);
      setShowIntercroppingDetails(prev => ({ ...prev, [index]: true }));
    } else {
      setValue(`cropProductions.${index}.isIntercropped`, false);
      setShowIntercroppingDetails(prev => ({ ...prev, [index]: false }));
    }
  };

  const calculateYield = (index: number) => {
    const crop = getValues(`cropProductions.${index}`);
    if (crop.cropName && crop.areaAllocated) {
      const estimatedYield = calculateEstimatedYield(crop.cropName, crop.areaAllocated);
      setValue(`cropProductions.${index}.averageYieldPerHectare`, Math.round(estimatedYield / crop.areaAllocated));
      setValue(`cropProductions.${index}.annualProduction`, estimatedYield);
    }
  };

  const updateAreaPercentage = (index: number, areaAllocated: number) => {
    if (totalFarmSize > 0) {
      const percentage = calculateAreaPercentage(areaAllocated, totalFarmSize);
      setAreaPercentages(prev => ({ ...prev, [index]: percentage }));
    }
  };

  const handleCropNameChange = (index: number, cropName: string) => {
    setValue(`cropProductions.${index}.cropName`, cropName);
    // Reset variety when crop changes
    setValue(`cropProductions.${index}.variety`, '');
    // Auto-set category based on crop
    const category = cropName.includes('Maize') || cropName.includes('Rice') || cropName.includes('Millet') || cropName.includes('Sorghum') ? 'Cereals' :
                    cropName.includes('Groundnut') || cropName.includes('Cowpea') || cropName.includes('Soybeans') ? 'Legumes' :
                    cropName.includes('Cassava') || cropName.includes('Yam') || cropName.includes('Potato') ? 'Roots' :
                    cropName.includes('Tomato') || cropName.includes('Onion') || cropName.includes('Pepper') || cropName.includes('Okra') ? 'Vegetables' :
                    cropName.includes('Plantain') || cropName.includes('Mango') || cropName.includes('Orange') ? 'Fruits' :
                    cropName.includes('Palm') || cropName.includes('Sunflower') ? 'Oils' : 'Other';
    setValue(`cropProductions.${index}.category`, category);
    calculateYield(index);
  };

  const getTotalAllocationErrors = (): string[] => {
    if (totalFarmSize > 0) {
      return validateTotalAllocation(allCrops, totalFarmSize);
    }
    return [];
  };

  const calculateGrowingPeriodFromMonths = (plantingMonths: number[], harvestingMonths: number[]): number => {
    if (!plantingMonths.length || !harvestingMonths.length) return 120;
    
    const avgPlanting = plantingMonths.reduce((sum, month) => sum + month, 0) / plantingMonths.length;
    const avgHarvest = harvestingMonths.reduce((sum, month) => sum + month, 0) / harvestingMonths.length;
    
    let periodMonths = avgHarvest - avgPlanting;
    if (periodMonths <= 0) {
      // Handle year overlap (e.g., plant in Nov, harvest in Feb)
      periodMonths = (12 - avgPlanting) + avgHarvest;
    }
    
    return Math.round(periodMonths * 30); // Convert months to days
  };

  const handleSeasonalityChange = (index: number, field: 'plantingMonths' | 'harvestingMonths', value: number[]) => {
    setValue(`cropProductions.${index}.seasonality.${field}` as const, value);
    
    // Auto-calculate growing period when months change
    if (field === 'plantingMonths' || field === 'harvestingMonths') {
      const crop = getValues(`cropProductions.${index}`);
      const plantingMonths = field === 'plantingMonths' ? value : crop.seasonality?.plantingMonths || [];
      const harvestingMonths = field === 'harvestingMonths' ? value : crop.seasonality?.harvestingMonths || [];
      
      if (plantingMonths.length > 0 && harvestingMonths.length > 0) {
        const calculatedPeriod = calculateGrowingPeriodFromMonths(plantingMonths, harvestingMonths);
        setValue(`cropProductions.${index}.seasonality.growingPeriod`, calculatedPeriod);
      }
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center"
      >
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-xl font-semibold text-ink">Crop Production Details</h3>
            <p className="text-muted">Add all crops you grow on your farm</p>
          </div>
          <button
            type="button"
            onClick={addNewCrop}
            disabled={!canAddCrop}
            title={!canAddCrop ? 'No farm area left to allocate' : undefined}
            className="flex items-center space-x-2 bg-spruce text-white px-4 py-2 rounded-lg hover:bg-ink transition-colors disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-spruce"
          >
            <Plus className="w-4 h-4" />
            <span>Add Crop</span>
          </button>
        </div>

        {totalFarmSize > 0 && (
          <div className="bg-white border border-line rounded-lg p-4 mb-6 text-left">
            <div className="flex flex-wrap items-baseline justify-between gap-2 mb-2">
              <p className="text-sm text-ink">
                <span className="font-medium">{totalAllocated.toFixed(2)} ha</span>
                <span className="text-muted"> of </span>
                <span className="font-medium">{totalFarmSize} ha</span>
                <span className="text-muted"> allocated</span>
              </p>
              <p className={`text-sm font-medium ${remainingHa < 0.01 ? 'text-amber' : 'text-moss'}`}>
                {remainingHa.toFixed(2)} ha left
              </p>
            </div>
            <div className="h-2 rounded-full bg-surface overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  totalAllocated > totalFarmSize ? 'bg-amber' : 'bg-moss'
                }`}
                style={{
                  width: `${Math.min(100, (totalAllocated / totalFarmSize) * 100)}%`,
                }}
              />
            </div>
          </div>
        )}

        {/* Quick Add Common Crops */}
        {getCommonCrops().length > 0 && (
          <div className="bg-moss/10 border border-moss/30 rounded-lg p-4 mb-6">
            <div className="text-sm text-spruce mb-2">
              <strong>Common crops in {region}, {country}:</strong>
            </div>
            <div className="flex flex-wrap gap-2">
              {getCommonCrops().map((cropName) => (
                <button
                  key={cropName}
                  type="button"
                  disabled={!canAddCrop}
                  onClick={() => {
                    if (!canAddCrop) return;
                    addNewCrop();
                    const newIndex = fields.length;
                    setTimeout(() => {
                      setValue(`cropProductions.${newIndex}.cropName`, cropName);
                      const category = cropName.includes('Maize') || cropName.includes('Rice') ? 'Cereals' :
                                     cropName.includes('Groundnut') || cropName.includes('Cowpea') ? 'Legumes' :
                                     cropName.includes('Cassava') || cropName.includes('Yam') ? 'Roots' : 'Other';
                      setValue(`cropProductions.${newIndex}.category`, category);
                    }, 100);
                  }}
                  className="text-xs bg-white border border-line text-spruce px-2 py-1 rounded hover:bg-moss/10 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-white"
                >
                  + {cropName}
                </button>
              ))}
            </div>
            {!canAddCrop && (
              <p className="mt-2 text-xs text-amber">
                All {totalFarmSize} ha are allocated. Reduce a crop&apos;s area before adding another.
              </p>
            )}
          </div>
        )}
      </motion.div>

      {/* Crop Forms */}
      <div className="space-y-6">
        <AnimatePresence>
          {fields.map((field, index) => {
            const maxForCrop = totalFarmSize > 0
              ? remainingFarmArea(allCrops, totalFarmSize, index)
              : undefined;
            const otherAllocated = totalAllocated - (Number(allCrops[index]?.areaAllocated) || 0);
            return (
            <motion.div
              key={field.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
              className="bg-white border border-line rounded-xl p-6 shadow-sm"
            >
              {/* Crop Header */}
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-moss/10 rounded-lg flex items-center justify-center">
                    <Sprout className="w-5 h-5 text-moss" />
                  </div>
                  <div>
                    <h4 className="text-lg font-semibold text-ink">
                      Crop {index + 1}
                      {watch(`cropProductions.${index}.cropName`) && 
                        ` - ${watch(`cropProductions.${index}.cropName`)}`
                      }
                    </h4>
                    <p className="text-sm text-muted">
                      {watch(`cropProductions.${index}.areaAllocated`) || 0} hectares
                    </p>
                  </div>
                </div>
                {fields.length > 1 && (
                  <button
                    type="button"
                    onClick={() => remove(index)}
                    className="text-red-500 hover:text-red-700 p-2"
                    title="Remove this crop"
                    aria-label="Remove this crop"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                )}
              </div>

              {/* Basic Crop Information */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-6">
                <div>
                  <label className="block text-sm font-medium text-ink mb-2">
                    Crop Name *
                  </label>
                  <input
                    {...register(`cropProductions.${index}.cropName`)}
                    placeholder="e.g., Maize, Rice, Cassava"
                    className="gmg-input"
                    onChange={(e) => handleCropNameChange(index, e.target.value)}
                    onBlur={() => calculateYield(index)}
                  />
                  {errors.cropProductions?.[index]?.cropName && (
                    <p className="mt-1 text-sm text-red-600">
                      {errors.cropProductions[index]?.cropName?.message}
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-ink mb-2">
                    Local Name (Optional)
                  </label>
                  <input
                    {...register(`cropProductions.${index}.localName`)}
                    placeholder="e.g., Abelawo, Agbeli"
                    className="gmg-input"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-ink mb-2">
                    Category *
                  </label>
                  <select
                    {...register(`cropProductions.${index}.category`)}
                    className="gmg-input"
                  >
                    <option value="">Select category</option>
                    {foodCategories.map((cat) => (
                      <option key={cat.value} value={cat.value}>
                        {cat.label}
                      </option>
                    ))}
                  </select>
                  {errors.cropProductions?.[index]?.category && (
                    <p className="mt-1 text-sm text-red-600">
                      {errors.cropProductions[index]?.category?.message}
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-ink mb-2">
                    Variety/Cultivar *
                  </label>
                  <select
                    {...register(`cropProductions.${index}.variety`)}
                    className="gmg-input"
                  >
                    <option value="">Select variety</option>
                    {watch(`cropProductions.${index}.cropName`) && 
                      getCropVarieties(watch(`cropProductions.${index}.cropName`)).map((variety) => (
                        <option key={variety} value={variety}>
                          {variety}
                        </option>
                      ))
                    }
                  </select>
                  {errors.cropProductions?.[index]?.variety && (
                    <p className="mt-1 text-sm text-red-600">
                      {errors.cropProductions[index]?.variety?.message}
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-ink mb-2">
                    Area Allocated (hectares) *
                    {totalFarmSize > 0 && (
                      <span className="text-xs text-muted ml-1">
                        (up to {maxForCrop?.toFixed(2)} ha of {totalFarmSize} ha total
                        {otherAllocated > 0
                          ? `; ${otherAllocated.toFixed(2)} ha used by other crops`
                          : ''}
                        )
                      </span>
                    )}
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min={0}
                    max={maxForCrop}
                    {...register(`cropProductions.${index}.areaAllocated`, { valueAsNumber: true })}
                    placeholder="e.g., 1.5"
                    className="gmg-input"
                    onChange={(e) => {
                      let value = parseFloat(e.target.value);
                      if (!Number.isFinite(value) || value < 0) value = 0;
                      if (maxForCrop !== undefined && value > maxForCrop) {
                        value = maxForCrop;
                        e.target.value = String(value);
                      }
                      setValue(`cropProductions.${index}.areaAllocated`, value, {
                        shouldValidate: true,
                        shouldDirty: true,
                      });
                      updateAreaPercentage(index, value);
                    }}
                    onBlur={() => calculateYield(index)}
                  />
                  {totalFarmSize > 0 && (
                    <p className="mt-1 text-sm text-moss">
                      {calculateAreaPercentage(
                        Number(watch(`cropProductions.${index}.areaAllocated`)) || 0,
                        totalFarmSize,
                      )}% of farm
                      {maxForCrop !== undefined && (
                        <span className="text-muted">
                          {' · '}
                          {(
                            maxForCrop -
                            (Number(watch(`cropProductions.${index}.areaAllocated`)) || 0)
                          ).toFixed(2)}{' '}
                          ha would remain after this crop
                        </span>
                      )}
                    </p>
                  )}
                  {errors.cropProductions?.[index]?.areaAllocated && (
                    <p className="mt-1 text-sm text-red-600">
                      {errors.cropProductions[index]?.areaAllocated?.message}
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-ink mb-2">
                    Annual Production (kg) *
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    {...register(`cropProductions.${index}.annualProduction`, { valueAsNumber: true })}
                    placeholder="e.g., 2250"
                    className="gmg-input"
                  />
                  {errors.cropProductions?.[index]?.annualProduction && (
                    <p className="mt-1 text-sm text-red-600">
                      {errors.cropProductions[index]?.annualProduction?.message}
                    </p>
                  )}
                </div>
              </div>

              {/* Production System & Cropping Pattern */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                <div>
                  <label className="block text-sm font-medium text-ink mb-3">
                    <Target className="w-4 h-4 inline mr-1" />
                    Production System *
                  </label>
                  <div className="space-y-2">
                    {productionSystems.map((system) => (
                      <label key={system.value} className="flex items-start space-x-3">
                        <input
                          type="radio"
                          {...register(`cropProductions.${index}.productionSystem`)}
                          value={system.value}
                          className="mt-1 text-moss focus:ring-moss"
                        />
                        <div className="flex-1">
                          <div className="font-medium text-ink">{system.label}</div>
                          <div className="text-sm text-muted">{system.description}</div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-ink mb-3">
                    <Layers className="w-4 h-4 inline mr-1" />
                    Cropping Pattern *
                  </label>
                  <div className="space-y-2">
                    {croppingPatterns.map((pattern) => (
                      <label key={pattern.value} className="flex items-start space-x-3">
                        <input
                          type="radio"
                          {...register(`cropProductions.${index}.croppingPattern`)}
                          value={pattern.value}
                          onChange={() => handleCroppingPatternChange(index, pattern.value)}
                          className="mt-1 text-moss focus:ring-moss"
                        />
                        <div className="flex-1">
                          <div className="font-medium text-ink">{pattern.label}</div>
                          <div className="text-sm text-muted">{pattern.description}</div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              </div>

              {/* Intercropping Details */}
              {showIntercroppingDetails[index] && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="bg-moss/10 rounded-lg p-4 mb-6"
                >
                  <h5 className="font-medium text-ink mb-3">Intercropping Details</h5>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-ink mb-2">
                        Intercropping Partners
                      </label>
                      <input
                        {...register(`cropProductions.${index}.intercroppingPartners.0`)}
                        placeholder="e.g., Groundnuts, Beans"
                        className="gmg-input"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-ink mb-2">
                        Additional Partners
                      </label>
                      <input
                        {...register(`cropProductions.${index}.intercroppingPartners.1`)}
                        placeholder="e.g., Cowpea"
                        className="gmg-input"
                      />
                    </div>
                  </div>
                </motion.div>
              )}

              {/* Seasonal Information */}
              <div className="bg-moss/10 rounded-lg p-4">
                <h5 className="font-medium text-ink mb-4 flex items-center">
                  <Calendar className="w-4 h-4 mr-2" />
                  Seasonal Pattern
                </h5>
                
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-ink mb-2">
                      Planting Months *
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      {months.map((month, monthIndex) => {
                        const currentValues = watch(`cropProductions.${index}.seasonality.plantingMonths`) || [];
                        const isChecked = currentValues.includes(monthIndex + 1);
                        
                        return (
                          <label key={month} className="flex items-center space-x-2">
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={(e) => {
                                const newValues = e.target.checked 
                                  ? [...currentValues, monthIndex + 1]
                                  : currentValues.filter((m: number) => m !== monthIndex + 1);
                                handleSeasonalityChange(index, 'plantingMonths', newValues);
                              }}
                              className="text-moss focus:ring-moss rounded"
                            />
                            <span className="text-xs">{month.slice(0, 3)}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-ink mb-2">
                      Harvesting Months *
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      {months.map((month, monthIndex) => {
                        const currentValues = watch(`cropProductions.${index}.seasonality.harvestingMonths`) || [];
                        const isChecked = currentValues.includes(monthIndex + 1);
                        
                        return (
                          <label key={month} className="flex items-center space-x-2">
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={(e) => {
                                const newValues = e.target.checked 
                                  ? [...currentValues, monthIndex + 1]
                                  : currentValues.filter((m: number) => m !== monthIndex + 1);
                                handleSeasonalityChange(index, 'harvestingMonths', newValues);
                              }}
                              className="text-moss focus:ring-moss rounded"
                            />
                            <span className="text-xs">{month.slice(0, 3)}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-ink mb-2">
                      Growing Period (days) *
                    </label>
                    <input
                      type="number"
                      min="30"
                      max="365"
                      {...register(`cropProductions.${index}.seasonality.growingPeriod`, { valueAsNumber: true })}
                      placeholder="e.g., 120"
                      className="gmg-input"
                    />
                    {watch(`cropProductions.${index}.seasonality.growingPeriod`) && (
                      <p className="mt-1 text-sm text-moss">
                        📅 ~{Math.round(watch(`cropProductions.${index}.seasonality.growingPeriod`) / 30 * 10) / 10} months
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-ink mb-2">
                      Crops per Year *
                    </label>
                    <select
                      {...register(`cropProductions.${index}.seasonality.cropsPerYear`, { valueAsNumber: true })}
                      className="gmg-input"
                    >
                      <option value={1}>1 crop per year</option>
                      <option value={2}>2 crops per year</option>
                      <option value={3}>3 crops per year</option>
                    </select>
                  </div>
                </div>
              </div>
            </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {/* Add First Crop */}
      {fields.length === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-12 bg-surface rounded-xl border-2 border-dashed border-line"
        >
          <Sprout className="w-16 h-16 text-muted mx-auto mb-4" />
          <h3 className="text-lg font-medium text-ink mb-2">No crops added yet</h3>
          <p className="text-muted mb-4">Start by adding the crops you grow on your farm</p>
          <button
            type="button"
            onClick={addNewCrop}
            className="bg-spruce text-white px-6 py-3 rounded-lg hover:bg-ink transition-colors inline-flex items-center space-x-2"
          >
            <Plus className="w-5 h-5" />
            <span>Add Your First Crop</span>
          </button>
        </motion.div>
      )}

      {/* Total Allocation Warning */}
      {(getTotalAllocationErrors().length > 0 ||
        (typeof errors.cropProductions?.message === 'string' && errors.cropProductions.message)) && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-amber/10 border border-amber/30 rounded-lg p-4"
        >
          <div className="flex items-center space-x-2 text-spruce">
            <AlertCircle className="w-5 h-5" />
            <span className="font-medium">Area Allocation Warning:</span>
          </div>
          <div className="mt-2 text-sm text-amber">
            <ul className="list-disc list-inside space-y-1">
              {getTotalAllocationErrors().map((error, index) => (
                <li key={index}>{error}</li>
              ))}
              {typeof errors.cropProductions?.message === 'string' &&
                !getTotalAllocationErrors().includes(errors.cropProductions.message) && (
                  <li>{errors.cropProductions.message}</li>
                )}
            </ul>
          </div>
        </motion.div>
      )}

      {/* Validation Errors - Only show if user has started filling crops */}
      {errors.cropProductions && fields.length > 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-red-50 border border-red-200 rounded-lg p-4"
        >
          <div className="flex items-center space-x-2 text-red-800">
            <AlertCircle className="w-5 h-5" />
            <span className="font-medium">Please complete the following required fields:</span>
          </div>
          <div className="mt-2 text-sm text-red-700">
            <ul className="list-disc list-inside space-y-1">
              {fields.map((field, index) => {
                const cropErrors = errors.cropProductions?.[index];
                if (!cropErrors) return null;
                
                const errorMessages = [];
                if (cropErrors.cropName) errorMessages.push(`Crop ${index + 1}: Crop name is required`);
                if (cropErrors.category) errorMessages.push(`Crop ${index + 1}: Please select a category`);
                if (cropErrors.variety) errorMessages.push(`Crop ${index + 1}: Please specify the variety`);
                if (cropErrors.areaAllocated) errorMessages.push(`Crop ${index + 1}: Please enter area allocated`);
                if (cropErrors.annualProduction) errorMessages.push(`Crop ${index + 1}: Please enter annual production`);
                if (cropErrors.productionSystem) errorMessages.push(`Crop ${index + 1}: Please select production system`);
                if (cropErrors.croppingPattern) errorMessages.push(`Crop ${index + 1}: Please select cropping pattern`);
                if (cropErrors.seasonality?.plantingMonths) errorMessages.push(`Crop ${index + 1}: Please select planting months`);
                if (cropErrors.seasonality?.harvestingMonths) errorMessages.push(`Crop ${index + 1}: Please select harvesting months`);
                
                return errorMessages.map((msg, i) => (
                  <li key={`${index}-${i}`}>{msg}</li>
                ));
              })}
            </ul>
          </div>
        </motion.div>
      )}

      {/* Info Box */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="bg-moss/10 border border-moss/30 rounded-lg p-4"
      >
        <div className="flex items-start space-x-3">
          <Info className="w-5 h-5 text-moss mt-0.5" />
          <div className="text-sm text-spruce">
            <strong>Tip:</strong> Include all crops you grow, even small plots. Intercropping and crop 
            rotation information helps us calculate more accurate environmental impacts and provide 
            better sustainability recommendations.
          </div>
        </div>
      </motion.div>

      {/* Progress Guide */}
      {fields.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="bg-moss/10 border border-line rounded-lg p-4"
        >
          <div className="flex items-start space-x-3">
            <Info className="w-5 h-5 text-moss mt-0.5" />
            <div className="text-sm text-spruce">
              <strong>Form Progress:</strong> For each crop, please complete the basic information (name, category, variety), 
              production details (area, annual production), and seasonal pattern. You can fill them in any order - 
              the form will guide you through any missing required fields when you try to proceed.
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}