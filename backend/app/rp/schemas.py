from typing import List, Literal, Optional
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class LegacyIdpSchema(BaseModel):
    client_id: Optional[str] = None
    client_name: str
    protocol: Literal["oidc", "saml"] = "oidc"
    provider_key: Optional[str] = None
    display_name: Optional[str] = None
    client_secret: Optional[str] = None
    openid_configuration: Optional[str] = None
    redirect_uris: List[str] = Field(default_factory=list)
    scope: Optional[str] = None
    max_age: Optional[int] = None
    code_challenge_method: Optional[str] = None
    token_endpoint_auth_method: Optional[str] = "client_secret_post"
    entity_id: Optional[str] = None
    metadata_url: Optional[str] = None
    expected_legacy_provider: Optional[str] = None
    expected_nameid_format: Optional[str] = None
    requested_authn_context: Optional[str] = None
    requested_authn_context_comparison: Optional[str] = "exact"
    sp_entity_id: Optional[str] = None
    acs_url: Optional[str] = None
    logout_url: Optional[str] = None
    simulator_login_url: Optional[str] = None
    metadata_tls_verify: bool = True
    allow_local_fallback_identifier: bool = False
    local_fallback_identifier_attribute: Optional[str] = None

    @field_validator("protocol", mode="before")
    @classmethod
    def normalize_protocol(cls, value):
        if value is None or value == "":
            return "oidc"
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @model_validator(mode="after")
    def validate_protocol_config(self):
        if not self.provider_key:
            self.provider_key = self.client_name.strip().lower().replace(" ", "-")

        if not self.display_name:
            self.display_name = self.client_name

        if self.protocol == "oidc":
            missing = [
                field_name
                for field_name in (
                    "client_id",
                    "openid_configuration",
                    "scope",
                    "max_age",
                    "code_challenge_method",
                )
                if getattr(self, field_name) in (None, "")
            ]
            if not self.redirect_uris:
                missing.append("redirect_uris")
            if missing:
                raise ValueError(
                    "OIDC legacy IDP configuration is missing required field(s): "
                    + ", ".join(missing)
                )

        if self.protocol == "saml":
            missing = [
                field_name
                for field_name in (
                    "provider_key",
                    "entity_id",
                    "metadata_url",
                    "expected_nameid_format",
                    "sp_entity_id",
                    "acs_url",
                )
                if getattr(self, field_name) in (None, "")
            ]
            if missing:
                raise ValueError(
                    "SAML legacy IDP configuration is missing required field(s): "
                    + ", ".join(missing)
                )

            if not self.expected_legacy_provider:
                self.expected_legacy_provider = self.client_name

        return self


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


class LegacyIdpConfigSchema(LegacyIdpSchema):
    pass


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
