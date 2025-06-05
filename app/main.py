from fastapi import FastAPI
from app.routes import workflow, oauth_redirect

app = FastAPI(title="AutoAgent")

app.include_router(workflow.router, prefix="/api/workflow", tags=["Workflow"])
app.include_router(oauth_redirect.router, prefix="/api", tags=["OAuth"])
