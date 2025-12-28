from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from datetime import datetime
import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import processing, production, and reports modules
from processing.routes import router as processing_router
from production.routes import router as production_router
from reports.routes import router as reports_router

# Environment detection
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"

# Disable docs in production for security
app = FastAPI(
    title="African Environmental Sustainability Assessment API",
    description="Comprehensive LCA API for food companies, farmers, and processing facilities in Africa - supports farm and processing assessments with AI-powered report generation",
    version="2.1.0",
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# Trusted hosts middleware - prevent host header attacks
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["greenmeansgo.ai", "www.greenmeansgo.ai", "localhost", "127.0.0.1"],
)

# Add CORS middleware - restrict to known origins
ALLOWED_ORIGINS = [
    "https://greenmeansgo.ai",
    "https://www.greenmeansgo.ai",
    "http://localhost:3000",  # Development only
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Include processing, production, and reports routes
app.include_router(processing_router)
app.include_router(production_router)
app.include_router(reports_router)


@app.get("/")
async def root():
    response = {
        "message": "African Environmental Sustainability Assessment API",
        "version": "2.1.0",
        "features": [
            "Simple LCA Assessment",
            "Comprehensive Farm Assessment",
            "Processing Facility Assessment",
            "AI-Powered Professional Reports",
            "Management Recommendations",
            "Processing Efficiency Analysis"
        ],
        "endpoints": {
            "farm_assessments": "/assess, /assess/comprehensive",
            "processing_assessments": "/processing/assess",
            "reports": "/reports/generate, /reports/report/{id}",
        },
    }
    # Only show docs endpoint in development
    if not IS_PRODUCTION:
        response["endpoints"]["documentation"] = "/docs"
        response["docs"] = "/docs"
    return response

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(), "version": "2.1.0"}



if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)