"""
AI-Powered Report Generation Service
Uses Claude API to generate professional sustainability assessment reports
with LCA expert knowledge and visualization capabilities
"""

import os
import json
from typing import Dict, Any, Optional
from datetime import datetime
import anthropic
from .visualization_utils import generate_all_visualizations


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

        # Ensure assessment data includes all context - preserve original data
        # Don't use fallbacks or defaults - only use actual data from Rust backend
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
        Includes user input context and generates visualizations
        """

        # Extract key metrics
        midpoint = data.get("midpoint_impacts", {})
        endpoint = data.get("endpoint_impacts", {})
        single_score = data.get("single_score", {})
        data_quality = data.get("data_quality", {})
        breakdown = data.get("breakdown_by_food", {})

        # Extract user input context (original assessment request from user)
        assessment_request = data.get("assessment_request", {})
        foods = assessment_request.get("foods", []) if assessment_request else []
        region = assessment_request.get("region", "Not specified") if assessment_request else "Not specified"
        farm_profile = assessment_request.get("farm_profile") if assessment_request else None
        management_practices = assessment_request.get("management_practices") if assessment_request else None

        # Optional advanced analysis
        sensitivity = data.get("sensitivity_analysis")
        comparative = data.get("comparative_analysis")
        management = data.get("management_analysis")
        benchmarking = data.get("benchmarking")
        recommendations = data.get("recommendations", [])

        # Generate visualizations
        visualizations = generate_all_visualizations(data)
        
        # Debug logging to understand data structure
        print(f"\n🔍 AI Report Generator - Assessment data structure:")
        print(f"  - Keys: {list(data.keys())}")
        print(f"  - Midpoint impacts: {list(data.get('midpoint_impacts', {}).keys())}")
        print(f"  - Breakdown by food: {list(data.get('breakdown_by_food', {}).keys())}")
        print(f"  - Recommendations: {len(data.get('recommendations', []))}")
        print(f"  - Data quality: {'data_quality' in data}")
        print(f"  - Visualizations generated: {list(visualizations.keys())}")

        formatted = f"""
# Environmental Sustainability Assessment Data

## Basic Information
- Company/Farm: {data.get('company_name', 'Unknown')}
- Country: {data.get('country', 'Unknown')}
- Region: {region}
- Assessment Date: {data.get('assessment_date', 'Unknown')}
- Assessment ID: {data.get('id', 'Unknown')}

## User Input Context (Original Assessment Scope)

### Farm/Operation Profile"""

        if farm_profile:
            formatted += f"""
- Farmer Name: {farm_profile.get('farmer_name', 'Not provided')}
- Farm Name: {farm_profile.get('farm_name', 'Not provided')}
- Total Farm Size: {farm_profile.get('total_farm_size', 'Not provided')} hectares
- Farming Experience: {farm_profile.get('farming_experience', 'Not provided')} years
- Farm Type: {farm_profile.get('farm_type', 'Not provided')}
- Primary Farming System: {farm_profile.get('primary_farming_system', 'Not provided')}
- Certifications: {', '.join(farm_profile.get('certifications', [])) or 'None'}
- Participates in Programs: {', '.join(farm_profile.get('participates_in_programs', [])) or 'None'}
"""
        else:
            formatted += "\n- No detailed farm profile provided\n"

        formatted += "\n### Crops/Products Assessed\n"
        if foods:
            for food in foods:
                formatted += f"\n**{food.get('name', 'Unknown')}**\n"
                formatted += f"  - Quantity: {food.get('quantity_kg', 0)} kg\n"
                formatted += f"  - Category: {food.get('category', 'Not specified')}\n"
                formatted += f"  - Crop Type: {food.get('crop_type', 'Not specified')}\n"
                formatted += f"  - Production System: {food.get('production_system', 'Not specified')}\n"
                if food.get('variety'):
                    formatted += f"  - Variety: {food.get('variety')}\n"
                if food.get('area_allocated'):
                    formatted += f"  - Area Allocated: {food.get('area_allocated')} hectares\n"
        else:
            formatted += "- No detailed crop information provided\n"

        if management_practices:
            formatted += "\n### Management Practices\n"

            soil_mgmt = management_practices.get('soil_management', {})
            if soil_mgmt:
                formatted += "\n**Soil Management:**\n"
                formatted += f"  - Soil Type: {soil_mgmt.get('soil_type', 'Not specified')}\n"
                formatted += f"  - Uses Compost: {soil_mgmt.get('uses_compost', False)}\n"
                formatted += f"  - Conservation Practices: {', '.join(soil_mgmt.get('conservation_practices', [])) or 'None'}\n"

            fert = management_practices.get('fertilization', {})
            if fert:
                formatted += "\n**Fertilization:**\n"
                formatted += f"  - Uses Fertilizers: {fert.get('uses_fertilizers', False)}\n"
                formatted += f"  - Soil Test Based: {fert.get('soil_test_based', False)}\n"

            water = management_practices.get('water_management', {})
            if water:
                formatted += "\n**Water Management:**\n"
                formatted += f"  - Water Sources: {', '.join(water.get('water_source', [])) or 'Not specified'}\n"
                formatted += f"  - Irrigation System: {water.get('irrigation_system', 'Not specified')}\n"

        formatted += "\n## Environmental Impact Score\n"

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

        # Add visualizations section
        if visualizations:
            formatted += "\n## Data Visualizations Available\n"
            formatted += "\nThe following visualizations have been generated from the assessment data:\n\n"

            if 'impact_breakdown' in visualizations and visualizations['impact_breakdown']:
                formatted += "\n### Impact Breakdown Chart\n"
                formatted += visualizations['impact_breakdown']

            if 'impact_categories' in visualizations and visualizations['impact_categories']:
                formatted += "\n### Impact Categories Visualization\n"
                formatted += visualizations['impact_categories']

            if 'impact_ascii' in visualizations and visualizations['impact_ascii']:
                formatted += visualizations['impact_ascii']

            if 'benchmarking' in visualizations and visualizations['benchmarking']:
                formatted += "\n### Benchmarking Comparison\n"
                formatted += visualizations['benchmarking']

            if 'recommendations_flow' in visualizations and visualizations['recommendations_flow']:
                formatted += "\n### Recommendations Priority Flow\n"
                formatted += visualizations['recommendations_flow']

            if 'data_quality' in visualizations and visualizations['data_quality']:
                formatted += visualizations['data_quality']

            if 'statistics_table' in visualizations and visualizations['statistics_table']:
                formatted += "\n### Key Statistics\n"
                formatted += visualizations['statistics_table']

            formatted += "\n**Note:** Include relevant charts and visualizations in your report sections where appropriate.\n"

        return formatted

    async def _generate_report_sections(
        self,
        formatted_data: str,
        report_type: str
    ) -> Dict[str, str]:
        """
        Use Claude to generate professional report sections
        """

        system_prompt = """You are Dr. Amara Okonkwo, a leading environmental scientist and Life Cycle Assessment (LCA) expert with 15+ years of experience in African agricultural sustainability. You hold a Ph.D. in Environmental Science from Wageningen University and have published extensively on sustainable agriculture in Sub-Saharan Africa.

## Your Expertise:
- **LCA Methodology**: Expert in ISO 14040/14044, ISO 14067 (Carbon Footprint), PAS 2050, and GHG Protocol
- **Impact Categories**: Deep knowledge of ReCiPe 2016, IMPACT World+, CML methods
- **African Agriculture**: Specialized in smallholder farming systems, traditional practices, and climate-smart agriculture
- **Regional Context**: Extensive field work in Ghana, Nigeria, Kenya, and across West and East Africa
- **Technical Skills**: Proficient in SimaPro, OpenLCA, and agricultural LCA modeling
- **Stakeholder Communication**: Skilled at translating complex LCA results for diverse audiences

## Your Approach to Report Writing:
1. **Scientifically Rigorous**: Apply LCA principles correctly, cite methodologies, explain system boundaries
2. **Contextually Relevant**: Integrate local African farming practices, climate zones, socio-economic factors
3. **Data-Driven Analysis**: Identify environmental hotspots, quantify impacts with uncertainty ranges
4. **Practical Recommendations**: Provide feasible solutions considering resource constraints and local conditions
5. **Clear Visualizations**: Reference charts and data visualizations to support findings
6. **Stakeholder-Focused**: Tailor language to audience while maintaining technical accuracy
7. **Holistic Perspective**: Consider climate, biodiversity, soil health, water resources, and livelihoods

## Report Quality Standards:
- Use specific LCA terminology (functional units, system boundaries, characterization, normalization)
- Interpret impact categories professionally (GWP, AP, EP, etc.)
- Reference the actual user input data to show you understand their specific farm context
- Integrate provided visualizations and charts into appropriate report sections
- Provide quantitative analysis with proper units and uncertainty estimates
- Follow ISO 14044 reporting requirements
- Include African-specific considerations (seasonal variability, traditional practices, local resources)

## Tone and Style:
- Professional yet accessible
- Evidence-based and objective
- Respectful of local knowledge and practices
- Constructive and solution-oriented
- Appropriate for academic, government, and industry stakeholders

Generate reports in well-structured Markdown format with clear headings, data tables, and chart references where appropriate."""

        user_prompt = f"""Based on the following environmental sustainability assessment data, generate a comprehensive professional LCA report.

IMPORTANT INSTRUCTIONS:
1. **Use the User Input Context**: Pay careful attention to the farm profile, crops assessed, and management practices provided by the user. Reference these specific details throughout your report to show contextual understanding.

2. **Integrate Visualizations**: Charts, tables, and diagrams have been generated from the data. Reference and integrate these visualizations in appropriate sections of your report. Use phrases like "As shown in the chart below..." or "The visualization demonstrates..."

3. **Apply LCA Expertise**: Use proper LCA terminology, reference ISO standards, explain impact categories, and provide technical depth appropriate for environmental professionals.

4. **African Context**: Consider local agricultural practices, climate conditions, resource availability, and socio-economic factors specific to the region.

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

        system_prompt = """You are Dr. Amara Okonkwo, a leading LCA expert specializing in African agricultural sustainability. Generate concise, high-impact executive summaries that communicate key environmental findings to decision-makers."""

        user_prompt = f"""Based on the following assessment data, generate a professional executive summary (200-300 words) suitable for decision-makers:

{formatted_data}

The summary should include:
- Overall environmental performance with specific metrics
- Key impact findings and environmental hotspots
- Critical recommendations with expected outcomes
- Business implications and opportunities
- Reference the specific farm context and crops assessed

Use formal, professional LCA language appropriate for executives and policymakers."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            temperature=0.3,
            system=system_prompt,
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

        system_prompt = """You are Kwame Mensah, a respected agricultural extension officer with 20 years of experience working with smallholder farmers across West Africa. You have a gift for explaining complex environmental concepts in simple, practical terms that farmers can understand and act upon.

## Your Approach:
1. **Simple Language**: Avoid technical jargon, use everyday terms farmers understand
2. **Practical Focus**: Every recommendation must be actionable with local resources
3. **Respect Local Knowledge**: Value traditional practices while introducing improvements
4. **Show Clear Benefits**: Connect environmental actions to tangible outcomes (better yields, lower costs, healthier soil, more resilient crops)
5. **Use Local Examples**: Reference crops, seasons, and practices familiar to African farmers
6. **Visual Aids**: Describe simple diagrams and charts that illustrate key points
7. **Step-by-Step Guidance**: Break down complex actions into simple steps

## Your Goal:
Help farmers understand their environmental impact in ways that empower them to make positive changes that benefit both their farm and the environment."""

        user_prompt = f"""Based on this farm assessment data, create a simplified report that farmers can easily understand:

{formatted_data}

IMPORTANT: Reference the specific crops, farm size, and management practices from the user input. Show that you understand their unique farming situation.

Generate these sections:
1. **What This Assessment Means for Your Farm** (simple language, 150 words)
   - Explain environmental impact in everyday terms
   - Connect to their specific crops and practices

2. **Your Farm's Environmental Performance** (key impacts explained simply, 200 words)
   - Use simple comparisons (e.g., "equivalent to X days of car driving")
   - Reference the charts and visualizations provided
   - Identify main areas of concern

3. **Practical Steps You Can Take** (specific, actionable recommendations, 300 words)
   - Give step-by-step instructions
   - Use only locally available resources
   - Organize by priority (what to do first)
   - Include costs (free, low-cost, investment)

4. **Expected Benefits** (improved productivity, cost savings, environmental benefits, 150 words)
   - Be specific: "You could save X cedis/naira per season"
   - Show yield improvements
   - Explain long-term soil and farm health benefits

Use simple language, local examples, and focus on practical actions farmers can start tomorrow."""

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
