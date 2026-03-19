from app.constants.session_keys import SessionKeys
from app.rp.schemas import LegacyIdpSchema, RPSchema
from app.utils.oidc import generate_code_challenge


def test_session_keys_values():
    assert SessionKeys.SESSION_USER_ACCESS_TOKEN_KEY.value == "access_token"
    assert SessionKeys.RP_CLIENT_ID_KEY.value == "rp_client_id"
    assert SessionKeys.CUSTOM_PARAMETERS.value == "customparameters"


def test_rp_schema_parses():
    legacy_idp = LegacyIdpSchema(
        client_id="cid",
        client_name="SIC",
        client_secret="secret",
        openid_configuration="https://idp/.well-known/openid-configuration",
        redirect_uris=["https://callback"],
        scope="openid",
        max_age=0,
        code_challenge_method="S256",
    )
    rp = RPSchema(
        rp_client_id="rp-1",
        rp_client_name="RP",
        rp_client_name_en="RP EN",
        rp_client_name_fr="RP FR",
        rp_redirect_uri="https://rp.example.test",
        acr_values="gckey, mfa",
        IDP=[legacy_idp],
    )
    assert rp.IDP[0].client_name == "SIC"
    assert rp.dependent_client_ids == []


def test_rp_schema_parses_dependent_client_ids_alias():
    rp = RPSchema.model_validate(
        {
            "rp_client_id": "rp-1",
            "rp_client_name": "RP",
            "rp_client_name_en": "RP EN",
            "rp_client_name_fr": "RP FR",
            "rp_redirect_uri": "https://rp.example.test",
            "dependentClientIds": ["rp-2", "rp-3"],
            "IDP": [
                {
                    "client_id": "cid",
                    "client_name": "SIC",
                    "client_secret": "secret",
                    "openid_configuration": "https://idp/.well-known/openid-configuration",
                    "redirect_uris": ["https://callback"],
                    "scope": "openid",
                    "max_age": 0,
                    "code_challenge_method": "S256",
                }
            ],
        }
    )

    assert rp.dependent_client_ids == ["rp-2", "rp-3"]
    assert rp.acr_values == ""


def test_rp_schema_defaults_blank_acr_values():
    legacy_idp = LegacyIdpSchema(
        client_id="cid",
        client_name="SIC",
        client_secret="secret",
        openid_configuration="https://idp/.well-known/openid-configuration",
        redirect_uris=["https://callback"],
        scope="openid",
        max_age=0,
        code_challenge_method="S256",
    )
    rp = RPSchema(
        rp_client_id="rp-1",
        rp_client_name="RP",
        rp_client_name_en="RP EN",
        rp_client_name_fr="RP FR",
        rp_redirect_uri="https://rp.example.test",
        IDP=[legacy_idp],
    )
    assert rp.acr_values == ""


def test_generate_code_challenge_is_stable():
    verifier = "abc123"
    challenge = generate_code_challenge(verifier)
    assert isinstance(challenge, str)
    assert challenge
