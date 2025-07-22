from fastapi import FastAPI
import logging
from app.logging_config import setup_logging
from app.routes import workflow, oauth_redirect

# Initialize centralized logging
logger = setup_logging()
logger.info("🚀 APPLICATION: AutoAgent starting up with centralized logging")

app = FastAPI(title="AutoAgent")

@app.get("/")
async def root():
    """Root endpoint to test logging."""
    logger.info("🚀 APPLICATION: Root endpoint accessed - logging is working!")
    return {"message": "AutoAgent is running", "logging": "enabled"}

@app.get("/health")
async def health_check():
    """Health check endpoint with logging."""
    logger.info("🚀 APPLICATION: Health check requested")
    return {"status": "healthy", "logging": "working"}

app.include_router(workflow.router, prefix="/api/workflow", tags=["Workflow"])
app.include_router(oauth_redirect.router, prefix="/api", tags=["OAuth"])
