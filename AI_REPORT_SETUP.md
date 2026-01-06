# AI-Powered Report Generation Setup Guide

This guide explains how to set up and use the professional AI-powered sustainability report generation feature powered by Claude API.

## Overview

The AI Report Generation system uses Anthropic's Claude AI to automatically generate comprehensive, professional sustainability assessment reports from your LCA (Life Cycle Assessment) data. It supports three report types:

1. **Comprehensive Report**: Full professional report with all sections (Executive Summary, Methodology, Impact Analysis, Recommendations, etc.)
2. **Executive Summary**: Concise summary for decision-makers and executives
3. **Farmer-Friendly Report**: Simplified report for smallholder farmers with practical guidance

## Features

✅ **Professional Quality**: Reports follow ISO 14044 and ISO 14067 standards
✅ **AI-Powered Analysis**: Uses Claude Sonnet 4 for intelligent insights
✅ **Multiple Export Formats**: Markdown, JSON
✅ **Context-Aware**: Considers African agricultural context
✅ **Actionable Recommendations**: Provides specific, implementable suggestions
✅ **Data-Driven**: Based on comprehensive LCA assessment results

## Prerequisites

### 1. Anthropic Claude API Key

You need an Anthropic API key to use the AI report generation feature.

**Get your API key:**
1. Visit [Anthropic Console](https://console.anthropic.com/)
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key (it starts with `sk-ant-...`)

### 2. Python Dependencies

Install the required Python package:

```bash
cd green_means_go
pip install anthropic==0.42.0
```

Or install all dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

### Backend Configuration

#### Option 1: Environment Variable (Recommended)

Set the `ANTHROPIC_API_KEY` environment variable:

**Windows (PowerShell):**
```powershell
$env:ANTHROPIC_API_KEY="sk-ant-your-api-key-here"
```

**Windows (Command Prompt):**
```cmd
set ANTHROPIC_API_KEY=sk-ant-your-api-key-here
```

**Linux/Mac:**
```bash
export ANTHROPIC_API_KEY="sk-ant-your-api-key-here"
```

#### Option 2: .env File

Create a `.env` file in the `app` directory:

```env
# app/.env
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
```

Then load it in your application:

```python
from dotenv import load_dotenv
load_dotenv()
```

### Frontend Configuration

No additional configuration needed for the frontend. It communicates with the backend API endpoints.

## Usage

### Starting the Backend API

```bash
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### Accessing the Documentation

Open your browser and navigate to:
- API Documentation: `http://localhost:8000/docs`
- Report Health Check: `http://localhost:8000/reports/health`

### Using the Frontend

1. Complete a sustainability assessment
2. Navigate to the Results page
3. Scroll to the "AI-Powered Professional Reports" section
4. Select a report type (Comprehensive, Executive, or Farmer-Friendly)
5. Click "Generate Report"
6. Wait for the AI to generate the report (typically 10-30 seconds)
7. View the report in the modal
8. Export as Markdown or JSON if needed

## API Endpoints

### Generate Report

**Endpoint:** `POST /reports/generate`

**Request Body:**
```json
{
  "assessment_id": "abc123",
  "report_type": "comprehensive"
}
```

**Response:**
```json
{
  "report_id": "REPORT-abc123",
  "status": "success",
  "message": "Comprehensive report generated successfully",
  "report_data": {
    "report_id": "REPORT-abc123",
    "generated_at": "2025-10-29T12:00:00",
    "report_type": "comprehensive",
    "assessment_id": "abc123",
    "company_name": "Example Farm",
    "country": "Ghana",
    "sections": {
      "executive_summary": "...",
      "introduction": "...",
      "methodology": "...",
      "impact_analysis": "...",
      "comparative_analysis": "...",
      "sensitivity_analysis": "...",
      "recommendations": "...",
      "conclusions": "...",
      "technical_appendix": "..."
    },
    "metadata": {
      "model_used": "claude-sonnet-4-20250514",
      "generation_timestamp": "2025-10-29T12:00:00"
    }
  }
}
```

### Get Report

**Endpoint:** `GET /reports/report/{report_id}`

**Response:** Returns the complete report data.

### Export Report (Markdown)

**Endpoint:** `GET /reports/report/{report_id}/export/markdown`

**Response:**
```json
{
  "report_id": "REPORT-abc123",
  "format": "markdown",
  "content": "# Environmental Sustainability Assessment Report\n\n..."
}
```

### Export Report (JSON)

**Endpoint:** `GET /reports/report/{report_id}/export/json`

**Response:** Returns the complete report in JSON format.

### List Reports for Assessment

**Endpoint:** `GET /reports/assessment/{assessment_id}/reports`

**Response:**
```json
{
  "assessment_id": "abc123",
  "reports": [
    {
      "report_id": "REPORT-abc123",
      "report_type": "comprehensive",
      "generated_at": "2025-10-29T12:00:00",
      "company_name": "Example Farm",
      "country": "Ghana"
    }
  ],
  "total": 1
}
```

### Service Health Check

**Endpoint:** `GET /reports/health`

**Response:**
```json
{
  "status": "healthy",
  "service": "AI Report Generation",
  "ai_enabled": true,
  "reports_generated": 5,
  "supported_types": ["comprehensive", "executive", "farmer_friendly"]
}
```

## Report Types Explained

### 1. Comprehensive Report

**Sections:**
- Executive Summary (200-300 words)
- Introduction (150-200 words)
- Assessment Methodology (200-250 words)
- Environmental Impact Analysis (400-500 words)
- Comparative Performance Analysis (300-400 words)
- Sensitivity and Uncertainty Analysis (200-300 words)
- Recommendations and Action Plan (400-500 words)
- Conclusions (200-250 words)
- Technical Appendix (200-300 words)

**Best for:**
- Stakeholder presentations
- Grant applications
- Sustainability certifications
- Detailed technical analysis

### 2. Executive Summary

**Sections:**
- Executive Summary (200-300 words)

**Best for:**
- Board meetings
- Investor presentations
- Quick decision-making
- High-level overviews

### 3. Farmer-Friendly Report

**Sections:**
- What This Assessment Means for Your Farm (150 words)
- Your Farm's Environmental Performance (200 words)
- Practical Steps You Can Take (300 words)
- Expected Benefits (150 words)

**Best for:**
- Smallholder farmers
- Extension services
- Training programs
- Community outreach

## Troubleshooting

### Error: "AI Report Generation service not available"

**Cause:** The `ANTHROPIC_API_KEY` environment variable is not set.

**Solution:**
1. Verify your API key is correctly set
2. Restart the backend API server
3. Check `/reports/health` endpoint

### Error: "Assessment not found"

**Cause:** The assessment ID doesn't exist or hasn't been completed yet.

**Solution:**
1. Complete the assessment first
2. Verify the assessment ID is correct
3. Check `/assessments` endpoint to list available assessments

### Slow Report Generation

**Normal Behavior:** Comprehensive reports typically take 15-30 seconds to generate due to the detailed analysis performed by Claude AI.

**If taking longer:**
1. Check your internet connection
2. Verify Anthropic API status
3. Try generating an Executive Summary (faster)

### Export Not Working

**Solution:**
1. Ensure the report was generated successfully
2. Check browser console for errors
3. Try a different browser
4. Verify file download permissions

## Cost Considerations

### Anthropic API Pricing

Claude API charges based on tokens used:
- Input tokens (your data sent to Claude)
- Output tokens (the generated report)

**Estimated costs per report type:**
- **Executive Summary**: ~$0.05 - $0.10
- **Comprehensive Report**: ~$0.20 - $0.40
- **Farmer-Friendly Report**: ~$0.10 - $0.20

**Tip:** Use Executive Summaries for quick reviews and Comprehensive Reports only when needed to minimize costs.

### Free Tier

Anthropic offers free credits for new accounts. Check [Anthropic Pricing](https://www.anthropic.com/pricing) for current offers.

## Best Practices

### 1. Data Quality

Ensure your assessment data is complete and accurate:
- Include all required fields
- Provide comprehensive farm profile information
- Complete management practices data
- Include equipment and energy usage

**Better input data = Better AI-generated reports**

### 2. Report Selection

Choose the appropriate report type:
- Use **Comprehensive** for official documentation
- Use **Executive** for quick reviews
- Use **Farmer-Friendly** for farmer education

### 3. Review and Edit

AI-generated reports should be reviewed by experts:
- Verify all data and calculations
- Add local context where needed
- Customize recommendations based on specific situations
- Add relevant images and charts

### 4. Version Control

Keep track of generated reports:
- Export reports to your document management system
- Include report ID and generation timestamp
- Associate reports with specific assessment versions

### 5. Security

Protect your API key:
- Never commit API keys to version control
- Use environment variables
- Rotate keys periodically
- Monitor usage in Anthropic Console

## Advanced Usage

### Programmatic Report Generation

Generate reports programmatically using Python:

```python
import requests

API_URL = "http://localhost:8000"

def generate_report(assessment_id: str, report_type: str = "comprehensive"):
    response = requests.post(
        f"{API_URL}/reports/generate",
        json={
            "assessment_id": assessment_id,
            "report_type": report_type
        }
    )
    return response.json()

# Generate a comprehensive report
result = generate_report("assessment-123", "comprehensive")
print(f"Report ID: {result['report_id']}")
```

### Batch Report Generation

Generate reports for multiple assessments:

```python
assessment_ids = ["id1", "id2", "id3"]

for assessment_id in assessment_ids:
    try:
        result = generate_report(assessment_id, "executive")
        print(f"✓ Generated report for {assessment_id}")
    except Exception as e:
        print(f"✗ Failed for {assessment_id}: {e}")
```

## Integration Examples

### Frontend Integration (React/Next.js)

```typescript
import { assessmentAPI } from '@/lib/api';

async function generateAndDownloadReport(assessmentId: string) {
  try {
    // Generate report
    const result = await assessmentAPI.generateReport(
      assessmentId,
      'comprehensive'
    );

    // Export as Markdown
    const markdown = await assessmentAPI.exportReportMarkdown(
      result.report_id
    );

    // Download file
    const blob = new Blob([markdown.content], { type: 'text/markdown' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `report-${result.report_id}.md`;
    a.click();
  } catch (error) {
    console.error('Report generation failed:', error);
  }
}
```

### Backend Integration (Python)

```python
from services.ai_report_generator import AIReportGenerator

# Initialize generator
generator = AIReportGenerator()

# Generate report
report = await generator.generate_comprehensive_report(
    assessment_data=assessment,
    report_type="comprehensive"
)

# Access sections
executive_summary = report["sections"]["executive_summary"]
recommendations = report["sections"]["recommendations"]
```

## Support and Resources

### Documentation
- API Docs: `http://localhost:8000/docs`
- Claude AI Docs: https://docs.anthropic.com/

### Getting Help
- Check the API health endpoint first
- Review error messages carefully
- Check Anthropic Console for API status
- Verify environment variables are set

### Contributing
- Report issues on GitHub
- Submit feature requests
- Share your use cases
- Contribute improvements

## License

This AI Report Generation feature is part of the African LCA Assessment API project. See the main project README for license information.

---

**Version:** 2.1.0
**Last Updated:** October 29, 2025
**Powered by:** Claude AI (Anthropic)
