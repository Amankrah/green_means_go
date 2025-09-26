'use client';

import React from 'react';
import { useFormContext, useFieldArray } from 'react-hook-form';
import { motion } from 'framer-motion';
import { Shield, Info, AlertCircle, Plus, Trash2, Bug, Leaf } from 'lucide-react';
import { EnhancedAssessmentFormData } from '@/lib/enhanced-assessment-schema';
import { 
  PestManagementApproach, 
  MonitoringFrequency, 
  PesticideType, 
  IPMPractice 
} from '@/types/enhanced-assessment';

export default function PestManagementStep() {
  const { register, formState: { errors }, control, setValue } = useFormContext<EnhancedAssessmentFormData>();

  // Dynamic arrays
  const { fields: pesticideFields, append: appendPesticide, remove: removePesticide } = useFieldArray({
    control,
    name: 'pestManagement.pesticides'
  });

  const [primaryPests, setPrimaryPests] = React.useState<string[]>([]);
  const [primaryDiseases, setPrimaryDiseases] = React.useState<string[]>([]);
  const [biologicalControls, setBiologicalControls] = React.useState<string[]>([]);
  const [selectedIPMPractices, setSelectedIPMPractices] = React.useState<IPMPractice[]>([]);

  // Update form values when arrays change
  React.useEffect(() => {
    setValue('pestManagement.primaryPests', primaryPests);
    setValue('pestManagement.primaryDiseases', primaryDiseases);
    setValue('pestManagement.biologicalControls', biologicalControls);
    setValue('pestManagement.ipmPractices', selectedIPMPractices);
  }, [primaryPests, primaryDiseases, biologicalControls, selectedIPMPractices, setValue]);

  return (
    <div className="space-y-8">
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-red-50 rounded-xl p-6"
      >
        <div className="flex items-center space-x-3 mb-6">
          <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
            <Shield className="w-5 h-5 text-red-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Pest & Disease Management</h3>
            <p className="text-sm text-gray-600">How do you protect your crops from pests and diseases?</p>
          </div>
        </div>

        <div className="space-y-6">
          {/* Primary Pests */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Primary Pests Encountered
            </label>
            <div className="space-y-2">
              {primaryPests.map((pest, index) => (
                <div key={index} className="flex items-center space-x-2">
                  <input
                    type="text"
                    value={pest}
                    onChange={(e) => {
                      const newPests = [...primaryPests];
                      newPests[index] = e.target.value;
                      setPrimaryPests(newPests);
                    }}
                    placeholder="e.g., Fall armyworm, Stem borer"
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const newPests = primaryPests.filter((_, i) => i !== index);
                      setPrimaryPests(newPests);
                    }}
                    className="text-red-600 hover:text-red-800 p-1"
                    title="Remove this pest"
                    aria-label="Remove this pest"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => setPrimaryPests([...primaryPests, ''])}
                className="flex items-center space-x-2 px-3 py-2 text-red-600 hover:text-red-800 border border-red-300 rounded-lg hover:bg-red-50 transition-colors"
              >
                <Plus className="w-4 h-4" />
                <span>Add Pest</span>
              </button>
            </div>
          </div>

          {/* Primary Diseases */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Primary Diseases Encountered
            </label>
            <div className="space-y-2">
              {primaryDiseases.map((disease, index) => (
                <div key={index} className="flex items-center space-x-2">
                  <input
                    type="text"
                    value={disease}
                    onChange={(e) => {
                      const newDiseases = [...primaryDiseases];
                      newDiseases[index] = e.target.value;
                      setPrimaryDiseases(newDiseases);
                    }}
                    placeholder="e.g., Leaf blight, Root rot"
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const newDiseases = primaryDiseases.filter((_, i) => i !== index);
                      setPrimaryDiseases(newDiseases);
                    }}
                    className="text-red-600 hover:text-red-800 p-1"
                    title="Remove this disease"
                    aria-label="Remove this disease"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => setPrimaryDiseases([...primaryDiseases, ''])}
                className="flex items-center space-x-2 px-3 py-2 text-red-600 hover:text-red-800 border border-red-300 rounded-lg hover:bg-red-50 transition-colors"
              >
                <Plus className="w-4 h-4" />
                <span>Add Disease</span>
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Management Approach *
            </label>
            <select
              {...register('pestManagement.managementApproach')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
            >
              <option value="">Select approach</option>
              {Object.values(PestManagementApproach).map((approach) => (
                <option key={approach} value={approach}>{approach}</option>
              ))}
            </select>
            {errors.pestManagement?.managementApproach && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.pestManagement.managementApproach.message}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Monitoring Frequency *
            </label>
            <select
              {...register('pestManagement.pestMonitoringFrequency')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
            >
              <option value="">Select frequency</option>
              {Object.values(MonitoringFrequency).map((freq) => (
                <option key={freq} value={freq}>{freq}</option>
              ))}
            </select>
            {errors.pestManagement?.pestMonitoringFrequency && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                {errors.pestManagement.pestMonitoringFrequency.message}
              </p>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                {...register('pestManagement.usesIPM')}
                className="text-green-600 focus:ring-green-500 rounded"
              />
              <span className="text-sm text-gray-700">
                I use Integrated Pest Management (IPM)
              </span>
            </label>

            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                {...register('pestManagement.usesEconomicThresholds')}
                className="text-green-600 focus:ring-green-500 rounded"
              />
              <span className="text-sm text-gray-700">
                I use economic thresholds for pest control
              </span>
            </label>
          </div>
        </div>
      </motion.section>

      {/* Pesticides Section */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-orange-50 rounded-xl p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
              <Bug className="w-5 h-5 text-orange-600" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Pesticides Used</h3>
              <p className="text-sm text-gray-600">Chemical pesticides and their application details</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => appendPesticide({
              pesticideType: PesticideType.INSECTICIDE,
              activeIngredient: '',
              brandName: '',
              applicationRate: 0,
              applicationsPerSeason: 0,
              targetPests: [],
              cost: undefined
            })}
            className="flex items-center space-x-2 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Add Pesticide</span>
          </button>
        </div>

        {pesticideFields.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Bug className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>No pesticides added yet. Click &quot;Add Pesticide&quot; to get started.</p>
            <p className="text-xs mt-2">Leave empty if you don&apos;t use chemical pesticides</p>
          </div>
        ) : (
          <div className="space-y-4">
            {pesticideFields.map((field, index) => (
              <motion.div
                key={field.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-white border border-orange-200 rounded-lg p-4"
              >
                <div className="flex items-center justify-between mb-4">
                  <h4 className="font-medium text-gray-900">Pesticide #{index + 1}</h4>
                  <button
                    type="button"
                    onClick={() => removePesticide(index)}
                    className="text-red-600 hover:text-red-800 p-1"
                    title="Remove this pesticide"
                    aria-label="Remove this pesticide"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Pesticide Type *
                    </label>
                    <select
                      {...register(`pestManagement.pesticides.${index}.pesticideType`)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500"
                    >
                      <option value="">Select type</option>
                      {Object.values(PesticideType).map((type) => (
                        <option key={type} value={type}>{type}</option>
                      ))}
                    </select>
                    {errors.pestManagement?.pesticides?.[index]?.pesticideType && (
                      <p className="mt-1 text-sm text-red-600 flex items-center">
                        <AlertCircle className="w-4 h-4 mr-1" />
                        {errors.pestManagement.pesticides[index].pesticideType.message}
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Brand Name *
                    </label>
                    <input
                      type="text"
                      {...register(`pestManagement.pesticides.${index}.brandName`)}
                      placeholder="e.g., Karate, Confidor"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500"
                    />
                    {errors.pestManagement?.pesticides?.[index]?.brandName && (
                      <p className="mt-1 text-sm text-red-600 flex items-center">
                        <AlertCircle className="w-4 h-4 mr-1" />
                        {errors.pestManagement.pesticides[index].brandName.message}
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Active Ingredient *
                    </label>
                    <input
                      type="text"
                      {...register(`pestManagement.pesticides.${index}.activeIngredient`)}
                      placeholder="e.g., Lambda-cyhalothrin, Imidacloprid"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500"
                    />
                    {errors.pestManagement?.pesticides?.[index]?.activeIngredient && (
                      <p className="mt-1 text-sm text-red-600 flex items-center">
                        <AlertCircle className="w-4 h-4 mr-1" />
                        {errors.pestManagement.pesticides[index].activeIngredient.message}
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Application Rate (L or kg/ha) *
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max="100"
                      {...register(`pestManagement.pesticides.${index}.applicationRate`, { valueAsNumber: true })}
                      placeholder="e.g., 2.5"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500"
                    />
                    {errors.pestManagement?.pesticides?.[index]?.applicationRate && (
                      <p className="mt-1 text-sm text-red-600 flex items-center">
                        <AlertCircle className="w-4 h-4 mr-1" />
                        {errors.pestManagement.pesticides[index].applicationRate.message}
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Applications Per Season *
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="20"
                      {...register(`pestManagement.pesticides.${index}.applicationsPerSeason`, { valueAsNumber: true })}
                      placeholder="e.g., 3"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500"
                    />
                    {errors.pestManagement?.pesticides?.[index]?.applicationsPerSeason && (
                      <p className="mt-1 text-sm text-red-600 flex items-center">
                        <AlertCircle className="w-4 h-4 mr-1" />
                        {errors.pestManagement.pesticides[index].applicationsPerSeason.message}
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Cost Per Application (optional)
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      {...register(`pestManagement.pesticides.${index}.cost`, { valueAsNumber: true })}
                      placeholder="e.g., 15000"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Total cost per hectare for one application (local currency)
                    </p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </motion.section>

      {/* IPM Practices Section */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-green-50 rounded-xl p-6"
      >
        <div className="flex items-center space-x-3 mb-6">
          <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
            <Leaf className="w-5 h-5 text-green-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">IPM Practices</h3>
            <p className="text-sm text-gray-600">Integrated Pest Management techniques you use</p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Select IPM Practices You Use
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.values(IPMPractice).map((practice) => (
                <label key={practice} className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={selectedIPMPractices.includes(practice)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedIPMPractices([...selectedIPMPractices, practice]);
                      } else {
                        setSelectedIPMPractices(selectedIPMPractices.filter(p => p !== practice));
                      }
                    }}
                    className="text-green-600 focus:ring-green-500 rounded"
                  />
                  <span className="text-sm text-gray-700">{practice}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Biological Controls */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Biological Controls Used
            </label>
            <div className="space-y-2">
              {biologicalControls.map((control, index) => (
                <div key={index} className="flex items-center space-x-2">
                  <input
                    type="text"
                    value={control}
                    onChange={(e) => {
                      const newControls = [...biologicalControls];
                      newControls[index] = e.target.value;
                      setBiologicalControls(newControls);
                    }}
                    placeholder="e.g., Beneficial insects, Predatory mites"
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const newControls = biologicalControls.filter((_, i) => i !== index);
                      setBiologicalControls(newControls);
                    }}
                    className="text-red-600 hover:text-red-800 p-1"
                    title="Remove this biological control"
                    aria-label="Remove this biological control"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => setBiologicalControls([...biologicalControls, ''])}
                className="flex items-center space-x-2 px-3 py-2 text-green-600 hover:text-green-800 border border-green-300 rounded-lg hover:bg-green-50 transition-colors"
              >
                <Plus className="w-4 h-4" />
                <span>Add Biological Control</span>
              </button>
            </div>
          </div>
        </div>
      </motion.section>

      {/* Validation Errors Summary */}
      {Object.keys(errors.pestManagement || {}).length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-red-50 border border-red-200 rounded-lg p-4"
        >
          <div className="flex items-center space-x-2 text-red-800 mb-2">
            <AlertCircle className="w-5 h-5" />
            <span className="font-medium">Please complete the following required fields:</span>
          </div>
          <ul className="text-sm text-red-700 space-y-1">
            {errors.pestManagement?.managementApproach && (
              <li>• Please select your pest management approach</li>
            )}
            {errors.pestManagement?.pestMonitoringFrequency && (
              <li>• Please select monitoring frequency</li>
            )}
          </ul>
        </motion.div>
      )}

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-blue-50 border border-blue-200 rounded-lg p-4"
      >
        <div className="flex items-start space-x-3">
          <Info className="w-5 h-5 text-blue-600 mt-0.5" />
          <div className="text-sm text-blue-700">
            <strong>Note:</strong> Your pest management practices affect environmental impact through 
            pesticide use, beneficial insect conservation, and overall ecosystem health.
          </div>
        </div>
      </motion.div>
    </div>
  );
}