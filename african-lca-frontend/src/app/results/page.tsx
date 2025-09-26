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
            <p className="text-lg text-gray-600">Loading your assessment results...</p>
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
            <p className="text-gray-600 mb-8">{error}</p>
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
            <BarChart3 className="w-16 h-16 text-gray-400 mx-auto mb-6" />
            <h1 className="text-3xl font-bold text-gray-900 mb-4">
              No Assessment Results Yet
            </h1>
            <p className="text-lg text-gray-600 mb-8">
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

  // Helper function to format display values
  const formatDisplayValue = (value: number, precision: number = 1): string => {
    if (value === 0) return 'N/A';
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

  // Debug log to see the actual data structure
  console.log('Results data:', results);

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
              <div className="flex items-center justify-center space-x-6 text-sm text-gray-600">
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
                  const perUnitValue = calculatePerUnitImpact(totalValue, totalProductionKg);
                  const displayValue = formatDisplayValue(perUnitValue);
                  
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
                    const perUnitValue = calculatePerUnitImpact(totalValue, totalProductionKg);
                    const displayValue = formatDisplayValue(perUnitValue);
                    
                    return (
                      <div key={index} className="text-center p-3 bg-gray-50 rounded-lg border">
                        <div className="text-lg font-bold text-gray-900 mb-1">
                          {displayValue}
                        </div>
                        <div className="text-xs text-gray-600 leading-tight">
                          {category.replace(/([A-Z])/g, ' $1').trim()} (per kg)
                        </div>
                      </div>
                    );
                  })
                }
              </div>
            </div>
          </motion.div>

          {/* Debug Information (remove in production) */}
          {process.env.NODE_ENV === 'development' && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.5 }}
              className="mb-12"
            >
              <div className="bg-gray-100 rounded-2xl p-6 shadow-lg">
                <h3 className="text-xl font-bold text-gray-900 mb-4">Debug Information</h3>
                <div className="space-y-4 text-sm">
                  <div>
                    <strong>Total Production Quantity:</strong> {totalProductionKg.toLocaleString()} kg
                  </div>
                  <div>
                    <strong>Crop Breakdown Keys:</strong> {Object.keys(results.breakdown_by_food).join(', ')}
                  </div>
                  <div>
                    <strong>Single Score Type:</strong> {typeof results.single_score} 
                    {typeof results.single_score === 'object' && results.single_score !== null && 
                      ` (keys: ${Object.keys(results.single_score).join(', ')})`
                    }
                  </div>
                  <div>
                    <strong>Sample Midpoint Value (total):</strong> {JSON.stringify(Object.values(results.midpoint_impacts)[0])}
                  </div>
                  <div>
                    <strong>Sample Per-Unit Value:</strong> {
                      (() => {
                        const sampleValue = extractValue(Object.values(results.midpoint_impacts)[0]);
                        const perUnit = calculatePerUnitImpact(sampleValue, totalProductionKg);
                        return perUnit.toFixed(4);
                      })()
                    } per kg
                  </div>
                </div>
              </div>
            </motion.div>
          )}

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
                    const totalPerKg = calculatePerUnitImpact(totalImpact, cropQuantityKg);
                    
                    return (
                      <div key={index} className="border border-gray-200 rounded-xl p-6">
                        <div className="flex items-center justify-between mb-4">
                          <div>
                            <h4 className="text-lg font-semibold text-gray-900">{cleanCropName}</h4>
                            <p className="text-sm text-gray-500">{cropQuantityKg.toLocaleString()} kg annual production</p>
                          </div>
                          <div className="text-sm text-gray-600 text-right">
                            <div>Total Impact: {formatDisplayValue(totalPerKg)} per kg</div>
                          </div>
                        </div>
                        
                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                          {Object.entries(impacts as Record<string, unknown>).slice(0, 4).map(([category, rawValue]) => {
                            const totalValue = extractValue(rawValue);
                            const perUnitValue = calculatePerUnitImpact(totalValue, cropQuantityKg);
                            const displayValue = formatDisplayValue(perUnitValue);
                            
                            return (
                              <div key={category} className="text-center">
                                <div className="text-lg font-bold text-gray-900">
                                  {displayValue}
                                </div>
                                <div className="text-xs text-gray-600">
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


          {/* Actions */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 1.0 }}
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
            <p className="text-lg text-gray-600">Loading...</p>
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