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
