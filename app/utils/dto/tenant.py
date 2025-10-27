from pydantic import BaseModel, ConfigDict, EmailStr

class TenantCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class TenantResponse(BaseModel):
    id: str
    name: str
    email: str
    api_key: str
    jwt_token: str

    model_config = ConfigDict(from_attributes=True)