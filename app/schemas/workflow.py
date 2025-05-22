from pydantic import BaseModel

class WorkflowRequest(BaseModel):
    user_id: str
    prompt: str
