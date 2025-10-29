'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { 
  BarChart3, 
  Droplets, 
  Leaf, 
  Sun, 
  TreePine,
  Award,
  AlertTriangle,
  CheckCircle,
  Download,
  Share,
  ArrowRight,
  RefreshCw
} from 'lucide-react';
import {
  ResponsiveContainer,
  RadialBarChart,
  RadialBar
} from 'recharts';
import Layout from '@/components/Layout';
import ProfessionalReportViewer from '@/components/ProfessionalReportViewer';
import { assessmentAPI, getScoreInterpretation } from '@/lib/api';
import { AssessmentResult } from '@/types/assessment';

// Color schemes for charts
// const IMPACT_COLORS = [
//   '#10B981', '#3B82F6', '#8B5CF6', '#F59E0B', '#EF4444',
//   '#06B6D4', '#84CC16', '#F97316', '#EC4899', '#6366F1'
// ];

const SCORE_COLORS = {
  excellent: '#10B981',
  good: '#3B82F6', 
  typical: '#F59E0B',
  'above-average': '#F97316',
  'high-impact': '#EF4444',
};

interface ResultsContentProps {
  assessmentId: string | null;
}

function ResultsContent({ assessmentId }: ResultsContentProps) {
  const [results, setResults] = useState<AssessmentResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rerunning, setRerunning] = useState(false);

  useEffect(() => {
    if (assessmentId) {
      loadResults(assessmentId);
    } else {
      // Load most recent results or show empty state
      setLoading(false);
    }
  }, [assessmentId]);

  const loadResults = async (id: string) => {
    try {
      setLoading(true);
      const result = await assessmentAPI.getAssessment(id);
      console.log('🔍 Results data from backend:', result);
      setResults(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load results');
    } finally {
      setLoading(false);
    }
  };

  const handleRerun = async () => {
    if (!assessmentId) return;
    
    try {
      setRerunning(true);
      setError(null);
      
      // Refresh the assessment results
      const updatedResult = await assessmentAPI.getAssessment(assessmentId);
      console.log('🔄 Refreshed results data from backend:', updatedResult);
      setResults(updatedResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh assessment results');
    } finally {
      setRerunning(false);
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-center">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
              className="w-12 h-12 border-4 border-green-500 border-t-transparent rounded-full mx-auto mb-4"
            />
            <p className="text-lg text-gray-900">Loading your assessment results...</p>
          </div>
        </div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout>
        <div className="py-12 px-4 sm:px-6 lg:px-8">
          <div className="max-w-2xl mx-auto text-center">
            <AlertTriangle className="w-16 h-16 text-red-500 mx-auto mb-6" />
            <h1 className="text-2xl font-bold text-gray-900 mb-4">Unable to Load Results</h1>
            <p className="text-gray-900 mb-8">{error}</p>
            <button
              onClick={() => window.location.href = '/assessment'}
              className="bg-green-600 text-white px-6 py-3 rounded-lg hover:bg-green-700"
            >
              Start New Assessment
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  if (!results) {
    return (
      <Layout>
        <div className="py-12 px-4 sm:px-6 lg:px-8">
          <div className="max-w-4xl mx-auto text-center">
            <BarChart3 className="w-16 h-16 text-gray-800 mx-auto mb-6" />
            <h1 className="text-3xl font-bold text-gray-900 mb-4">
              No Assessment Results Yet
            </h1>
            <p className="text-lg text-gray-900 mb-8">
              Complete a farm assessment to see your sustainability analysis and recommendations.
            </p>
            <a
              href="/assessment"
              className="bg-green-600 text-white px-8 py-4 rounded-xl font-semibold text-lg hover:bg-green-700 inline-flex items-center space-x-2"
            >
              <BarChart3 className="w-5 h-5" />
              <span>Start Assessment</span>
              <ArrowRight className="w-5 h-5" />
            </a>
          </div>
        </div>
      </Layout>
    );
  }

  // Helper function to extract numeric value from result data
  const extractValue = (data: unknown): number => {
    if (typeof data === 'number') {
      return data;
    }
    if (typeof data === 'object' && data !== null) {
      if ('value' in data && typeof data.value === 'number') {
        return data.value;
      }
    }
    return 0;
  };

  // Helper to check if value is already per-kg
  const isAlreadyPerKg = (data: unknown): boolean => {
    if (typeof data === 'object' && data !== null) {
      if ('unit' in data && typeof data.unit === 'string') {
        return data.unit.includes('per kg');
      }
    }
    return false;
  };


  // Helper function to format display values
  const formatDisplayValue = (value: number | undefined, precision: number = 1, categoryName?: string): string => {
    // Handle undefined or null values
    if (value === undefined || value === null || isNaN(value)) {
      return 'N/A';
    }

    // Special handling for zero values in water-related categories
    if (value === 0) {
      if (categoryName === 'Water consumption' || categoryName === 'Water Use') {
        return '0 (Rainfed)';
      }
      if (categoryName === 'Water scarcity') {
        return '0 (No irrigation)';
      }
      // For other categories, show N/A if truly zero
      return 'N/A';
    }
    if (value < 0.01) return value.toExponential(2);
    if (value < 1) return value.toFixed(precision + 1);
    if (value < 1000) return value.toFixed(precision);
    return value.toLocaleString(undefined, { maximumFractionDigits: precision });
  };

  // Helper function to calculate per-unit impacts
  const calculatePerUnitImpact = (totalImpact: number, totalQuantityKg: number): number => {
    if (totalQuantityKg === 0) return 0;
    return totalImpact / totalQuantityKg;
  };

  // Calculate total production quantity from breakdown
  const getTotalProductionQuantity = (): number => {
    // Try to extract from crop breakdown data or use a reasonable estimate
    const cropEntries = Object.entries(results.breakdown_by_food);
    if (cropEntries.length > 0) {
      // Extract quantity from crop name if it includes quantity info
      // Look for patterns like "Cassava (48000kg)" in crop names
      let totalQuantity = 0;
      cropEntries.forEach(([cropName]) => {
        const quantityMatch = cropName.match(/\((\d+(?:,\d+)*)kg\)/);
        if (quantityMatch) {
          const quantity = parseInt(quantityMatch[1].replace(/,/g, ''));
          totalQuantity += quantity;
        }
      });
      
      if (totalQuantity > 0) return totalQuantity;
    }
    
    // Fallback: assume 1 kg if we can't determine the quantity
    // This will show total impacts but with per-kg units
    return 1;
  };

  const totalProductionKg = getTotalProductionQuantity();

  // Extract single score value safely
  const singleScoreValue = extractValue(results.single_score);
  const scoreInterpretation = getScoreInterpretation(singleScoreValue);

  const scoreData = [{
    name: 'Your Score',
    score: singleScoreValue * 100,
    fill: SCORE_COLORS[scoreInterpretation.category as keyof typeof SCORE_COLORS]
  }];

  return (
    <Layout>
      <div className="py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-center mb-6 sm:mb-8"
          >
            <div className="flex items-center justify-center space-x-4 mb-6">
              <Award className="w-8 h-8 text-green-600" />
              <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold text-gray-900">
                Sustainability Assessment Results
              </h1>
            </div>
            <div className="bg-white rounded-xl p-6 shadow-lg">
              <h2 className="text-xl font-semibold text-gray-900 mb-2">
                {results.company_name}
              </h2>
              <div className="flex items-center justify-center space-x-6 text-sm text-gray-900">
                <span>📍 {results.country}</span>
                <span>📅 {new Date(results.assessment_date).toLocaleDateString()}</span>
              </div>
            </div>
          </motion.div>

          {/* Score Overview */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="mb-12"
          >
            <div className={`rounded-2xl p-8 border-2 ${scoreInterpretation.color}`}>
              <div className="flex flex-col md:flex-row items-center justify-between">
                <div className="text-center md:text-left mb-6 md:mb-0">
                  <h3 className="text-2xl font-bold mb-2">
                    Environmental Impact Score
                  </h3>
                  <div className="text-5xl font-bold mb-4">
                    {(singleScoreValue * 100).toFixed(1)}%
                  </div>
                  <div className="text-xl font-semibold mb-2">
                    {scoreInterpretation.title}
                  </div>
                  <p className="text-lg opacity-90 max-w-md">
                    {scoreInterpretation.description}
                  </p>
                </div>
                
                <div className="w-64 h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadialBarChart cx="50%" cy="50%" innerRadius="60%" outerRadius="90%" data={scoreData}>
                      <RadialBar dataKey="score" cornerRadius={10} fill={scoreData[0].fill} />
                      <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle" className="fill-current text-2xl font-bold">
                        {scoreData[0].score.toFixed(1)}%
                      </text>
                    </RadialBarChart>
                  </ResponsiveContainer>
                </div>
              </div>
              
              <div className="mt-6 pt-6 border-t border-opacity-20">
                <h4 className="font-semibold mb-3">Key Recommendations:</h4>
                <div className="grid md:grid-cols-3 gap-4">
                  {scoreInterpretation.recommendations.map((rec, index) => (
                    <div key={index} className="flex items-start space-x-2">
                      <CheckCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
                      <span className="text-sm">{rec}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>

          {/* Methodology & Weighting */}
          {results.single_score && results.single_score.weighting_factors && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
              className="mb-12"
            >
              <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl p-8 border border-blue-200">
                <h3 className="text-2xl font-bold text-gray-900 mb-4">
                  🔬 Assessment Methodology
                </h3>
                <p className="text-sm text-gray-900 mb-6 max-w-3xl">
                  {results.single_score.methodology}
                </p>

                <div className="grid md:grid-cols-3 gap-6">
                  {Object.entries(results.single_score.weighting_factors).map(([category, weight]: [string, number]) => (
                    <div key={category} className="bg-white rounded-xl p-5 shadow-sm">
                      <h4 className="font-semibold text-gray-900 mb-2">{category}</h4>
                      <div className="text-4xl font-bold text-indigo-600 mb-2">
                        {(weight * 100).toFixed(0)}%
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                        <div
                          className="bg-indigo-600 h-2 rounded-full transition-all"
                          style={{ width: `${weight * 100}%` }}
                        />
                      </div>
                      <p className="text-xs text-gray-900">Weighting in final score</p>
                    </div>
                  ))}
                </div>

                <div className="mt-6 p-4 bg-white bg-opacity-60 rounded-lg border border-blue-200">
                  <p className="text-xs text-gray-900">
                    <strong>Note:</strong> This assessment follows ISO 14044 standards with African-context normalization
                    and priorities-based weighting to ensure relevance for African agricultural systems.
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* Impact Categories Chart */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="mb-12"
          >
            <div className="bg-white rounded-2xl p-8 shadow-lg">
              <h3 className="text-2xl font-bold text-gray-900 mb-6 flex items-center">
                <BarChart3 className="w-6 h-6 text-green-600 mr-3" />
                Environmental Impact Categories
              </h3>
              
              {/* Key Impact Metrics */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                {[
                  { icon: Leaf, label: 'Climate Impact', key: 'Global warming', unit: 'kg CO₂-eq', color: 'bg-red-50 border-red-200 text-red-700' },
                  { icon: Droplets, label: 'Water Use', key: 'Water consumption', unit: 'cubic meters', color: 'bg-blue-50 border-blue-200 text-blue-700' },
                  { icon: Sun, label: 'Land Impact', key: 'Land use', unit: 'm²-years', color: 'bg-yellow-50 border-yellow-200 text-yellow-700' },
                  { icon: TreePine, label: 'Biodiversity', key: 'Biodiversity loss', unit: 'impact units', color: 'bg-green-50 border-green-200 text-green-700' },
                ].map((item, index) => {
                  const rawValue = results.midpoint_impacts[item.key];
                  const totalValue = extractValue(rawValue);
                  // Check if value is already per-kg from backend
                  const perUnitValue = isAlreadyPerKg(rawValue)
                    ? totalValue
                    : calculatePerUnitImpact(totalValue, totalProductionKg);
                  const displayValue = formatDisplayValue(perUnitValue, 1, item.key);
                  
                  return (
                    <div key={index} className={`text-center p-6 rounded-xl border-2 ${item.color}`}>
                      <item.icon className="w-10 h-10 mx-auto mb-3" />
                      <div className="text-2xl font-bold mb-1">
                        {displayValue}
                      </div>
                      <div className="text-sm font-medium opacity-75 mb-1">{item.unit} per kg</div>
                      <div className="text-sm font-semibold">
                        {item.label}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Additional Impact Categories */}
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
                {Object.entries(results.midpoint_impacts)
                  .filter(([key]) => !['Global warming', 'Water consumption', 'Land use', 'Biodiversity loss'].includes(key))
                  .map(([category, rawValue], index) => {
                    const totalValue = extractValue(rawValue);
                    // Check if value is already per-kg from backend
                    const perUnitValue = isAlreadyPerKg(rawValue)
                      ? totalValue
                      : calculatePerUnitImpact(totalValue, totalProductionKg);
                    const displayValue = formatDisplayValue(perUnitValue, 1, category);
                    
                    return (
                      <div key={index} className="text-center p-3 bg-gray-50 rounded-lg border">
                        <div className="text-lg font-bold text-gray-900 mb-1">
                          {displayValue}
                        </div>
                        <div className="text-xs text-gray-900 leading-tight">
                          {category.replace(/([A-Z])/g, ' $1').trim()} (per kg)
                        </div>
                      </div>
                    );
                  })
                }
              </div>
            </div>
          </motion.div>


          {/* Crop Breakdown */}
          {Object.keys(results.breakdown_by_food).length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.6 }}
              className="mb-12"
            >
              <div className="bg-white rounded-2xl p-8 shadow-lg">
                <h3 className="text-2xl font-bold text-gray-900 mb-6">
                  Impact by Crop
                </h3>
                
                <div className="space-y-6">
                  {Object.entries(results.breakdown_by_food).map(([cropName, impacts], index) => {
                    // Extract crop quantity from crop name (e.g., "Cassava (48000kg)")
                    const quantityMatch = cropName.match(/\((\d+(?:,\d+)*)kg\)/);
                    const cropQuantityKg = quantityMatch ? parseInt(quantityMatch[1].replace(/,/g, '')) : 1;
                    const cleanCropName = cropName.replace(/\s*\(\d+(?:,\d+)*kg\)/, '');
                    
                    const impactValues = Object.values(impacts as Record<string, unknown>)
                      .map(value => extractValue(value));
                    const totalImpact = impactValues.reduce((sum, value) => sum + value, 0);
                    // breakdown_by_food contains total impacts per crop, need to divide by quantity
                    const totalPerKg = calculatePerUnitImpact(totalImpact, cropQuantityKg);
                    
                    return (
                      <div key={index} className="border border-gray-200 rounded-xl p-6">
                        <div className="flex items-center justify-between mb-4">
                          <div>
                            <h4 className="text-lg font-semibold text-gray-900">{cleanCropName}</h4>
                            <p className="text-sm text-gray-800">{cropQuantityKg.toLocaleString()} kg annual production</p>
                          </div>
                          <div className="text-sm text-gray-900 text-right">
                            <div>Total Impact: {formatDisplayValue(totalPerKg)} per kg</div>
                          </div>
                        </div>
                        
                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                          {Object.entries(impacts as Record<string, unknown>).slice(0, 4).map(([category, rawValue]) => {
                            const totalValue = extractValue(rawValue);
                            // breakdown_by_food contains total impacts per crop, need to divide by quantity
                            const perUnitValue = calculatePerUnitImpact(totalValue, cropQuantityKg);
                            const displayValue = formatDisplayValue(perUnitValue, 1, category);
                            
                            return (
                              <div key={category} className="text-center">
                                <div className="text-lg font-bold text-gray-900">
                                  {displayValue}
                                </div>
                                <div className="text-xs text-gray-900">
                                  {category.replace(/([A-Z])/g, ' $1').trim()} (per kg)
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </motion.div>
          )}

          {/* Endpoint Impacts */}
          {results.endpoint_impacts && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.7 }}
              className="mb-12"
            >
              <div className="bg-white rounded-2xl p-8 shadow-lg">
                <h3 className="text-2xl font-bold text-gray-900 mb-6">
                  🌍 Endpoint Impact Assessment
                </h3>
                <p className="text-gray-900 mb-6">
                  Aggregated impacts on three areas of protection (Human Health, Ecosystem Quality, Resource Scarcity)
                </p>

                <div className="grid md:grid-cols-3 gap-6">
                  {Object.entries(results.endpoint_impacts).map(([category, data]) => (
                    <div key={category} className="border border-gray-200 rounded-xl p-6 hover:border-green-500 transition-colors">
                      <h4 className="text-lg font-semibold text-gray-900 mb-2">{category}</h4>
                      <div className="text-3xl font-bold text-green-600 mb-2">
                        {formatDisplayValue(data.value, 3)}
                      </div>
                      <div className="text-sm text-gray-900 mb-4">{data.unit}</div>
                      {/* Note: EndpointResult doesn't have contributing_sources, using fallback display */}
                      {data.uncertainty_range && (
                        <div className="mt-4 pt-4 border-t">
                          <p className="text-xs font-semibold text-gray-900 mb-2">Uncertainty Range:</p>
                          <p className="text-xs text-gray-900">
                            {formatDisplayValue(data.uncertainty_range[0], 2)} - {formatDisplayValue(data.uncertainty_range[1], 2)}
                          </p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}


          {/* Sensitivity Analysis */}
          {results.sensitivity_analysis && results.sensitivity_analysis.most_influential_parameters && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.9 }}
              className="mb-12"
            >
              <div className="bg-white rounded-2xl p-8 shadow-lg border border-gray-300">
                <h3 className="text-2xl font-bold text-gray-900 mb-6">
                  🎯 Sensitivity Analysis
                </h3>
                <p className="text-gray-900 mb-6">
                  Most influential parameters affecting your environmental footprint
                </p>

                <div className="space-y-4">
                  {results.sensitivity_analysis.most_influential_parameters.map((param, idx: number) => (
                    <div key={idx} className="border border-gray-200 rounded-xl p-6">
                      <div className="flex items-start justify-between mb-4">
                        <div>
                          <h4 className="text-lg font-semibold text-gray-900">{param.parameter_name}</h4>
                          <p className="text-sm text-gray-900">Influence on total impact: <span className="font-bold text-blue-600 text-lg">{param.influence_percentage.toFixed(1)}%</span></p>
                        </div>
                        <div className="text-right">
                          <div className="text-3xl font-bold text-green-600">{param.improvement_potential}%</div>
                          <div className="text-sm font-medium text-gray-900">Improvement potential</div>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="text-gray-900 font-medium">Current Uncertainty:</span>
                          <div className="font-bold text-gray-900 text-lg mt-1">
                            {param.current_uncertainty ? `±${param.current_uncertainty}%` : 'N/A'}
                          </div>
                        </div>
                        <div>
                          <span className="text-gray-900 font-medium">Impact Influence:</span>
                          <div className="font-bold text-blue-600 text-lg mt-1">
                            {param.influence_percentage ? `${param.influence_percentage.toFixed(1)}%` : 'N/A'}
                          </div>
                        </div>
                      </div>

                      <div className="mt-4">
                        <div className="w-full bg-gray-200 rounded-full h-3">
                          <div
                            className="bg-gradient-to-r from-green-400 to-green-600 h-3 rounded-full transition-all"
                            style={{ width: `${param.influence_percentage}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

              </div>
            </motion.div>
          )}

          {/* Scenario Analysis (from sensitivity analysis) */}
          {results.sensitivity_analysis?.scenario_analysis && results.sensitivity_analysis.scenario_analysis.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.95 }}
              className="mb-12"
            >
              <div className="bg-white rounded-2xl p-8 shadow-lg">
                <h3 className="text-2xl font-bold text-gray-900 mb-6">
                  📈 What-If Scenario Analysis
                </h3>
                <p className="text-gray-900 mb-6">
                  Explore potential improvements by adopting different farming practices and technologies
                </p>

                <div className="grid md:grid-cols-2 gap-6">
                  {results.sensitivity_analysis.scenario_analysis.map((scenario, idx: number) => (
                    <div key={idx} className="border-2 border-gray-200 rounded-xl p-6 hover:border-green-500 transition-all hover:shadow-lg">
                      <div className="flex items-start justify-between mb-4">
                        <div>
                          <h4 className="text-lg font-semibold text-gray-900 mb-1">{scenario.scenario_name}</h4>
                          <p className="text-sm text-gray-900">{scenario.description}</p>
                        </div>
                        <ArrowRight className="w-6 h-6 text-green-600 flex-shrink-0" />
                      </div>

                      <div className="space-y-3">
                        <h5 className="font-semibold text-gray-900 text-sm">Expected Impact Changes:</h5>
                        {Object.entries(scenario.impact_changes).map(([category, change]: [string, number]) => (
                          <div key={category} className="flex items-center justify-between bg-gray-50 rounded-lg p-3">
                            <span className="text-sm text-gray-900">{category}</span>
                            <div className="flex items-center space-x-2">
                              <span className={`text-lg font-bold ${change < 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {change > 0 ? '+' : ''}{change}%
                              </span>
                              {change < 0 ? (
                                <CheckCircle className="w-5 h-5 text-green-600" />
                              ) : (
                                <AlertTriangle className="w-5 h-5 text-red-600" />
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          {/* Comparative Analysis */}
          {results.comparative_analysis && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 1.0 }}
              className="mb-12"
            >
              <div className="bg-white rounded-2xl p-8 shadow-lg border border-gray-300">
                <h3 className="text-2xl font-bold text-gray-900 mb-6">
                  📊 Comparative Analysis
                </h3>

                {/* Benchmark Comparisons */}
                {results.comparative_analysis.benchmark_comparisons && results.comparative_analysis.benchmark_comparisons.length > 0 && (
                  <div className="mb-8">
                    <h4 className="text-lg font-semibold text-gray-900 mb-4">Benchmark Comparisons</h4>
                    <div className="space-y-4">
                      {results.comparative_analysis.benchmark_comparisons.map((benchmark, idx: number) => (
                        <div key={idx} className="border border-gray-200 rounded-xl p-6">
                          <div className="flex items-center justify-between mb-3">
                            <span className="font-semibold text-gray-900">{benchmark.benchmark_name}</span>
                            <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
                              benchmark.performance_category === 'Excellent' ? 'bg-green-100 text-green-800' :
                              benchmark.performance_category === 'Good' ? 'bg-blue-100 text-blue-800' :
                              benchmark.performance_category === 'Average' ? 'bg-yellow-100 text-yellow-800' :
                              'bg-orange-100 text-orange-800'
                            }`}>
                              {benchmark.performance_category}
                            </span>
                          </div>
                          <div className="grid grid-cols-3 gap-4 text-sm">
                            <div>
                              <div className="text-gray-900">Your Performance</div>
                              <div className="font-bold text-gray-900 text-lg">{formatDisplayValue(benchmark.your_performance, 2)}</div>
                            </div>
                            <div>
                              <div className="text-gray-900">Benchmark Value</div>
                              <div className="font-bold text-gray-900 text-lg">{formatDisplayValue(benchmark.benchmark_value, 2)}</div>
                            </div>
                            <div>
                              <div className="text-gray-900">Difference</div>
                              <div className="font-bold text-green-600 text-lg">{formatDisplayValue(benchmark.percentage_difference, 1)}%</div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Regional Comparisons */}
                {results.comparative_analysis.regional_comparisons && results.comparative_analysis.regional_comparisons.length > 0 && (
                  <div className="mb-8">
                    <h4 className="text-lg font-semibold text-gray-900 mb-4">Regional Comparisons</h4>
                    <div className="space-y-4">
                      {results.comparative_analysis.regional_comparisons.map((regional, idx: number) => (
                        <div key={idx} className="border border-gray-200 rounded-xl p-6">
                          <div className="mb-3">
                            <span className="font-semibold text-gray-900">{regional.region_name}</span>
                          </div>
                          <div className="grid grid-cols-2 gap-4 text-sm">
                            {Object.entries(regional.impact_ratios).map(([impact, ratio]: [string, number]) => (
                              <div key={impact} className="mb-2">
                                <div className="text-gray-900 font-medium">{impact}</div>
                                <div className="font-bold text-gray-900 text-lg">{formatDisplayValue(ratio, 2)}x regional average</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Best Practices */}
                {results.comparative_analysis.best_practices && results.comparative_analysis.best_practices.length > 0 && (
                  <div>
                    <h4 className="text-lg font-semibold text-gray-900 mb-4">🌟 Best Practices for Improvement</h4>
                    <div className="grid md:grid-cols-2 gap-4">
                      {results.comparative_analysis.best_practices.map((practice, idx: number) => (
                        <div key={idx} className="border-2 border-green-500 bg-white rounded-xl p-5 shadow-sm">
                          <div className="flex items-start space-x-3">
                            <CheckCircle className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
                            <div>
                              <h5 className="font-semibold text-gray-900 mb-1">{practice.practice_name}</h5>
                              <p className="text-sm text-gray-900 mb-2">{practice.description}</p>
                              <div className="flex items-center space-x-4 text-xs">
                                <span className="text-green-700 font-semibold">
                                  Impact reduction potential available
                                </span>
                                <span className="text-gray-900">
                                  Implementation: {practice.implementation_difficulty}
                                </span>
                                <span className="text-gray-900">
                                  Cost: {practice.cost_category}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {/* AI-Powered Professional Report with Charts */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 1.1 }}
            className="mb-12"
          >
            <ProfessionalReportViewer
              assessmentId={assessmentId || ''}
              companyName={results.company_name}
              assessmentData={results}
            />
          </motion.div>

          {/* Actions */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 1.2 }}
            className="text-center"
          >
            <div className="bg-gradient-to-r from-green-600 to-emerald-600 rounded-2xl p-8 text-white">
              <h3 className="text-2xl font-bold mb-4">Take Action on Your Results</h3>
              <p className="text-green-100 mb-6 max-w-2xl mx-auto">
                Use these insights to improve your farm&apos;s sustainability and productivity
              </p>
              
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <button 
                  onClick={handleRerun}
                  disabled={rerunning || !assessmentId}
                  className="bg-white text-green-600 px-6 py-3 rounded-xl font-semibold hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 transition-all"
                >
                  <RefreshCw className={`w-5 h-5 ${rerunning ? 'animate-spin' : ''}`} />
                  <span>{rerunning ? 'Refreshing...' : 'Refresh Results'}</span>
                </button>

                <button className="border-2 border-white text-white px-6 py-3 rounded-xl font-semibold hover:bg-white hover:text-green-600 flex items-center space-x-2 transition-colors">
                  <Download className="w-5 h-5" />
                  <span>Download Report</span>
                </button>
                
                <button className="border-2 border-white text-white px-6 py-3 rounded-xl font-semibold hover:bg-white hover:text-green-600 flex items-center space-x-2 transition-colors">
                  <Share className="w-5 h-5" />
                  <span>Share Results</span>
                </button>
                
                <a
                  href="/assessment"
                  className="border-2 border-white text-white px-6 py-3 rounded-xl font-semibold hover:bg-white hover:text-green-600 flex items-center space-x-2 transition-colors"
                >
                  <BarChart3 className="w-5 h-5" />
                  <span>New Assessment</span>
                </a>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </Layout>
  );
}

export default function ResultsPage() {
  return (
    <Suspense fallback={
      <Layout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-center">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
              className="w-12 h-12 border-4 border-green-500 border-t-transparent rounded-full mx-auto mb-4"
            />
            <p className="text-lg text-gray-900">Loading...</p>
          </div>
        </div>
      </Layout>
    }>
      <ResultsPageContent />
    </Suspense>
  );
}

function ResultsPageContent() {
  const searchParams = useSearchParams();
  const assessmentId = searchParams.get('id');

  return <ResultsContent assessmentId={assessmentId} />;
}