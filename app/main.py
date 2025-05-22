from fastapi import FastAPI
from app.routes import workflow

app = FastAPI(title="AutoAgent")

app.include_router(workflow.router, prefix="/api/workflow", tags=["Workflow"])
