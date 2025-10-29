'use client';

import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileText,
  Download,
  Loader2,
  CheckCircle,
  X,
  Printer,
  Share2,
  TrendingUp,
  TrendingDown,
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
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Area,
  AreaChart
} from 'recharts';
import { assessmentAPI } from '@/lib/api';

interface ProfessionalReportViewerProps {
  assessmentId: string;
  companyName: string;
  assessmentData: any;
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
  const [generatedReport, setGeneratedReport] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedReportType, setSelectedReportType] = useState<ReportType>('comprehensive');
  const [showReportModal, setShowReportModal] = useState(false);
  const reportRef = useRef<HTMLDivElement>(null);

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

  // Prepare chart data from assessment
  const prepareChartData = () => {
    const midpoint = assessmentData?.midpoint_impacts || {};
    const breakdown = assessmentData?.breakdown_by_food || {};
    const dataQuality = assessmentData?.data_quality || {};

    // Impact categories for bar chart
    const impactCategories = Object.entries(midpoint).map(([key, value]: [string, any]) => ({
      name: key.replace(/([A-Z])/g, ' $1').trim(),
      value: typeof value === 'object' ? value.value : value,
      unit: typeof value === 'object' ? value.unit : 'units'
    })).slice(0, 8); // Top 8 categories

    // Crop breakdown for pie chart
    const cropBreakdown = Object.entries(breakdown).map(([food, impacts]: [string, any]) => {
      const climateImpact = impacts?.ClimateChange || impacts?.climate_change || impacts?.['Global Warming'] || {};
      return {
        name: food,
        value: typeof climateImpact === 'object' ? climateImpact.value : climateImpact || 0
      };
    });

    // Data quality radar
    const dataQualityMetrics = [
      {
        metric: 'Completeness',
        value: (dataQuality.completeness_score || 0) * 100,
        fullMark: 100
      },
      {
        metric: 'Temporal',
        value: (dataQuality.temporal_representativeness || 0) * 100,
        fullMark: 100
      },
      {
        metric: 'Geographical',
        value: (dataQuality.geographical_representativeness || 0) * 100,
        fullMark: 100
      },
      {
        metric: 'Technological',
        value: (dataQuality.technological_representativeness || 0) * 100,
        fullMark: 100
      }
    ];

    // Recommendations priority
    const recommendations = assessmentData?.recommendations || [];
    const recommendationsByPriority = {
      high: recommendations.filter((r: any) => r.priority?.toLowerCase() === 'high').length,
      medium: recommendations.filter((r: any) => r.priority?.toLowerCase() === 'medium').length,
      low: recommendations.filter((r: any) => r.priority?.toLowerCase() === 'low').length
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
    try {
      setGenerating(true);
      setError(null);

      const response = await assessmentAPI.generateReport(assessmentId, selectedReportType);

      if (response.status === 'success') {
        setGeneratedReport(response.report_data);
        setShowReportModal(true);
      } else {
        setError('Report generation failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate report');
    } finally {
      setGenerating(false);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  const handleExportPDF = () => {
    // Trigger print dialog which can save as PDF
    window.print();
  };

  // Render impact categories bar chart
  const renderImpactCategoriesChart = () => (
    <div className="mb-8 bg-white rounded-xl p-6 shadow-lg border border-gray-200">
      <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
        <BarChart3 className="w-6 h-6 mr-2 text-blue-600" />
        Environmental Impact Categories
      </h3>
      <ResponsiveContainer width="100%" height={400}>
        <BarChart data={chartData.impactCategories} margin={{ top: 20, right: 30, left: 20, bottom: 80 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis
            dataKey="name"
            angle={-45}
            textAnchor="end"
            height={100}
            tick={{ fill: '#6B7280', fontSize: 12 }}
          />
          <YAxis tick={{ fill: '#6B7280' }} />
          <Tooltip
            contentStyle={{ backgroundColor: '#FFF', border: '1px solid #E5E7EB', borderRadius: '8px' }}
          />
          <Bar dataKey="value" fill="#3B82F6" radius={[8, 8, 0, 0]}>
            {chartData.impactCategories.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS.primary[index % COLORS.primary.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="text-sm text-gray-600 mt-4 text-center">
        Figure 1: Comparative analysis of environmental impact categories (normalized values)
      </p>
    </div>
  );

  // Render crop breakdown pie chart
  const renderCropBreakdownChart = () => (
    <div className="mb-8 bg-white rounded-xl p-6 shadow-lg border border-gray-200">
      <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
        <PieChartIcon className="w-6 h-6 mr-2 text-green-600" />
        Climate Impact Breakdown by Crop
      </h3>
      <ResponsiveContainer width="100%" height={400}>
        <PieChart>
          <Pie
            data={chartData.cropBreakdown}
            cx="50%"
            cy="50%"
            labelLine={true}
            label={(entry) => `${entry.name}: ${entry.value.toFixed(2)}`}
            outerRadius={120}
            fill="#8884d8"
            dataKey="value"
          >
            {chartData.cropBreakdown.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS.primary[index % COLORS.primary.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ backgroundColor: '#FFF', border: '1px solid #E5E7EB', borderRadius: '8px' }}
          />
          <Legend verticalAlign="bottom" height={36} />
        </PieChart>
      </ResponsiveContainer>
      <p className="text-sm text-gray-600 mt-4 text-center">
        Figure 2: Distribution of climate change impacts across different crops (kg CO₂-eq)
      </p>
    </div>
  );

  // Render data quality radar chart
  const renderDataQualityChart = () => (
    <div className="mb-8 bg-white rounded-xl p-6 shadow-lg border border-gray-200">
      <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
        <LineChartIcon className="w-6 h-6 mr-2 text-purple-600" />
        Data Quality Assessment
      </h3>
      <ResponsiveContainer width="100%" height={400}>
        <RadarChart data={chartData.dataQualityMetrics}>
          <PolarGrid stroke="#E5E7EB" />
          <PolarAngleAxis dataKey="metric" tick={{ fill: '#6B7280' }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: '#6B7280' }} />
          <Radar
            name="Quality Score"
            dataKey="value"
            stroke="#8B5CF6"
            fill="#8B5CF6"
            fillOpacity={0.6}
          />
          <Tooltip
            contentStyle={{ backgroundColor: '#FFF', border: '1px solid #E5E7EB', borderRadius: '8px' }}
          />
          <Legend />
        </RadarChart>
      </ResponsiveContainer>
      <p className="text-sm text-gray-600 mt-4 text-center">
        Figure 3: Data quality metrics across different representativeness dimensions (%)
      </p>
    </div>
  );

  // Render recommendations priority chart
  const renderRecommendationsPriorityChart = () => (
    <div className="mb-8 bg-white rounded-xl p-6 shadow-lg border border-gray-200">
      <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
        <AlertCircle className="w-6 h-6 mr-2 text-orange-600" />
        Recommendations by Priority
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData.priorityData} layout="vertical" margin={{ left: 80 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis type="number" tick={{ fill: '#6B7280' }} />
          <YAxis dataKey="priority" type="category" tick={{ fill: '#6B7280' }} />
          <Tooltip
            contentStyle={{ backgroundColor: '#FFF', border: '1px solid #E5E7EB', borderRadius: '8px' }}
          />
          <Bar dataKey="count" fill="#F59E0B" radius={[0, 8, 8, 0]}>
            {chartData.priorityData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="text-sm text-gray-600 mt-4 text-center">
        Figure 4: Distribution of action recommendations by implementation priority
      </p>
    </div>
  );

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
                {new Date(assessmentData?.assessment_date || Date.now()).toLocaleDateString()}
              </p>
            </div>
            <div>
              <p className="text-sm text-blue-200">Country/Region</p>
              <p className="font-semibold text-lg">{assessmentData?.country || 'N/A'}</p>
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
              {typeof assessmentData?.single_score === 'object'
                ? assessmentData.single_score.value?.toFixed(2)
                : assessmentData?.single_score?.toFixed(2) || 'N/A'}
            </p>
            <p className="text-sm text-blue-100 mt-1">
              {typeof assessmentData?.single_score === 'object'
                ? assessmentData.single_score.unit
                : 'points'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );

  // Render report content with sections
  const renderReportContent = () => {
    if (!generatedReport?.sections) return null;

    const sections = generatedReport.sections;

    return (
      <div className="space-y-8">
        {/* Executive Summary */}
        {sections.executive_summary && (
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-6 border-l-4 border-blue-600">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Executive Summary</h2>
            <div className="prose prose-lg max-w-none text-gray-700"
                 dangerouslySetInnerHTML={{ __html: sections.executive_summary.replace(/\n/g, '<br/>') }}
            />
          </div>
        )}

        {/* Key Metrics Dashboard */}
        <div className="grid md:grid-cols-3 gap-6">
          <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Climate Change</p>
                <p className="text-2xl font-bold text-gray-900">
                  {assessmentData?.midpoint_impacts?.ClimateChange?.value?.toFixed(2) || 'N/A'}
                </p>
                <p className="text-xs text-gray-500">
                  {assessmentData?.midpoint_impacts?.ClimateChange?.unit || 'kg CO₂-eq'}
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
                  {((assessmentData?.data_quality?.completeness_score || 0) * 100).toFixed(0)}%
                </p>
                <p className="text-xs text-gray-500">
                  {assessmentData?.data_quality?.overall_confidence || 'Medium'} Confidence
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
                  {assessmentData?.recommendations?.length || 0}
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

        {/* Other sections */}
        {Object.entries(sections).map(([key, content]) => {
          if (key === 'executive_summary') return null; // Already rendered

          return (
            <div key={key} className="bg-white rounded-xl p-6 shadow-lg border border-gray-200">
              <h2 className="text-2xl font-bold text-gray-900 mb-4 capitalize">
                {key.replace(/_/g, ' ')}
              </h2>
              <div className="prose prose-lg max-w-none text-gray-700"
                   dangerouslySetInnerHTML={{ __html: String(content).replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br/>') }}
              />
            </div>
          );
        })}

        {/* Report Footer */}
        <div className="bg-gray-50 rounded-xl p-6 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Generated by</p>
              <p className="font-semibold text-gray-900">Dr. Amara Okonkwo - LCA Expert</p>
              <p className="text-xs text-gray-500 mt-1">
                Powered by Claude AI | Model: {generatedReport?.metadata?.model_used}
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-600">Report Date</p>
              <p className="font-semibold text-gray-900">
                {new Date(generatedReport?.generated_at || Date.now()).toLocaleString()}
              </p>
            </div>
          </div>
        </div>
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
            <p className="text-sm text-gray-600">Generate comprehensive reports with interactive visualizations</p>
          </div>
        </div>
      </div>

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
        disabled={generating}
        className="w-full bg-gradient-to-r from-purple-600 to-blue-600 text-white px-8 py-4 rounded-xl font-semibold text-lg hover:from-purple-700 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-3 transition-all shadow-lg"
      >
        {generating ? (
          <>
            <Loader2 className="w-6 h-6 animate-spin" />
            <span>Generating Professional Report...</span>
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
                  >
                    <X className="w-6 h-6 text-gray-600" />
                  </button>
                </div>
              </div>

              {/* Modal Content */}
              <div ref={reportRef} className="overflow-y-auto p-8 space-y-6 print:p-0">
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
          body * {
            visibility: hidden;
          }
          #report-content, #report-content * {
            visibility: visible;
          }
          #report-content {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
          }
          @page {
            size: A4;
            margin: 1cm;
          }
        }
      `}</style>
    </div>
  );
}
