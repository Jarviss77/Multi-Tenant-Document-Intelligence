from pydantic import BaseModel, ConfigDict

class DocumentCreate(BaseModel):
    title: str
    content: str

class DocumentResponse(BaseModel):
    id: str
    title: str
    content: str

    model_config = ConfigDict(from_attributes=True)


