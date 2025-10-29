"""
Report Generation API Routes
Professional AI-powered sustainability report generation endpoints
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ai_report_generator import AIReportGenerator

# Create router for report endpoints
router = APIRouter(prefix="/reports", tags=["reports"])

# Initialize AI Report Generator
try:
    report_generator = AIReportGenerator()
except ValueError as e:
    print(f"WARNING: AI Report Generator not initialized: {e}")
    print("Set ANTHROPIC_API_KEY environment variable to enable AI report generation")
    report_generator = None

# Global storage for generated reports (in production, use a proper database)
reports_db: Dict[str, Dict[str, Any]] = {}


def generate_data_driven_recommendations(assessment_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate recommendations based ONLY on actual assessment impact data
    No defaults, no abstractions - purely data-driven

    Args:
        assessment_data: Actual assessment results from Rust backend

    Returns:
        Assessment data with data-driven recommendations added
    """
    if not assessment_data:
        return assessment_data

    enhanced_data = assessment_data.copy()
    midpoint = enhanced_data.get('midpoint_impacts', {})

    if not midpoint:
        # No impact data = no recommendations possible
        enhanced_data['recommendations'] = []
        return enhanced_data

    recommendations = []

    # Extract impact values and sort by magnitude
    impact_analysis = []
    for category, impact in midpoint.items():
        try:
            if isinstance(impact, dict):
                value = impact.get('value', 0)
                unit = impact.get('unit', 'units')
            elif isinstance(impact, (int, float)):
                value = impact
                unit = 'units'
            else:
                continue

            if value > 0:  # Only process non-zero impacts
                impact_analysis.append({
                    'category': category,
                    'value': value,
                    'unit': unit
                })
        except Exception as e:
            print(f"Warning: Error analyzing impact {category}: {e}")
            continue

    # Sort by value (highest impacts first)
    impact_analysis.sort(key=lambda x: x['value'], reverse=True)

    # Generate recommendations for top 3-5 impact categories based on actual data
    # Build a map of impact data for easy lookup
    impact_map = {item['category']: item for item in impact_analysis}

    impact_recommendations_templates = {
        'Global warming': {
            'title': 'Reduce Carbon Footprint from Agricultural Operations',
            'description_template': "Your assessment shows {value:.2f} {unit} of greenhouse gas emissions. Consider adopting practices like reduced tillage, optimizing fertilizer use, and using cover crops to sequester carbon.",
            'category': 'Climate Action',
            'priority': 'high',
            'implementation_difficulty': 'Medium',
            'cost_category': 'Low to Medium'
        },
        'Water consumption': {
            'title': 'Optimize Water Use Efficiency',
            'description_template': "Water consumption is {value:.2f} {unit}. Implement drip irrigation, rainwater harvesting, and water-efficient crops to reduce water usage.",
            'category': 'Water Management',
            'priority': 'high',
            'implementation_difficulty': 'Medium',
            'cost_category': 'Medium'
        },
        'Land use': {
            'title': 'Improve Land Use Efficiency',
            'description_template': "Land use impact is {value:.2f} {unit}. Consider intensifying production sustainably through crop rotation, intercropping, and improved varieties to reduce land footprint per unit output.",
            'category': 'Land Management',
            'priority': 'medium',
            'implementation_difficulty': 'Medium',
            'cost_category': 'Low to Medium'
        },
        'Terrestrial acidification': {
            'title': 'Reduce Acidification from Fertilizers',
            'description_template': "Acidification impact is {value:.2f} {unit}. Use precision fertilization, switch to organic amendments, and apply lime to buffer soil pH.",
            'category': 'Soil Health',
            'priority': 'medium',
            'implementation_difficulty': 'Low',
            'cost_category': 'Low'
        },
        'Freshwater eutrophication': {
            'title': 'Prevent Nutrient Runoff',
            'description_template': "Eutrophication risk is {value:.2f} {unit}. Implement buffer strips, reduce fertilizer application, and use slow-release fertilizers to minimize nutrient leaching.",
            'category': 'Water Quality',
            'priority': 'high',
            'implementation_difficulty': 'Medium',
            'cost_category': 'Low to Medium'
        },
        'Biodiversity loss': {
            'title': 'Enhance On-Farm Biodiversity',
            'description_template': "Biodiversity impact is {value:.2f} {unit}. Create wildlife corridors, maintain diverse crop rotations, and preserve natural habitats on farm boundaries.",
            'category': 'Ecosystem Protection',
            'priority': 'medium',
            'implementation_difficulty': 'Medium',
            'cost_category': 'Low'
        },
        'Soil degradation': {
            'title': 'Prevent Soil Degradation',
            'description_template': "Soil degradation risk is {value:.2f} {unit}. Implement conservation tillage, maintain soil cover, and use organic amendments to improve soil health.",
            'category': 'Soil Health',
            'priority': 'high',
            'implementation_difficulty': 'Medium',
            'cost_category': 'Low'
        }
    }

    # Add recommendations for top impact categories (up to 5)
    for impact in impact_analysis[:5]:
        category = impact['category']
        if category in impact_recommendations_templates:
            template = impact_recommendations_templates[category]
            rec = {
                'title': template['title'],
                'description': template['description_template'].format(
                    value=impact['value'],
                    unit=impact['unit']
                ),
                'category': template['category'],
                'priority': template['priority'],
                'implementation_difficulty': template['implementation_difficulty'],
                'cost_category': template['cost_category']
            }
            recommendations.append(rec)

    # If we have fewer than 3 recommendations, add a general one
    if len(recommendations) < 3:
        recommendations.append({
            'title': 'Implement Integrated Farm Management',
            'description': f"Your assessment identified multiple environmental impact areas. Consider adopting an integrated approach combining soil conservation, water management, and biodiversity enhancement for comprehensive sustainability improvement.",
            'category': 'General',
            'priority': 'medium',
            'implementation_difficulty': 'Medium',
            'cost_category': 'Medium'
        })

    enhanced_data['recommendations'] = recommendations
    return enhanced_data


def enhance_assessment_data_for_reporting(assessment_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance assessment data to ensure it has the required structure for report generation
    
    Args:
        assessment_data: Original assessment data
        
    Returns:
        Enhanced assessment data with fallback values
    """
    if not assessment_data:
        print("⚠️ Warning: No assessment data provided to enhance")
        return {}
    
    try:
        enhanced_data = assessment_data.copy()
        
        # Ensure breakdown_by_food exists - create from request data if possible
        breakdown = enhanced_data.get('breakdown_by_food')
        if not breakdown or len(breakdown) == 0:
            print("🔧 Creating breakdown_by_food from assessment request data...")
            enhanced_data['breakdown_by_food'] = {}
            
            # Try to extract from assessment_request if available
            assessment_request = enhanced_data.get('assessment_request', {})
            foods = assessment_request.get('foods', [])
            midpoint = enhanced_data.get('midpoint_impacts', {})
            
            if foods and midpoint:
                # Distribute total impacts across crops proportionally
                total_production = sum(food.get('quantity_kg', 0) for food in foods if food.get('quantity_kg'))
                
                for food in foods:
                    food_name = food.get('name', 'Unknown Crop')
                    quantity = food.get('quantity_kg', 0)
                    proportion = quantity / total_production if total_production > 0 else 1.0 / len(foods)
                    
                    # Create crop-specific impacts
                    food_impacts = {}
                    for category, impact_data in midpoint.items():
                        try:
                            if isinstance(impact_data, dict):
                                value = impact_data.get('value', 0) * proportion
                                food_impacts[category] = {
                                    'value': value,
                                    'unit': impact_data.get('unit', 'units')
                                }
                            else:
                                food_impacts[category] = {
                                    'value': impact_data * proportion if isinstance(impact_data, (int, float)) else 0,
                                    'unit': 'units'
                                }
                        except Exception as e:
                            print(f"Warning: Error processing impact {category}: {e}")
                            food_impacts[category] = {'value': 0, 'unit': 'units'}
                    
                    enhanced_data['breakdown_by_food'][food_name] = food_impacts
        
        # Ensure recommendations exist - create basic ones if missing
        recommendations = enhanced_data.get('recommendations')
        if not recommendations or len(recommendations) == 0:
            print("🔧 Creating fallback recommendations...")
            enhanced_data['recommendations'] = []
            
            midpoint = enhanced_data.get('midpoint_impacts', {})
            if midpoint:
                try:
                    # Create recommendations based on highest impacts
                    sorted_impacts = []
                    for category, impact in midpoint.items():
                        try:
                            if isinstance(impact, dict):
                                value = impact.get('value', 0)
                            elif isinstance(impact, (int, float)):
                                value = impact
                            else:
                                value = 0
                            sorted_impacts.append((category, value))
                        except Exception as e:
                            print(f"Warning: Error processing impact {category}: {e}")
                            continue
                    
                    sorted_impacts.sort(key=lambda x: x[1], reverse=True)
                    
                    priorities = ['high', 'medium', 'low']
                    for i, (category, _) in enumerate(sorted_impacts[:3]):
                        clean_category = category.replace('_', ' ').replace('Change', '').strip()
                        enhanced_data['recommendations'].append({
                            'title': f"Reduce {clean_category} Impact",
                            'priority': priorities[i] if i < len(priorities) else 'low',
                            'category': 'Environmental',
                            'description': f"Implement practices to reduce {clean_category.lower()} through improved farming techniques",
                            'implementation_difficulty': 'Medium',
                            'cost_category': 'Low to Medium'
                        })
                except Exception as e:
                    print(f"Warning: Error creating recommendations: {e}")
                    enhanced_data['recommendations'] = []
        
        # Ensure data_quality exists
        if not enhanced_data.get('data_quality'):
            print("🔧 Creating fallback data quality metrics...")
            enhanced_data['data_quality'] = {
                'overall_confidence': 'Medium',
                'completeness_score': 0.7,
                'temporal_representativeness': 0.8,
                'geographical_representativeness': 0.7,
                'technological_representativeness': 0.6,
                'warnings': ['Some data points estimated based on regional averages']
            }
        
        # Safe logging
        breakdown_count = len(enhanced_data.get('breakdown_by_food', {}))
        rec_count = len(enhanced_data.get('recommendations', []))
        print(f"✅ Enhanced assessment data - breakdown_by_food: {breakdown_count}, recommendations: {rec_count}")
        
        return enhanced_data
        
    except Exception as e:
        print(f"❌ Error enhancing assessment data: {e}")
        # Return original data if enhancement fails
        return assessment_data or {}


class ReportGenerationRequest(BaseModel):
    assessment_id: str
    report_type: str = "comprehensive"  # comprehensive, executive, farmer_friendly
    include_sections: Optional[list] = None  # Optional: specific sections to generate


class ReportGenerationResponse(BaseModel):
    report_id: str
    status: str
    message: str
    report_data: Optional[Dict[str, Any]] = None


@router.post("/generate", response_model=ReportGenerationResponse)
async def generate_report(
    request: ReportGenerationRequest,
    background_tasks: BackgroundTasks
):
    """
    Generate a professional AI-powered sustainability report from an assessment

    Supports three report types:
    - comprehensive: Full professional report with all sections
    - executive: Executive summary and key findings only
    - farmer_friendly: Simplified report for smallholder farmers

    Args:
        request: Report generation request with assessment ID and preferences

    Returns:
        Generated report with all sections and metadata
    """
    if not report_generator:
        raise HTTPException(
            status_code=503,
            detail="AI Report Generation service not available. Please configure ANTHROPIC_API_KEY."
        )

    # Import here to avoid circular imports
    from production.routes import assessments_db

    # Get the assessment data
    assessment_id = request.assessment_id
    if assessment_id not in assessments_db:
        raise HTTPException(
            status_code=404,
            detail=f"Assessment {assessment_id} not found"
        )

    assessment_data = assessments_db[assessment_id]

    # Debug logging to understand assessment data structure (safe)
    print(f"\n🔍 Report Generation - Assessment data for {assessment_id}:")
    print(f"  - Keys: {list(assessment_data.keys()) if assessment_data else 'None'}")
    print(f"  - Company: {assessment_data.get('company_name', 'Unknown') if assessment_data else 'Unknown'}")
    print(f"  - Midpoint impacts: {len(assessment_data.get('midpoint_impacts', {}) or {})}")
    print(f"  - Breakdown by food: {len(assessment_data.get('breakdown_by_food', {}) or {})}")

    # Safe check for recommendations
    recommendations = assessment_data.get('recommendations') if assessment_data else None
    rec_count = len(recommendations) if recommendations is not None else 0
    print(f"  - Recommendations: {rec_count}")
    print(f"  - Has data quality: {'data_quality' in (assessment_data or {})}")

    # Generate data-driven recommendations if missing
    if not recommendations or len(recommendations) == 0:
        assessment_data = generate_data_driven_recommendations(assessment_data)
        # Save the updated recommendations back to the assessment database
        assessments_db[assessment_id] = assessment_data
        print(f"✅ Generated {len(assessment_data.get('recommendations', []))} data-driven recommendations and saved to assessment")

    try:
        # Generate the report based on type
        if request.report_type == "comprehensive":
            report = await report_generator.generate_comprehensive_report(
                assessment_data,
                report_type="comprehensive"
            )
        elif request.report_type == "executive":
            executive_summary = await report_generator.generate_executive_summary(
                assessment_data
            )
            report = {
                "report_id": f"EXEC-{assessment_id}",
                "generated_at": datetime.now().isoformat(),
                "report_type": "executive",
                "assessment_id": assessment_id,
                "company_name": assessment_data.get("company_name"),
                "country": assessment_data.get("country"),
                "sections": {
                    "executive_summary": executive_summary
                }
            }
        elif request.report_type == "farmer_friendly":
            sections = await report_generator.generate_farmer_friendly_report(
                assessment_data
            )
            report = {
                "report_id": f"FARMER-{assessment_id}",
                "generated_at": datetime.now().isoformat(),
                "report_type": "farmer_friendly",
                "assessment_id": assessment_id,
                "company_name": assessment_data.get("company_name"),
                "country": assessment_data.get("country"),
                "sections": sections
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid report type: {request.report_type}. Must be 'comprehensive', 'executive', or 'farmer_friendly'"
            )

        # Store the generated report
        report_id = report["report_id"]
        reports_db[report_id] = report

        return ReportGenerationResponse(
            report_id=report_id,
            status="success",
            message=f"{request.report_type.title()} report generated successfully",
            report_data=report
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Report generation failed: {str(e)}"
        )


@router.get("/report/{report_id}")
async def get_report(report_id: str):
    """
    Retrieve a previously generated report by ID

    Args:
        report_id: Unique report identifier

    Returns:
        Complete report with all sections
    """
    if report_id not in reports_db:
        raise HTTPException(
            status_code=404,
            detail=f"Report {report_id} not found"
        )

    return reports_db[report_id]


@router.get("/assessment/{assessment_id}/reports")
async def list_reports_for_assessment(assessment_id: str):
    """
    List all generated reports for a specific assessment

    Args:
        assessment_id: Assessment identifier

    Returns:
        List of report summaries for the assessment
    """
    assessment_reports = [
        {
            "report_id": report_id,
            "report_type": report_data["report_type"],
            "generated_at": report_data["generated_at"],
            "company_name": report_data.get("company_name"),
            "country": report_data.get("country")
        }
        for report_id, report_data in reports_db.items()
        if report_data.get("assessment_id") == assessment_id
    ]

    return {
        "assessment_id": assessment_id,
        "reports": assessment_reports,
        "total": len(assessment_reports)
    }


@router.get("/list")
async def list_all_reports():
    """
    List all generated reports in the system

    Returns:
        List of all report summaries
    """
    all_reports = [
        {
            "report_id": report_id,
            "assessment_id": report_data.get("assessment_id"),
            "report_type": report_data["report_type"],
            "generated_at": report_data["generated_at"],
            "company_name": report_data.get("company_name"),
            "country": report_data.get("country")
        }
        for report_id, report_data in reports_db.items()
    ]

    return {
        "reports": all_reports,
        "total": len(all_reports)
    }


@router.delete("/report/{report_id}")
async def delete_report(report_id: str):
    """
    Delete a generated report

    Args:
        report_id: Unique report identifier

    Returns:
        Success message
    """
    if report_id not in reports_db:
        raise HTTPException(
            status_code=404,
            detail=f"Report {report_id} not found"
        )

    del reports_db[report_id]

    return {
        "status": "success",
        "message": f"Report {report_id} deleted successfully"
    }


@router.get("/report/{report_id}/export/markdown")
async def export_report_markdown(report_id: str):
    """
    Export report as Markdown format

    Args:
        report_id: Unique report identifier

    Returns:
        Markdown-formatted report
    """
    if report_id not in reports_db:
        raise HTTPException(
            status_code=404,
            detail=f"Report {report_id} not found"
        )

    report = reports_db[report_id]

    # Generate markdown document
    markdown = f"""# Environmental Sustainability Assessment Report

**Report ID:** {report['report_id']}
**Assessment ID:** {report.get('assessment_id', 'N/A')}
**Company/Farm:** {report.get('company_name', 'N/A')}
**Country:** {report.get('country', 'N/A')}
**Report Type:** {report['report_type'].title()}
**Generated:** {report['generated_at']}

---

"""

    # Add all sections
    sections = report.get("sections", {})
    for section_key, section_content in sections.items():
        markdown += f"\n{section_content}\n\n---\n\n"

    # Add metadata
    markdown += f"""
## Report Metadata

- **Model Used:** {report.get('metadata', {}).get('model_used', 'Claude')}
- **Generation Timestamp:** {report.get('metadata', {}).get('generation_timestamp', 'N/A')}

---

*This report was generated using AI-powered analysis. For questions or clarifications, please consult with environmental sustainability experts.*
"""

    return {
        "report_id": report_id,
        "format": "markdown",
        "content": markdown
    }


@router.get("/report/{report_id}/export/json")
async def export_report_json(report_id: str):
    """
    Export report as JSON format

    Args:
        report_id: Unique report identifier

    Returns:
        JSON-formatted report
    """
    if report_id not in reports_db:
        raise HTTPException(
            status_code=404,
            detail=f"Report {report_id} not found"
        )

    return reports_db[report_id]


@router.get("/health")
async def health_check():
    """
    Check if the report generation service is healthy and configured

    Returns:
        Service status and configuration info
    """
    return {
        "status": "healthy" if report_generator else "degraded",
        "service": "AI Report Generation",
        "ai_enabled": report_generator is not None,
        "reports_generated": len(reports_db),
        "supported_types": ["comprehensive", "executive", "farmer_friendly"]
    }
