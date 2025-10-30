'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileText,
  Loader2,
  CheckCircle,
  X,
  Printer,
  TrendingUp,
  AlertCircle,
  BarChart3,
  PieChart as PieChartIcon,
  LineChart as LineChartIcon
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar
} from 'recharts';
import { assessmentAPI, Report } from '@/lib/api';
import { AssessmentResult } from '@/types/assessment';

interface ProfessionalReportViewerProps {
  assessmentId: string;
  companyName: string;
  assessmentData: AssessmentResult;
}

type ReportType = 'comprehensive' | 'executive' | 'farmer_friendly';

// Color palette for professional charts
const COLORS = {
  primary: ['#10B981', '#3B82F6', '#8B5CF6', '#F59E0B', '#EF4444', '#EC4899'],
  gradient: ['#059669', '#0EA5E9', '#7C3AED', '#D97706', '#DC2626'],
  neutral: ['#6B7280', '#9CA3AF', '#D1D5DB'],
  status: {
    excellent: '#10B981',
    good: '#3B82F6',
    average: '#F59E0B',
    poor: '#EF4444'
  }
};

export default function ProfessionalReportViewer({
  assessmentId,
  companyName,
  assessmentData
}: ProfessionalReportViewerProps) {
  const [generating, setGenerating] = useState(false);
  const [generatedReport, setGeneratedReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedReportType, setSelectedReportType] = useState<ReportType>('comprehensive');
  const [showReportModal, setShowReportModal] = useState(false);
  const [currentAssessmentData, setCurrentAssessmentData] = useState<AssessmentResult | undefined>(assessmentData);
  const reportRef = useRef<HTMLDivElement>(null);

  // Update assessment data if it changes and add fallback data fetching
  // Fallback function to fetch assessment data if not provided
  const fetchAssessmentData = useCallback(async () => {
    if (!assessmentId) return;

    try {
      console.log('🔄 Fetching assessment data for ID:', assessmentId);
      const data = await assessmentAPI.getAssessment(assessmentId);
      console.log('✅ Fetched assessment data:', data);
      setCurrentAssessmentData(data);
    } catch (err) {
      console.error('❌ Failed to fetch assessment data:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch assessment data');
    }
  }, [assessmentId]);

  useEffect(() => {
    console.log('📊 ProfessionalReportViewer - Received assessment data:', assessmentData);
    setCurrentAssessmentData(assessmentData);

    // If no assessment data is provided but we have an assessmentId, try to fetch it
    if (!assessmentData && assessmentId) {
      console.log('⚠️ No assessment data provided, attempting to fetch...');
      fetchAssessmentData();
    }
  }, [assessmentData, assessmentId, fetchAssessmentData]);

  const reportTypes = [
    {
      value: 'comprehensive' as ReportType,
      label: 'Comprehensive Report',
      description: 'Full professional report with charts and detailed analysis',
      icon: <BarChart3 className="w-6 h-6" />
    },
    {
      value: 'executive' as ReportType,
      label: 'Executive Summary',
      description: 'Concise summary with key metrics and visualizations',
      icon: <FileText className="w-6 h-6" />
    },
    {
      value: 'farmer_friendly' as ReportType,
      label: 'Farmer-Friendly Report',
      description: 'Simplified report with practical guidance and simple charts',
      icon: <PieChartIcon className="w-6 h-6" />
    }
  ];

  // Normalize impact data for proper chart display
  const normalizeImpactData = (impactData: Record<string, { value: number; unit: string } | number>) => {
    const normalized: Array<{
      name: string;
      originalValue: number;
      normalizedValue: number;
      unit: string;
      significance: string;
    }> = [];

    // Extract all values first to find max for relative scaling
    const tempData: Array<{ key: string; originalValue: number; unit: string }> = [];

    Object.entries(impactData).forEach(([key, value]) => {
      let originalValue = 0;
      let unit = 'units';

      // Safe value extraction
      if (typeof value === 'object' && value !== null) {
        originalValue = typeof value.value === 'number' ? value.value : 0;
        unit = value.unit || 'units';
      } else if (typeof value === 'number') {
        originalValue = value;
      }

      // Skip entries with no valid data
      if (originalValue === 0 && !value) return;

      tempData.push({ key, originalValue, unit });
    });

    // Find max value for relative normalization
    const maxValue = Math.max(...tempData.map(item => Math.abs(item.originalValue)));

    // Normalize all values relative to max (scale 0-100)
    tempData.forEach(({ key, originalValue, unit }) => {
      const normalizedValue = maxValue > 0 ? (Math.abs(originalValue) / maxValue) * 100 : 0;

      normalized.push({
        name: key.replace(/([A-Z])/g, ' $1').replace(/Change/g, '').trim(),
        originalValue,
        normalizedValue,
        unit,
        significance: normalizedValue > 70 ? 'high' : normalizedValue > 30 ? 'medium' : 'low'
      });
    });

    return normalized
      .filter(item => item.originalValue !== 0) // Remove zero values
      .sort((a, b) => b.normalizedValue - a.normalizedValue)
      .slice(0, 8);
  };

  // Prepare chart data from assessment (using the properly fetched data)
  const prepareChartData = () => {
    // Ensure we have valid assessment data
    if (!currentAssessmentData) {
      console.warn('No assessment data available for charts');
      return {
        impactCategories: [],
        cropBreakdown: [],
        dataQualityMetrics: [],
        priorityData: []
      };
    }

    // Debug logging to understand data structure
    console.log('🔍 Debug - Current assessment data structure:', {
      hasData: !!currentAssessmentData,
      keys: Object.keys(currentAssessmentData),
      midpoint_keys: Object.keys(currentAssessmentData?.midpoint_impacts || {}),
      breakdown_keys: Object.keys(currentAssessmentData?.breakdown_by_food || {}),
      breakdown_sample: currentAssessmentData?.breakdown_by_food,
      recommendations_count: (currentAssessmentData?.recommendations || []).length
    });

    const midpoint = currentAssessmentData?.midpoint_impacts || {};
    const breakdown = currentAssessmentData?.breakdown_by_food || {};
    const dataQuality = currentAssessmentData?.data_quality || {};

    // Impact categories for bar chart - properly normalized
    const impactCategories = normalizeImpactData(midpoint);

    // Crop breakdown for pie chart - use actual data only, NO FALLBACKS
    const cropBreakdown = Object.entries(breakdown)
      .map(([food, impacts]) => {
        const climateImpact = impacts?.ClimateChange || impacts?.climate_change || impacts?.['Global warming'] || {};
        let value = 0;

        if (typeof climateImpact === 'object' && climateImpact !== null) {
          value = typeof climateImpact.value === 'number' ? climateImpact.value : 0;
        } else if (typeof climateImpact === 'number') {
          value = climateImpact;
        }

        return {
          name: food,
          value: value
        };
      })
      .filter(crop => crop.value > 0); // Remove crops with zero or invalid values

    // Data quality radar with safe value handling
    const dataQualityMetrics = [
      {
        metric: 'Completeness',
        value: Math.max(0, Math.min(100, (dataQuality.completeness_score || 0) * 100)),
        fullMark: 100
      },
      {
        metric: 'Temporal',
        value: Math.max(0, Math.min(100, (dataQuality.temporal_representativeness || 0) * 100)),
        fullMark: 100
      },
      {
        metric: 'Geographical',
        value: Math.max(0, Math.min(100, (dataQuality.geographical_representativeness || 0) * 100)),
        fullMark: 100
      },
      {
        metric: 'Technological',
        value: Math.max(0, Math.min(100, (dataQuality.technological_representativeness || 0) * 100)),
        fullMark: 100
      }
    ].filter(metric => !isNaN(metric.value)); // Remove any NaN values

    // Use actual recommendations from assessment data only - NO FALLBACKS
    const recommendations = currentAssessmentData?.recommendations || [];

    const recommendationsByPriority = {
      high: recommendations.filter((r) => r.priority?.toLowerCase() === 'high').length,
      medium: recommendations.filter((r) => r.priority?.toLowerCase() === 'medium').length,
      low: recommendations.filter((r) => r.priority?.toLowerCase() === 'low').length
    };

    const priorityData = [
      { priority: 'High', count: recommendationsByPriority.high, fill: COLORS.status.poor },
      { priority: 'Medium', count: recommendationsByPriority.medium, fill: COLORS.status.average },
      { priority: 'Low', count: recommendationsByPriority.low, fill: COLORS.status.good }
    ];

    return {
      impactCategories,
      cropBreakdown,
      dataQualityMetrics,
      priorityData
    };
  };

  const chartData = prepareChartData();

  const handleGenerateReport = async () => {
    // Ensure we have assessment data before generating report
    if (!currentAssessmentData) {
      setError('No assessment data available. Please ensure the assessment has completed successfully.');
      return;
    }

    if (!assessmentId) {
      setError('No assessment ID provided. Cannot generate report.');
      return;
    }

    try {
      setGenerating(true);
      setError(null);

      console.log('🚀 Generating report for assessment:', assessmentId, 'type:', selectedReportType);
      const response = await assessmentAPI.generateReport(assessmentId, selectedReportType);
      console.log('📄 Report generation response:', response);

      // Extract report_data from the response
      const report: Report = ('report_data' in response && (response as { report_data?: Report }).report_data) 
        ? (response as { report_data: Report }).report_data 
        : response;
      console.log('📋 Extracted report:', report);

      // Refresh assessment data to get updated recommendations
      if (assessmentId) {
        try {
          const updatedAssessment = await assessmentAPI.getAssessment(assessmentId);
          setCurrentAssessmentData(updatedAssessment);
          console.log('✅ Refreshed assessment data with recommendations:', updatedAssessment.recommendations?.length);
        } catch (refreshErr) {
          console.warn('⚠️ Could not refresh assessment data:', refreshErr);
        }
      }

      setGeneratedReport(report);
      setShowReportModal(true);
    } catch (err) {
      console.error('❌ Report generation error:', err);
      setError(err instanceof Error ? err.message : 'Failed to generate report');
    } finally {
      setGenerating(false);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  // Render impact categories bar chart with normalized data
  const renderImpactCategoriesChart = () => (
    <div className="mb-8 bg-white rounded-xl p-6 shadow-lg border border-gray-200">
      <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
        <BarChart3 className="w-6 h-6 mr-2 text-blue-600" />
        Environmental Impact Categories (Normalized)
      </h3>
      <div className="mb-4 p-3 bg-blue-50 rounded-lg">
        <p className="text-sm text-blue-700">
          📊 <strong>Note:</strong> Values are normalized using LCA characterization factors for cross-category comparison.
          Bar colors indicate impact significance: High (red), Medium (yellow), Low (green).
        </p>
      </div>
      <ResponsiveContainer width="100%" height={450}>
        <BarChart data={chartData.impactCategories} margin={{ top: 20, right: 30, left: 60, bottom: 100 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis
            dataKey="name"
            angle={-45}
            textAnchor="end"
            height={100}
            tick={{ fill: '#6B7280', fontSize: 11 }}
          />
          <YAxis 
            tick={{ fill: '#6B7280' }} 
            label={{ value: 'Normalized Impact Score', angle: -90, position: 'insideLeft' }}
          />
          <Tooltip
            contentStyle={{ 
              backgroundColor: '#FFF', 
              border: '1px solid #E5E7EB', 
              borderRadius: '8px',
              boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
            }}
            formatter={(value: number, name: string, props: { payload?: { originalValue?: number; unit?: string; significance?: string } }) => {
              const data = props.payload || {};
              return [
                <div key="tooltip" className="space-y-1">
                  <div><strong>Normalized Score:</strong> {value.toFixed(3)}</div>
                  <div><strong>Original Value:</strong> {typeof data.originalValue === 'number' ? data.originalValue.toFixed(6) : 'N/A'}</div>
                  <div><strong>Unit:</strong> {data.unit || 'N/A'}</div>
                  <div><strong>Significance:</strong>
                    <span className={`ml-1 px-2 py-1 rounded text-xs ${
                      data.significance === 'high' ? 'bg-red-100 text-red-800' :
                      data.significance === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-green-100 text-green-800'
                    }`}>
                      {data.significance}
                    </span>
                  </div>
                </div>,
                ''
              ];
            }}
            labelFormatter={(label) => `Impact Category: ${label}`}
          />
          <Bar dataKey="normalizedValue" fill="#3B82F6" radius={[8, 8, 0, 0]}>
            {chartData.impactCategories.map((entry, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={
                  entry.significance === 'high' ? '#EF4444' :
                  entry.significance === 'medium' ? '#F59E0B' :
                  '#10B981'
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      
      {/* Add summary table */}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50">
              <th className="px-3 py-2 text-left">Category</th>
              <th className="px-3 py-2 text-right">Original Value</th>
              <th className="px-3 py-2 text-center">Unit</th>
              <th className="px-3 py-2 text-right">Normalized</th>
              <th className="px-3 py-2 text-center">Significance</th>
            </tr>
          </thead>
          <tbody>
            {chartData.impactCategories.slice(0, 5).map((item, index) => (
              <tr key={index} className="border-b border-gray-200">
                <td className="px-3 py-2 font-medium">{item.name}</td>
                <td className="px-3 py-2 text-right font-mono">
                  {item.originalValue < 0.001 ?
                    item.originalValue.toExponential(3) :
                    item.originalValue.toFixed(6)
                  }
                </td>
                <td className="px-3 py-2 text-center text-gray-600">{item.unit}</td>
                <td className="px-3 py-2 text-right font-mono">{item.normalizedValue.toFixed(3)}</td>
                <td className="px-3 py-2 text-center">
                  <span className={`px-2 py-1 rounded-full text-xs ${
                    item.significance === 'high' ? 'bg-red-100 text-red-800' :
                    item.significance === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-green-100 text-green-800'
                  }`}>
                    {item.significance}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      <p className="text-sm text-gray-600 mt-4 text-center italic">
        Figure 1: Environmental impact categories with normalization for cross-category comparison
      </p>
    </div>
  );

  // Render crop breakdown pie chart with enhanced formatting
  const renderCropBreakdownChart = () => {
    // Safety check for empty or invalid data
    if (!chartData.cropBreakdown || chartData.cropBreakdown.length === 0) {
      return (
        <div className="mb-8 bg-white rounded-xl p-6 shadow-lg border border-gray-200">
          <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
            <PieChartIcon className="w-6 h-6 mr-2 text-green-600" />
            Climate Impact Distribution by Crop
          </h3>
          <div className="p-8 text-center bg-gray-50 rounded-lg">
            <p className="text-gray-600">No climate impact data available for crops in this assessment.</p>
          </div>
        </div>
      );
    }

    const totalImpact = chartData.cropBreakdown.reduce((sum, crop) => sum + (crop.value || 0), 0);
    
    if (totalImpact === 0) {
      return (
        <div className="mb-8 bg-white rounded-xl p-6 shadow-lg border border-gray-200">
          <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
            <PieChartIcon className="w-6 h-6 mr-2 text-green-600" />
            Climate Impact Distribution by Crop
          </h3>
          <div className="p-8 text-center bg-gray-50 rounded-lg">
            <p className="text-gray-600">Climate impact calculations are in progress or unavailable.</p>
          </div>
        </div>
      );
    }
    
    return (
      <div className="mb-8 bg-white rounded-xl p-6 shadow-lg border border-gray-200">
        <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
          <PieChartIcon className="w-6 h-6 mr-2 text-green-600" />
          Climate Impact Distribution by Crop
        </h3>
        
        <div className="mb-4 p-3 bg-green-50 rounded-lg flex items-center justify-between">
          <p className="text-sm text-green-700">
            🌾 <strong>Total Climate Impact:</strong> {totalImpact.toFixed(6)} kg CO₂-eq
          </p>
          <p className="text-xs text-green-600">
            {chartData.cropBreakdown.length} crops analyzed
          </p>
        </div>

        <div className="flex flex-col lg:flex-row items-center">
          <div className="lg:w-1/2">
            <ResponsiveContainer width="100%" height={350}>
              <PieChart>
                <Pie
                  data={chartData.cropBreakdown}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={false}
                  outerRadius={120}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {chartData.cropBreakdown.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS.primary[index % COLORS.primary.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ 
                    backgroundColor: '#FFF', 
                    border: '1px solid #E5E7EB', 
                    borderRadius: '8px',
                    boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
                  }}
                  formatter={(value: number, name: string) => {
                    const safeValue = typeof value === 'number' ? value : 0;
                    const safeTotalImpact = totalImpact || 1;
                    const percentage = ((safeValue / safeTotalImpact) * 100).toFixed(3);
                    return [
                      <div key="tooltip" className="space-y-1">
                        <div><strong>Impact:</strong> {safeValue.toFixed(6)} kg CO₂-eq</div>
                        <div><strong>Percentage:</strong> {percentage}%</div>
                      </div>,
                      `${name || 'Unknown'}`
                    ];
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          
          {/* Legend and breakdown table */}
          <div className="lg:w-1/2 lg:pl-6 mt-4 lg:mt-0">
            <h4 className="text-lg font-semibold text-gray-800 mb-3">Impact Breakdown</h4>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {chartData.cropBreakdown
                .filter(crop => crop.value && typeof crop.value === 'number' && crop.value > 0) // Additional safety filter
                .sort((a, b) => (b.value || 0) - (a.value || 0))
                .map((crop, index) => {
                  const cropValue = crop.value || 0;
                  const percentage = totalImpact > 0 ? ((cropValue / totalImpact) * 100) : 0;
                  const significance = percentage > 40 ? 'high' : percentage > 15 ? 'medium' : 'low';
                  
                  return (
                    <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center space-x-3">
                        <div 
                          className="w-4 h-4 rounded-full" 
                          style={{ backgroundColor: COLORS.primary[index % COLORS.primary.length] }}
                        />
                        <span className="font-medium text-gray-800">{crop.name || 'Unknown Crop'}</span>
                      </div>
                      <div className="text-right">
                        <div className="font-semibold text-gray-900">
                          {cropValue.toFixed(6)} kg CO₂-eq
                        </div>
                        <div className="flex items-center space-x-2">
                          <span className="text-sm text-gray-600">{percentage.toFixed(3)}%</span>
                          <span className={`px-2 py-1 rounded-full text-xs ${
                            significance === 'high' ? 'bg-red-100 text-red-800' :
                            significance === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                            'bg-green-100 text-green-800'
                          }`}>
                            {significance}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        </div>
        
        <p className="text-sm text-gray-600 mt-4 text-center italic">
          Figure 2: Climate change impact distribution across crop portfolio with contribution analysis
        </p>
      </div>
    );
  };

  // Render data quality radar chart with enhanced information
  const renderDataQualityChart = () => {
    // Safety check for empty metrics
    if (!chartData.dataQualityMetrics || chartData.dataQualityMetrics.length === 0) {
      return (
        <div className="mb-8 bg-white rounded-xl p-6 shadow-lg border border-gray-200">
          <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
            <LineChartIcon className="w-6 h-6 mr-2 text-purple-600" />
            Data Quality Assessment
          </h3>
          <div className="p-8 text-center bg-gray-50 rounded-lg">
            <p className="text-gray-600">Data quality metrics are being calculated...</p>
          </div>
        </div>
      );
    }

    const avgQuality = chartData.dataQualityMetrics.reduce((sum, item) => sum + (item.value || 0), 0) / Math.max(chartData.dataQualityMetrics.length, 1);
    const qualityLevel = avgQuality > 80 ? 'excellent' : avgQuality > 60 ? 'good' : avgQuality > 40 ? 'fair' : 'poor';
    
    return (
      <div className="mb-8 bg-white rounded-xl p-6 shadow-lg border border-gray-200">
        <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
          <LineChartIcon className="w-6 h-6 mr-2 text-purple-600" />
          Data Quality Assessment
        </h3>
        
        <div className="mb-4 p-3 bg-purple-50 rounded-lg flex items-center justify-between">
          <div>
            <p className="text-sm text-purple-700">
              📊 <strong>Overall Quality Score:</strong> {avgQuality.toFixed(3)}%
            </p>
            <p className="text-xs text-purple-600 mt-1">
              Assessment reliability: 
              <span className={`ml-1 px-2 py-1 rounded text-xs ${
                qualityLevel === 'excellent' ? 'bg-green-100 text-green-800' :
                qualityLevel === 'good' ? 'bg-blue-100 text-blue-800' :
                qualityLevel === 'fair' ? 'bg-yellow-100 text-yellow-800' :
                'bg-red-100 text-red-800'
              }`}>
                {qualityLevel}
              </span>
            </p>
          </div>
        </div>

        <div className="flex flex-col lg:flex-row items-center">
          <div className="lg:w-1/2">
            <ResponsiveContainer width="100%" height={350}>
              <RadarChart data={chartData.dataQualityMetrics}>
                <PolarGrid stroke="#E5E7EB" gridType="polygon" />
                <PolarAngleAxis dataKey="metric" tick={{ fill: '#6B7280', fontSize: 12 }} />
                <PolarRadiusAxis 
                  angle={90} 
                  domain={[0, 100]} 
                  tick={{ fill: '#6B7280', fontSize: 10 }}
                  tickCount={6}
                />
                <Radar
                  name="Quality Score"
                  dataKey="value"
                  stroke="#8B5CF6"
                  fill="#8B5CF6"
                  fillOpacity={0.3}
                  strokeWidth={2}
                />
                <Tooltip
                  contentStyle={{ 
                    backgroundColor: '#FFF', 
                    border: '1px solid #E5E7EB', 
                    borderRadius: '8px',
                    boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
                  }}
                  formatter={(value: number, name: string) => {
                    const level = value > 80 ? 'Excellent' : value > 60 ? 'Good' : value > 40 ? 'Fair' : 'Poor';
                    return [
                      <div key="tooltip" className="space-y-1">
                        <div><strong>Score:</strong> {value.toFixed(3)}%</div>
                        <div><strong>Level:</strong> {level}</div>
                      </div>,
                      name
                    ];
                  }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
          
          {/* Quality metrics breakdown */}
          <div className="lg:w-1/2 lg:pl-6 mt-4 lg:mt-0">
            <h4 className="text-lg font-semibold text-gray-800 mb-3">Quality Dimensions</h4>
            <div className="space-y-3">
              {chartData.dataQualityMetrics.map((metric, index) => {
                const level = metric.value > 80 ? 'excellent' : metric.value > 60 ? 'good' : metric.value > 40 ? 'fair' : 'poor';
                const recommendations = {
                  'Completeness': metric.value < 70 ? 'Consider collecting additional data points' : 'Data completeness is adequate',
                  'Temporal': metric.value < 70 ? 'Update with more recent data when available' : 'Temporal coverage is suitable',
                  'Geographical': metric.value < 70 ? 'Include more region-specific data sources' : 'Geographical representation is good',
                  'Technological': metric.value < 70 ? 'Verify technology assumptions with local practices' : 'Technology representation is appropriate'
                };
                
                return (
                  <div key={index} className="p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-gray-800">{metric.metric}</span>
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-gray-900">{metric.value.toFixed(3)}%</span>
                        <span className={`px-2 py-1 rounded-full text-xs ${
                          level === 'excellent' ? 'bg-green-100 text-green-800' :
                          level === 'good' ? 'bg-blue-100 text-blue-800' :
                          level === 'fair' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {level}
                        </span>
                      </div>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                      <div
                        className={`h-2 rounded-full ${
                          level === 'excellent' ? 'bg-green-500' :
                          level === 'good' ? 'bg-blue-500' :
                          level === 'fair' ? 'bg-yellow-500' :
                          'bg-red-500'
                        }`}
                        style={{ width: `${metric.value}%` }}
                      />
                    </div>
                    <p className="text-xs text-gray-600">
                      {recommendations[metric.metric as keyof typeof recommendations]}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
        
        <p className="text-sm text-gray-600 mt-4 text-center italic">
          Figure 3: Data quality assessment across key representativeness dimensions with improvement recommendations
        </p>
      </div>
    );
  };

  // Render recommendations priority chart
  const renderRecommendationsPriorityChart = () => {
    const totalRecs = chartData.priorityData.reduce((sum, item) => sum + item.count, 0);

    return (
      <div className="mb-8 bg-white rounded-xl p-6 shadow-lg border border-gray-200">
        <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
          <AlertCircle className="w-6 h-6 mr-2 text-orange-600" />
          Recommendations by Priority ({totalRecs} total)
        </h3>

        {totalRecs > 0 ? (
          <>
            <div className="space-y-4 mb-4">
              {chartData.priorityData.map((item, index) => (
                <div key={index} className="flex items-center">
                  <div className="w-24 font-medium text-gray-700">{item.priority}</div>
                  <div className="flex-1">
                    <div className="flex items-center">
                      <div
                        className="h-10 rounded-lg flex items-center justify-end pr-3 text-white font-semibold"
                        style={{
                          width: `${totalRecs > 0 ? (item.count / totalRecs) * 100 : 0}%`,
                          backgroundColor: item.fill,
                          minWidth: item.count > 0 ? '80px' : '0px'
                        }}
                      >
                        {item.count > 0 ? `${item.count} action${item.count !== 1 ? 's' : ''}` : ''}
                      </div>
                      {item.count > 0 && (
                        <span className="ml-3 text-sm text-gray-600">
                          ({((item.count / totalRecs) * 100).toFixed(1)}%)
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-sm text-gray-600 mt-4 text-center italic">
              Figure 4: Distribution of action recommendations by implementation priority
            </p>
          </>
        ) : (
          <div className="text-center py-8 text-gray-500">
            <AlertCircle className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p>No recommendations available</p>
          </div>
        )}
      </div>
    );
  };

  // Render report header
  const renderReportHeader = () => (
    <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white p-8 rounded-t-2xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold mb-2">
            Environmental Sustainability Assessment Report
          </h1>
          <p className="text-blue-100 text-lg mb-4">
            Life Cycle Assessment (LCA) - ISO 14044/14067 Compliant
          </p>
          <div className="grid grid-cols-2 gap-4 mt-6">
            <div>
              <p className="text-sm text-blue-200">Organization</p>
              <p className="font-semibold text-lg">{companyName}</p>
            </div>
            <div>
              <p className="text-sm text-blue-200">Assessment Date</p>
              <p className="font-semibold text-lg">
                {new Date(currentAssessmentData?.assessment_date || Date.now()).toLocaleDateString()}
              </p>
            </div>
            <div>
              <p className="text-sm text-blue-200">Country/Region</p>
              <p className="font-semibold text-lg">{currentAssessmentData?.country || 'N/A'}</p>
            </div>
            <div>
              <p className="text-sm text-blue-200">Report ID</p>
              <p className="font-semibold text-lg">{generatedReport?.report_id || 'N/A'}</p>
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="bg-white/20 backdrop-blur-sm rounded-lg p-4">
            <p className="text-sm text-blue-100">Overall Score</p>
            <p className="text-4xl font-bold">
              {currentAssessmentData?.single_score?.value?.toFixed(3) || 'N/A'}
            </p>
            <p className="text-sm text-blue-100 mt-1">
              {currentAssessmentData?.single_score?.unit || 'pt'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );

  // Render report content with sections
  // Helper function to format farmer-friendly report text (simpler, more robust)
  const formatFarmerFriendlyText = (text: string): string => {
    if (!text) {
      console.warn('⚠️ formatFarmerFriendlyText received empty text');
      return '';
    }

    console.log('📝 Formatting farmer-friendly text, length:', text.length);

    let formatted = text;

    // Remove the first markdown header if present (handles both single-line and compound headers)
    // This removes headers like "# TITLE" or "# TITLE ## Subtitle"
    formatted = formatted.replace(/^#+ .*?\n\n/, '');

    // Also handle case where the first line might be a compound header on one line
    // e.g., "# MENSAH FAMILY FARMS - ENVIRONMENTAL REPORT ## Simple Guide..."
    if (formatted.startsWith('#')) {
      const firstNewline = formatted.indexOf('\n');
      if (firstNewline > 0) {
        formatted = formatted.substring(firstNewline + 1);
      }
    }

    // Split into paragraphs
    const paragraphs = formatted.split(/\n\n+/);
    console.log('📝 Split into', paragraphs.length, 'paragraphs');

    formatted = paragraphs.map((para, idx) => {
      const trimmed = para.trim();
      if (!trimmed) return '';

      // Check for headers FIRST (before bold/italic replacement)
      if (trimmed.startsWith('#### ')) {
        let headerText = trimmed.substring(5);
        // Apply bold/italic to header text
        headerText = headerText.replace(/\*\*([^*]+?)\*\*/g, '<strong class="font-semibold text-gray-900">$1</strong>');
        headerText = headerText.replace(/\*([^*]+?)\*/g, '<em class="italic">$1</em>');
        return `<h4 class="text-base font-semibold text-gray-800 mt-5 mb-2">${headerText}</h4>`;
      }
      if (trimmed.startsWith('### ')) {
        let headerText = trimmed.substring(4);
        headerText = headerText.replace(/\*\*([^*]+?)\*\*/g, '<strong class="font-semibold text-gray-900">$1</strong>');
        headerText = headerText.replace(/\*([^*]+?)\*/g, '<em class="italic">$1</em>');
        return `<h3 class="text-lg font-semibold text-gray-900 mt-6 mb-3">${headerText}</h3>`;
      }
      if (trimmed.startsWith('## ')) {
        let headerText = trimmed.substring(3);
        headerText = headerText.replace(/\*\*([^*]+?)\*\*/g, '<strong class="font-semibold text-gray-900">$1</strong>');
        headerText = headerText.replace(/\*([^*]+?)\*/g, '<em class="italic">$1</em>');
        return `<h2 class="text-xl font-bold text-gray-900 mt-8 mb-4">${headerText}</h2>`;
      }
      if (trimmed.startsWith('# ')) {
        let headerText = trimmed.substring(2);
        headerText = headerText.replace(/\*\*([^*]+?)\*\*/g, '<strong class="font-semibold text-gray-900">$1</strong>');
        headerText = headerText.replace(/\*([^*]+?)\*/g, '<em class="italic">$1</em>');
        return `<h1 class="text-2xl font-bold text-gray-900 mt-10 mb-5">${headerText}</h1>`;
      }

      // Now apply bold/italic replacement for non-header content
      let processed = trimmed;

      // Replace bold text - use global flag and check repeatedly
      let prevProcessed = '';
      while (prevProcessed !== processed) {
        prevProcessed = processed;
        processed = processed.replace(/\*\*([^*]+?)\*\*/g, '<strong class="font-semibold text-gray-900">$1</strong>');
      }

      // Replace italic text
      processed = processed.replace(/\*([^*]+?)\*/g, '<em class="italic">$1</em>');

      // Horizontal rule
      if (trimmed === '---' || trimmed === '***') {
        return '<hr class="my-6 border-t-2 border-gray-200" />';
      }

      // Check for markdown tables (must be checked before lists since tables use |)
      if (processed.includes('|') && processed.split('\n').filter(line => line.includes('|')).length >= 2) {
        const lines = processed.split('\n').filter(line => line.trim());
        if (lines.length >= 2 && lines[1].includes('---')) {
          // This is a markdown table
          const headers = lines[0].split('|').filter(h => h.trim()).map(h => h.trim());
          const rows = lines.slice(2).map(line =>
            line.split('|').filter(cell => cell.trim()).map(cell => cell.trim())
          );

          let tableHTML = '<table class="min-w-full divide-y divide-gray-200 my-4 border border-gray-300"><thead class="bg-gray-50"><tr>';
          headers.forEach(header => {
            tableHTML += `<th class="px-4 py-3 text-left text-xs font-bold text-black uppercase tracking-wider border-r border-gray-300">${header}</th>`;
          });
          tableHTML += '</tr></thead><tbody class="bg-white divide-y divide-gray-200">';
          rows.forEach(row => {
            tableHTML += '<tr>';
            row.forEach(cell => {
              tableHTML += `<td class="px-4 py-3 text-sm font-medium text-black border-r border-gray-200">${cell}</td>`;
            });
            tableHTML += '</tr>';
          });
          tableHTML += '</tbody></table>';
          return tableHTML;
        }
      }

      // Lists (bullet points)
      if (processed.includes('\n- ') || processed.startsWith('- ')) {
        const items = processed.split('\n')
          .filter(line => line.trim())
          .map(line => {
            if (line.trim().startsWith('- ')) {
              const itemText = line.trim().substring(2);
              return `<li class="mb-2">${itemText}</li>`;
            }
            return line;
          })
          .join('');
        return `<ul class="list-disc pl-6 mb-4 space-y-1">${items}</ul>`;
      }

      // Regular paragraph - replace newlines with <br/>
      processed = processed.replace(/\n/g, '<br/>');
      return `<p class="mb-4 leading-relaxed">${processed}</p>`;
    }).join('');

    console.log('📝 Final formatted HTML length:', formatted.length);
    console.log('📝 Final HTML still contains **:', formatted.includes('**') ? 'YES ❌' : 'NO ✅');
    if (formatted.includes('**')) {
      const idx = formatted.indexOf('**');
      console.log('📝 First ** found at position', idx, 'context:', formatted.substring(Math.max(0, idx - 20), idx + 50));
    }

    return formatted;
  };

  // Helper function to format comprehensive/executive report text (more complex)
  const formatMarkdownText = (text: string): string => {
    if (!text) {
      console.warn('⚠️ formatMarkdownText received empty text');
      return '';
    }

    console.log('📝 Formatting markdown text, length:', text.length);
    console.log('📝 First 200 chars:', text.substring(0, 200));
    console.log('📝 Checking for ** patterns:', text.match(/\*\*/g)?.length || 0, 'double asterisk pairs found');

    let formatted = text;

    // Remove the first markdown header if it's at the very start (it's redundant with our section title)
    // Only remove if followed by double newline
    formatted = formatted.replace(/^#+ .*?\n\n/, '');

    console.log('📝 After header removal, length:', formatted.length);
    console.log('📝 After header, first 200 chars:', formatted.substring(0, 200));

    // Split by double newlines to identify paragraphs
    const paragraphs = formatted.split(/\n\n+/);
    console.log('📝 Split into', paragraphs.length, 'paragraphs');

    formatted = paragraphs.map((para, idx) => {
      if (para.includes('**')) {
        console.log(`📝 Paragraph ${idx} contains **, length:`, para.length, 'preview:', para.substring(0, 80));
      }
      // Clean up markdown formatting in header text
      const cleanHeaderText = (headerText: string) => {
        return headerText
          .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Keep bold as strong tags
          .replace(/\*(.*?)\*/g, '<em>$1</em>')     // Keep italic as em tags
          .trim();
      };

      // Check if this is a markdown table
      if (para.includes('|') && para.split('\n').filter(line => line.includes('|')).length >= 2) {
        const lines = para.split('\n').filter(line => line.trim());
        if (lines.length >= 2 && lines[1].includes('---')) {
          // This is a markdown table
          const headers = lines[0].split('|').filter(h => h.trim()).map(h => h.trim());
          const rows = lines.slice(2).map(line =>
            line.split('|').filter(cell => cell.trim()).map(cell => cell.trim())
          );

          let tableHTML = '<table class="min-w-full divide-y divide-gray-200 my-4 border border-gray-300"><thead class="bg-gray-50"><tr>';
          headers.forEach(header => {
            tableHTML += `<th class="px-4 py-3 text-left text-xs font-bold text-black uppercase tracking-wider border-r border-gray-300">${header}</th>`;
          });
          tableHTML += '</tr></thead><tbody class="bg-white divide-y divide-gray-200">';
          rows.forEach(row => {
            tableHTML += '<tr>';
            row.forEach(cell => {
              const formattedCell = cell
                .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold">$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>');
              tableHTML += `<td class="px-4 py-3 text-sm font-medium text-black border-r border-gray-200">${formattedCell}</td>`;
            });
            tableHTML += '</tr>';
          });
          tableHTML += '</tbody></table>';
          return tableHTML;
        }
      }

      // Headers with markdown cleanup (check h4 first, then h3, h2, h1)
      if (para.startsWith('#### ')) {
        return `<h4 class="text-base font-semibold text-gray-800 mt-5 mb-2">${cleanHeaderText(para.substring(5))}</h4>`;
      }
      if (para.startsWith('### ')) {
        return `<h3 class="text-lg font-semibold text-gray-900 mt-6 mb-3">${cleanHeaderText(para.substring(4))}</h3>`;
      }
      if (para.startsWith('## ')) {
        return `<h2 class="text-xl font-bold text-gray-900 mt-8 mb-4">${cleanHeaderText(para.substring(3))}</h2>`;
      }
      if (para.startsWith('# ')) {
        return `<h1 class="text-2xl font-bold text-gray-900 mt-10 mb-5">${cleanHeaderText(para.substring(2))}</h1>`;
      }

      // Horizontal rule
      if (para.trim() === '---' || para.trim() === '***') {
        return '<hr class="my-6 border-t-2 border-gray-200" />';
      }

      // Lists (bullet points)
      if (para.includes('\n* ') || para.includes('\n- ') || para.startsWith('* ') || para.startsWith('- ')) {
        const items = para.split('\n')
          .filter(line => line.trim())
          .map(line => {
            if (line.trim().startsWith('* ') || line.trim().startsWith('- ')) {
              const itemText = line.trim().substring(2);
              // Apply inline formatting to list items
              const formattedText = itemText
                .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-gray-900">$1</strong>')
                .replace(/\*(.*?)\*/g, '<em class="italic">$1</em>');
              return `<li class="mb-2">${formattedText}</li>`;
            }
            return line;
          })
          .join('');
        return `<ul class="list-disc pl-6 mb-4 space-y-1">${items}</ul>`;
      }

      // Handle paragraphs that might have line breaks with bold text (like subsection headers)
      const lines = para.split('\n').filter(line => line.trim());

      // Check if paragraph contains numbered items with bold text (like **1. Item**)
      const trimmedPara = para.trim();

      // Single line that's entirely bold (like **Financial Benefits:** or **4. Title**)
      // Match pattern: starts with **, ends with **, optional whitespace at end
      if (trimmedPara.match(/^\*\*[^*].*?\*\*\s*$/)) {
        const text = trimmedPara.replace(/^\*\*|\*\*$/g, '').trim();
        return `<p class="font-bold text-gray-900 mt-5 mb-3 text-base">${text}</p>`;
      }

      // Multi-line paragraph with some lines having bold formatting
      if (lines.length > 1) {
        return lines.map(line => {
          const trimmedLine = line.trim();

          // Check if line is entirely bold (and nothing else)
          if (trimmedLine.match(/^\*\*[^*].*?\*\*\s*$/)) {
            const text = trimmedLine.replace(/^\*\*|\*\*$/g, '').trim();
            return `<p class="font-bold text-gray-900 mt-5 mb-3 text-base">${text}</p>`;
          }

          // Apply inline bold/italic formatting to any **text** or *text* in the line
          const formatted = trimmedLine
            .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-gray-900">$1</strong>')
            .replace(/\*(.+?)\*/g, '<em class="italic">$1</em>');

          return `<p class="mb-2 leading-relaxed">${formatted}</p>`;
        }).join('');
      }

      // Regular single-line paragraph with inline formatting (including **text**)
      // Use .+? instead of .*? to ensure we match at least one character
      const content = para
        .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-gray-900">$1</strong>')
        .replace(/\*(.+?)\*/g, '<em class="italic">$1</em>')
        .replace(/\n/g, '<br/>');

      return `<p class="mb-4 leading-relaxed">${content}</p>`;
    }).join('');

    console.log('📝 Final formatted HTML length:', formatted.length);
    console.log('📝 Final HTML still contains **:', formatted.includes('**') ? 'YES ❌' : 'NO ✅');
    if (formatted.includes('**')) {
      // Find and log the first occurrence
      const idx = formatted.indexOf('**');
      console.log('📝 First ** found at position', idx, 'context:', formatted.substring(Math.max(0, idx - 20), idx + 50));
    }

    return formatted;
  };

  const renderReportContent = () => {
    if (!generatedReport?.sections) {
      console.log('❌ No sections in generated report');
      return null;
    }

    const sections = generatedReport.sections;
    console.log('✅ Rendering report sections:', Object.keys(sections));

    return (
      <div className="space-y-8">
        {/* Executive Summary */}
        {sections.executive_summary && (
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-6 border-l-4 border-blue-600">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Executive Summary</h2>
            <div className="prose prose-lg max-w-none text-gray-700">
              <div dangerouslySetInnerHTML={{ __html: formatMarkdownText(sections.executive_summary) }} />
            </div>
          </div>
        )}

        {/* Key Metrics Dashboard */}
        <div className="grid md:grid-cols-3 gap-6">
          <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Climate Change</p>
                <p className="text-2xl font-bold text-gray-900">
                  {currentAssessmentData?.midpoint_impacts?.ClimateChange?.value?.toFixed(3) ||
                   currentAssessmentData?.midpoint_impacts?.['Global warming']?.value?.toFixed(3) || 'N/A'}
                </p>
                <p className="text-xs text-gray-500">
                  {currentAssessmentData?.midpoint_impacts?.ClimateChange?.unit ||
                   currentAssessmentData?.midpoint_impacts?.['Global warming']?.unit || 'kg CO₂-eq per kg'}
                </p>
              </div>
              <TrendingUp className="w-12 h-12 text-green-600 opacity-20" />
            </div>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Data Quality</p>
                <p className="text-2xl font-bold text-gray-900">
                  {(() => {
                    const dq = currentAssessmentData?.data_quality;
                    if (!dq) return 'N/A';
                    // Calculate average quality score from all dimensions
                    const completeness = (dq.completeness_score || 0) * 100;
                    const temporal = (dq.temporal_representativeness || 0) * 100;
                    const geographical = (dq.geographical_representativeness || 0) * 100;
                    const technological = (dq.technological_representativeness || 0) * 100;
                    const avgQuality = (completeness + temporal + geographical + technological) / 4;
                    return `${avgQuality.toFixed(3)}%`;
                  })()}
                </p>
                <p className="text-xs text-gray-500">
                  {currentAssessmentData?.data_quality?.overall_confidence || 'N/A'} Confidence
                </p>
              </div>
              <CheckCircle className="w-12 h-12 text-blue-600 opacity-20" />
            </div>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Recommendations</p>
                <p className="text-2xl font-bold text-gray-900">
                  {currentAssessmentData?.recommendations?.length || 0}
                </p>
                <p className="text-xs text-gray-500">Action Items</p>
              </div>
              <AlertCircle className="w-12 h-12 text-orange-600 opacity-20" />
            </div>
          </div>
        </div>

        {/* Charts Section */}
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Visual Analysis</h2>
          {renderImpactCategoriesChart()}
          {renderCropBreakdownChart()}
          {renderDataQualityChart()}
          {renderRecommendationsPriorityChart()}
        </div>

        {/* Other sections - ISO 14044 compliant order */}
        {(() => {
          const sectionOrder = [
            'introduction',
            'methodology',
            'impact_analysis',
            'comparative_analysis',
            'sensitivity_analysis',
            'recommendations',
            'conclusions',
            'data_quality_limitations',
            'critical_review',
            'technical_appendix'
          ];

          const sectionTitles: Record<string, string> = {
            introduction: 'Introduction',
            methodology: 'Assessment Methodology',
            impact_analysis: 'Environmental Impact Analysis',
            comparative_analysis: 'Comparative Performance Analysis',
            sensitivity_analysis: 'Sensitivity and Uncertainty Analysis',
            recommendations: 'Recommendations and Action Plan',
            conclusions: 'Conclusions',
            data_quality_limitations: 'Data Quality and Limitations',
            critical_review: 'Critical Review and Validation (ISO 14044)',
            technical_appendix: 'Technical Appendix',
            farmer_report: 'Your Farm Sustainability Report',
            full_report: 'Report'
          };

          // Render sections in ISO order
          const orderedSections = sectionOrder
            .filter(key => sections[key])
            .map((key) => {
              const isCriticalSection = key === 'critical_review' || key === 'data_quality_limitations';

              return (
                <div
                  key={key}
                  className={`bg-white rounded-xl p-6 shadow-lg border ${
                    isCriticalSection ? 'border-purple-300 border-2' : 'border-gray-200'
                  }`}
                >
                  {isCriticalSection && (
                    <div className="mb-4 flex items-center text-sm text-purple-700 bg-purple-50 px-4 py-2 rounded-lg">
                      <CheckCircle className="w-4 h-4 mr-2" />
                      <span className="font-semibold">ISO 14044 Compliance Section</span>
                    </div>
                  )}
                  <h2 className="text-2xl font-bold text-gray-900 mb-4">
                    {sectionTitles[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </h2>
                  <div className="prose prose-lg max-w-none text-gray-700">
                    <div dangerouslySetInnerHTML={{ __html: formatMarkdownText(String(sections[key])) }} />
                  </div>
                </div>
              );
            });

          // Render additional sections not in the predefined order (like farmer_report)
          const additionalSections = Object.entries(sections)
            .filter(([key]) => !sectionOrder.includes(key))
            .map(([key, content]) => {
              // Use farmer-friendly formatter for farmer_report, standard for others
              const formatter = key === 'farmer_report' ? formatFarmerFriendlyText : formatMarkdownText;

              return (
                <div
                  key={key}
                  className="bg-white rounded-xl p-6 shadow-lg border border-gray-200"
                >
                  <h2 className="text-2xl font-bold text-gray-900 mb-4">
                    {sectionTitles[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </h2>
                  <div className="prose prose-lg max-w-none text-gray-700">
                    <div dangerouslySetInnerHTML={{ __html: formatter(String(content)) }} />
                  </div>
                </div>
              );
            });

          return [...orderedSections, ...additionalSections];
        })()}

      </div>
    );
  };

  return (
    <div className="bg-gradient-to-br from-purple-50 to-blue-50 rounded-2xl p-8 border-2 border-purple-200">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <FileText className="w-8 h-8 text-purple-600" />
          <div>
            <h3 className="text-2xl font-bold text-gray-900">Professional Report with Charts</h3>
            <p className="text-sm text-gray-600">ISO 14044 compliant with interactive visualizations & chain-of-thought analysis</p>
            {!currentAssessmentData && assessmentId && (
              <p className="text-xs text-orange-600 mt-1">⚠️ Loading assessment data...</p>
            )}
            {!currentAssessmentData && !assessmentId && (
              <p className="text-xs text-red-600 mt-1">❌ No assessment data available</p>
            )}
            {currentAssessmentData && (
              <p className="text-xs text-green-600 mt-1">✅ Assessment data loaded successfully</p>
            )}
          </div>
        </div>
      </div>

      {/* Enhanced Metadata Display */}
      {generatedReport?.metadata && (
        <div className="mb-4 p-4 bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200 rounded-xl">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div className="flex items-center">
              <CheckCircle className="w-4 h-4 mr-2 text-green-600" />
              <div>
                <div className="text-xs text-gray-600">Model</div>
                <div className="font-semibold text-gray-900">{generatedReport.metadata.model_used?.split('-').pop()}</div>
              </div>
            </div>
            <div className="flex items-center">
              <CheckCircle className="w-4 h-4 mr-2 text-purple-600" />
              <div>
                <div className="text-xs text-gray-600">ISO 14044</div>
                <div className="font-semibold text-gray-900">
                  {generatedReport.metadata.iso_14044_compliant ? 'Compliant' : 'N/A'}
                </div>
              </div>
            </div>
            <div className="flex items-center">
              <CheckCircle className="w-4 h-4 mr-2 text-blue-600" />
              <div>
                <div className="text-xs text-gray-600">Data Quality</div>
                <div className="font-semibold text-gray-900 capitalize">
                  {generatedReport.metadata.data_quality_level}
                </div>
              </div>
            </div>
            <div className="flex items-center">
              <CheckCircle className="w-4 h-4 mr-2 text-indigo-600" />
              <div>
                <div className="text-xs text-gray-600">Sections</div>
                <div className="font-semibold text-gray-900">
                  {generatedReport.metadata.sections_generated}
                </div>
              </div>
            </div>
          </div>
          {generatedReport.metadata.chain_of_thought_enabled && (
            <div className="mt-3 pt-3 border-t border-blue-200">
              <div className="flex items-center text-xs text-blue-700">
                <CheckCircle className="w-3 h-3 mr-2" />
                <span className="font-semibold">Enhanced with Chain-of-Thought Reasoning</span>
                <span className="ml-2 text-blue-600">• Temperature: {generatedReport.metadata.temperature}</span>
              </div>
            </div>
          )}
          {generatedReport.metadata?.validation_warnings && generatedReport.metadata.validation_warnings.length > 0 && (
            <div className="mt-3 pt-3 border-t border-yellow-200 bg-yellow-50 rounded px-3 py-2">
              <div className="text-xs text-yellow-800">
                <AlertCircle className="w-3 h-3 inline mr-1" />
                <strong>Validation Warnings:</strong>
                <ul className="list-disc list-inside mt-1">
                  {generatedReport.metadata.validation_warnings.map((warning: string, i: number) => (
                    <li key={i}>{warning}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Report Type Selection */}
      <div className="grid md:grid-cols-3 gap-4 mb-6">
        {reportTypes.map((type) => (
          <button
            key={type.value}
            onClick={() => setSelectedReportType(type.value)}
            className={`p-4 rounded-xl border-2 transition-all text-left ${
              selectedReportType === type.value
                ? 'border-purple-600 bg-purple-50 shadow-lg'
                : 'border-gray-300 bg-white hover:border-purple-400'
            }`}
          >
            <div className="flex items-center space-x-3 mb-2">
              <div className={`${selectedReportType === type.value ? 'text-purple-600' : 'text-gray-600'}`}>
                {type.icon}
              </div>
              <div className="font-semibold text-gray-900">{type.label}</div>
            </div>
            <div className="text-xs text-gray-600">{type.description}</div>
          </button>
        ))}
      </div>

      {/* Error Display */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start space-x-3"
        >
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-red-900">Report Generation Error</div>
            <div className="text-sm text-red-700">{error}</div>
          </div>
        </motion.div>
      )}

      {/* Generated Report Info */}
      {generatedReport && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg flex items-start space-x-3"
        >
          <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="font-semibold text-green-900">Professional Report Generated</div>
            <div className="text-sm text-green-700">
              ID: {generatedReport.report_id} | Type: {generatedReport.report_type}
            </div>
          </div>
          <button
            onClick={() => setShowReportModal(true)}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center space-x-2"
          >
            <FileText className="w-4 h-4" />
            <span>View Report</span>
          </button>
        </motion.div>
      )}

      {/* Generate Button */}
      <button
        onClick={handleGenerateReport}
        disabled={generating || !currentAssessmentData}
        className="w-full bg-gradient-to-r from-purple-600 to-blue-600 text-white px-8 py-4 rounded-xl font-semibold text-lg hover:from-purple-700 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-3 transition-all shadow-lg"
      >
        {generating ? (
          <>
            <Loader2 className="w-6 h-6 animate-spin" />
            <span>Generating Professional Report...</span>
          </>
        ) : !currentAssessmentData ? (
          <>
            <AlertCircle className="w-6 h-6" />
            <span>Waiting for Assessment Data...</span>
          </>
        ) : (
          <>
            <BarChart3 className="w-6 h-6" />
            <span>Generate {reportTypes.find(t => t.value === selectedReportType)?.label}</span>
          </>
        )}
      </button>

      {/* Professional Report Modal */}
      <AnimatePresence>
        {showReportModal && generatedReport && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
            onClick={() => setShowReportModal(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-gray-50 rounded-2xl shadow-2xl max-w-7xl w-full max-h-[95vh] overflow-hidden flex flex-col"
            >
              {/* Modal Actions Bar */}
              <div className="bg-white border-b border-gray-200 p-4 flex items-center justify-between">
                <h2 className="text-xl font-bold text-gray-900">Professional LCA Report</h2>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={handlePrint}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center space-x-2"
                  >
                    <Printer className="w-4 h-4" />
                    <span>Print/PDF</span>
                  </button>
                  <button
                    onClick={() => setShowReportModal(false)}
                    className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                    aria-label="Close report modal"
                    title="Close report"
                  >
                    <X className="w-6 h-6 text-gray-600" />
                  </button>
                </div>
              </div>

              {/* Modal Content */}
              <div id="report-content" ref={reportRef} className="overflow-y-auto p-8 space-y-6 print:p-0">
                {renderReportHeader()}
                {renderReportContent()}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Print Styles */}
      <style jsx global>{`
        @media print {
          /* Hide everything except the report */
          body * {
            visibility: hidden;
          }

          #report-content, #report-content * {
            visibility: visible;
          }

          /* Position report content properly */
          #report-content {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            max-width: 100%;
            padding: 0 !important;
            margin: 0 !important;
            overflow: visible !important;
          }

          /* Ensure proper page breaks */
          #report-content > * {
            page-break-inside: avoid;
            break-inside: avoid;
          }

          /* Fix chart and image sizing */
          #report-content img,
          #report-content canvas,
          #report-content svg {
            max-width: 100% !important;
            height: auto !important;
            page-break-inside: avoid;
          }

          /* Fix table styling for print */
          #report-content table {
            page-break-inside: avoid;
            width: 100% !important;
          }

          /* Remove shadows and rounded corners for print */
          #report-content * {
            box-shadow: none !important;
            border-radius: 0 !important;
          }

          /* Ensure text is black */
          #report-content {
            color: black !important;
          }

          /* Hide interactive elements */
          button, .print\\:hidden {
            display: none !important;
          }

          @page {
            size: A4;
            margin: 1.5cm;
          }
        }
      `}</style>
    </div>
  );
}
