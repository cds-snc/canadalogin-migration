from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


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
    dependent_client_ids: List[str] = Field(
        default_factory=list, alias="dependentClientIds"
    )
    acr_values: Optional[str] = ""
    IDP: List[LegacyIdpSchema]
    model_config = ConfigDict(populate_by_name=True)


class LegacyIdpConfigSchema(BaseModel):
    client_id: str
    client_name: str
    client_secret: Optional[str] = None
    openid_configuration: str
    redirect_uris: List[str]
    scope: str
    max_age: int
    code_challenge_method: str
    token_endpoint_auth_method: Optional[str] = "client_secret_post"


class RPConfigSourceSchema(BaseModel):
    rp_client_id: str
    rp_client_name: str
    rp_client_name_en: str
    rp_client_name_fr: str
    rp_redirect_uri: str
    dependent_client_ids: List[str] = Field(
        default_factory=list, alias="dependentClientIds"
    )
    acr_values: Optional[str] = ""
    IDP: List[LegacyIdpConfigSchema]
    model_config = ConfigDict(populate_by_name=True)


class LegacyIdpSecretSchema(BaseModel):
    client_id: str
    client_secret: str
