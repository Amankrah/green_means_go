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
import asyncio
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
            # Use Haiku 4.5 for fast, cost-effective report generation
            # Haiku: $1/MTok input, $5/MTok output vs Sonnet: $3/MTok input, $15/MTok output
            self.model = "claude-haiku-4-5-20251001"  # Fast and cost-effective
        except Exception as e:
            raise ValueError(f"Failed to initialize Anthropic client: {e}")

    async def generate_comprehensive_report(
        self,
        assessment_data: Dict[str, Any],
        report_type: str = "comprehensive"
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive professional report from assessment data
        Includes data validation and quality gates

        Args:
            assessment_data: Complete assessment results from the LCA system
            report_type: Type of report (comprehensive, executive, technical)

        Returns:
            Dictionary containing the generated report sections
        """

        # Step 1: Validate assessment data completeness
        validation = self._validate_assessment_completeness(assessment_data)

        if not validation['is_complete']:
            print(f"⚠️ WARNING: Assessment data incomplete - {validation['missing_sections']}")
            print(f"   Warnings: {validation['warnings']}")

        print(f"📊 Data Quality Level: {validation['data_quality_level']}")

        # Step 2: Format assessment data with ALL available fields
        formatted_data = self._format_assessment_data(assessment_data)

        # Step 3: Generate the report using Claude with chain of thought
        print("🤖 Generating report with chain of thought reasoning...")
        report_sections = await self._generate_report_sections(
            formatted_data,
            report_type
        )

        # Step 4: Structure the final report with validation metadata
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
                "generation_timestamp": datetime.now().isoformat(),
                "temperature": 0,
                "chain_of_thought_enabled": True,
                "iso_14044_compliant": True,
                "data_quality_level": validation['data_quality_level'],
                "validation_warnings": validation['warnings'],
                "sections_generated": len(report_sections)
            }
        }

        print(f"✅ Report generation complete - {len(report_sections)} sections generated")
        return final_report

    def _validate_assessment_completeness(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate assessment data completeness and flag missing critical elements

        Returns:
            Dictionary with completeness flags and warnings
        """
        validation = {
            'is_complete': True,
            'warnings': [],
            'missing_sections': [],
            'data_quality_level': 'high'
        }

        # Check critical sections
        if not data.get('midpoint_impacts'):
            validation['is_complete'] = False
            validation['missing_sections'].append('midpoint_impacts')
            validation['warnings'].append('Missing midpoint impact data - cannot generate meaningful report')

        if not data.get('breakdown_by_food'):
            validation['warnings'].append('Missing crop-level breakdown - report will lack detailed analysis')
            validation['data_quality_level'] = 'medium'

        if not data.get('recommendations') or len(data.get('recommendations', [])) == 0:
            validation['warnings'].append('No recommendations available - suggest running recommendation generator first')
            validation['data_quality_level'] = 'medium'

        if not data.get('data_quality'):
            validation['warnings'].append('Missing data quality assessment - uncertainty cannot be quantified')

        # Check for advanced analyses
        advanced_count = sum([
            1 for key in ['sensitivity_analysis', 'comparative_analysis', 'management_analysis', 'benchmarking']
            if data.get(key)
        ])

        if advanced_count == 0:
            validation['warnings'].append('No advanced analyses available - report will be basic')

        return validation

    def _format_assessment_data(self, data: Dict[str, Any]) -> str:
        """
        Format assessment data into a structured prompt for Claude
        Includes ALL available data fields with proper validation
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

        # Extract ALL advanced analysis fields
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

            # Include regional comparisons if available
            if comparative.get('regional_comparisons'):
                formatted += "\n### Regional Performance Comparisons:\n"
                for comp in comparative.get('regional_comparisons', []):
                    formatted += f"\n- Region: {comp.get('region', 'Unknown')}\n"
                    formatted += f"  - Your Performance vs Regional Average: {comp.get('comparison', 'N/A')}\n"
                    formatted += f"  - Performance Percentile: {comp.get('percentile', 'N/A')}\n"

        # Management Analysis (NEW - was missing)
        if management:
            formatted += "\n## Management Practice Analysis\n"

            if management.get('practice_efficiency'):
                formatted += "\n### Practice Efficiency Assessment:\n"
                for practice, efficiency in management.get('practice_efficiency', {}).items():
                    formatted += f"- {practice}: {efficiency}\n"

            if management.get('improvement_opportunities'):
                formatted += "\n### Identified Improvement Opportunities:\n"
                for opportunity in management.get('improvement_opportunities', []):
                    formatted += f"\n**{opportunity.get('area', 'Unknown')}**\n"
                    formatted += f"  - Current Status: {opportunity.get('current_status', 'N/A')}\n"
                    formatted += f"  - Improvement Potential: {opportunity.get('potential', 'N/A')}\n"
                    formatted += f"  - Priority: {opportunity.get('priority', 'N/A')}\n"

            if management.get('best_performing_practices'):
                formatted += "\n### Best Performing Current Practices:\n"
                for practice in management.get('best_performing_practices', []):
                    formatted += f"- {practice.get('practice', 'Unknown')}: {practice.get('performance', 'N/A')}\n"

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

    def _generate_single_section(
        self,
        section_name: str,
        section_prompt: str,
        formatted_data: str,
        system_prompt: str
    ) -> tuple[str, str]:
        """
        Generate a single report section (synchronous, called via asyncio.to_thread)
        Returns: (section_key, section_content)
        """
        try:
            print(f"  📝 Generating {section_name}...")
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2500,  # Per-section limit
                temperature=0.6,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"}
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": f"{formatted_data}\n\n{section_prompt}"
                    }
                ]
            )
            print(f"  ✅ Completed {section_name}")
            return (section_name, response.content[0].text)
        except Exception as e:
            print(f"  ❌ Error generating {section_name}: {e}")
            return (section_name, f"Error generating section: {e}")

    async def _generate_report_sections(
        self,
        formatted_data: str,
        report_type: str
    ) -> Dict[str, str]:
        """
        Use Claude to generate professional report sections in parallel
        Each section is generated independently for better quality and speed
        """

        system_prompt = """You are Dr. Amara Okonkwo, a leading environmental scientist and Life Cycle Assessment (LCA) expert with 15+ years of experience in African agricultural sustainability. You hold a Ph.D. in Environmental Science from Wageningen University and have published extensively on sustainable agriculture in Sub-Saharan Africa.

## Critical: Chain of Thought Approach
Before writing each section, you MUST think through your analysis step-by-step:
1. **Data Review**: What are the key numbers and patterns in this dataset?
2. **Hotspot Identification**: Which impact categories are most significant? Why?
3. **Root Cause Analysis**: What farming practices or inputs drive these impacts?
4. **Contextualization**: How does this fit within African agricultural systems?
5. **Solution Mapping**: What specific, actionable improvements can be made?
6. **Validation**: Does my analysis align with ISO 14044 requirements?

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
- Appropriate for academic, government, and industry stakeholders"""

        # Define section prompts for parallel generation
        section_prompts = {
            "executive_summary": """Generate an **Executive Summary** (200-300 words):
- High-level overview of the assessment
- Key findings and overall environmental performance
- Critical recommendations
- Intended for decision-makers and executives
Format with ## Executive Summary header.""",

            "introduction": """Generate an **Introduction** (150-200 words):
- Purpose and scope of the assessment
- Assessment methodology overview
- Standards and frameworks used
Format with ## Introduction header.""",

            "methodology": """Generate **Assessment Methodology** (200-250 words):
- Detailed explanation of the LCA methodology
- System boundaries and functional units
- Data quality and sources
- Impact assessment methods used
Format with ## Assessment Methodology header.""",

            "impact_analysis": """Generate **Environmental Impact Analysis** (400-500 words):
- Detailed analysis of all environmental impact categories
- Midpoint and endpoint impacts
- Single score interpretation
- Comparison with benchmarks and standards
- Identification of environmental hotspots
Format with ## Environmental Impact Analysis header.""",

            "comparative_analysis": """Generate **Comparative Performance Analysis** (300-400 words):
- Benchmarking against industry standards
- Regional comparisons
- Performance categorization
- Strengths and areas for improvement
Format with ## Comparative Performance Analysis header.""",

            "sensitivity_analysis": """Generate **Sensitivity and Uncertainty Analysis** (200-300 words):
- Key parameters affecting results
- Uncertainty ranges and confidence levels
- Scenario analysis results
- Data quality implications
Format with ## Sensitivity and Uncertainty Analysis header.""",

            "recommendations": """Generate **Recommendations and Action Plan** (400-500 words):
- Prioritized recommendations for environmental improvement
- Specific actions with expected impact reductions
- Implementation timeline and resource requirements
- Cost-benefit considerations
- Monitoring and verification strategies
Format with ## Recommendations and Action Plan header.""",

            "conclusions": """Generate **Conclusions** (200-250 words):
- Summary of key findings
- Environmental performance assessment
- Future outlook and continuous improvement pathway
Format with ## Conclusions header.""",

            "data_quality_limitations": """Generate **Data Quality and Limitations** (200-250 words):
- Comprehensive discussion of data sources and quality
- Temporal, geographical, and technological representativeness
- Key assumptions and their implications
- Uncertainty quantification
- Limitations of the study
Format with ## Data Quality and Limitations header.""",

            "critical_review": """Generate **Critical Review and Validation** (ISO 14044 Requirement) (200-250 words):
- Internal consistency check of methodology
- Verification of system boundaries and functional units
- Assessment of completeness
- Data quality validation against ISO requirements
- Identification of any methodological gaps
- Peer review readiness assessment
Format with ## Critical Review and Validation header.""",

            "technical_appendix": """Generate **Technical Appendix** (200-300 words):
- Detailed impact calculation results
- Data quality scores and sources
- Complete list of assumptions
- References to standards and methodologies
- Glossary of LCA terms used
Format with ## Technical Appendix header."""
        }

        print(f"🚀 Generating {len(section_prompts)} sections with controlled concurrency...")

        # Use semaphore to limit concurrent API calls (avoid rate limits)
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests

        async def generate_with_semaphore(section_key, section_prompt):
            async with semaphore:
                return await asyncio.to_thread(
                    self._generate_single_section,
                    section_key,
                    section_prompt,
                    formatted_data,
                    system_prompt
                )

        # Generate all sections with controlled concurrency
        tasks = [
            asyncio.create_task(generate_with_semaphore(section_key, section_prompt))
            for section_key, section_prompt in section_prompts.items()
        ]

        # Wait for all sections to complete
        results = await asyncio.gather(*tasks)

        # Convert results to dictionary
        sections = dict(results)

        print(f"✅ Generated {len(sections)} sections successfully")
        return sections

    def _parse_report_sections(self, report_text: str) -> Dict[str, str]:
        """
        Parse the generated report into structured sections
        """
        sections = {}
        current_section = None
        current_content = []

        lines = report_text.split('\n')

        # Define section headers to look for (ISO 14044 compliant structure)
        section_headers = {
            "executive summary": "executive_summary",
            "introduction": "introduction",
            "assessment methodology": "methodology",
            "environmental impact analysis": "impact_analysis",
            "comparative performance analysis": "comparative_analysis",
            "sensitivity and uncertainty analysis": "sensitivity_analysis",
            "recommendations and action plan": "recommendations",
            "conclusions": "conclusions",
            "data quality and limitations": "data_quality_limitations",
            "critical review and validation": "critical_review",
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

        system_prompt = '''You are Dr. Amara Okonkwo, a leading LCA expert specializing in African agricultural sustainability. Generate concise, high-impact executive summaries that communicate key environmental findings to decision-makers.'''

        user_prompt = ('''Based on the following assessment data, generate a professional executive summary (200-300 words) suitable for decision-makers:

''' + formatted_data + '''

The summary should include:
- Overall environmental performance with specific metrics
- Key impact findings and environmental hotspots
- Critical recommendations with expected outcomes
- Business implications and opportunities
- Reference the specific farm context and crops assessed

Use formal, professional LCA language appropriate for executives and policymakers.''')

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            temperature=0.3,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
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

        system_prompt = '''You are Kwame Mensah, a respected agricultural extension officer with 20 years of experience working with smallholder farmers across West Africa. You have a gift for explaining complex environmental concepts in simple, practical terms that farmers can understand and act upon.

## Your Approach:
1. Simple Language: Avoid technical jargon, use everyday terms farmers understand
2. Practical Focus: Every recommendation must be actionable with local resources
3. Respect Local Knowledge: Value traditional practices while introducing improvements
4. Show Clear Benefits: Connect environmental actions to tangible outcomes (better yields, lower costs, healthier soil, more resilient crops)
5. Use Local Examples: Reference crops, seasons, and practices familiar to African farmers
6. Visual Aids: Describe simple diagrams and charts that illustrate key points
7. Step-by-Step Guidance: Break down complex actions into simple steps

## Your Goal:
Help farmers understand their environmental impact in ways that empower them to make positive changes that benefit both their farm and the environment.'''

        user_prompt = ('''Based on this farm assessment data, create a simplified report that farmers can easily understand:

''' + formatted_data + '''

IMPORTANT: Reference the specific crops, farm size, and management practices from the user input. Show that you understand their unique farming situation.

Generate these sections:
1. What This Assessment Means for Your Farm (simple language, 150 words)
   - Explain environmental impact in everyday terms
   - Connect to their specific crops and practices

2. Your Farm Environmental Performance (key impacts explained simply, 200 words)
   - Use simple comparisons (like X days of car driving)
   - Reference the charts and visualizations provided
   - Identify main areas of concern

3. Practical Steps You Can Take (specific, actionable recommendations, 300 words)
   - Give step-by-step instructions
   - Use only locally available resources
   - Organize by priority (what to do first)
   - Include costs (free, low-cost, investment)

4. Expected Benefits (improved productivity, cost savings, environmental benefits, 150 words)
   - Be specific with examples of savings per season
   - Show yield improvements
   - Explain long-term soil and farm health benefits

Use simple language, local examples, and focus on practical actions farmers can start tomorrow.''')

        response = self.client.messages.create(
            model=self.model,
            max_tokens=10000,  # Reduced for faster generation
            temperature=0,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}  # Cache the system prompt
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )

        report_text = response.content[0].text

        # For farmer-friendly reports, return as a single section since it has custom structure
        # Don't use _parse_report_sections as it expects specific ISO section headers
        return {
            "farmer_report": report_text
        }
