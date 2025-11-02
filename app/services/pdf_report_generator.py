"""
PDF Report Generator Service
Generates professional PDF reports with charts and formatted content
"""

import io
import re
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether, ListFlowable, ListItem
)
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor


class PDFReportGenerator:
    """Generate professional PDF reports for LCA assessments"""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles"""
        # Helper function to add style only if it doesn't exist
        def add_style_if_not_exists(style_def):
            if style_def.name not in self.styles:
                self.styles.add(style_def)

        # Title style
        add_style_if_not_exists(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#000000'),
            spaceAfter=12,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        ))

        # Subtitle style
        add_style_if_not_exists(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=18,
            textColor=colors.HexColor('#333333'),
            spaceAfter=10,
            spaceBefore=6,
            fontName='Helvetica-Bold'
        ))

        # Section header style
        add_style_if_not_exists(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#000000'),
            spaceAfter=8,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        ))

        # Subsection header style
        add_style_if_not_exists(ParagraphStyle(
            name='SubsectionHeader',
            parent=self.styles['Heading3'],
            fontSize=14,
            textColor=colors.HexColor('#000000'),
            spaceAfter=6,
            spaceBefore=10,
            fontName='Helvetica-Bold'
        ))

        # Body text style
        add_style_if_not_exists(ParagraphStyle(
            name='CustomBodyText',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#000000'),
            spaceAfter=8,
            alignment=TA_JUSTIFY
        ))

        # Bullet list style
        add_style_if_not_exists(ParagraphStyle(
            name='BulletText',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#000000'),
            leftIndent=20,
            spaceAfter=4
        ))

    def generate_pdf(self, report_data: Dict[str, Any], assessment_data: Dict[str, Any],
                     report_type: str) -> bytes:
        """
        Generate a complete PDF report

        Args:
            report_data: The generated report data with sections
            assessment_data: The assessment data for metrics and charts
            report_type: Type of report (farmer_friendly, executive, comprehensive)

        Returns:
            PDF bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        # Build the PDF content
        story = []

        # Add header
        story.extend(self._create_header(report_data, assessment_data, report_type))

        # Add key metrics summary
        if report_type in ['farmer_friendly', 'executive']:
            story.extend(self._create_key_metrics(assessment_data))
            story.append(Spacer(1, 0.5*cm))

        # Add visualizations for farmer_friendly and comprehensive reports
        if report_type in ['farmer_friendly', 'comprehensive']:
            chart = self._create_impact_chart(assessment_data)
            if chart:
                story.append(Paragraph("Visual Analysis", self.styles['SectionHeader']))
                story.append(Spacer(1, 0.3*cm))
                story.append(chart)
                story.append(Spacer(1, 0.5*cm))

        # Add report sections
        sections = report_data.get('sections', {})
        for section_key, section_content in sections.items():
            story.extend(self._format_section(str(section_content)))
            story.append(Spacer(1, 0.3*cm))

        # Add footer
        story.extend(self._create_footer())

        # Build PDF
        doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)

        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    def _create_header(self, report_data: Dict, assessment_data: Dict, report_type: str) -> List:
        """Create PDF header with title and metadata"""
        elements = []

        # Company name/title
        company_name = assessment_data.get('company_name', 'Assessment Report')
        elements.append(Paragraph(company_name, self.styles['CustomTitle']))

        # Report type subtitle
        report_titles = {
            'farmer_friendly': 'Farm Sustainability Report',
            'executive': 'Executive Summary Report',
            'comprehensive': 'Comprehensive LCA Report'
        }
        subtitle = report_titles.get(report_type, 'Assessment Report')
        elements.append(Paragraph(subtitle, self.styles['CustomSubtitle']))

        # Metadata
        report_id = report_data.get('report_id', 'N/A')
        generated_at = report_data.get('generated_at', datetime.now().isoformat())
        try:
            gen_date = datetime.fromisoformat(generated_at).strftime('%B %d, %Y at %I:%M %p')
        except:
            gen_date = generated_at

        metadata_text = f"<b>Report ID:</b> {report_id}<br/><b>Generated:</b> {gen_date}"
        elements.append(Paragraph(metadata_text, self.styles['Normal']))
        elements.append(Spacer(1, 0.5*cm))

        # Horizontal line
        elements.append(self._create_horizontal_line())
        elements.append(Spacer(1, 0.5*cm))

        return elements

    def _create_key_metrics(self, assessment_data: Dict) -> List:
        """Create key metrics summary box"""
        elements = []

        elements.append(Paragraph("Key Metrics", self.styles['SectionHeader']))

        # Get metrics
        climate_value = 'N/A'
        climate_unit = 'kg CO₂-eq per kg'
        if assessment_data.get('midpoint_impacts'):
            impacts = assessment_data['midpoint_impacts']
            if 'ClimateChange' in impacts:
                climate_value = f"{impacts['ClimateChange']['value']:.3f}"
                climate_unit = impacts['ClimateChange'].get('unit', climate_unit)
            elif 'Global warming' in impacts:
                climate_value = f"{impacts['Global warming']['value']:.3f}"
                climate_unit = impacts['Global warming'].get('unit', climate_unit)

        # Data quality
        data_quality = 'N/A'
        data_conf = 'N/A'
        if assessment_data.get('data_quality'):
            dq = assessment_data['data_quality']
            completeness = (dq.get('completeness_score', 0)) * 100
            temporal = (dq.get('temporal_representativeness', 0)) * 100
            geographical = (dq.get('geographical_representativeness', 0)) * 100
            technological = (dq.get('technological_representativeness', 0)) * 100
            avg_quality = (completeness + temporal + geographical + technological) / 4
            data_quality = f"{avg_quality:.1f}%"
            data_conf = dq.get('overall_confidence', 'N/A')

        # Recommendations
        recommendations = assessment_data.get('recommendations', [])
        rec_count = len(recommendations)

        # Create table
        data = [
            ['Climate Change', 'Data Quality', 'Recommendations'],
            [climate_value, data_quality, str(rec_count)],
            [climate_unit, f"{data_conf} Confidence", 'Action Items']
        ]

        table = Table(data, colWidths=[5.5*cm, 5.5*cm, 5.5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),  # Indigo header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (0, 1), colors.HexColor('#fef3c7')),  # Light yellow for climate
            ('BACKGROUND', (1, 1), (1, 1), colors.HexColor('#dbeafe')),  # Light blue for data quality
            ('BACKGROUND', (2, 1), (2, 1), colors.HexColor('#fed7aa')),  # Light orange for recommendations
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, 1), 14),
            ('FONTSIZE', (0, 2), (-1, 2), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#4f46e5'))
        ]))

        elements.append(table)

        return elements

    def _format_section(self, content: str) -> List:
        """Format markdown-style content for PDF"""
        elements = []

        # Remove first header if present
        content = re.sub(r'^#+\s+.*?\n\n', '', content, count=1)

        # Split into paragraphs
        paragraphs = re.split(r'\n\n+', content)

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Check for headers
            if para.startswith('#### '):
                text = para[5:].strip()
                text = self._convert_markdown_inline(text)
                elements.append(Paragraph(text, self.styles['SubsectionHeader']))
                continue
            elif para.startswith('### '):
                text = para[4:].strip()
                text = self._convert_markdown_inline(text)
                elements.append(Paragraph(text, self.styles['SubsectionHeader']))
                continue
            elif para.startswith('## '):
                text = para[3:].strip()
                text = self._convert_markdown_inline(text)
                elements.append(Paragraph(text, self.styles['SectionHeader']))
                continue
            elif para.startswith('# '):
                text = para[2:].strip()
                text = self._convert_markdown_inline(text)
                elements.append(Paragraph(text, self.styles['SectionHeader']))
                continue

            # Horizontal rule
            if para.strip() in ['---', '***']:
                elements.append(self._create_horizontal_line())
                continue

            # Tables
            if '|' in para and para.count('\n') >= 2:
                lines = para.split('\n')
                if len(lines) >= 2 and '---' in lines[1]:
                    table_elem = self._create_table_from_markdown(lines)
                    if table_elem:
                        elements.append(table_elem)
                        continue

            # Bullet lists
            if para.startswith('- ') or '\n- ' in para:
                list_items = []
                for line in para.split('\n'):
                    if line.strip().startswith('- '):
                        item_text = line.strip()[2:]
                        item_text = self._convert_markdown_inline(item_text)
                        list_items.append(ListItem(Paragraph(item_text, self.styles['BulletText']), leftIndent=20))
                if list_items:
                    elements.append(ListFlowable(list_items, bulletType='bullet', start='•'))
                continue

            # Regular paragraph
            text = self._convert_markdown_inline(para)
            # Replace newlines with line breaks
            text = text.replace('\n', '<br/>')
            elements.append(Paragraph(text, self.styles['CustomBodyText']))

        return elements

    def _convert_markdown_inline(self, text: str) -> str:
        """Convert inline markdown (bold, italic) to HTML"""
        # Bold
        text = re.sub(r'\*\*([^*]+?)\*\*', r'<b>\1</b>', text)
        # Italic
        text = re.sub(r'\*([^*]+?)\*', r'<i>\1</i>', text)
        return text

    def _create_table_from_markdown(self, lines: List[str]) -> Optional[Table]:
        """Create a ReportLab table from markdown table"""
        try:
            # Parse headers
            headers = [h.strip() for h in lines[0].split('|') if h.strip()]

            # Parse rows (skip separator line)
            rows = []
            for line in lines[2:]:
                if line.strip():
                    row = [cell.strip() for cell in line.split('|') if cell.strip()]
                    if row:
                        # Convert markdown in cells
                        row = [self._convert_markdown_inline(cell) for cell in row]
                        rows.append(row)

            # Create table data
            table_data = [headers] + rows

            # Create table
            col_widths = [16*cm / len(headers)] * len(headers)
            table = Table(table_data, colWidths=col_widths)

            # Style the table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f5f5f5')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#000000')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP')
            ]))

            return table
        except Exception as e:
            print(f"Error creating table: {e}")
            return None

    def _create_horizontal_line(self):
        """Create a horizontal line separator"""
        from reportlab.graphics.shapes import Drawing, Line

        d = Drawing(16*cm, 0.1*cm)
        d.add(Line(0, 0, 16*cm, 0, strokeColor=colors.HexColor('#000000'), strokeWidth=2))
        return d

    def _create_impact_chart(self, assessment_data: Dict) -> Optional[Image]:
        """Create a colored bar chart of environmental impacts"""
        try:
            midpoint = assessment_data.get('midpoint_impacts', {})
            if not midpoint:
                return None

            # Extract and sort impacts
            impacts = []
            for category, data in midpoint.items():
                if isinstance(data, dict):
                    value = data.get('value', 0)
                else:
                    value = data if isinstance(data, (int, float)) else 0

                if value > 0:
                    impacts.append((category, value))

            if not impacts:
                return None

            # Sort by value descending and take top 8
            impacts.sort(key=lambda x: x[1], reverse=True)
            impacts = impacts[:8]

            categories = [x[0] for x in impacts]
            values = [x[1] for x in impacts]

            # Normalize values for better visualization
            max_val = max(values) if values else 1
            normalized_values = [100 * v / max_val for v in values]

            # Create figure with colors
            fig = Figure(figsize=(7, 4))
            ax = fig.add_subplot(111)

            # Color bars based on impact level
            colors_list = []
            for norm_val in normalized_values:
                if norm_val >= 75:
                    colors_list.append('#ef4444')  # Red for high impact
                elif norm_val >= 40:
                    colors_list.append('#f59e0b')  # Orange for medium impact
                else:
                    colors_list.append('#10b981')  # Green for low impact

            bars = ax.barh(range(len(categories)), normalized_values, color=colors_list)
            ax.set_yticks(range(len(categories)))
            ax.set_yticklabels(categories, fontsize=9)
            ax.set_xlabel('Normalized Impact', fontsize=10)
            ax.set_title('Environmental Impact Categories (Normalized)', fontsize=11, fontweight='bold')
            ax.set_xlim(0, 105)

            # Add value labels
            for i, (bar, val) in enumerate(zip(bars, normalized_values)):
                ax.text(val + 2, i, f'{val:.0f}', va='center', fontsize=8)

            # Add legend
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor='#ef4444', label='High (≥75%)'),
                Patch(facecolor='#f59e0b', label='Medium (40-74%)'),
                Patch(facecolor='#10b981', label='Low (<40%)')
            ]
            ax.legend(handles=legend_elements, loc='lower right', fontsize=8)

            fig.tight_layout()

            # Convert to image
            img_buffer = io.BytesIO()
            fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close(fig)

            # Create ReportLab Image
            img = Image(img_buffer, width=16*cm, height=9*cm)
            return img

        except Exception as e:
            print(f"Error creating impact chart: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _create_footer(self) -> List:
        """Create PDF footer"""
        elements = []

        elements.append(Spacer(1, 1*cm))
        elements.append(self._create_horizontal_line())
        elements.append(Spacer(1, 0.3*cm))

        footer_text = """
        <para align="center">
        <b>Life Cycle Assessment Report</b><br/>
        Generated by Green Means Go - African LCA Platform<br/>
        <i>This report follows ISO 14044:2006 standards for Life Cycle Assessment</i>
        </para>
        """
        elements.append(Paragraph(footer_text, self.styles['Normal']))

        return elements

    def _add_page_number(self, canvas_obj, doc):
        """Add page numbers to each page"""
        page_num = canvas_obj.getPageNumber()
        text = f"Page {page_num}"
        canvas_obj.setFont('Helvetica', 9)
        canvas_obj.drawRightString(A4[0] - 2*cm, 1*cm, text)


# Singleton instance
_pdf_generator = None

def get_pdf_generator() -> PDFReportGenerator:
    """Get or create PDF generator instance"""
    global _pdf_generator
    if _pdf_generator is None:
        _pdf_generator = PDFReportGenerator()
    return _pdf_generator
