'use client';

import React from 'react';
import { useFormContext } from 'react-hook-form';
import { motion } from 'framer-motion';
import { 
  CheckCircle, 
  BarChart3, 
  User, 
  Sprout, 
  Settings, 
  Shield, 
  Zap,
  Info,
  AlertCircle,
  Loader2
} from 'lucide-react';

import { EnhancedAssessmentFormData } from '@/lib/enhanced-assessment-schema';

interface ReviewSubmitStepProps {
  onSubmit: () => void;
  isSubmitting: boolean;
  onPrevious?: () => void;
}

export default function ReviewSubmitStep({ onSubmit, isSubmitting, onPrevious }: ReviewSubmitStepProps) {
  const { watch, formState: { errors } } = useFormContext<EnhancedAssessmentFormData>();
  
  const formData = watch();

  const renderFarmProfileSummary = () => (
    <div className="bg-green-50 rounded-lg p-4">
      <div className="flex items-center space-x-2 mb-3">
        <User className="w-5 h-5 text-green-600" />
        <h4 className="font-semibold text-green-900">Farm Profile</h4>
      </div>
      <div className="space-y-2 text-sm text-green-800">
        <p><strong>Farmer:</strong> {formData.farmProfile?.farmerName}</p>
        <p><strong>Farm:</strong> {formData.farmProfile?.farmName}</p>
        <p><strong>Location:</strong> {formData.farmProfile?.region}, {formData.farmProfile?.country}</p>
        <p><strong>Size:</strong> {formData.farmProfile?.totalFarmSize} hectares</p>
        <p><strong>Type:</strong> {formData.farmProfile?.farmType}</p>
        <p><strong>System:</strong> {formData.farmProfile?.primaryFarmingSystem}</p>
      </div>
    </div>
  );

  const renderCropsSummary = () => (
    <div className="bg-emerald-50 rounded-lg p-4">
      <div className="flex items-center space-x-2 mb-3">
        <Sprout className="w-5 h-5 text-emerald-600" />
        <h4 className="font-semibold text-emerald-900">Crop Production</h4>
      </div>
      <div className="space-y-3">
        {formData.cropProductions?.map((crop, index) => (
          <div key={index} className="bg-white rounded p-3 text-sm">
            <p className="font-medium text-emerald-900">{crop.cropName}</p>
            <p className="text-emerald-700">
              {crop.areaAllocated} ha • {crop.annualProduction} kg/year • {crop.productionSystem}
            </p>
            <p className="text-emerald-600">{crop.croppingPattern}</p>
          </div>
        )) || <p className="text-sm text-emerald-700">No crops added</p>}
      </div>
    </div>
  );

  const renderManagementSummary = () => (
    <div className="bg-blue-50 rounded-lg p-4">
      <div className="flex items-center space-x-2 mb-3">
        <Settings className="w-5 h-5 text-blue-600" />
        <h4 className="font-semibold text-blue-900">Soil & Water Management</h4>
      </div>
      <div className="space-y-3 text-sm text-blue-800">
        {/* Soil Management */}
        <div>
          <strong>Soil Management:</strong>
          <div className="ml-4 space-y-1">
            <p>• Soil Type: {formData.managementPractices?.soilManagement?.soilType || 'Not specified'}</p>
            <p>• Testing Frequency: {formData.managementPractices?.soilManagement?.soilTestingFrequency || 'Not specified'}</p>
            {formData.managementPractices?.soilManagement?.conservationPractices && formData.managementPractices.soilManagement.conservationPractices.length > 0 && (
              <p>• Conservation Practices: {formData.managementPractices.soilManagement.conservationPractices.join(', ')}</p>
            )}
            <p>• Uses Compost: {formData.managementPractices?.soilManagement?.compostUse?.usesCompost ? 'Yes' : 'No'}</p>
            {formData.managementPractices?.soilManagement?.compostUse?.usesCompost && (
              <p>• Compost Source: {formData.managementPractices?.soilManagement?.compostUse?.compostsource || 'Not specified'}</p>
            )}
          </div>
        </div>

        {/* Fertilization */}
        <div>
          <strong>Fertilization:</strong>
          <div className="ml-4 space-y-1">
            <p>• Uses Fertilizers: {formData.managementPractices?.fertilization?.usesFertilizers ? 'Yes' : 'No'}</p>
            <p>• Soil Test Based: {formData.managementPractices?.fertilization?.soilTestBased ? 'Yes' : 'No'}</p>
            <p>• Follows Nutrient Plan: {formData.managementPractices?.fertilization?.followsNutrientPlan ? 'Yes' : 'No'}</p>
            {formData.managementPractices?.fertilization?.fertilizerApplications && formData.managementPractices.fertilization.fertilizerApplications.length > 0 && (
              <div>
                <p>• Fertilizer Applications:</p>
                <div className="ml-4 space-y-1">
                  {formData.managementPractices.fertilization.fertilizerApplications.map((fert, index) => (
                    <p key={index} className="text-xs">
                      - {fert.fertilizerType}: {fert.applicationRate} kg/ha, {fert.applicationsPerSeason} times/season
                    </p>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Water Management */}
        <div>
          <strong>Water Management:</strong>
          <div className="ml-4 space-y-1">
            <p>• Water Sources: {formData.managementPractices?.waterManagement?.waterSource?.join(', ') || 'Not specified'}</p>
            <p>• Irrigation System: {formData.managementPractices?.waterManagement?.irrigationSystem || 'None'}</p>
            <p>• Drainage System: {formData.managementPractices?.waterManagement?.drainageSystem ? 'Yes' : 'No'}</p>
            {formData.managementPractices?.waterManagement?.waterConservationPractices && formData.managementPractices.waterManagement.waterConservationPractices.length > 0 && (
              <p>• Conservation Practices: {formData.managementPractices.waterManagement.waterConservationPractices.join(', ')}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  const renderPestManagementSummary = () => (
    <div className="bg-red-50 rounded-lg p-4">
      <div className="flex items-center space-x-2 mb-3">
        <Shield className="w-5 h-5 text-red-600" />
        <h4 className="font-semibold text-red-900">Pest & Disease Management</h4>
      </div>
      <div className="space-y-3 text-sm text-red-800">
        <div>
          <p><strong>Primary Pests:</strong> {formData.pestManagement?.primaryPests?.join(', ') || 'Not specified'}</p>
          <p><strong>Primary Diseases:</strong> {formData.pestManagement?.primaryDiseases?.join(', ') || 'Not specified'}</p>
        </div>
        <p><strong>Management Approach:</strong> {formData.pestManagement?.managementApproach || 'Not specified'}</p>
        <p><strong>Uses IPM:</strong> {formData.pestManagement?.usesIPM ? 'Yes' : 'No'}</p>
        {formData.pestManagement?.ipmPractices && formData.pestManagement.ipmPractices.length > 0 && (
          <p><strong>IPM Practices:</strong> {formData.pestManagement.ipmPractices.join(', ')}</p>
        )}
        {formData.pestManagement?.biologicalControls && formData.pestManagement.biologicalControls.length > 0 && (
          <p><strong>Biological Controls:</strong> {formData.pestManagement.biologicalControls.join(', ')}</p>
        )}
        <p><strong>Monitoring Frequency:</strong> {formData.pestManagement?.pestMonitoringFrequency || 'Not specified'}</p>
        <p><strong>Uses Economic Thresholds:</strong> {formData.pestManagement?.usesEconomicThresholds ? 'Yes' : 'No'}</p>
        {formData.pestManagement?.pesticides && formData.pestManagement.pesticides.length > 0 && (
          <div>
            <strong>Pesticides Used:</strong>
            <div className="ml-4 space-y-1">
              {formData.pestManagement.pesticides.map((pest, index) => (
                <p key={index}>
                  • {pest.pesticideType}: {pest.brandName} ({pest.activeIngredient}) - {pest.applicationsPerSeason} applications/season
                </p>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );

  const renderEquipmentSummary = () => (
    <div className="bg-purple-50 rounded-lg p-4">
      <div className="flex items-center space-x-2 mb-3">
        <Zap className="w-5 h-5 text-purple-600" />
        <h4 className="font-semibold text-purple-900">Equipment & Infrastructure</h4>
      </div>
      <div className="space-y-3 text-sm text-purple-800">
        {formData.equipmentEnergy?.equipment && formData.equipmentEnergy.equipment.length > 0 ? (
          <div>
            <strong>Equipment:</strong>
            <div className="ml-4 space-y-1">
              {formData.equipmentEnergy.equipment.map((eq, index) => (
                <p key={index}>• {eq.equipmentType} ({eq.powerSource}, {eq.hoursPerYear || 0} hrs/year)</p>
              ))}
            </div>
          </div>
        ) : (
          <p><strong>Equipment:</strong> No equipment listed</p>
        )}
        
        {formData.equipmentEnergy?.energySources && formData.equipmentEnergy.energySources.length > 0 ? (
          <div>
            <strong>Energy Sources:</strong>
            <div className="ml-4 space-y-1">
              {formData.equipmentEnergy.energySources.map((energy, index) => (
                <p key={index}>• {energy.energyType} ({energy.monthlyConsumption || 0} units/month)</p>
              ))}
            </div>
          </div>
        ) : (
          <p><strong>Energy Sources:</strong> No energy sources listed</p>
        )}
        
        <div>
          <strong>Infrastructure:</strong>
          <div className="ml-4 space-y-1">
            <p>• Storage: {formData.equipmentEnergy?.infrastructure?.storageCapacity || 0} cubic meters</p>
            <p>• Road Access: {formData.equipmentEnergy?.infrastructure?.transportAccess?.roadAccess || 'Not specified'}</p>
            <p>• Distance to Market: {formData.equipmentEnergy?.infrastructure?.transportAccess?.distanceToMarket || 0} km</p>
            <p>• Transport Mode: {formData.equipmentEnergy?.infrastructure?.transportAccess?.transportMode?.join(', ') || 'Not specified'}</p>
          </div>
        </div>
      </div>
    </div>
  );

  const renderAssessmentParametersSummary = () => (
    <div className="bg-indigo-50 rounded-lg p-4">
      <div className="flex items-center space-x-2 mb-3">
        <BarChart3 className="w-5 h-5 text-indigo-600" />
        <h4 className="font-semibold text-indigo-900">Assessment Parameters</h4>
      </div>
      <div className="space-y-2 text-sm text-indigo-800">
        <p><strong>Functional Unit:</strong> {formData.assessmentParameters?.functionalUnit || 'Not specified'}</p>
        <p><strong>System Boundary:</strong> {formData.assessmentParameters?.systemBoundary || 'Not specified'}</p>
        <p><strong>Assessment Period:</strong> {formData.assessmentParameters?.assessmentPeriod || 1} year(s)</p>
        <p><strong>Uncertainty Analysis:</strong> {formData.assessmentParameters?.includeUncertaintyAnalysis ? 'Yes' : 'No'}</p>
        <p><strong>Sensitivity Analysis:</strong> {formData.assessmentParameters?.includeSensitivityAnalysis ? 'Yes' : 'No'}</p>
        <p><strong>Benchmark Comparison:</strong> {formData.assessmentParameters?.benchmarkComparison ? 'Yes' : 'No'}</p>
      </div>
    </div>
  );

  const hasErrors = Object.keys(errors).length > 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center"
      >
        <div className="w-16 h-16 bg-gradient-to-r from-green-500 to-emerald-500 rounded-full flex items-center justify-center mx-auto mb-4">
          <BarChart3 className="w-8 h-8 text-white" />
        </div>
        <h3 className="text-2xl font-semibold text-gray-900 mb-2">Review Your Assessment</h3>
        <p className="text-gray-600">
          Please review the information below before submitting for analysis
        </p>
      </motion.div>

      {/* Summary Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
        >
          {renderFarmProfileSummary()}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
        >
          {renderCropsSummary()}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
        >
          {renderManagementSummary()}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.4 }}
        >
          {renderPestManagementSummary()}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.5 }}
          className="lg:col-span-2"
        >
          {renderEquipmentSummary()}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.6 }}
          className="lg:col-span-2"
        >
          {renderAssessmentParametersSummary()}
        </motion.div>
      </div>



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
              <p>Farm Profile Errors: {JSON.stringify(errors.farmProfile || {})}</p>
              <p>Crop Productions Errors: {JSON.stringify(errors.cropProductions || {})}</p>
              <p>All Errors: {JSON.stringify(Object.keys(errors))}</p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Errors Display */}
      {hasErrors && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-red-50 border border-red-200 rounded-lg p-4"
        >
          <div className="flex items-center space-x-2 text-red-800 mb-2">
            <AlertCircle className="w-5 h-5" />
            <span className="font-medium">Please fix the following errors before submitting:</span>
          </div>
          <ul className="text-sm text-red-700 space-y-1">
            {Object.entries(errors).map(([field, error]) => (
              <li key={field}>• {field}: {typeof error === 'object' && error?.message ? error.message : 'Invalid value'}</li>
            ))}
          </ul>
        </motion.div>
      )}

      {/* What Happens Next */}
              <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8 }}
          className="bg-blue-50 border border-blue-200 rounded-lg p-6"
        >
        <div className="flex items-start space-x-3">
          <Info className="w-6 h-6 text-blue-600 mt-0.5" />
          <div>
            <h4 className="font-semibold text-blue-900 mb-2">What Happens Next?</h4>
            <div className="text-sm text-blue-700 space-y-2">
              <p>✓ <strong>Comprehensive Analysis:</strong> Your data will be processed using advanced LCA models</p>
              <p>✓ <strong>Environmental Impact Calculation:</strong> Climate, water, land, and biodiversity impacts</p>
              <p>✓ <strong>Regional Benchmarking:</strong> Compare your farm to similar operations in your region</p>
              <p>✓ <strong>Actionable Recommendations:</strong> Specific steps to improve sustainability</p>
              <p>✓ <strong>Detailed Report:</strong> Comprehensive results with visual charts and explanations</p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Navigation and Submit Buttons */}
              <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.9 }}
          className="flex flex-col items-center space-y-4"
        >
        {/* Back Button */}
        {onPrevious && (
          <button
            type="button"
            onClick={onPrevious}
            disabled={isSubmitting}
            className="w-full md:w-auto bg-gray-100 hover:bg-gray-200 text-gray-700 px-8 py-3 rounded-lg font-medium flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
          >
            <span>← Back to Previous Step</span>
          </button>
        )}
        <button
          type="button"
          onClick={onSubmit}
          disabled={hasErrors || isSubmitting}
          className="w-full md:w-auto bg-gradient-to-r from-green-600 to-emerald-600 text-white px-12 py-4 rounded-xl font-semibold text-lg flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl transition-all duration-200"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-6 h-6 animate-spin" />
              <span>Processing Comprehensive Assessment...</span>
            </>
          ) : (
            <>
              <BarChart3 className="w-6 h-6" />
              <span>Submit for Analysis</span>
            </>
          )}
        </button>

        <div className="text-center text-sm text-gray-600">
          <p>⏱️ <strong>Processing time:</strong> 2-3 minutes</p>
          <p>📊 <strong>Assessment type:</strong> Comprehensive LCA following ISO 14040/14044 standards</p>
        </div>
      </motion.div>
    </div>
  );
}