from pydantic import BaseModel
from typing import List, Optional


class LegacyIdpSchema(BaseModel):
    client_id: str
    client_name: str
    client_secret: str
    openid_configuration: str
    redirect_uris: List[str]
    scope: str
    max_age: int
    code_challenge_method: str
    token_endpoint_auth_method: Optional[str] = "client_secret_post"


class RPSchema(BaseModel):
    rp_client_id: str
    rp_client_name: str
    rp_client_name_en: str
    rp_client_name_fr: str
    rp_redirect_uri: str
    IDP: List[LegacyIdpSchema]
