import os
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyUrl, Field
from dotenv import load_dotenv
from pathlib import Path
from app.constants.verify_endpoints import VerifyAPIEndpoint

# Load .env file from backend directory (if it exists)
# In production, environment variables are typically set directly in the system
# load_dotenv() won't override existing environment variables
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    # In production/containers, env vars are set directly, no .env file needed
    load_dotenv()  # Still call to allow .env in other locations if present


class AppInfo(BaseSettings):
    app_name: str = "GC Sign In Backend API"
    github_url: AnyUrl = "https://github.com/cds-snc/gc-signin-user-self-service-webapp"
    email: str = "gcsignin@cds-snc.ca"


class IBMVerifyConfig(BaseSettings):

    IBM_VERIFY_TENANT_URL: str
    IBM_VERIFY_MIGRATION_API_CLIENT_ID: str
    IBM_VERIFY_MIGRATION_API_SECRET: str
    IBM_VERIFY_MIGRATION_CLIENT_ID: str
    IBM_VERIFY_MIGRATION_SECRET: str
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=True
    )


class SessionConfig(BaseSettings):
    SESSION_REDIS_URL: str = "redis://localhost:6379/0"
    SESSION_COOKIE_NAME: str = "gc-manage-app"
    SESSION_LIFETIME: int = 60 * 30  # default to 30 minutes in seconds
    REDIS_AUTH_SECRET: str = "test-secret"
    REDIS_DOMAIN: str = "localhost"
    REDIS_PORT: int = 6379
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=True
    )


class LegacyIdpConfig(BaseSettings):
    # Indexed environment variables for multiple IDPs
    # LEGACY_IDP_0_CLIENT_ID, LEGACY_IDP_1_CLIENT_ID, etc.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=True
    )

    @property
    def idp_configs_list(self) -> List[dict]:
        """Parse indexed environment variables into a list of IDP configs."""
        idps = []
        index = 0

        # Keep reading IDPs until we don't find one at the current index
        while True:
            client_id = os.getenv(f"LEGACY_IDP_{index}_CLIENT_ID")
            if not client_id:
                break

            redirect_uris_str = os.getenv(f"LEGACY_IDP_{index}_REDIRECT_URIS", "")
            redirect_uris = [
                uri.strip() for uri in redirect_uris_str.split(",") if uri.strip()
            ]

            idp = {
                "client_id": client_id,
                "client_name": os.getenv(f"LEGACY_IDP_{index}_CLIENT_NAME", ""),
                "client_secret": os.getenv(f"LEGACY_IDP_{index}_CLIENT_SECRET", ""),
                "openid_configuration": os.getenv(
                    f"LEGACY_IDP_{index}_OPENID_CONFIGURATION", ""
                ),
                "redirect_uris": redirect_uris,
                "scope": os.getenv(f"LEGACY_IDP_{index}_SCOPE", "openid profile email"),
                "max_age": int(os.getenv(f"LEGACY_IDP_{index}_MAX_AGE", "3600")),
                "code_challenge_method": os.getenv(
                    f"LEGACY_IDP_{index}_CODE_CHALLENGE_METHOD", "S256"
                ),
            }
            idps.append(idp)
            index += 1

        return idps


class RPConfig(BaseSettings):
    RP_CLIENT_ID: str
    RP_CLIENT_NAME: str
    RP_CLIENT_NAME_EN: str
    RP_CLIENT_NAME_FR: str
    RP_REDIRECT_URI: str
    RP_REDIRECT_URI_EN: str
    RP_REDIRECT_URI_FR: str

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=True
    )


class Configuration(BaseSettings):
    app_info: AppInfo = AppInfo()
    ibm_verify_config: IBMVerifyConfig = IBMVerifyConfig()
    session_config: SessionConfig = SessionConfig()
    legacy_idp_config: LegacyIdpConfig = LegacyIdpConfig()
    rp_config: RPConfig = RPConfig()
    ENVIRONMENT: str = Field(default="local")
    LOG_LEVEL: str = Field(default="INFO")
    V1_API_VERSION: str = "/v1"
    ROOT_DOMAIN: Optional[str] = (
        None  # Not required for local development, value should be ".gc-signin.cdssandbox.xyz"
    )
    PROFILE_MANAGEMENT_DOMAIN: str = (
        "http://localhost:3000"  # Frontend Management App domain to app.gc-signin.cdssandbox.xyz
    )

    CORS_ORIGINS: str = Field(
        default="localhost:3000,localhost:8000",
        description="Comma-separated list of CORS origins, Terraform cant pass in a list[str].",
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS_ORIGINS string to list - Terraform cant pass in a list[str]."""
        http_value = "https://"
        if self.ENVIRONMENT == "local":
            http_value = "http://"
        return [
            f"{http_value}{origin.strip()}" for origin in self.CORS_ORIGINS.split(",")
        ]

    @property
    def profile_api_endpoint(self) -> str:
        return f"{self.ibm_verify_config.IBM_VERIFY_TENANT_URL}{VerifyAPIEndpoint.PROFILE.value}"

    @property
    def oidc_well_known_config(self) -> str:
        return f"{self.ibm_verify_config.IBM_VERIFY_TENANT_URL}{VerifyAPIEndpoint.OIDC_WELL_KNOWN_CONFIG.value}"

    @property
    def rp_user_applications_api_endpoint(self) -> str:
        return f"{self.ibm_verify_config.IBM_VERIFY_TENANT_URL}{VerifyAPIEndpoint.RP_USER_APPLICATIONS.value}"

    @property
    def password_resetter_api_endpoint(self) -> str:
        return f"{self.ibm_verify_config.IBM_VERIFY_TENANT_URL}{VerifyAPIEndpoint.PASSWORD_RESETTER.value}"

    @property
    def introspect_token_api_endpoint(self) -> str:
        return f"{self.ibm_verify_config.IBM_VERIFY_TENANT_URL}{VerifyAPIEndpoint.INTROSPECT_TOKEN.value}"

    @property
    def user_otp_factors_api_endpoint(self) -> str:
        return f"{self.ibm_verify_config.IBM_VERIFY_TENANT_URL}{VerifyAPIEndpoint.USER_OTP_FACTORS.value}"

    @property
    def password_policy_api_endpoint(self) -> str:
        return f"{self.ibm_verify_config.IBM_VERIFY_TENANT_URL}{VerifyAPIEndpoint.PASSWORDPOLICY.value}"

    @property
    def end_session_endpoint(self) -> str:
        return f"{self.ibm_verify_config.IBM_VERIFY_TENANT_URL}{VerifyAPIEndpoint.END_SESSION_ENDPOINT.value}"

    @property
    def users_api_endpoint(self) -> str:
        return f"{self.ibm_verify_config.IBM_VERIFY_TENANT_URL}{VerifyAPIEndpoint.USERS.value}"


@lru_cache
def get_configuration():
    return Configuration()
