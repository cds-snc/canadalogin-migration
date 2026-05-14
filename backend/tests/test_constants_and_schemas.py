import pytest

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
    assert rp.IDP[0].protocol == "oidc"
    assert rp.IDP[0].provider_key == "sic"
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


def test_rp_schema_parses_saml_legacy_idp():
    legacy_idp = LegacyIdpSchema(
        client_name="GCKey",
        protocol="saml",
        provider_key="gckey-sim",
        display_name="GCKey Simulator",
        entity_id="local-gckey-saml-idp",
        metadata_url="https://localhost:9443/sso/saml2/idp/metadata.php",
        metadata_tls_verify=False,
        expected_legacy_provider="GCKey",
        expected_nameid_format="urn:oasis:names:tc:SAML:2.0:nameid-format:persistent",
        requested_authn_context="urn:gc-ca:cyber-auth:assurance:loa2",
        sp_entity_id="http://localhost:8000/v1/auth/legacy/saml/metadata",
        acs_url="http://localhost:8000/v1/auth/legacy/saml/acs",
    )
    rp = RPSchema(
        rp_client_id="rp-1",
        rp_client_name="RP",
        rp_client_name_en="RP EN",
        rp_client_name_fr="RP FR",
        rp_redirect_uri="https://rp.example.test",
        IDP=[legacy_idp],
    )

    assert rp.IDP[0].protocol == "saml"
    assert rp.IDP[0].provider_key == "gckey-sim"
    assert rp.IDP[0].client_id is None
    assert rp.IDP[0].metadata_tls_verify is False
    assert rp.IDP[0].metadata_url == "https://localhost:9443/sso/saml2/idp/metadata.php"


def test_saml_legacy_idp_requires_saml_fields():
    with pytest.raises(ValueError, match="SAML legacy IDP configuration"):
        LegacyIdpSchema(
            client_name="GCKey",
            protocol="saml",
            provider_key="gckey-sim",
            entity_id="local-gckey-saml-idp",
        )


def test_rp_schema_accepts_language_specific_redirect_uris():
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
        rp_redirect_uri_en="https://rp.example.test/en",
        rp_redirect_uri_fr="https://rp.example.test/fr",
        IDP=[legacy_idp],
    )

    assert rp.rp_redirect_uri is None
    assert rp.rp_redirect_uri_en == "https://rp.example.test/en"
    assert rp.rp_redirect_uri_fr == "https://rp.example.test/fr"


def test_rp_schema_requires_at_least_one_redirect_uri():
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

    with pytest.raises(ValueError, match="rp_redirect_uri"):
        RPSchema(
            rp_client_id="rp-1",
            rp_client_name="RP",
            rp_client_name_en="RP EN",
            rp_client_name_fr="RP FR",
            IDP=[legacy_idp],
        )


def test_generate_code_challenge_is_stable():
    verifier = "abc123"
    challenge = generate_code_challenge(verifier)
    assert isinstance(challenge, str)
    assert challenge
