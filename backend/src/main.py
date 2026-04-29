"""
Main FastAPI application entry point.
Configures the application, middleware, routes, and startup/shutdown events.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from src.config.settings import settings
from src.config.keyvault import setup_keyvault_credentials
from src.services.database import DatabaseManager
from src.utils.logger import setup_logging
from src.utils.errors import SmartRetailException
from src.routers import sales, inventory

# Configure logging
setup_logging(
    log_level=settings.LOG_LEVEL,
    log_file="logs/smartretail_sync.log"
)

logger = logging.getLogger(__name__)

# Global database manager instance
db_manager: DatabaseManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle:
    - Startup: Initialize database connections
    - Shutdown: Close database connections and cleanup
    """
    # Startup
    logger.info("=" * 50)
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info("=" * 50)
    
    try:
        # Setup Key Vault credentials if production
        if settings.ENVIRONMENT == "production":
            setup_keyvault_credentials(settings)
        
        # Initialize database manager
        global db_manager
        db_manager = DatabaseManager(settings)
        await db_manager.initialize()
        
        # Test database connection
        if not await db_manager.test_connection():
            raise RuntimeError("Failed to connect to database")
        
        logger.info(f"Database initialized: {settings.DB_HOST}:{settings.DB_PORT}")
        logger.info("Application started successfully")
    
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    if db_manager:
        await db_manager.close()
    logger.info("Application stopped")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Real-time sales and inventory synchronization system with Power BI integration",
    version=settings.APP_VERSION,
    docs_url=f"{settings.API_PREFIX}/docs" if not settings.DEBUG is False else "/docs",
    openapi_url=f"{settings.API_PREFIX}/openapi.json" if not settings.DEBUG is False else "/openapi.json",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ============================================
# EXCEPTION HANDLERS
# ============================================

@app.exception_handler(SmartRetailException)
async def smartretail_exception_handler(request: Request, exc: SmartRetailException):
    """Handle custom SmartRetail exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error_code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error_code": "INTERNAL_ERROR",
            "message": "Internal server error",
            "details": str(exc) if settings.DEBUG else "Contact support"
        }
    )


# ============================================
# ROOT ENDPOINTS
# ============================================

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": f"{settings.API_PREFIX}/docs"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring and load balancers."""
    db_ok = await db_manager.test_connection() if db_manager else False
    
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


# ============================================
# INCLUDE ROUTERS
# ============================================

app.include_router(
    sales.router,
    prefix=settings.API_PREFIX,
)

app.include_router(
    inventory.router,
    prefix=settings.API_PREFIX,
)


# ============================================
# STARTUP AND SHUTDOWN EVENTS (for reference)
# ============================================

@app.on_event("startup")
async def startup_event():
    """Additional startup operations if needed."""
    logger.info("Startup event triggered")


@app.on_event("shutdown")
async def shutdown_event():
    """Additional shutdown operations if needed."""
    logger.info("Shutdown event triggered")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
