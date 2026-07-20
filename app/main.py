from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.utils import generate_unique_id as _default_unique_id
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from datetime import datetime
import logging
import sys
import uvicorn
import os
from dotenv import load_dotenv

# Windows consoles default to a legacy codepage (cp1252), so any log line
# carrying a non-latin1 character raises UnicodeEncodeError mid-request.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# Load environment variables from .env file
load_dotenv()

# Import processing, production, and chat modules
from processing.routes import router as processing_router
from production.routes import router as production_router
from chat.routes import router as chat_router
from inventory.routes import router as inventory_router
from farm.routes import router as farm_router
from auth.routes import router as auth_router
from workspace.routes import router as workspace_router
from share.routes import router as share_router
from studies.routes import router as studies_router
from db import init_db

# Environment detection
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"

# The API is mounted twice: at the root (legacy surface the web app uses) and under /v1
# (the canonical, versioned surface for researcher scripts / generated clients). Give the
# two mounts distinct operationIds so OpenAPI client codegen (openapi-python-client, R
# httr2) does not choke on duplicates.
def _unique_operation_id(route) -> str:
    base = _default_unique_id(route)
    return f"v1_{base}" if route.path.startswith("/v1/") else base


# Serve the OpenAPI schema and docs, including in production: this is a free/non-commercial
# research tool, the schema exposes only the API shape (no secrets), and a served schema is
# what makes the API usable from Jupyter/R via generated clients. Set GMG_DISABLE_DOCS=1 to
# turn the interactive docs off while keeping the machine-readable schema at /openapi.json.
_DISABLE_DOCS = os.getenv("GMG_DISABLE_DOCS") == "1"
app = FastAPI(
    title="Green Means Go Sustainability Assessment API",
    description="Life cycle assessment API for farmers, agricultural extension officers, and food processors worldwide - supports farm and processing assessments with AI plain-language guides. The versioned /v1 surface is the stable contract for research scripts and generated clients.",
    version="2.1.0",
    docs_url=None if _DISABLE_DOCS else "/docs",
    redoc_url=None if _DISABLE_DOCS else "/redoc",
    openapi_url="/openapi.json",
    generate_unique_id_function=_unique_operation_id,
)

class CatchUnhandledErrorsMiddleware(BaseHTTPMiddleware):
    """Turn an uncaught exception into a JSON 500 *inside* the CORS layer.

    Starlette's built-in ServerErrorMiddleware sits OUTSIDE CORSMiddleware, so an
    unhandled exception's 500 is emitted above CORS and reaches the browser with no
    Access-Control-Allow-Origin header. The browser then reports it as a CORS error,
    masking the real server error. This middleware is added BEFORE CORSMiddleware (so
    CORS wraps it); catching here keeps the CORS headers on error responses, so a 500
    shows up in the browser as a real 500 with a readable message, not a phantom CORS block.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            logging.getLogger("uvicorn.error").exception(
                "Unhandled error on %s %s", request.method, request.url.path
            )
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Trusted hosts middleware - prevent host header attacks
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["greenmeansgo.ai", "www.greenmeansgo.ai", "localhost", "127.0.0.1"],
)

# Catch-all error handler. Added BEFORE CORS so CORS remains the outer wrapper and its
# headers are present on the 500 responses this produces (see the class docstring).
app.add_middleware(CatchUnhandledErrorsMiddleware)

# Add CORS middleware - restrict to known origins. Added LAST so it is the OUTERMOST
# middleware, wrapping the catch-all above and thus every error response.
ALLOWED_ORIGINS = [
    "https://greenmeansgo.ai",
    "https://www.greenmeansgo.ai",
    "http://localhost:3000",  # Development only
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Include auth, workspace, processing, production, chat, and other routes. Each router is
# mounted twice: at the root (legacy, what the web app calls today) and under /v1 (the
# canonical versioned surface). Existing clients keep working; researchers pin to /v1.
_API_ROUTERS = [
    auth_router, workspace_router, share_router, studies_router,
    processing_router, production_router, chat_router, inventory_router, farm_router,
]
for _r in _API_ROUTERS:
    app.include_router(_r)               # legacy root surface
    app.include_router(_r, prefix="/v1")  # canonical versioned surface


@app.on_event("startup")
async def _init_database():
    """Create the application tables (users, farms, facilities, assessments) if they
    don't exist yet. Uses the SQLite dev database by default; production runs Alembic
    migrations instead but create_all is idempotent and safe."""
    init_db()


@app.on_event("startup")
async def _warm_engine():
    """Pre-load the validated engine (matcher index) in the background so the first
    assessment isn't slow. Non-fatal if the store isn't built yet."""
    import threading
    def _go():
        try:
            import sys
            from pathlib import Path
            root = Path(__file__).resolve().parents[1]
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from engine.service import warm
            warm(("GH",))
        except Exception as e:
            print(f"engine warmup skipped: {e}")
    threading.Thread(target=_go, daemon=True).start()


@app.get("/")
async def root():
    response = {
        "message": "Green Means Go Sustainability Assessment API",
        "version": "2.1.0",
        "features": [
            "Simple LCA Assessment",
            "Comprehensive Farm Assessment",
            "Processing Facility Assessment",
            "AI-Powered Professional Reports",
            "Management Recommendations",
            "Processing Efficiency Analysis"
        ],
        "api_versions": {
            "v1": "/v1 (canonical, versioned surface for research scripts and generated clients)",
            "root": "/ (legacy alias; same endpoints without the /v1 prefix)",
        },
        "endpoints": {
            "auth": "/v1/auth/signup, /v1/auth/login, /v1/auth/refresh, /v1/auth/me",
            "farm_assessments": "/v1/assess, /v1/assess/comprehensive",
            "processing_assessments": "/v1/processing/assess",
            "workspace": "/v1/farms, /v1/facilities, /v1/me/assessments",
            "research_export": "/v1/me/assessments/{id}/export.json, /v1/me/assessments/{id}/export.csv",
            "openapi_schema": "/openapi.json",
        },
    }
    if not _DISABLE_DOCS:
        response["endpoints"]["documentation"] = "/docs"
        response["docs"] = "/docs"
    return response

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(), "version": "2.1.0"}



if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)