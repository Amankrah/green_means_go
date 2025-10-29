'use client';

import React from 'react';
import { useFormContext, useFieldArray } from 'react-hook-form';
import { motion } from 'framer-motion';
import { Zap, Truck, Info, AlertCircle, BarChart3, Plus, Trash2, Settings, Battery } from 'lucide-react';
import { EnhancedAssessmentFormData } from '@/lib/enhanced-assessment-schema';
import { 
  StorageFacilityType, 
  RoadAccessType, 
  TransportMode, 
  FunctionalUnit, 
  SystemBoundary,
  EquipmentType,
  PowerSource,
  EnergyType
} from '@/types/enhanced-assessment';

export default function EquipmentEnergyStep() {
  const { register, formState: { errors }, setValue, watch, control } = useFormContext<EnhancedAssessmentFormData>();

  const currentStorageFacilities = watch('equipmentEnergy.infrastructure.storageFacilities') || [];

  // Dynamic arrays for equipment and energy sources
  const { fields: equipmentFields, append: appendEquipment, remove: removeEquipment } = useFieldArray({
    control,
    name: 'equipmentEnergy.equipment'
  });

  const { fields: energySourceFields, append: appendEnergySource, remove: removeEnergySource } = useFieldArray({
    control,
    name: 'equipmentEnergy.energySources'
  });

  // Set default values for required arrays
  React.useEffect(() => {
    if (!watch('equipmentEnergy.infrastructure.storageFacilities')) {
      setValue('equipmentEnergy.infrastructure.storageFacilities', []);
    }
    if (!watch('equipmentEnergy.infrastructure.transportAccess.transportMode')) {
      setValue('equipmentEnergy.infrastructure.transportAccess.transportMode', []);
    }
    // Set default values for missing schema fields
    if (!watch('equipmentEnergy.equipment')) {
      setValue('equipmentEnergy.equipment', []);
    }
    if (!watch('equipmentEnergy.energySources')) {
      setValue('equipmentEnergy.energySources', []);
    }
  }, [setValue, watch]);

  // Set default values for assessment parameters if they're not already set
  React.useEffect(() => {
    if (!watch('assessmentParameters.functionalUnit')) {
      setValue('assessmentParameters.functionalUnit', FunctionalUnit.PER_KG_PRODUCT);
    }
    if (!watch('assessmentParameters.systemBoundary')) {
      setValue('assessmentParameters.systemBoundary', SystemBoundary.CRADLE_TO_GATE);
    }
    if (!watch('assessmentParameters.assessmentPeriod')) {
      setValue('assessmentParameters.assessmentPeriod', 1);
    }
  }, [setValue, watch]);

  // Handle storage facility selection with mutual exclusivity
  const handleStorageFacilityChange = (facility: StorageFacilityType, isChecked: boolean) => {
    const currentFacilities = [...currentStorageFacilities];
    
    if (facility === StorageFacilityType.NONE) {
      // If "No dedicated storage" is selected, clear all other options
      if (isChecked) {
        setValue('equipmentEnergy.infrastructure.storageFacilities', [StorageFacilityType.NONE]);
      } else {
        setValue('equipmentEnergy.infrastructure.storageFacilities', []);
      }
    } else {
      // If any other option is selected, remove "No dedicated storage"
      let updatedFacilities = currentFacilities.filter(f => f !== StorageFacilityType.NONE);
      
      if (isChecked) {
        // Add the selected facility
        if (!updatedFacilities.includes(facility)) {
          updatedFacilities.push(facility);
        }
      } else {
        // Remove the unselected facility
        updatedFacilities = updatedFacilities.filter(f => f !== facility);
      }
      
      setValue('equipmentEnergy.infrastructure.storageFacilities', updatedFacilities);
    }
  };

  return (
    <div className="space-y-8">
      {/* Farm Equipment Section */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-green-50 rounded-xl p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <Settings className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Farm Equipment</h3>
              <p className="text-sm text-gray-600">Equipment used for farming operations</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => appendEquipment({
              equipmentType: EquipmentType.HAND_TOOLS,
              powerSource: PowerSource.MANUAL,
              age: 0,
              hoursPerYear: 0,
              fuelEfficiency: undefined
            })}
            className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Add Equipment</span>
          </button>
        </div>

        {equipmentFields.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Settings className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>No equipment added yet. Click &quot;Add Equipment&quot; to get started.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {equipmentFields.map((field, index) => (
              <motion.div
                key={field.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-white border border-green-200 rounded-lg p-4"
              >
                <div className="flex items-center justify-between mb-4">
                  <h4 className="font-medium text-gray-900">Equipment #{index + 1}</h4>
                  <button
                    type="button"
                    onClick={() => removeEquipment(index)}
                    className="text-red-600 hover:text-red-800 p-1"
                    title="Remove this equipment"
                    aria-label="Remove this equipment"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Equipment Type *
                    </label>
                    <select
                      {...register(`equipmentEnergy.equipment.${index}.equipmentType`)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 text-gray-900"
                    >
                      <option value="">Select equipment type</option>
                      {Object.values(EquipmentType).map((type) => (
                        <option key={type} value={type}>{type}</option>
                      ))}
                    </select>
                    {errors.equipmentEnergy?.equipment?.[index]?.equipmentType && (
                      <p className="mt-1 text-sm text-red-600 flex items-center">
                        <AlertCircle className="w-4 h-4 mr-1" />
                        {errors.equipmentEnergy.equipment[index].equipmentType.message}
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Power Source *
                    </label>
                    <select
                      {...register(`equipmentEnergy.equipment.${index}.powerSource`)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 text-gray-900"
                    >
                      <option value="">Select power source</option>
                      {Object.values(PowerSource).map((source) => (
                        <option key={source} value={source}>{source}</option>
                      ))}
                    </select>
                    {errors.equipmentEnergy?.equipment?.[index]?.powerSource && (
                      <p className="mt-1 text-sm text-red-600 flex items-center">
                        <AlertCircle className="w-4 h-4 mr-1" />
                        {errors.equipmentEnergy.equipment[index].powerSource.message}
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Age (years) *
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="50"
                      {...register(`equipmentEnergy.equipment.${index}.age`, { valueAsNumber: true })}
                      placeholder="e.g., 5"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 text-gray-900"
                    />
                    {errors.equipmentEnergy?.equipment?.[index]?.age && (
                      <p className="mt-1 text-sm text-red-600 flex items-center">
                        <AlertCircle className="w-4 h-4 mr-1" />
                        {errors.equipmentEnergy.equipment[index].age.message}
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Hours Per Year *
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="4000"
                      {...register(`equipmentEnergy.equipment.${index}.hoursPerYear`, { valueAsNumber: true })}
                      placeholder="e.g., 200"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 text-gray-900"
                    />
                    {errors.equipmentEnergy?.equipment?.[index]?.hoursPerYear && (
                      <p className="mt-1 text-sm text-red-600 flex items-center">
                        <AlertCircle className="w-4 h-4 mr-1" />
                        {errors.equipmentEnergy.equipment[index].hoursPerYear.message}
                      </p>
                    )}
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Fuel Efficiency (optional)
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      {...register(`equipmentEnergy.equipment.${index}.fuelEfficiency`, { valueAsNumber: true })}
                      placeholder="e.g., 3.5 (liters per hour or km)"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 text-gray-900"
                    />
                    <p className="text-xs text-gray-500 mt-1">For fuel-powered equipment only</p>
                    {errors.equipmentEnergy?.equipment?.[index]?.fuelEfficiency && (
                      <p className="mt-1 text-sm text-red-600 flex items-center">
                        <AlertCircle className="w-4 h-4 mr-1" />
                        {errors.equipmentEnergy.equipment[index].fuelEfficiency.message}
                      </p>
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </motion.section>

      {/* Energy Sources Section */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-blue-50 rounded-xl p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Battery className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Energy Sources</h3>
              <p className="text-sm text-gray-600">Energy used for farm operations</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => appendEnergySource({
              energyType: EnergyType.GRID_ELECTRICITY,
              monthlyConsumption: 0,
              primaryUse: '',
              cost: undefined
            })}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Add Energy Source</span>
          </button>
        </div>

        {energySourceFields.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Battery className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>No energy sources added yet. Click &quot;Add Energy Source&quot; to get started.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {energySourceFields.map((field, index) => (
              <motion.div
                key={field.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-white border border-blue-200 rounded-lg p-4"
              >
                <div className="flex items-center justify-between mb-4">
                  <h4 className="font-medium text-gray-900">Energy Source #{index + 1}</h4>
                  <button
                    type="button"
                    onClick={() => removeEnergySource(index)}
                    className="text-red-600 hover:text-red-800 p-1"
                    title="Remove this energy source"
                    aria-label="Remove this energy source"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Energy Type *
                    </label>
                    <select
                      {...register(`equipmentEnergy.energySources.${index}.energyType`)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
                    >
                      <option value="">Select energy type</option>
                      {Object.values(EnergyType).map((type) => (
                        <option key={type} value={type}>{type}</option>
                      ))}
                    </select>
                    {errors.equipmentEnergy?.energySources?.[index]?.energyType && (
                      <p className="mt-1 text-sm text-red-600 flex items-center">
                        <AlertCircle className="w-4 h-4 mr-1" />
                        {errors.equipmentEnergy.energySources[index].energyType.message}
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Monthly Consumption *
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="0.1"
                      {...register(`equipmentEnergy.energySources.${index}.monthlyConsumption`, { valueAsNumber: true })}
                      placeholder="e.g., 150"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Units: kWh for electricity, liters for diesel/petrol/biogas, kg for firewood/charcoal
                    </p>
                    {errors.equipmentEnergy?.energySources?.[index]?.monthlyConsumption && (
                      <p className="mt-1 text-sm text-red-600 flex items-center">
                        <AlertCircle className="w-4 h-4 mr-1" />
                        {errors.equipmentEnergy.energySources[index].monthlyConsumption.message}
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Primary Use *
                    </label>
                    <input
                      type="text"
                      {...register(`equipmentEnergy.energySources.${index}.primaryUse`)}
                      placeholder="e.g., Irrigation, Processing, Storage"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
                    />
                    {errors.equipmentEnergy?.energySources?.[index]?.primaryUse && (
                      <p className="mt-1 text-sm text-red-600 flex items-center">
                        <AlertCircle className="w-4 h-4 mr-1" />
                        {errors.equipmentEnergy.energySources[index].primaryUse.message}
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Total Monthly Cost (optional)
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      {...register(`equipmentEnergy.energySources.${index}.cost`, { valueAsNumber: true })}
                      placeholder="e.g., 25000"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Total monthly cost for the consumption amount specified above (local currency)
                    </p>
                    {errors.equipmentEnergy?.energySources?.[index]?.cost && (
                      <p className="mt-1 text-sm text-red-600 flex items-center">
                        <AlertCircle className="w-4 h-4 mr-1" />
                        {errors.equipmentEnergy.energySources[index].cost.message}
                      </p>
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </motion.section>

      {/* Storage & Infrastructure Section */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-purple-50 rounded-xl p-6"
      >
        <div className="flex items-center space-x-3 mb-6">
          <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
            <Zap className="w-5 h-5 text-purple-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Storage & Infrastructure</h3>
            <p className="text-sm text-gray-600">Storage facilities and farm infrastructure</p>
          </div>
        </div>

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Storage Capacity (cubic meters or tons) *
            </label>
            <input
              type="number"
              step="0.1"
              {...register('equipmentEnergy.infrastructure.storageCapacity', { valueAsNumber: true })}
              placeholder="e.g., 50"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 text-gray-900"
            />
            {errors.equipmentEnergy?.infrastructure?.storageCapacity && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.equipmentEnergy.infrastructure.storageCapacity.message}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Storage Facilities (select all that apply)
            </label>
            {currentStorageFacilities.includes(StorageFacilityType.NONE) && (
              <div className="mb-3 p-2 bg-blue-50 border border-blue-200 rounded text-sm text-blue-700">
                ℹ️ <strong>No dedicated storage</strong> is selected. Other storage options are disabled.
              </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.values(StorageFacilityType).map((facility) => {
                const isChecked = currentStorageFacilities.includes(facility);
                const isNoDedicatedStorage = facility === StorageFacilityType.NONE;
                const hasNoDedicatedSelected = currentStorageFacilities.includes(StorageFacilityType.NONE);
                const isDisabled = !isNoDedicatedStorage && hasNoDedicatedSelected;
                
                return (
                  <label 
                    key={facility} 
                    className={`flex items-center space-x-2 ${
                      isDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      disabled={isDisabled}
                      onChange={(e) => handleStorageFacilityChange(facility, e.target.checked)}
                      className="text-purple-600 focus:ring-purple-500 rounded disabled:opacity-50"
                    />
                    <span className={`text-sm ${
                      isNoDedicatedStorage ? 'text-gray-600 font-medium' : 
                      isDisabled ? 'text-gray-400' : 'text-gray-700'
                    }`}>
                      {facility}
                      {isNoDedicatedStorage && ' (excludes other options)'}
                    </span>
                  </label>
                );
              })}
            </div>
          </div>
        </div>
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="bg-yellow-50 rounded-xl p-6"
      >
        <div className="flex items-center space-x-3 mb-6">
          <div className="w-10 h-10 bg-yellow-100 rounded-lg flex items-center justify-center">
            <Truck className="w-5 h-5 text-yellow-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Transport & Market Access</h3>
            <p className="text-sm text-gray-600">How do you transport your produce to market?</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Road Access *
            </label>
            <select
              {...register('equipmentEnergy.infrastructure.transportAccess.roadAccess')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 text-gray-900"
            >
              <option value="">Select road access</option>
              {Object.values(RoadAccessType).map((access) => (
                <option key={access} value={access}>{access}</option>
              ))}
            </select>
            {errors.equipmentEnergy?.infrastructure?.transportAccess?.roadAccess && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.equipmentEnergy.infrastructure.transportAccess.roadAccess.message}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Distance to Market (kilometers) *
            </label>
            <input
              type="number"
              step="0.1"
              {...register('equipmentEnergy.infrastructure.transportAccess.distanceToMarket', { valueAsNumber: true })}
              placeholder="e.g., 15"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 text-gray-900"
            />
            {errors.equipmentEnergy?.infrastructure?.transportAccess?.distanceToMarket && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.equipmentEnergy.infrastructure.transportAccess.distanceToMarket.message}
              </p>
            )}
            {errors.equipmentEnergy?.infrastructure?.transportAccess?.transportMode && (
              <p className="mt-2 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.equipmentEnergy.infrastructure.transportAccess.transportMode.message}
              </p>
            )}
          </div>
        </div>

        <div className="mt-6">
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Transport Methods (select all that apply) *
          </label>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {Object.values(TransportMode).map((mode) => (
              <label key={mode} className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  {...register('equipmentEnergy.infrastructure.transportAccess.transportMode')}
                  value={mode}
                  className="text-yellow-600 focus:ring-yellow-500 rounded"
                />
                <span className="text-sm text-gray-700">{mode}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="mt-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Transport Cost (local currency per trip - optional)
          </label>
          <input
            type="number"
            step="0.01"
            min="0"
            {...register('equipmentEnergy.infrastructure.transportAccess.transportCost')}
            placeholder="e.g., 50000"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-yellow-500 text-gray-900"
          />
          <p className="text-xs text-gray-500 mt-1">Leave empty if cost varies or is unknown</p>
        </div>
      </motion.section>

      {/* Validation Errors Summary */}
      {(() => {
        // Debug logging
        if (Object.keys(errors.equipmentEnergy || {}).length > 0) {
          console.log('Equipment Energy Validation Errors:', errors.equipmentEnergy);
        }
        if (Object.keys(errors.assessmentParameters || {}).length > 0) {
          console.log('Assessment Parameters Validation Errors:', errors.assessmentParameters);
        }
        return Object.keys(errors.equipmentEnergy || {}).length > 0 || Object.keys(errors.assessmentParameters || {}).length > 0;
      })() && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-red-50 border border-red-200 rounded-lg p-4"
        >
          <div className="flex items-center space-x-2 text-red-800 mb-2">
            <AlertCircle className="w-5 h-5" />
            <span className="font-medium">Please complete the following required fields:</span>
          </div>
          <div className="text-sm text-red-700">
            {(() => {
              const errorMessages = [];
              
              // Equipment & Energy Errors
              if (errors.equipmentEnergy?.infrastructure?.storageCapacity) {
                errorMessages.push('• Equipment: Please enter storage capacity (use 0 if no storage)');
              }
              if (errors.equipmentEnergy?.infrastructure?.transportAccess?.roadAccess) {
                errorMessages.push('• Transport: Please select road access type');
              }
              if (errors.equipmentEnergy?.infrastructure?.transportAccess?.distanceToMarket) {
                errorMessages.push('• Transport: Please enter distance to market in kilometers');
              }
              if (errors.equipmentEnergy?.infrastructure?.transportAccess?.transportMode) {
                errorMessages.push('• Transport: Please select at least one transport method');
              }
              if (errors.equipmentEnergy?.infrastructure?.transportAccess?.transportCost) {
                errorMessages.push('• Transport: Please enter a valid transport cost (or leave empty)');
              }
              
              // Infrastructure validation
              if (errors.equipmentEnergy?.infrastructure?.storageFacilities) {
                errorMessages.push('• Equipment: Storage facilities validation error');
              }
              
              // Equipment array errors
              if (errors.equipmentEnergy?.equipment && Array.isArray(errors.equipmentEnergy.equipment)) {
                errors.equipmentEnergy.equipment.forEach((equipError, index) => {
                  if (equipError?.equipmentType) errorMessages.push(`• Equipment ${index + 1}: Please select equipment type`);
                  if (equipError?.powerSource) errorMessages.push(`• Equipment ${index + 1}: Please select power source`);
                  if (equipError?.age) errorMessages.push(`• Equipment ${index + 1}: Please enter equipment age`);
                  if (equipError?.hoursPerYear) errorMessages.push(`• Equipment ${index + 1}: Please enter hours per year`);
                });
              }
              
              // Energy Sources array errors
              if (errors.equipmentEnergy?.energySources && Array.isArray(errors.equipmentEnergy.energySources)) {
                errors.equipmentEnergy.energySources.forEach((energyError, index) => {
                  if (energyError?.energyType) errorMessages.push(`• Energy Source ${index + 1}: Please select energy type`);
                  if (energyError?.monthlyConsumption) errorMessages.push(`• Energy Source ${index + 1}: Please enter monthly consumption`);
                  if (energyError?.primaryUse) errorMessages.push(`• Energy Source ${index + 1}: Please enter primary use`);
                });
              }
              
              // Assessment Parameters Errors
              if (errors.assessmentParameters?.functionalUnit) {
                errorMessages.push('• Assessment: Please select assessment focus');
              }
              if (errors.assessmentParameters?.systemBoundary) {
                errorMessages.push('• Assessment: Please select assessment scope');
              }
              if (errors.assessmentParameters?.assessmentPeriod) {
                errorMessages.push('• Assessment: Please enter assessment period');
              }
              
              // If no specific errors found, show debug info
              if (errorMessages.length === 0) {
                if (Object.keys(errors.equipmentEnergy || {}).length > 0) {
                  Object.entries(errors.equipmentEnergy || {}).forEach(([section]) => {
                    errorMessages.push(`• Debug: Error in equipmentEnergy.${section} - please check all fields`);
                  });
                }
                if (Object.keys(errors.assessmentParameters || {}).length > 0) {
                  Object.entries(errors.assessmentParameters || {}).forEach(([field]) => {
                    errorMessages.push(`• Debug: Error in assessmentParameters.${field} - please check this field`);
                  });
                }
              }
              
              return (
                <ul className="space-y-1">
                  {errorMessages.map((message, index) => (
                    <li key={index}>{message}</li>
                  ))}
                </ul>
              );
            })()}
          </div>
        </motion.div>
      )}

      {/* Assessment Parameters Section */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="bg-indigo-50 border border-indigo-200 rounded-xl p-6"
      >
        <div className="flex items-center space-x-3 mb-6">
          <BarChart3 className="w-6 h-6 text-indigo-600" />
          <h3 className="text-lg font-semibold text-indigo-900">Assessment Configuration</h3>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Assessment Focus *
            </label>
            <select
              {...register('assessmentParameters.functionalUnit')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-gray-900"
            >
              {Object.entries(FunctionalUnit).map(([key, value]) => (
                <option key={key} value={value}>
                  {value}{key === 'PER_KG_PRODUCT' ? ' (recommended)' : ''}
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-1">
              How should we measure environmental impact?
            </p>
            {errors.assessmentParameters?.functionalUnit && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.assessmentParameters.functionalUnit.message}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Assessment Scope *
            </label>
            <select
              {...register('assessmentParameters.systemBoundary')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-gray-900"
            >
              {Object.entries(SystemBoundary).map(([key, value]) => (
                <option key={key} value={value}>
                  {value}{key === 'CRADLE_TO_GATE' ? ' (recommended)' : ''}
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-1">
              What stages should we include in the assessment?
            </p>
            {errors.assessmentParameters?.systemBoundary && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.assessmentParameters.systemBoundary.message}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Assessment Period (years) *
            </label>
            <input
              type="number"
              min="1"
              max="5"
              {...register('assessmentParameters.assessmentPeriod', { valueAsNumber: true })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-gray-900"
            />
            <p className="text-xs text-gray-500 mt-1">
              Typical farming cycle period to assess
            </p>
            {errors.assessmentParameters?.assessmentPeriod && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.assessmentParameters.assessmentPeriod.message}
              </p>
            )}
          </div>

          <div className="space-y-3">
            <label className="block text-sm font-medium text-gray-700">
              Advanced Analysis Options
            </label>
            
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                {...register('assessmentParameters.includeUncertaintyAnalysis')}
                className="text-indigo-600 focus:ring-indigo-500 rounded"
              />
              <span className="text-sm text-gray-700">Include uncertainty analysis</span>
            </label>
            
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                {...register('assessmentParameters.includeSensitivityAnalysis')}
                className="text-indigo-600 focus:ring-indigo-500 rounded"
              />
              <span className="text-sm text-gray-700">Include sensitivity analysis</span>
            </label>
            
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                {...register('assessmentParameters.benchmarkComparison')}
                className="text-indigo-600 focus:ring-indigo-500 rounded"
              />
              <span className="text-sm text-gray-700">Compare with regional benchmarks</span>
            </label>
          </div>
        </div>
      </motion.section>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="bg-blue-50 border border-blue-200 rounded-lg p-4"
      >
        <div className="flex items-start space-x-3">
          <Info className="w-5 h-5 text-blue-600 mt-0.5" />
          <div className="text-sm text-blue-700">
            <strong>Energy & Transport Impact:</strong> Equipment usage, storage facilities, and 
            transportation contribute to your farm&apos;s carbon footprint. This information helps us 
            calculate the full life-cycle environmental impact.
          </div>
        </div>
      </motion.div>

    </div>
  );
}