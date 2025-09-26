from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uvicorn

# Import processing and production modules
from processing.routes import router as processing_router
from production.routes import router as production_router

app = FastAPI(
    title="African Environmental Sustainability Assessment API",
    description="Comprehensive LCA API for food companies, farmers, and processing facilities in Africa - supports farm and processing assessments",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include processing and production routes
app.include_router(processing_router)
app.include_router(production_router)


@app.get("/")
async def root():
    return {
        "message": "African Environmental Sustainability Assessment API",
        "version": "2.0.0",
        "features": [
            "Simple LCA Assessment", 
            "Comprehensive Farm Assessment", 
            "Processing Facility Assessment",
            "Management Recommendations",
            "Processing Efficiency Analysis"
        ],
        "endpoints": {
            "farm_assessments": "/assess, /assess/comprehensive",
            "processing_assessments": "/processing/assess",
            "documentation": "/docs"
        },
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(), "version": "2.0.0"}



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)