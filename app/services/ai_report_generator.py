"""
AI-Powered Report Generation Service
Uses Claude API to generate professional sustainability assessment reports
"""

import os
import json
from typing import Dict, Any, Optional
from datetime import datetime
import anthropic


class AIReportGenerator:
    """
    Professional AI Report Generator using Claude API
    Generates comprehensive, formal sustainability assessment reports
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the AI Report Generator

        Args:
            api_key: Anthropic API key (defaults to environment variable)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable must be set")

        try:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.model = "claude-sonnet-4-20250514"  # Latest Claude model
        except Exception as e:
            raise ValueError(f"Failed to initialize Anthropic client: {e}")

    async def generate_comprehensive_report(
        self,
        assessment_data: Dict[str, Any],
        report_type: str = "comprehensive"
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive professional report from assessment data

        Args:
            assessment_data: Complete assessment results from the LCA system
            report_type: Type of report (comprehensive, executive, technical)

        Returns:
            Dictionary containing the generated report sections
        """

        # Prepare the assessment data for the AI
        formatted_data = self._format_assessment_data(assessment_data)

        # Generate the report using Claude
        report_sections = await self._generate_report_sections(
            formatted_data,
            report_type
        )

        # Structure the final report
        final_report = {
            "report_id": f"REPORT-{assessment_data.get('id', 'UNKNOWN')}",
            "generated_at": datetime.now().isoformat(),
            "report_type": report_type,
            "assessment_id": assessment_data.get("id"),
            "company_name": assessment_data.get("company_name"),
            "country": assessment_data.get("country"),
            "assessment_date": assessment_data.get("assessment_date"),
            "sections": report_sections,
            "metadata": {
                "model_used": self.model,
                "generation_timestamp": datetime.now().isoformat()
            }
        }

        return final_report

    def _format_assessment_data(self, data: Dict[str, Any]) -> str:
        """
        Format assessment data into a structured prompt for Claude
        """

        # Extract key metrics
        midpoint = data.get("midpoint_impacts", {})
        endpoint = data.get("endpoint_impacts", {})
        single_score = data.get("single_score", {})
        data_quality = data.get("data_quality", {})
        breakdown = data.get("breakdown_by_food", {})

        # Optional advanced analysis
        sensitivity = data.get("sensitivity_analysis")
        comparative = data.get("comparative_analysis")
        management = data.get("management_analysis")
        benchmarking = data.get("benchmarking")
        recommendations = data.get("recommendations", [])

        formatted = f"""
# Environmental Sustainability Assessment Data

## Basic Information
- Company/Farm: {data.get('company_name', 'Unknown')}
- Country: {data.get('country', 'Unknown')}
- Assessment Date: {data.get('assessment_date', 'Unknown')}
- Assessment ID: {data.get('id', 'Unknown')}

## Environmental Impact Score
"""

        # Single Score
        if isinstance(single_score, dict):
            formatted += f"""
- Overall Score: {single_score.get('value', 0):.4f} {single_score.get('unit', 'pt')}
- Methodology: {single_score.get('methodology', 'ISO 14044 with African Context')}
- Uncertainty Range: {single_score.get('uncertainty_range', [0, 0])}
"""
            if single_score.get('weighting_factors'):
                formatted += "\n### Weighting Factors:\n"
                for category, weight in single_score.get('weighting_factors', {}).items():
                    formatted += f"  - {category}: {weight * 100:.1f}%\n"
        else:
            formatted += f"- Overall Score: {single_score}\n"

        # Midpoint Impacts
        formatted += "\n## Midpoint Environmental Impacts\n"
        for category, impact in midpoint.items():
            if isinstance(impact, dict):
                formatted += f"- {category}: {impact.get('value', 0):.4f} {impact.get('unit', 'units')}\n"
                formatted += f"  - Data Quality Score: {impact.get('data_quality_score', 0):.2f}\n"
                formatted += f"  - Uncertainty Range: {impact.get('uncertainty_range', [0, 0])}\n"
            else:
                formatted += f"- {category}: {impact}\n"

        # Endpoint Impacts
        if endpoint:
            formatted += "\n## Endpoint Impact Categories\n"
            for category, impact in endpoint.items():
                if isinstance(impact, dict):
                    formatted += f"- {category}: {impact.get('value', 0):.4f} {impact.get('unit', 'pt')}\n"
                else:
                    formatted += f"- {category}: {impact}\n"

        # Crop/Food Breakdown
        if breakdown:
            formatted += "\n## Impact Breakdown by Crop/Food Product\n"
            for food_name, impacts in breakdown.items():
                formatted += f"\n### {food_name}\n"
                for category, impact in impacts.items():
                    if isinstance(impact, dict):
                        formatted += f"  - {category}: {impact.get('value', 0):.4f} {impact.get('unit', 'units')}\n"
                    else:
                        formatted += f"  - {category}: {impact}\n"

        # Data Quality
        formatted += "\n## Data Quality Assessment\n"
        if isinstance(data_quality, dict):
            formatted += f"- Overall Confidence: {data_quality.get('overall_confidence', 'Unknown')}\n"
            formatted += f"- Regional Adaptation: {data_quality.get('regional_adaptation', False)}\n"
            formatted += f"- Completeness Score: {data_quality.get('completeness_score', 0):.2f}\n"
            formatted += f"- Temporal Representativeness: {data_quality.get('temporal_representativeness', 0):.2f}\n"
            formatted += f"- Geographical Representativeness: {data_quality.get('geographical_representativeness', 0):.2f}\n"

            if data_quality.get('warnings'):
                formatted += "\n### Warnings:\n"
                for warning in data_quality.get('warnings', []):
                    formatted += f"  - {warning}\n"

        # Sensitivity Analysis
        if sensitivity:
            formatted += "\n## Sensitivity Analysis\n"
            if sensitivity.get('most_influential_parameters'):
                formatted += "\n### Most Influential Parameters:\n"
                for param in sensitivity.get('most_influential_parameters', []):
                    formatted += f"- {param.get('parameter_name', 'Unknown')}\n"
                    formatted += f"  - Influence: {param.get('influence_percentage', 0):.1f}%\n"
                    formatted += f"  - Improvement Potential: {param.get('improvement_potential', 0):.1f}%\n"

            if sensitivity.get('scenario_analysis'):
                formatted += "\n### Scenario Analysis:\n"
                for scenario in sensitivity.get('scenario_analysis', []):
                    formatted += f"\n#### {scenario.get('scenario_name', 'Unknown')}\n"
                    formatted += f"Description: {scenario.get('description', '')}\n"
                    formatted += "Impact Changes:\n"
                    for impact, change in scenario.get('impact_changes', {}).items():
                        formatted += f"  - {impact}: {change:+.1f}%\n"

        # Comparative Analysis
        if comparative:
            formatted += "\n## Comparative Analysis\n"

            if comparative.get('benchmark_comparisons'):
                formatted += "\n### Benchmark Comparisons:\n"
                for benchmark in comparative.get('benchmark_comparisons', []):
                    formatted += f"\n- {benchmark.get('benchmark_name', 'Unknown')}\n"
                    formatted += f"  - Your Performance: {benchmark.get('your_performance', 0):.4f}\n"
                    formatted += f"  - Benchmark Value: {benchmark.get('benchmark_value', 0):.4f}\n"
                    formatted += f"  - Difference: {benchmark.get('percentage_difference', 0):.1f}%\n"
                    formatted += f"  - Category: {benchmark.get('performance_category', 'Unknown')}\n"

            if comparative.get('best_practices'):
                formatted += "\n### Recommended Best Practices:\n"
                for practice in comparative.get('best_practices', []):
                    formatted += f"\n- {practice.get('practice_name', 'Unknown')}\n"
                    formatted += f"  - Description: {practice.get('description', '')}\n"
                    formatted += f"  - Implementation Difficulty: {practice.get('implementation_difficulty', 'Unknown')}\n"
                    formatted += f"  - Cost Category: {practice.get('cost_category', 'Unknown')}\n"

        # Recommendations
        if recommendations:
            formatted += "\n## System Recommendations\n"
            for rec in recommendations:
                formatted += f"\n### {rec.get('title', 'Recommendation')}\n"
                formatted += f"- Category: {rec.get('category', 'General')}\n"
                formatted += f"- Priority: {rec.get('priority', 'Medium')}\n"
                formatted += f"- Description: {rec.get('description', '')}\n"
                formatted += f"- Implementation Difficulty: {rec.get('implementation_difficulty', 'Unknown')}\n"
                formatted += f"- Cost Category: {rec.get('cost_category', 'Unknown')}\n"

        return formatted

    async def _generate_report_sections(
        self,
        formatted_data: str,
        report_type: str
    ) -> Dict[str, str]:
        """
        Use Claude to generate professional report sections
        """

        system_prompt = """You are a professional environmental sustainability consultant specializing in Life Cycle Assessment (LCA) and agricultural sustainability in Africa. Your task is to generate formal, comprehensive, and professional sustainability assessment reports that follow international standards (ISO 14044, ISO 14067).

Your reports should be:
1. **Professional and Formal**: Use technical terminology appropriately while remaining accessible
2. **Data-Driven**: Base all conclusions on the provided assessment data
3. **Actionable**: Provide specific, implementable recommendations
4. **Context-Aware**: Consider the African agricultural context, local conditions, and development priorities
5. **Standards-Compliant**: Reference ISO 14044, ISO 14067, and other relevant LCA standards
6. **Comprehensive**: Cover all aspects of environmental sustainability
7. **Objective**: Present findings without bias, acknowledging uncertainties

Format your reports in Markdown with clear sections and professional language suitable for stakeholders including farmers, agricultural extension officers, policymakers, and investors."""

        user_prompt = f"""Based on the following environmental sustainability assessment data, generate a comprehensive professional report.

{formatted_data}

Generate the following report sections:

1. **Executive Summary** (200-300 words)
   - High-level overview of the assessment
   - Key findings and overall environmental performance
   - Critical recommendations
   - Intended for decision-makers and executives

2. **Introduction** (150-200 words)
   - Purpose and scope of the assessment
   - Assessment methodology overview
   - Standards and frameworks used

3. **Assessment Methodology** (200-250 words)
   - Detailed explanation of the LCA methodology
   - System boundaries and functional units
   - Data quality and sources
   - Impact assessment methods used

4. **Environmental Impact Analysis** (400-500 words)
   - Detailed analysis of all environmental impact categories
   - Midpoint and endpoint impacts
   - Single score interpretation
   - Comparison with benchmarks and standards
   - Identification of environmental hotspots

5. **Comparative Performance Analysis** (300-400 words if data available)
   - Benchmarking against industry standards
   - Regional comparisons
   - Performance categorization
   - Strengths and areas for improvement

6. **Sensitivity and Uncertainty Analysis** (200-300 words if data available)
   - Key parameters affecting results
   - Uncertainty ranges and confidence levels
   - Scenario analysis results
   - Data quality implications

7. **Recommendations and Action Plan** (400-500 words)
   - Prioritized recommendations for environmental improvement
   - Specific actions with expected impact reductions
   - Implementation timeline and resource requirements
   - Cost-benefit considerations
   - Monitoring and verification strategies

8. **Conclusions** (200-250 words)
   - Summary of key findings
   - Environmental performance assessment
   - Future outlook and continuous improvement pathway

9. **Technical Appendix** (200-300 words)
   - Detailed impact calculation results
   - Data quality scores and sources
   - Assumptions and limitations
   - References to standards and methodologies

Please format each section with clear markdown headers (##) and use professional, technical language. Include specific numbers, percentages, and data from the assessment. Make the report suitable for formal presentation to stakeholders."""

        # Call Claude API
        response = self.client.messages.create(
            model=self.model,
            max_tokens=16000,  # Large token limit for comprehensive reports
            temperature=0.3,  # Low temperature for consistent, factual output
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )

        # Extract the generated report
        report_text = response.content[0].text

        # Parse sections from the response
        sections = self._parse_report_sections(report_text)

        return sections

    def _parse_report_sections(self, report_text: str) -> Dict[str, str]:
        """
        Parse the generated report into structured sections
        """
        sections = {}
        current_section = None
        current_content = []

        lines = report_text.split('\n')

        # Define section headers to look for
        section_headers = {
            "executive summary": "executive_summary",
            "introduction": "introduction",
            "assessment methodology": "methodology",
            "environmental impact analysis": "impact_analysis",
            "comparative performance analysis": "comparative_analysis",
            "sensitivity and uncertainty analysis": "sensitivity_analysis",
            "recommendations and action plan": "recommendations",
            "conclusions": "conclusions",
            "technical appendix": "technical_appendix"
        }

        for line in lines:
            # Check if this line is a section header
            line_lower = line.lower().strip()
            is_header = False

            for header_text, section_key in section_headers.items():
                if line_lower.startswith("##") and header_text in line_lower:
                    # Save previous section
                    if current_section:
                        sections[current_section] = '\n'.join(current_content).strip()

                    # Start new section
                    current_section = section_key
                    current_content = [line]  # Include the header
                    is_header = True
                    break

            if not is_header and current_section:
                current_content.append(line)

        # Save the last section
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()

        # If parsing failed, return the whole text as a single section
        if not sections:
            sections["full_report"] = report_text

        return sections

    async def generate_executive_summary(
        self,
        assessment_data: Dict[str, Any]
    ) -> str:
        """
        Generate a concise executive summary only
        """
        formatted_data = self._format_assessment_data(assessment_data)

        user_prompt = f"""Based on the following assessment data, generate a professional executive summary (200-300 words) suitable for decision-makers:

{formatted_data}

The summary should include:
- Overall environmental performance
- Key impact findings
- Critical recommendations
- Business implications

Use formal, professional language."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            temperature=0.3,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )

        return response.content[0].text

    async def generate_farmer_friendly_report(
        self,
        assessment_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Generate a simplified, farmer-friendly version of the report
        """
        formatted_data = self._format_assessment_data(assessment_data)

        system_prompt = """You are an agricultural extension officer who explains environmental sustainability to smallholder farmers in Africa. Your explanations are:
1. Simple and clear, avoiding technical jargon
2. Practical and actionable
3. Respectful of local farming practices
4. Focused on benefits to the farmer (improved yields, reduced costs, better soil health)
5. Using local context and examples"""

        user_prompt = f"""Based on this farm assessment data, create a simplified report that farmers can easily understand:

{formatted_data}

Generate these sections:
1. **What This Assessment Means for Your Farm** (simple language, 150 words)
2. **Your Farm's Environmental Performance** (key impacts explained simply, 200 words)
3. **Practical Steps You Can Take** (specific, actionable recommendations, 300 words)
4. **Expected Benefits** (improved productivity, cost savings, environmental benefits, 150 words)

Use simple language, local examples, and focus on practical actions."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            temperature=0.4,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )

        report_text = response.content[0].text
        sections = self._parse_report_sections(report_text)

        return sections
