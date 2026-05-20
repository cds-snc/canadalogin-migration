import base64
import zlib
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException

from app.auth_legacy.services.saml import (
    HTTP_REDIRECT_BINDING,
    _normalize_saml_response_b64,
    build_saml_authn_request_xml,
    build_saml_login_redirect_url,
    build_saml_redirect_url,
    load_saml_idp_metadata,
    normalize_saml_identity,
    parse_saml_idp_metadata,
    parse_saml_response_payload,
)

PERSISTENT_NAMEID_FORMAT = "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent"


def _saml_idp():
    return SimpleNamespace(
        client_name="GCKey",
        provider_key="gckey-sim",
        entity_id="local-gckey-saml-idp",
        expected_legacy_provider="GCKey",
        expected_nameid_format=PERSISTENT_NAMEID_FORMAT,
        requested_authn_context="urn:gc-ca:cyber-auth:assurance:loa2",
        requested_authn_context_comparison="exact",
        sp_entity_id="http://localhost:8000/v1/auth/legacy/saml/metadata",
        acs_url="http://localhost:8000/v1/auth/legacy/saml/acs",
        allow_local_fallback_identifier=False,
    )


def _encoded_response(
    *,
    provider: str = "GCKey",
    nameid: str = "gckey-pai-12345",
    nameid_format: str = PERSISTENT_NAMEID_FORMAT,
    issuer: str = "local-gckey-saml-idp",
) -> str:
    xml = f"""<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
        xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
        ID="_response" InResponseTo="_request">
      <saml:Issuer>{issuer}</saml:Issuer>
      <saml:Assertion ID="_assertion">
        <saml:Issuer>{issuer}</saml:Issuer>
        <saml:Subject>
          <saml:NameID Format="{nameid_format}">{nameid}</saml:NameID>
        </saml:Subject>
        <saml:AuthnStatement SessionIndex="_session-123"/>
        <saml:AttributeStatement>
          <saml:Attribute Name="legacy_provider">
            <saml:AttributeValue>{provider}</saml:AttributeValue>
          </saml:Attribute>
          <saml:Attribute Name="loa">
            <saml:AttributeValue>urn:gc-ca:cyber-auth:assurance:loa2</saml:AttributeValue>
          </saml:Attribute>
        </saml:AttributeStatement>
      </saml:Assertion>
    </samlp:Response>"""
    return base64.b64encode(xml.encode("utf-8")).decode("ascii")


def test_normalize_saml_response_repairs_form_decoded_plus():
    assert _normalize_saml_response_b64("abc def\n\tghi") == "abc+defghi"


def test_parse_saml_idp_metadata_prefers_redirect_sso_service():
    metadata = """<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
        xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
        entityID="local-gckey-saml-idp">
      <md:IDPSSODescriptor>
        <md:KeyDescriptor>
          <ds:KeyInfo><ds:X509Data><ds:X509Certificate>
            abc
          </ds:X509Certificate></ds:X509Data></ds:KeyInfo>
        </md:KeyDescriptor>
        <md:SingleSignOnService
          Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
          Location="https://localhost:9443/post"/>
        <md:SingleSignOnService
          Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
          Location="https://localhost:9443/redirect"/>
      </md:IDPSSODescriptor>
    </md:EntityDescriptor>"""

    result = parse_saml_idp_metadata(
        metadata,
        expected_entity_id="local-gckey-saml-idp",
    )

    assert result.entity_id == "local-gckey-saml-idp"
    assert result.sso_url == "https://localhost:9443/redirect"
    assert result.sso_binding == HTTP_REDIRECT_BINDING
    assert result.x509cert == "abc"


@pytest.mark.asyncio
async def test_load_saml_idp_metadata_rewrites_simulator_container_host_for_browser(
    monkeypatch,
):
    metadata = """<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
        entityID="local-gckey-saml-idp">
      <md:IDPSSODescriptor>
        <md:SingleSignOnService
          Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
          Location="https://saml-gckey-idp:8443/sso"/>
      </md:IDPSSODescriptor>
    </md:EntityDescriptor>"""

    class FakeResponse:
        text = metadata

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *, verify, timeout):
            self.verify = verify
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url):
            assert url == "https://saml-gckey-idp:8443/metadata"
            return FakeResponse()

    monkeypatch.setattr(
        "app.auth_legacy.services.saml.httpx.AsyncClient",
        FakeAsyncClient,
    )

    legacy_idp = SimpleNamespace(
        entity_id="local-gckey-saml-idp",
        metadata_url="https://saml-gckey-idp:8443/metadata",
        metadata_tls_verify=False,
    )

    result = await load_saml_idp_metadata(legacy_idp)

    assert result.sso_url == "https://localhost:9443/sso"


@pytest.mark.asyncio
async def test_load_saml_idp_metadata_rewrites_http_simulator_port_for_browser(
    monkeypatch,
):
    metadata = """<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
        entityID="local-gckey-saml-idp">
      <md:IDPSSODescriptor>
        <md:SingleSignOnService
          Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
          Location="http://saml-gckey-idp:8080/sso"/>
      </md:IDPSSODescriptor>
    </md:EntityDescriptor>"""

    class FakeResponse:
        text = metadata

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *, verify, timeout):
            self.verify = verify
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url):
            assert url == "http://saml-gckey-idp:8080/metadata"
            return FakeResponse()

    monkeypatch.setattr(
        "app.auth_legacy.services.saml.httpx.AsyncClient",
        FakeAsyncClient,
    )

    legacy_idp = SimpleNamespace(
        entity_id="local-gckey-saml-idp",
        metadata_url="http://saml-gckey-idp:8080/metadata",
        metadata_tls_verify=True,
    )

    result = await load_saml_idp_metadata(legacy_idp)

    assert result.sso_url == "http://localhost:9080/sso"


@pytest.mark.asyncio
async def test_load_saml_idp_metadata_rewrites_docker_host_for_browser_redirects(
    monkeypatch,
):
    metadata = """<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
        entityID="local-gckey-saml-idp">
      <md:IDPSSODescriptor>
        <md:SingleSignOnService
          Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
          Location="https://host.docker.internal:9443/sso"/>
        <md:SingleLogoutService
          Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
          Location="https://host.docker.internal:9443/logout"/>
      </md:IDPSSODescriptor>
    </md:EntityDescriptor>"""

    class FakeResponse:
        text = metadata

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *, verify, timeout):
            self.verify = verify
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url):
            assert url == "https://host.docker.internal:9443/metadata"
            return FakeResponse()

    monkeypatch.setattr(
        "app.auth_legacy.services.saml.httpx.AsyncClient",
        FakeAsyncClient,
    )

    legacy_idp = SimpleNamespace(
        entity_id="local-gckey-saml-idp",
        metadata_url="https://host.docker.internal:9443/metadata",
        metadata_tls_verify=False,
    )

    result = await load_saml_idp_metadata(legacy_idp)

    assert result.sso_url == "https://localhost:9443/sso"
    assert result.slo_url == "https://localhost:9443/logout"


def test_build_saml_authn_request_includes_nameid_policy_and_authn_context():
    xml = build_saml_authn_request_xml(
        _saml_idp(),
        request_id="_request-123",
        destination="https://localhost:9443/sso",
        issue_instant=datetime(2026, 5, 14, tzinfo=timezone.utc),
    )

    assert 'ID="_request-123"' in xml
    assert 'Destination="https://localhost:9443/sso"' in xml
    assert f'Format="{PERSISTENT_NAMEID_FORMAT}"' in xml
    assert 'AllowCreate="true"' in xml
    assert 'Comparison="exact"' in xml
    assert "urn:gc-ca:cyber-auth:assurance:loa2" in xml


@pytest.mark.asyncio
async def test_build_saml_login_redirect_url_can_use_local_simulator_page(
    monkeypatch,
):
    metadata = """<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
        entityID="local-gckey-saml-idp">
      <md:IDPSSODescriptor>
        <md:SingleSignOnService
          Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
          Location="http://saml-gckey-idp:8080/sso/module.php/saml/idp/singleSignOnService"/>
      </md:IDPSSODescriptor>
    </md:EntityDescriptor>"""

    class FakeResponse:
        text = metadata

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *, verify, timeout):
            self.verify = verify
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url):
            assert url == "http://saml-gckey-idp:8080/metadata"
            return FakeResponse()

    monkeypatch.setattr(
        "app.auth_legacy.services.saml.httpx.AsyncClient",
        FakeAsyncClient,
    )
    legacy_idp = _saml_idp()
    legacy_idp.metadata_url = "http://saml-gckey-idp:8080/metadata"
    legacy_idp.metadata_tls_verify = True
    legacy_idp.simulator_login_url = "http://localhost:9080/sim/index.php"

    redirect_url = await build_saml_login_redirect_url(
        legacy_idp,
        request_id="_request-123",
        relay_state="relay-123",
    )

    parsed = urlparse(redirect_url)
    query = parse_qs(parsed.query)
    decoded = zlib.decompress(
        base64.b64decode(query["SAMLRequest"][0]),
        wbits=-15,
    ).decode("utf-8")

    assert parsed.scheme == "http"
    assert parsed.netloc == "localhost:9080"
    assert parsed.path == "/sim/index.php"
    assert 'Destination="http://localhost:9080/sso/module.php/saml/idp/singleSignOnService"' in decoded
    assert query["RelayState"] == ["relay-123"]


def test_build_saml_redirect_url_uses_redirect_binding_deflate_encoding():
    authn_request_xml = "<samlp:AuthnRequest>ok</samlp:AuthnRequest>"

    redirect_url = build_saml_redirect_url(
        sso_url="https://localhost:9443/sso",
        authn_request_xml=authn_request_xml,
        relay_state="relay-123",
    )

    parsed = urlparse(redirect_url)
    query = parse_qs(parsed.query)
    decoded = zlib.decompress(
        base64.b64decode(query["SAMLRequest"][0]),
        wbits=-15,
    ).decode("utf-8")
    assert decoded == authn_request_xml
    assert query["RelayState"] == ["relay-123"]


def test_parse_saml_response_extracts_nameid_attributes_and_session_index():
    parsed = parse_saml_response_payload(_encoded_response())

    assert parsed.issuer == "local-gckey-saml-idp"
    assert parsed.nameid == "gckey-pai-12345"
    assert parsed.nameid_format == PERSISTENT_NAMEID_FORMAT
    assert parsed.session_index == "_session-123"
    assert parsed.attributes["legacy_provider"] == ["GCKey"]


def test_normalize_saml_identity_uses_nameid_as_legacy_pai():
    parsed = parse_saml_response_payload(_encoded_response())

    identity = normalize_saml_identity(parsed, _saml_idp())

    assert identity.provider_key == "gckey-sim"
    assert identity.provider_name == "GCKey"
    assert identity.legacy_pai == "gckey-pai-12345"
    assert identity.nameid_format == PERSISTENT_NAMEID_FORMAT


def test_normalize_saml_identity_rejects_provider_mismatch():
    parsed = parse_saml_response_payload(_encoded_response(provider="Interac"))

    with pytest.raises(HTTPException) as raised:
        normalize_saml_identity(parsed, _saml_idp())

    assert raised.value.status_code == 400
    assert raised.value.detail == "Unexpected SAML legacy provider"
