from typing import Optional
from pydantic import BaseModel, Field


class CSRFTokenResponse(BaseModel):
    csrf_token: str


class RPContextRequest(BaseModel):
    rp_client_id: str = Field(min_length=1)


class RedirectResponseModel(BaseModel):
    redirect_url: str


class LogoutResponseModel(BaseModel):
    redirect_url: Optional[str] = None
    source: Optional[str] = None


class KeepAliveData(BaseModel):
    status: str
    login: Optional[str] = None
    expire: Optional[int] = None


class SSEventData(BaseModel):
    status: str
    expire: Optional[int] = None
    error: Optional[str] = None
    code: Optional[str] = None
