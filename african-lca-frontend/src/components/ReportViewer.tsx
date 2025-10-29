'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileText,
  Download,
  Loader2,
  CheckCircle,
  AlertTriangle,
  Eye,
  FileJson,
  X
} from 'lucide-react';
import { assessmentAPI } from '@/lib/api';

interface ReportViewerProps {
  assessmentId: string;
  companyName: string;
}

type ReportType = 'comprehensive' | 'executive' | 'farmer_friendly';

interface ReportSection {
  title: string;
  content: string;
}

export default function ReportViewer({ assessmentId, companyName }: ReportViewerProps) {
  const [generating, setGenerating] = useState(false);
  const [generatedReport, setGeneratedReport] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedReportType, setSelectedReportType] = useState<ReportType>('comprehensive');
  const [showReportModal, setShowReportModal] = useState(false);
  const [exportingMarkdown, setExportingMarkdown] = useState(false);
  const [exportingJSON, setExportingJSON] = useState(false);

  const reportTypes = [
    {
      value: 'comprehensive' as ReportType,
      label: 'Comprehensive Report',
      description: 'Full professional report with all sections and detailed analysis',
      icon: '📊'
    },
    {
      value: 'executive' as ReportType,
      label: 'Executive Summary',
      description: 'Concise summary for decision-makers and executives',
      icon: '📋'
    },
    {
      value: 'farmer_friendly' as ReportType,
      label: 'Farmer-Friendly Report',
      description: 'Simplified report for smallholder farmers with practical guidance',
      icon: '🌾'
    }
  ];

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

  const handleExportMarkdown = async () => {
    if (!generatedReport) return;

    try {
      setExportingMarkdown(true);
      const response = await assessmentAPI.exportReportMarkdown(generatedReport.report_id);

      // Create a blob and download
      const blob = new Blob([response.content], { type: 'text/markdown' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${companyName.replace(/\s+/g, '_')}_Report_${generatedReport.report_id}.md`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export markdown');
    } finally {
      setExportingMarkdown(false);
    }
  };

  const handleExportJSON = async () => {
    if (!generatedReport) return;

    try {
      setExportingJSON(true);
      const response = await assessmentAPI.exportReportJSON(generatedReport.report_id);

      // Create a blob and download
      const blob = new Blob([JSON.stringify(response, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${companyName.replace(/\s+/g, '_')}_Report_${generatedReport.report_id}.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export JSON');
    } finally {
      setExportingJSON(false);
    }
  };

  const renderReportSection = (sectionKey: string, sectionContent: string) => {
    return (
      <div key={sectionKey} className="mb-8 bg-white rounded-lg p-6 shadow-sm border border-gray-200">
        <div
          className="prose prose-lg max-w-none"
          dangerouslySetInnerHTML={{
            __html: convertMarkdownToHTML(sectionContent)
          }}
        />
      </div>
    );
  };

  // Enhanced markdown to HTML converter with better formatting
  const convertMarkdownToHTML = (markdown: string): string => {
    let html = markdown;

    // Headers with better styling
    html = html.replace(/^### (.*$)/gim, '<h3 class="text-xl font-bold text-gray-900 mt-6 mb-3 border-l-4 border-blue-500 pl-4 bg-blue-50 py-2">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 class="text-2xl font-bold text-gray-900 mt-8 mb-4 border-b-2 border-gray-300 pb-2">$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1 class="text-3xl font-bold text-gray-900 mt-10 mb-5 text-center bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">$1</h1>');

    // Tables with professional styling
    html = html.replace(/\|([^|\n]*)\|([^|\n]*)\|([^|\n]*)\|([^|\n]*)\|([^|\n]*)\|/g, 
      '<tr><td class="px-3 py-2 border-b">$1</td><td class="px-3 py-2 border-b text-right font-mono">$2</td><td class="px-3 py-2 border-b text-center text-gray-600">$3</td><td class="px-3 py-2 border-b text-right font-semibold">$4</td><td class="px-3 py-2 border-b text-center">$5</td></tr>');
    html = html.replace(/\|([^|\n]*)\|([^|\n]*)\|([^|\n]*)\|/g, 
      '<tr><td class="px-3 py-2 border-b font-medium">$1</td><td class="px-3 py-2 border-b text-right">$2</td><td class="px-3 py-2 border-b text-center">$3</td></tr>');
    
    // Table headers
    html = html.replace(/\|([^|\n]*)\|([^|\n]*)\|([^|\n]*)\|([^|\n]*)\|([^|\n]*)\|(\s*\n\s*\|[-\s|]*\|)/g,
      '<table class="w-full text-sm bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden mt-4 mb-4"><thead class="bg-gray-50"><tr><th class="px-3 py-2 text-left font-semibold text-gray-700">$1</th><th class="px-3 py-2 text-right font-semibold text-gray-700">$2</th><th class="px-3 py-2 text-center font-semibold text-gray-700">$3</th><th class="px-3 py-2 text-right font-semibold text-gray-700">$4</th><th class="px-3 py-2 text-center font-semibold text-gray-700">$5</th></tr></thead><tbody>');
    html = html.replace(/\|([^|\n]*)\|([^|\n]*)\|([^|\n]*)\|(\s*\n\s*\|[-\s|]*\|)/g,
      '<table class="w-full text-sm bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden mt-4 mb-4"><thead class="bg-gray-50"><tr><th class="px-3 py-2 text-left font-semibold text-gray-700">$1</th><th class="px-3 py-2 text-right font-semibold text-gray-700">$2</th><th class="px-3 py-2 text-center font-semibold text-gray-700">$3</th></tr></thead><tbody>');

    // Close tables
    html = html.replace(/<\/td><\/tr>(?!\s*<tr>)/g, '</td></tr></tbody></table>');

    // Code blocks with syntax highlighting
    html = html.replace(/```([^`]*)```/g, '<div class="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm overflow-x-auto mt-4 mb-4 shadow-inner"><pre>$1</pre></div>');

    // Inline code
    html = html.replace(/`([^`]*)`/g, '<code class="bg-gray-100 text-gray-800 px-2 py-1 rounded font-mono text-sm">$1</code>');

    // Emojis and status indicators
    html = html.replace(/🔴/g, '<span class="text-red-500 font-semibold">🔴</span>');
    html = html.replace(/🟡/g, '<span class="text-yellow-500 font-semibold">🟡</span>');
    html = html.replace(/🟢/g, '<span class="text-green-500 font-semibold">🟢</span>');
    html = html.replace(/✅/g, '<span class="text-green-600 font-semibold">✅</span>');
    html = html.replace(/⚠️/g, '<span class="text-yellow-600 font-semibold">⚠️</span>');
    html = html.replace(/🚨/g, '<span class="text-red-600 font-semibold">🚨</span>');

    // Bold and Italic with better styling
    html = html.replace(/\*\*\*(.*?)\*\*\*/g, '<strong class="font-bold text-gray-900"><em class="italic">$1</em></strong>');
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-gray-900">$1</strong>');
    html = html.replace(/\*(.*?)\*/g, '<em class="italic text-gray-700">$1</em>');

    // Lists with better styling
    html = html.replace(/^\- (.*$)/gim, '<li class="ml-4 mb-2 flex items-start"><span class="text-blue-500 mr-2">•</span><span>$1</span></li>');
    html = html.replace(/(<li.*<\/span><\/li>)/g, '<ul class="list-none ml-6 mb-4 space-y-1">$1</ul>');

    // Blockquotes for notes
    html = html.replace(/^\*([^*].*)\*$/gim, '<div class="bg-blue-50 border-l-4 border-blue-400 p-3 my-4 italic text-blue-800">$1</div>');

    // Key insights highlighting
    html = html.replace(/📊 \*\*([^*]*)\*\*/g, '<div class="bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200 rounded-lg p-3 my-3"><span class="text-lg">📊</span> <strong class="font-bold text-blue-900">$1</strong></div>');
    html = html.replace(/🌾 \*\*([^*]*)\*\*/g, '<div class="bg-green-50 border border-green-200 rounded-lg p-3 my-3"><span class="text-lg">🌾</span> <strong class="font-bold text-green-900">$1</strong></div>');
    html = html.replace(/⚡ \*\*([^*]*)\*\*/g, '<div class="bg-orange-50 border border-orange-200 rounded-lg p-3 my-3"><span class="text-lg">⚡</span> <strong class="font-bold text-orange-900">$1</strong></div>');

    // Paragraphs with better spacing
    html = html.replace(/\n\n+/g, '</p><p class="mb-4 text-gray-700 leading-relaxed">');
    html = '<p class="mb-4 text-gray-700 leading-relaxed">' + html + '</p>';

    // Clean up empty paragraphs
    html = html.replace(/<p class="[^"]*"><\/p>/g, '');

    return html;
  };

  return (
    <div className="bg-gradient-to-br from-purple-50 to-blue-50 rounded-2xl p-8 border-2 border-purple-200">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <FileText className="w-8 h-8 text-purple-600" />
          <div>
            <h3 className="text-2xl font-bold text-gray-900">AI-Powered Professional Reports</h3>
            <p className="text-sm text-gray-600">Generate comprehensive sustainability reports using Claude AI</p>
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
            <div className="text-3xl mb-2">{type.icon}</div>
            <div className="font-semibold text-gray-900 mb-1">{type.label}</div>
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
          <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
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
            <div className="font-semibold text-green-900">Report Generated Successfully</div>
            <div className="text-sm text-green-700">
              Report ID: {generatedReport.report_id} | Type: {generatedReport.report_type}
            </div>
          </div>
          <button
            onClick={() => setShowReportModal(true)}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center space-x-2"
          >
            <Eye className="w-4 h-4" />
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
            <span>Generating {selectedReportType} Report...</span>
          </>
        ) : (
          <>
            <FileText className="w-6 h-6" />
            <span>Generate {reportTypes.find(t => t.value === selectedReportType)?.label}</span>
          </>
        )}
      </button>

      {/* Report Modal */}
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
              className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[90vh] overflow-hidden"
            >
              {/* Modal Header */}
              <div className="bg-gradient-to-r from-purple-600 to-blue-600 text-white p-6 flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold">{generatedReport.report_type.toUpperCase()} REPORT</h2>
                  <p className="text-sm opacity-90">
                    {companyName} | Generated: {new Date(generatedReport.generated_at).toLocaleString()}
                  </p>
                </div>
                <button
                  onClick={() => setShowReportModal(false)}
                  className="p-2 hover:bg-white hover:bg-opacity-20 rounded-lg transition-colors"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              {/* Modal Content */}
              <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
                {Object.entries(generatedReport.sections).map(([key, content]) => (
                  renderReportSection(key, content as string)
                ))}
              </div>

              {/* Modal Footer */}
              <div className="bg-gray-50 p-6 border-t flex items-center justify-between">
                <div className="text-sm text-gray-600">
                  Powered by Claude AI | Model: {generatedReport.metadata?.model_used}
                </div>
                <div className="flex space-x-3">
                  <button
                    onClick={handleExportMarkdown}
                    disabled={exportingMarkdown}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center space-x-2"
                  >
                    {exportingMarkdown ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Download className="w-4 h-4" />
                    )}
                    <span>Export Markdown</span>
                  </button>
                  <button
                    onClick={handleExportJSON}
                    disabled={exportingJSON}
                    className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 flex items-center space-x-2"
                  >
                    {exportingJSON ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <FileJson className="w-4 h-4" />
                    )}
                    <span>Export JSON</span>
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
