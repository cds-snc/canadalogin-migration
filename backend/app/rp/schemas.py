from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class RPRedirectSchema(BaseModel):
    rp_redirect_uri: Optional[str] = None
    rp_redirect_uri_en: Optional[str] = None
    rp_redirect_uri_fr: Optional[str] = None

    @model_validator(mode="after")
    def validate_redirect_uris(self):
        redirect_uris = (
            self.rp_redirect_uri,
            self.rp_redirect_uri_en,
            self.rp_redirect_uri_fr,
        )
        if any(isinstance(value, str) and value.strip() for value in redirect_uris):
            return self

        raise ValueError(
            "At least one of rp_redirect_uri, rp_redirect_uri_en, or rp_redirect_uri_fr must be provided"
        )


class RPSchema(RPRedirectSchema):
    rp_client_id: str
    rp_client_name: str
    rp_client_name_en: str
    rp_client_name_fr: str
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


class RPConfigSourceSchema(RPRedirectSchema):
    rp_client_id: str
    rp_client_name: str
    rp_client_name_en: str
    rp_client_name_fr: str
    dependent_client_ids: List[str] = Field(
        default_factory=list, alias="dependentClientIds"
    )
    acr_values: Optional[str] = ""
    IDP: List[LegacyIdpConfigSchema]
    model_config = ConfigDict(populate_by_name=True)


class LegacyIdpSecretSchema(BaseModel):
    client_id: str
    client_secret: str
