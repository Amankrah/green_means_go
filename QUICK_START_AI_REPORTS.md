# Quick Start: AI-Powered Reports

Get professional sustainability reports in 5 minutes!

## Step 1: Get Your Claude API Key

1. Visit https://console.anthropic.com/
2. Sign up or log in
3. Go to API Keys → Create Key
4. Copy your key (starts with `sk-ant-...`)

## Step 2: Set Environment Variable

**Windows PowerShell:**
```powershell
$env:ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

**Windows CMD:**
```cmd
set ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Linux/Mac:**
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

## Step 3: Install Dependencies

```bash
cd green_means_go
pip install anthropic==0.42.0
```

Or install all:
```bash
pip install -r requirements.txt
```

## Step 4: Start the Backend

```bash
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Step 5: Start the Frontend

In a new terminal:
```bash
cd african-lca-frontend
npm install
npm run dev
```

## Step 6: Generate Your First Report

1. Open http://localhost:3000
2. Complete an assessment
3. Go to Results page
4. Scroll to "AI-Powered Professional Reports"
5. Click "Generate Comprehensive Report"
6. Wait 15-30 seconds
7. View and export your report!

## Verify Setup

Check if AI reports are enabled:
```bash
curl http://localhost:8000/reports/health
```

Should return:
```json
{
  "status": "healthy",
  "ai_enabled": true
}
```

## What You Get

### Comprehensive Report Includes:
✅ Executive Summary
✅ Assessment Methodology
✅ Environmental Impact Analysis
✅ Comparative Performance Analysis
✅ Sensitivity Analysis
✅ Recommendations and Action Plan
✅ Conclusions
✅ Technical Appendix

### Report Formats:
📄 Interactive Web View
📥 Markdown Export
📊 JSON Export

## Troubleshooting

**"Service not available" error?**
→ Check your API key is set correctly
→ Restart the backend server

**Report taking too long?**
→ Normal for comprehensive reports (15-30 sec)
→ Try "Executive Summary" for faster results

**Want to see costs?**
→ Check your Anthropic Console dashboard
→ Approximate: $0.05-$0.40 per report

## Next Steps

- Read full documentation: `AI_REPORT_SETUP.md`
- Explore API docs: http://localhost:8000/docs
- Try different report types (Executive, Farmer-Friendly)
- Export and customize reports

## Support

Need help? Check:
1. `/reports/health` endpoint
2. FastAPI docs at `/docs`
3. Anthropic Console for API status

---

**🎉 You're ready to generate professional AI-powered sustainability reports!**
