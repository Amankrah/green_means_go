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
import httpx

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ai_report_generator import AIReportGenerator
from services.pdf_report_generator import get_pdf_generator
from fastapi.responses import Response

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
    This is the SINGLE source of truth for recommendation generation

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
                dqi = impact.get('data_quality_score', 1.0)
            elif isinstance(impact, (int, float)):
                value = impact
                unit = 'units'
                dqi = 1.0
            else:
                continue

            if value > 0:
                impact_analysis.append({
                    'category': category,
                    'value': value,
                    'unit': unit,
                    'dqi': dqi
                })
        except Exception as e:
            print(f"Warning: Error analyzing impact {category}: {e}")
            continue

    # Sort by value (highest impacts first)
    impact_analysis.sort(key=lambda x: x['value'], reverse=True)

    # Impact-specific recommendation templates
    impact_recommendations_templates = {
        'Global warming': {
            'title': 'Reduce Carbon Footprint from Agricultural Operations',
            'description_template': "Your assessment shows {value:.4f} {unit} of greenhouse gas emissions. Consider adopting practices like reduced tillage, optimizing fertilizer use, and using cover crops to sequester carbon.",
            'category': 'Climate Action',
            'priority': 'high',
            'implementation_difficulty': 'Medium',
            'cost_category': 'Low to Medium'
        },
        'Water consumption': {
            'title': 'Optimize Water Use Efficiency',
            'description_template': "Water consumption is {value:.4f} {unit}. Implement drip irrigation, rainwater harvesting, and water-efficient crops to reduce water usage.",
            'category': 'Water Management',
            'priority': 'high',
            'implementation_difficulty': 'Medium',
            'cost_category': 'Medium'
        },
        'Water scarcity': {
            'title': 'Address Water Scarcity Risk',
            'description_template': "Water scarcity impact is {value:.4f} {unit}. Prioritize water conservation through efficient irrigation systems and drought-resistant crop varieties.",
            'category': 'Water Management',
            'priority': 'high',
            'implementation_difficulty': 'Medium',
            'cost_category': 'Medium'
        },
        'Land use': {
            'title': 'Improve Land Use Efficiency',
            'description_template': "Land use impact is {value:.4f} {unit}. Consider intensifying production sustainably through crop rotation, intercropping, and improved varieties.",
            'category': 'Land Management',
            'priority': 'medium',
            'implementation_difficulty': 'Medium',
            'cost_category': 'Low to Medium'
        },
        'Terrestrial acidification': {
            'title': 'Reduce Soil Acidification from Inputs',
            'description_template': "Acidification impact is {value:.4f} {unit}. Use precision fertilization, organic amendments, and lime application to maintain soil pH.",
            'category': 'Soil Health',
            'priority': 'medium',
            'implementation_difficulty': 'Low',
            'cost_category': 'Low'
        },
        'Freshwater eutrophication': {
            'title': 'Prevent Nutrient Runoff to Water Bodies',
            'description_template': "Eutrophication risk is {value:.4f} {unit}. Implement buffer strips, reduce fertilizer rates, and use slow-release formulations.",
            'category': 'Water Quality',
            'priority': 'high',
            'implementation_difficulty': 'Medium',
            'cost_category': 'Low to Medium'
        },
        'Marine eutrophication': {
            'title': 'Reduce Nutrient Loading to Marine Systems',
            'description_template': "Marine eutrophication impact is {value:.4f} {unit}. Control nitrogen losses through timing and placement optimization.",
            'category': 'Water Quality',
            'priority': 'medium',
            'implementation_difficulty': 'Medium',
            'cost_category': 'Low to Medium'
        },
        'Biodiversity loss': {
            'title': 'Enhance On-Farm Biodiversity',
            'description_template': "Biodiversity impact is {value:.4f} {unit}. Create wildlife corridors, maintain diverse rotations, and preserve natural habitats.",
            'category': 'Ecosystem Protection',
            'priority': 'medium',
            'implementation_difficulty': 'Medium',
            'cost_category': 'Low'
        },
        'Soil degradation': {
            'title': 'Prevent Soil Degradation',
            'description_template': "Soil degradation risk is {value:.4f} {unit}. Implement conservation tillage, maintain soil cover, and use organic amendments.",
            'category': 'Soil Health',
            'priority': 'high',
            'implementation_difficulty': 'Medium',
            'cost_category': 'Low'
        },
        'Fossil depletion': {
            'title': 'Reduce Fossil Fuel Dependency',
            'description_template': "Fossil depletion impact is {value:.4f} {unit}. Optimize machinery use, consider renewable energy, and reduce synthetic input dependency.",
            'category': 'Resource Efficiency',
            'priority': 'low',
            'implementation_difficulty': 'High',
            'cost_category': 'Medium to High'
        },
        'Mineral depletion': {
            'title': 'Optimize Mineral Resource Use',
            'description_template': "Mineral depletion impact is {value:.4f} {unit}. Improve nutrient cycling and use locally available mineral sources.",
            'category': 'Resource Efficiency',
            'priority': 'low',
            'implementation_difficulty': 'Low',
            'cost_category': 'Low'
        }
    }

    # Generate recommendations for top 5 impact categories
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
                'cost_category': template['cost_category'],
                'data_quality_index': impact['dqi']
            }
            recommendations.append(rec)

    # If fewer than 3 recommendations, add integrated management recommendation
    if len(recommendations) < 3:
        recommendations.append({
            'title': 'Implement Integrated Farm Management',
            'description': "Your assessment identified multiple environmental impact areas. Adopt an integrated approach combining soil conservation, water management, and biodiversity enhancement.",
            'category': 'General',
            'priority': 'medium',
            'implementation_difficulty': 'Medium',
            'cost_category': 'Medium',
            'data_quality_index': 1.0
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
        
        # Note: Recommendations are now handled by generate_data_driven_recommendations()
        # This function only handles data structure validation, not content generation
        
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

    # ALWAYS generate/regenerate recommendations to ensure they're data-driven and current
    # This is the single source of truth for recommendations
    assessment_data = generate_data_driven_recommendations(assessment_data)
    assessments_db[assessment_id] = assessment_data
    print(f"✅ Generated {len(assessment_data.get('recommendations', []))} data-driven recommendations")

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


@router.get("/report/{report_id}/download/pdf")
async def download_report_pdf(report_id: str, assessment_id: str):
    """
    Generate and download a PDF version of the report

    Args:
        report_id: Unique report identifier
        assessment_id: Assessment ID to fetch assessment data

    Returns:
        PDF file as downloadable response
    """
    # Check if report exists
    if report_id not in reports_db:
        raise HTTPException(
            status_code=404,
            detail=f"Report {report_id} not found"
        )

    report_data = reports_db[report_id]

    # Fetch assessment data from Rust backend
    try:
        rust_backend_url = "http://localhost:3000"
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{rust_backend_url}/assess/{assessment_id}")
            response.raise_for_status()
            assessment_data = response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Failed to fetch assessment data from Rust backend: {e.response.text}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch assessment data: {str(e)}"
        )

    # Generate PDF
    try:
        print(f"📄 Generating PDF for report {report_id}")
        print(f"📄 Report type: {report_data.get('report_type')}")
        print(f"📄 Assessment company: {assessment_data.get('company_name')}")

        pdf_generator = get_pdf_generator()
        pdf_bytes = pdf_generator.generate_pdf(
            report_data=report_data,
            assessment_data=assessment_data,
            report_type=report_data.get('report_type', 'comprehensive')
        )

        print(f"✅ PDF generated successfully, size: {len(pdf_bytes)} bytes")

        # Create filename
        company_name = assessment_data.get('company_name', 'report').replace(' ', '_')
        report_type = report_data.get('report_type', 'report')
        filename = f"{company_name}_{report_type}_report.pdf"

        # Return PDF response
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    except Exception as e:
        import traceback
        print(f"❌ PDF generation error: {str(e)}")
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {str(e)}"
        )
