from fastapi import APIRouter, HTTPException
from app.schemas.workflow import WorkflowRequest
from app.services.gemini_parser import parse_workflow
from app.services.firestore_db import save_workflow, get_all_workflows

router = APIRouter()

@router.post("/parse-and-save")
async def parse_and_save(req: WorkflowRequest):
    try:
        structured_output = await parse_workflow(req.prompt)
        workflow_id = save_workflow(req.user_id, req.prompt, structured_output)
        return {"status": "saved", "workflow_id": workflow_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{user_id}")
def get_user_workflows(user_id: str):
    try:
        workflows = get_all_workflows(user_id)
        return {"workflows": workflows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
