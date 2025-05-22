from fastapi import APIRouter, HTTPException
from app.schemas.workflow import WorkflowRequest
from app.services.gemini_parser import parse_workflow

router = APIRouter()

@router.post("/parse")
async def parse_user_workflow(req: WorkflowRequest):
    try:
        structured_output = await parse_workflow(req.prompt)
        return {"structured_workflow": structured_output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
