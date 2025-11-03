import React from 'react';
import { Report } from '@/lib/api';
import { AssessmentResult } from '@/types/assessment';

interface PrintableReportProps {
  reportData: Report;
  assessmentData?: AssessmentResult;
  companyName: string;
  reportType: string;
}

export const PrintableReport: React.FC<PrintableReportProps> = ({
  reportData,
  assessmentData,
  companyName,
  reportType
}) => {
  // Debug: Log the report data structure
  console.log('📄 PrintableReport - reportData:', reportData);
  console.log('📄 PrintableReport - sections:', reportData?.sections);
  console.log('📄 PrintableReport - reportType:', reportType);

  // Format markdown to HTML for printing (simple version without complex styling)
  const formatForPrint = (text: string): string => {
    if (!text) return '';

    let formatted = text;

    // Remove first header
    formatted = formatted.replace(/^#+ .*?\n\n/, '');

    // Split into paragraphs
    const paragraphs = formatted.split(/\n\n+/);

    return paragraphs.map(para => {
      const trimmed = para.trim();
      if (!trimmed) return '';

      // Headers
      if (trimmed.startsWith('#### ')) {
        return `<h4 style="font-size: 14px; font-weight: 600; margin: 16px 0 8px 0;">${trimmed.substring(5)}</h4>`;
      }
      if (trimmed.startsWith('### ')) {
        return `<h3 style="font-size: 16px; font-weight: 600; margin: 20px 0 12px 0;">${trimmed.substring(4)}</h3>`;
      }
      if (trimmed.startsWith('## ')) {
        return `<h2 style="font-size: 18px; font-weight: 700; margin: 24px 0 16px 0;">${trimmed.substring(3)}</h2>`;
      }
      if (trimmed.startsWith('# ')) {
        return `<h1 style="font-size: 20px; font-weight: 700; margin: 28px 0 20px 0;">${trimmed.substring(2)}</h1>`;
      }

      // Horizontal rule
      if (trimmed === '---' || trimmed === '***') {
        return '<hr style="margin: 20px 0; border: none; border-top: 1px solid #ccc;" />';
      }

      // Tables
      if (trimmed.includes('|') && trimmed.split('\n').filter(line => line.includes('|')).length >= 2) {
        const lines = trimmed.split('\n').filter(line => line.trim());
        if (lines.length >= 2 && lines[1].includes('---')) {
          const headers = lines[0].split('|').filter(h => h.trim()).map(h => h.trim());
          const rows = lines.slice(2).map(line =>
            line.split('|').filter(cell => cell.trim()).map(cell => cell.trim())
          );

          let tableHTML = '<table style="width: 100%; border-collapse: collapse; margin: 16px 0; page-break-inside: avoid;"><thead><tr style="background: #f5f5f5;">';
          headers.forEach(header => {
            tableHTML += `<th style="border: 1px solid #ddd; padding: 8px; text-align: left; font-weight: 600;">${header}</th>`;
          });
          tableHTML += '</tr></thead><tbody>';
          rows.forEach(row => {
            tableHTML += '<tr>';
            row.forEach(cell => {
              const processed = cell
                .replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*([^*]+?)\*/g, '<em>$1</em>');
              tableHTML += `<td style="border: 1px solid #ddd; padding: 8px;">${processed}</td>`;
            });
            tableHTML += '</tr>';
          });
          tableHTML += '</tbody></table>';
          return tableHTML;
        }
      }

      // Lists
      if (trimmed.includes('\n- ') || trimmed.startsWith('- ')) {
        const items = trimmed.split('\n')
          .filter(line => line.trim())
          .map(line => {
            if (line.trim().startsWith('- ')) {
              const itemText = line.trim().substring(2)
                .replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*([^*]+?)\*/g, '<em>$1</em>');
              return `<li style="margin: 4px 0;">${itemText}</li>`;
            }
            return '';
          })
          .join('');
        return `<ul style="margin: 12px 0; padding-left: 24px;">${items}</ul>`;
      }

      // Regular paragraph with bold/italic
      let processed = trimmed;
      let prevProcessed = '';
      while (prevProcessed !== processed) {
        prevProcessed = processed;
        processed = processed.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>');
      }
      processed = processed.replace(/\*([^*]+?)\*/g, '<em>$1</em>');
      processed = processed.replace(/\n/g, '<br/>');

      return `<p style="margin: 8px 0; line-height: 1.6;">${processed}</p>`;
    }).join('');
  };

  const getReportTitle = () => {
    switch (reportType) {
      case 'farmer_friendly':
        return 'Farm Sustainability Report';
      case 'executive':
        return 'Executive Summary Report';
      case 'comprehensive':
        return 'Comprehensive LCA Report';
      default:
        return 'Assessment Report';
    }
  };

  return (
    <div style={{
      fontFamily: 'Arial, sans-serif',
      fontSize: '12px',
      lineHeight: '1.6',
      color: '#000',
      padding: '0',
      maxWidth: '100%'
    }}>
      {/* Report Header */}
      <div style={{
        marginBottom: '24px',
        paddingBottom: '16px',
        borderBottom: '2px solid #000',
        pageBreakAfter: 'avoid'
      }}>
        <h1 style={{
          fontSize: '24px',
          fontWeight: '700',
          margin: '0 0 8px 0',
          color: '#000'
        }}>
          {companyName}
        </h1>
        <h2 style={{
          fontSize: '18px',
          fontWeight: '600',
          margin: '0 0 12px 0',
          color: '#333'
        }}>
          {getReportTitle()}
        </h2>
        <div style={{ fontSize: '11px', color: '#666' }}>
          <div>Report ID: {reportData.report_id}</div>
          <div>Generated: {new Date(reportData.generated_at).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
          })}</div>
        </div>
      </div>

      {/* Key Metrics Summary - Only for farmer_friendly and executive */}
      {(reportType === 'farmer_friendly' || reportType === 'executive') && assessmentData && (
        <div style={{
          marginBottom: '24px',
          padding: '16px',
          background: '#f9f9f9',
          border: '1px solid #ddd',
          pageBreakInside: 'avoid'
        }}>
          <h3 style={{
            fontSize: '16px',
            fontWeight: '700',
            margin: '0 0 12px 0'
          }}>
            Key Metrics
          </h3>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '12px'
          }}>
            <div>
              <div style={{ fontSize: '10px', color: '#666', marginBottom: '4px' }}>Climate Change</div>
              <div style={{ fontSize: '16px', fontWeight: '700' }}>
                {assessmentData?.midpoint_impacts?.ClimateChange?.value?.toFixed(3) ||
                 assessmentData?.midpoint_impacts?.['Global warming']?.value?.toFixed(3) || 'N/A'}
              </div>
              <div style={{ fontSize: '10px', color: '#666' }}>
                {assessmentData?.midpoint_impacts?.ClimateChange?.unit ||
                 assessmentData?.midpoint_impacts?.['Global warming']?.unit || 'kg CO₂-eq per kg'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '10px', color: '#666', marginBottom: '4px' }}>Data Quality</div>
              <div style={{ fontSize: '16px', fontWeight: '700' }}>
                {(() => {
                  const dq = assessmentData?.data_quality;
                  if (!dq) return 'N/A';
                  const completeness = (dq.completeness_score || 0) * 100;
                  const temporal = (dq.temporal_representativeness || 0) * 100;
                  const geographical = (dq.geographical_representativeness || 0) * 100;
                  const technological = (dq.technological_representativeness || 0) * 100;
                  const avgQuality = (completeness + temporal + geographical + technological) / 4;
                  return `${avgQuality.toFixed(1)}%`;
                })()}
              </div>
              <div style={{ fontSize: '10px', color: '#666' }}>
                {assessmentData?.data_quality?.overall_confidence || 'N/A'} Confidence
              </div>
            </div>
            <div>
              <div style={{ fontSize: '10px', color: '#666', marginBottom: '4px' }}>Recommendations</div>
              <div style={{ fontSize: '16px', fontWeight: '700' }}>
                {assessmentData?.recommendations?.length || 0}
              </div>
              <div style={{ fontSize: '10px', color: '#666' }}>Action Items</div>
            </div>
          </div>
        </div>
      )}

      {/* Report Content Sections */}
      {reportData?.sections ? (
        Object.entries(reportData.sections).map(([sectionKey, sectionContent]) => (
          <div
            key={sectionKey}
            style={{
              marginBottom: '24px',
              pageBreakInside: 'avoid'
            }}
          >
            <div
              dangerouslySetInnerHTML={{
                __html: formatForPrint(String(sectionContent))
              }}
            />
          </div>
        ))
      ) : (
        <div style={{
          padding: '40px',
          textAlign: 'center',
          fontSize: '14px',
          color: '#666'
        }}>
          <p>No report content available. Please generate a report first.</p>
          <p style={{ marginTop: '12px', fontSize: '12px' }}>
            Debug: reportData = {JSON.stringify(Object.keys(reportData || {}), null, 2)}
          </p>
        </div>
      )}

      {/* Footer */}
      <div style={{
        marginTop: '32px',
        paddingTop: '16px',
        borderTop: '1px solid #ddd',
        fontSize: '10px',
        color: '#666',
        textAlign: 'center'
      }}>
        <div>Life Cycle Assessment Report</div>
        <div>Generated by Green Means Go - African LCA Platform</div>
        <div style={{ marginTop: '4px' }}>
          This report follows ISO 14044:2006 standards for Life Cycle Assessment
        </div>
      </div>
    </div>
  );
};

export default PrintableReport;
