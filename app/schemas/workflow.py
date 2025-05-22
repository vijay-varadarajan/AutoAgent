from pydantic import BaseModel

class WorkflowRequest(BaseModel):
    prompt: str
