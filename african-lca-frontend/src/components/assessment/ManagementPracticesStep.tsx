'use client';

import React from 'react';
import { useFormContext, useFieldArray } from 'react-hook-form';
import { motion } from 'framer-motion';
import { 
  Layers, 
  Droplets, 
  Leaf,
  Plus,
  Trash2,
  AlertCircle,
  Info
} from 'lucide-react';

import { 
  SoilType,
  TestingFrequency,
  SoilConservationPractice,
  CompostSource,
  FertilizerType,
  ApplicationMethod,
  TimingStrategy,
  WaterSource,
  IrrigationSystem
} from '@/types/enhanced-assessment';
import { EnhancedAssessmentFormData } from '@/lib/enhanced-assessment-schema';

export default function ManagementPracticesStep() {
  const { 
    register, 
    control,
    formState: { errors }, 
    watch,
    setValue 
  } = useFormContext<EnhancedAssessmentFormData>();

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'managementPractices.fertilization.fertilizerApplications'
  });

  const usesFertilizers = watch('managementPractices.fertilization.usesFertilizers');
  const usesCompost = watch('managementPractices.soilManagement.compostUse.usesCompost');

  // Set default values for required fields
  React.useEffect(() => {
    if (!watch('managementPractices.soilManagement.conservationPractices')) {
      setValue('managementPractices.soilManagement.conservationPractices', []);
    }
    if (!watch('managementPractices.waterManagement.waterSource')) {
      setValue('managementPractices.waterManagement.waterSource', []);
    }
    if (!watch('managementPractices.waterManagement.waterConservationPractices')) {
      setValue('managementPractices.waterManagement.waterConservationPractices', []);
    }
    // Ensure compost defaults are set correctly
    if (watch('managementPractices.soilManagement.compostUse.compostsource') === undefined) {
      setValue('managementPractices.soilManagement.compostUse.compostsource', CompostSource.NONE);
    }
    // Fix any incorrect enum values
    const currentCompostSource = watch('managementPractices.soilManagement.compostUse.compostsource');
    if (currentCompostSource && !Object.values(CompostSource).includes(currentCompostSource as CompostSource)) {
      setValue('managementPractices.soilManagement.compostUse.compostsource', CompostSource.NONE);
    }
    if (watch('managementPractices.soilManagement.compostUse.applicationTiming') === undefined) {
      setValue('managementPractices.soilManagement.compostUse.applicationTiming', 'Before planting');
    }
  }, [setValue, watch]);

  // Fix enum value issues - ensure compost source is always the correct enum value
  React.useEffect(() => {
    const currentCompostSource = watch('managementPractices.soilManagement.compostUse.compostsource');
    if (currentCompostSource && !Object.values(CompostSource).includes(currentCompostSource as CompostSource)) {
      setValue('managementPractices.soilManagement.compostUse.compostsource', CompostSource.NONE);
    }
  }, [setValue, watch]);

  return (
    <div className="space-y-8">
      {/* Soil Management */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-amber-50 rounded-xl p-6"
      >
        <div className="flex items-center space-x-3 mb-6">
          <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
            <Layers className="w-5 h-5 text-amber-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Soil Management</h3>
            <p className="text-sm text-gray-600">How do you maintain and improve your soil?</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Predominant Soil Type *
            </label>
            <select
              {...register('managementPractices.soilManagement.soilType')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
            >
              <option value="">Select soil type</option>
              {Object.values(SoilType).map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
            {errors.managementPractices?.soilManagement?.soilType && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.managementPractices.soilManagement.soilType.message}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Soil Testing Frequency *
            </label>
            <select
              {...register('managementPractices.soilManagement.soilTestingFrequency')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
            >
              <option value="">Select frequency</option>
              {Object.values(TestingFrequency).map((freq) => (
                <option key={freq} value={freq}>{freq}</option>
              ))}
            </select>
            {errors.managementPractices?.soilManagement?.soilTestingFrequency && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.managementPractices.soilManagement.soilTestingFrequency.message}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Soil pH
            </label>
            <select
              {...register('managementPractices.soilManagement.soilpH')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
            >
              <option value="">Not known</option>
              <option value="3.0">Very acidic (3.0)</option>
              <option value="4.0">Strongly acidic (4.0)</option>
              <option value="5.0">Moderately acidic (5.0)</option>
              <option value="6.0">Slightly acidic (6.0)</option>
              <option value="6.5">Near neutral (6.5)</option>
              <option value="7.0">Neutral (7.0)</option>
              <option value="7.5">Slightly alkaline (7.5)</option>
              <option value="8.0">Moderately alkaline (8.0)</option>
              <option value="9.0">Strongly alkaline (9.0)</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">Select "Not known" if you haven't tested your soil pH</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Organic Matter Content (%)
            </label>
            <select
              {...register('managementPractices.soilManagement.organicMatterContent')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
            >
              <option value="">Not known</option>
              <option value="1">Low (1%)</option>
              <option value="2">Low-Medium (2%)</option>
              <option value="3">Medium (3%)</option>
              <option value="4">Medium-High (4%)</option>
              <option value="5">High (5%)</option>
              <option value="7">Very High (7%+)</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">Select "Not known" if you haven't tested your soil organic matter</p>
          </div>
        </div>

        {/* Soil Conservation Practices */}
        <div className="mt-6">
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Soil Conservation Practices (select all that apply - optional)
          </label>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {Object.values(SoilConservationPractice).map((practice) => (
              <label key={practice} className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  {...register('managementPractices.soilManagement.conservationPractices')}
                  value={practice}
                  className="text-green-600 focus:ring-green-500 rounded"
                />
                <span className="text-sm text-gray-700">{practice}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Compost Usage */}
        <div className="mt-6 bg-white rounded-lg p-4">
          <div className="flex items-center space-x-2 mb-4">
            <input
              type="checkbox"
              {...register('managementPractices.soilManagement.compostUse.usesCompost')}
              className="text-green-600 focus:ring-green-500 rounded"
              onChange={(e) => {
                setValue('managementPractices.soilManagement.compostUse.usesCompost', e.target.checked);
                // If disabling compost, reset to NONE and clear other fields
                if (!e.target.checked) {
                  setValue('managementPractices.soilManagement.compostUse.compostsource', CompostSource.NONE);
                  setValue('managementPractices.soilManagement.compostUse.applicationRate', undefined);
                  setValue('managementPractices.soilManagement.compostUse.applicationTiming', 'Before planting');
                }
              }}
            />
            <label className="text-sm font-medium text-gray-700">
              I use compost or organic matter
            </label>
          </div>

          {usesCompost && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="grid grid-cols-1 md:grid-cols-2 gap-4"
            >
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Compost Source
                </label>
                <select
                  {...register('managementPractices.soilManagement.compostUse.compostsource')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
                >
                  {Object.values(CompostSource).map((source) => (
                    <option key={source} value={source}>{source}</option>
                  ))}
                </select>
                {errors.managementPractices?.soilManagement?.compostUse?.compostsource && (
                  <p className="mt-1 text-sm text-red-600 flex items-center">
                    <AlertCircle className="w-4 h-4 mr-1" />
                    {errors.managementPractices.soilManagement.compostUse.compostsource.message}
                  </p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Application Rate (tons/hectare/year)
                </label>
                <input
                  type="number"
                  step="0.1"
                  {...register('managementPractices.soilManagement.compostUse.applicationRate')}
                  placeholder="e.g., 2.0"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
                />
              </div>
            </motion.div>
          )}
        </div>
      </motion.section>

      {/* Fertilizer Management */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-green-50 rounded-xl p-6"
      >
        <div className="flex items-center space-x-3 mb-6">
          <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
            <Leaf className="w-5 h-5 text-green-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Fertilizer Management</h3>
            <p className="text-sm text-gray-600">What fertilizers do you use and how?</p>
          </div>
        </div>

                  {/* Uses Fertilizers Checkbox */}
        <div className="mb-6">
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              {...register('managementPractices.fertilization.usesFertilizers')}
              className="text-green-600 focus:ring-green-500 rounded"
              onChange={(e) => {
                setValue('managementPractices.fertilization.usesFertilizers', e.target.checked);
                if (!e.target.checked) {
                  // Clear fertilizer applications when not using fertilizers
                  setValue('managementPractices.fertilization.fertilizerApplications', []);
                }
              }}
            />
            <span className="text-sm font-medium text-gray-700">
              I use chemical/synthetic fertilizers
            </span>
          </label>
        </div>

        {usesFertilizers && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="space-y-6"
          >
            {/* Fertilizer Applications */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-md font-medium text-gray-900">Fertilizers Used</h4>
                <button
                  type="button"
                  onClick={() => append({
                    fertilizerType: FertilizerType.NPK_COMPOUND,
                    brandName: '',
                    npkRatio: '',
                    applicationRate: 0,
                    applicationsPerSeason: 1,
                    cost: 0
                  })}
                  className="flex items-center space-x-2 text-green-600 hover:text-green-700"
                >
                  <Plus className="w-4 h-4" />
                  <span>Add Fertilizer</span>
                </button>
              </div>

              <div className="space-y-4">
                {fields.map((field, index) => (
                  <div key={field.id} className="bg-white rounded-lg p-4 border">
                    <div className="flex items-center justify-between mb-4">
                      <h5 className="font-medium text-gray-900">Fertilizer {index + 1}</h5>
                      {fields.length > 1 && (
                        <button
                          type="button"
                          onClick={() => remove(index)}
                          className="text-red-500 hover:text-red-700"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Type *
                        </label>
                        <select
                          {...register(`managementPractices.fertilization.fertilizerApplications.${index}.fertilizerType`)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
                        >
                          {Object.values(FertilizerType).map((type) => (
                            <option key={type} value={type}>{type}</option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Brand Name
                        </label>
                        <input
                          {...register(`managementPractices.fertilization.fertilizerApplications.${index}.brandName`)}
                          placeholder="e.g., Golden Harvest"
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          NPK Ratio
                        </label>
                        <input
                          {...register(`managementPractices.fertilization.fertilizerApplications.${index}.npkRatio`)}
                          placeholder="e.g., 15-15-15"
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Rate (kg/hectare/season) *
                        </label>
                        <input
                          type="number"
                          step="0.1"
                          {...register(`managementPractices.fertilization.fertilizerApplications.${index}.applicationRate`, { valueAsNumber: true })}
                          placeholder="e.g., 200"
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
                        />
                        {errors.managementPractices?.fertilization?.fertilizerApplications?.[index]?.applicationRate && (
                          <p className="mt-1 text-xs text-red-600 flex items-center">
                            <AlertCircle className="w-3 h-3 mr-1" />
                            {errors.managementPractices.fertilization.fertilizerApplications[index].applicationRate.message}
                          </p>
                        )}
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Applications per Season *
                        </label>
                        <input
                          type="number"
                          min="1"
                          max="10"
                          {...register(`managementPractices.fertilization.fertilizerApplications.${index}.applicationsPerSeason`, { valueAsNumber: true })}
                          placeholder="e.g., 2"
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
                        />
                        {errors.managementPractices?.fertilization?.fertilizerApplications?.[index]?.applicationsPerSeason && (
                          <p className="mt-1 text-xs text-red-600 flex items-center">
                            <AlertCircle className="w-3 h-3 mr-1" />
                            {errors.managementPractices.fertilization.fertilizerApplications[index].applicationsPerSeason.message}
                          </p>
                        )}
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Cost per kg (local currency)
                        </label>
                        <input
                          type="number"
                          step="0.01"
                          {...register(`managementPractices.fertilization.fertilizerApplications.${index}.cost`)}
                          placeholder="e.g., 1500 (per kg)"
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
                        />
                        <p className="text-xs text-gray-500 mt-1">Price per kilogram of fertilizer</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Application Method & Timing */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Application Method
                </label>
                <select
                  {...register('managementPractices.fertilization.applicationMethod')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
                >
                  <option value="">Select method</option>
                  {Object.values(ApplicationMethod).map((method) => (
                    <option key={method} value={method}>{method}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Timing Strategy
                </label>
                <select
                  {...register('managementPractices.fertilization.timingStrategy')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
                >
                  <option value="">Select timing</option>
                  {Object.values(TimingStrategy).map((timing) => (
                    <option key={timing} value={timing}>{timing}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Additional Practices */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  {...register('managementPractices.fertilization.soilTestBased')}
                  className="text-green-600 focus:ring-green-500 rounded"
                />
                <span className="text-sm text-gray-700">
                  Fertilizer application based on soil test results
                </span>
              </label>

              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  {...register('managementPractices.fertilization.followsNutrientPlan')}
                  className="text-green-600 focus:ring-green-500 rounded"
                />
                <span className="text-sm text-gray-700">
                  I follow a nutrient management plan
                </span>
              </label>
            </div>
          </motion.div>
        )}
      </motion.section>

      {/* Water Management */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-blue-50 rounded-xl p-6"
      >
        <div className="flex items-center space-x-3 mb-6">
          <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
            <Droplets className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Water Management</h3>
            <p className="text-sm text-gray-600">How do you source and manage water for your crops?</p>
          </div>
        </div>

        <div className="space-y-6">
          {/* Water Sources */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Water Sources (select all that apply) *
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.values(WaterSource).map((source) => (
                <label key={source} className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    {...register('managementPractices.waterManagement.waterSource')}
                    value={source}
                    className="text-blue-600 focus:ring-blue-500 rounded"
                  />
                  <span className="text-sm text-gray-700">{source}</span>
                </label>
              ))}
            </div>
            {errors.managementPractices?.waterManagement?.waterSource && (
              <p className="mt-2 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.managementPractices.waterManagement.waterSource.message}
              </p>
            )}
          </div>

          {/* Irrigation System */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Irrigation System (if used)
            </label>
            <select
              {...register('managementPractices.waterManagement.irrigationSystem')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select irrigation system</option>
              {Object.values(IrrigationSystem).map((system) => (
                <option key={system} value={system}>{system}</option>
              ))}
            </select>
          </div>

          {/* Additional Water Management */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                {...register('managementPractices.waterManagement.drainageSystem')}
                className="text-blue-600 focus:ring-blue-500 rounded"
              />
              <span className="text-sm text-gray-700">
                I have a drainage system
              </span>
            </label>
          </div>
        </div>
      </motion.section>

      {/* Debug Information - Temporary */}
      {process.env.NODE_ENV === 'development' && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-gray-100 border border-gray-300 rounded-lg p-4"
        >
          <div className="text-sm text-gray-700">
            <strong>Debug Info:</strong>
            <div className="mt-2 space-y-1">
              <p>Soil Type: {watch('managementPractices.soilManagement.soilType') || 'Not set'}</p>
              <p>Soil Testing Frequency: {watch('managementPractices.soilManagement.soilTestingFrequency') || 'Not set'}</p>
              <p>Uses Compost: {watch('managementPractices.soilManagement.compostUse.usesCompost') ? 'Yes' : 'No'}</p>
              <p>Compost Source: {watch('managementPractices.soilManagement.compostUse.compostsource') || 'Not set'}</p>
              <p>Water Sources: {JSON.stringify(watch('managementPractices.waterManagement.waterSource') || [])}</p>
              <p>Form Errors: {JSON.stringify(Object.keys(errors.managementPractices || {}))}</p>
              <p>Soil Management Errors: {JSON.stringify(errors.managementPractices?.soilManagement || {})}</p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Validation Errors Summary */}
      {(() => {
        // Debug logging
        if (Object.keys(errors.managementPractices || {}).length > 0) {
          console.log('Management Practices Validation Errors:', errors.managementPractices);
        }
        return Object.keys(errors.managementPractices || {}).length > 0;
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
            {/* Simple comprehensive error display */}
            {(() => {
              const errorMessages = [];
              
              // Soil Management Errors
              if (errors.managementPractices?.soilManagement?.soilType) {
                errorMessages.push('• Soil Management: Please select your predominant soil type');
              }
              if (errors.managementPractices?.soilManagement?.soilTestingFrequency) {
                errorMessages.push('• Soil Management: Please select how often you test your soil');
              }
              if (errors.managementPractices?.soilManagement?.compostUse?.compostsource && usesCompost) {
                errorMessages.push('• Soil Management: Please select a valid compost source (not "Not used") when using compost');
              }
              
              // Water Management Errors  
              if (errors.managementPractices?.waterManagement?.waterSource) {
                errorMessages.push('• Water Management: Please select at least one water source (rainfall, well, river, etc.)');
              }
              
              // Soil Conservation Practices Errors
              if (errors.managementPractices?.soilManagement?.conservationPractices) {
                errorMessages.push('• Soil Management: Conservation practices validation error');
              }
              
              // Fertilization Errors
              if (errors.managementPractices?.fertilization?.fertilizerApplications && Array.isArray(errors.managementPractices.fertilization.fertilizerApplications)) {
                errors.managementPractices.fertilization.fertilizerApplications.forEach((fertError, index) => {
                  if (fertError?.fertilizerType) errorMessages.push(`• Fertilization: Fertilizer ${index + 1} - Please select fertilizer type`);
                  if (fertError?.applicationRate) errorMessages.push(`• Fertilization: Fertilizer ${index + 1} - Please enter application rate`);
                  if (fertError?.applicationsPerSeason) errorMessages.push(`• Fertilization: Fertilizer ${index + 1} - Please enter applications per season`);
                });
              }
              
              // If no specific errors found, show detailed debug info
              if (errorMessages.length === 0) {
                // Check for specific missing required fields
                if (!watch('managementPractices.soilManagement.soilType')) {
                  errorMessages.push('• Soil Management: Please select your predominant soil type');
                }
                if (!watch('managementPractices.soilManagement.soilTestingFrequency')) {
                  errorMessages.push('• Soil Management: Please select how often you test your soil');
                }
                if (!watch('managementPractices.waterManagement.waterSource') || watch('managementPractices.waterManagement.waterSource').length === 0) {
                  errorMessages.push('• Water Management: Please select at least one water source');
                }
                
                // If still no specific errors, show generic debug info
                if (errorMessages.length === 0) {
                  Object.entries(errors.managementPractices || {}).forEach(([section, sectionErrors]) => {
                    errorMessages.push(`• Debug: Error in ${section} section - please check all fields`);
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

      {/* Info Box */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="bg-green-50 border border-green-200 rounded-lg p-4"
      >
        <div className="flex items-start space-x-3">
          <Info className="w-5 h-5 text-green-600 mt-0.5" />
          <div className="text-sm text-green-700">
            <strong>Why this matters:</strong> Your soil and fertilizer management practices directly 
            impact greenhouse gas emissions, water quality, and soil health. This information helps 
            us calculate accurate environmental impacts and suggest improvements.
          </div>
        </div>
      </motion.div>
    </div>
  );
}