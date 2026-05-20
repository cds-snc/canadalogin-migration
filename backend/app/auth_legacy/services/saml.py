import base64
import hashlib
import logging
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse
from xml.sax.saxutils import escape

import httpx
from fastapi import HTTPException, Request

try:
    from defusedxml import ElementTree as ET
except ImportError:  # pragma: no cover - dependency is installed in packaged envs.
    import xml.etree.ElementTree as ET

from app.config import get_configuration

logger = logging.getLogger(__name__)

SAML_ASSERTION_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
SAML_PROTOCOL_NS = "urn:oasis:names:tc:SAML:2.0:protocol"
SAML_METADATA_NS = "urn:oasis:names:tc:SAML:2.0:metadata"
DSIG_NS = "http://www.w3.org/2000/09/xmldsig#"
HTTP_POST_BINDING = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
HTTP_REDIRECT_BINDING = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
XMLDSIG_RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
XMLENC_SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"

NAMESPACES = {
    "saml": SAML_ASSERTION_NS,
    "samlp": SAML_PROTOCOL_NS,
    "md": SAML_METADATA_NS,
    "ds": DSIG_NS,
}


@dataclass(frozen=True)
class SamlIdpMetadata:
    entity_id: str
    sso_url: str
    sso_binding: str
    slo_url: str | None = None
    x509cert: str | None = None


@dataclass(frozen=True)
class ParsedSamlResponse:
    issuer: str | None
    nameid: str | None
    nameid_format: str | None
    session_index: str | None
    attributes: dict[str, list[str]]


@dataclass(frozen=True)
class SamlIdentity:
    provider_key: str
    provider_name: str
    legacy_pai: str
    nameid_format: str | None
    session_index: str | None
    attributes: dict[str, list[str]]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first_text(element) -> str | None:
    if element is None:
        return None
    text = "".join(element.itertext()).strip()
    return text or None


def _strip_cert(cert: str | None) -> str | None:
    if not cert:
        return None
    return "".join(cert.split())


def _format_saml_time(value: datetime | None = None) -> str:
    value = value or datetime.now(timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_saml_response_b64(saml_response: str) -> str:
    # Some local SAML POST flows arrive with base64 "+" decoded as spaces.
    # Repair that before XML signature validation so the signed XML bytes survive.
    repaired = saml_response.replace(" ", "+")
    return "".join(repaired.split())


def _trace_hash(value: str | bytes | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _saml_response_transport_summary(saml_response: str) -> dict[str, Any]:
    normalized = _normalize_saml_response_b64(saml_response)
    return {
        "raw_length": len(saml_response),
        "normalized_length": len(normalized),
        "space_count": saml_response.count(" "),
        "plus_count": saml_response.count("+"),
        "newline_count": saml_response.count("\n") + saml_response.count("\r"),
        "tab_count": saml_response.count("\t"),
        "normalized_changed": saml_response != normalized,
        "raw_sha256": _trace_hash(saml_response),
        "normalized_sha256": _trace_hash(normalized),
    }


def _cert_fingerprint(cert: str | None) -> str | None:
    stripped = _strip_cert(cert)
    if not stripped:
        return None
    try:
        return _trace_hash(base64.b64decode(stripped))
    except Exception:
        return _trace_hash(stripped)


def _unique_values(values: list[str | None]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def parse_saml_idp_metadata(
    metadata_xml: str,
    *,
    expected_entity_id: str | None = None,
) -> SamlIdpMetadata:
    try:
        root = ET.fromstring(metadata_xml)
    except ET.ParseError as exc:
        raise HTTPException(
            status_code=502, detail="SAML IdP metadata is not valid XML"
        ) from exc

    descriptor = root
    if _local_name(root.tag) != "EntityDescriptor":
        descriptor = root.find(".//md:EntityDescriptor", NAMESPACES)
    if descriptor is None:
        raise HTTPException(
            status_code=502, detail="SAML IdP metadata missing EntityDescriptor"
        )

    entity_id = descriptor.attrib.get("entityID")
    if not entity_id:
        raise HTTPException(
            status_code=502, detail="SAML IdP metadata missing entityID"
        )
    if expected_entity_id and entity_id != expected_entity_id:
        raise HTTPException(
            status_code=502,
            detail="SAML IdP metadata entityID does not match configured provider",
        )

    idp_descriptor = descriptor.find("md:IDPSSODescriptor", NAMESPACES)
    if idp_descriptor is None:
        idp_descriptor = descriptor.find(".//md:IDPSSODescriptor", NAMESPACES)
    if idp_descriptor is None:
        raise HTTPException(
            status_code=502, detail="SAML IdP metadata missing IDPSSODescriptor"
        )

    sso_services = idp_descriptor.findall("md:SingleSignOnService", NAMESPACES)
    if not sso_services:
        raise HTTPException(
            status_code=502, detail="SAML IdP metadata missing SingleSignOnService"
        )

    selected_sso = next(
        (
            service
            for service in sso_services
            if service.attrib.get("Binding") == HTTP_REDIRECT_BINDING
        ),
        sso_services[0],
    )
    sso_url = selected_sso.attrib.get("Location")
    sso_binding = selected_sso.attrib.get("Binding")
    if not sso_url or not sso_binding:
        raise HTTPException(
            status_code=502, detail="SAML IdP metadata has incomplete SSO service"
        )

    slo_service = idp_descriptor.find("md:SingleLogoutService", NAMESPACES)
    slo_url = slo_service.attrib.get("Location") if slo_service is not None else None
    cert = _strip_cert(
        _first_text(idp_descriptor.find(".//ds:X509Certificate", NAMESPACES))
    )

    return SamlIdpMetadata(
        entity_id=entity_id,
        sso_url=sso_url,
        sso_binding=sso_binding,
        slo_url=slo_url,
        x509cert=cert,
    )


def _ensure_unverified_metadata_tls_is_local(metadata_url: str) -> None:
    config = get_configuration()
    parsed = urlparse(metadata_url)
    local_hosts = {
        "localhost",
        "127.0.0.1",
        "::1",
        "host.docker.internal",
        "saml-gckey-idp",
        "saml-interac-idp",
    }
    if config.ENVIRONMENT == "local" and parsed.hostname in local_hosts:
        return
    raise HTTPException(
        status_code=500,
        detail="Unverified SAML metadata TLS is only allowed for local simulators",
    )


def _ensure_simulator_login_url_is_local(simulator_login_url: str) -> None:
    config = get_configuration()
    parsed = urlparse(simulator_login_url)
    local_hosts = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
    if config.ENVIRONMENT == "local" and parsed.hostname in local_hosts:
        return
    raise HTTPException(
        status_code=500,
        detail="SAML simulator login URL is only allowed for local simulators",
    )


def _host_for_browser(url: str) -> str:
    parsed = urlparse(url)
    gckey_port = 9080 if parsed.scheme == "http" else 9443
    interac_port = 9081 if parsed.scheme == "http" else 9444
    simulator_browser_hosts = {
        "host.docker.internal": parsed.port,
        "saml-gckey-idp": gckey_port,
        "saml-interac-idp": interac_port,
    }
    if parsed.hostname in simulator_browser_hosts:
        browser_port = simulator_browser_hosts[parsed.hostname]
        netloc = "localhost"
        if browser_port:
            netloc = f"{netloc}:{browser_port}"
        return urlunparse(parsed._replace(netloc=netloc))
    return url


def _metadata_for_browser_redirects(metadata: SamlIdpMetadata) -> SamlIdpMetadata:
    return SamlIdpMetadata(
        entity_id=metadata.entity_id,
        sso_url=_host_for_browser(metadata.sso_url),
        sso_binding=metadata.sso_binding,
        slo_url=_host_for_browser(metadata.slo_url) if metadata.slo_url else None,
        x509cert=metadata.x509cert,
    )


async def load_saml_idp_metadata(legacy_idp: Any) -> SamlIdpMetadata:
    metadata_url = getattr(legacy_idp, "metadata_url", None)
    if not metadata_url:
        raise HTTPException(status_code=500, detail="SAML metadata URL is not configured")

    verify_tls = getattr(legacy_idp, "metadata_tls_verify", True)
    if not verify_tls:
        _ensure_unverified_metadata_tls_is_local(metadata_url)

    try:
        async with httpx.AsyncClient(verify=verify_tls, timeout=10.0) as client:
            response = await client.get(metadata_url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Failed to load SAML IdP metadata", exc_info=True)
        raise HTTPException(
            status_code=502, detail="Failed to load SAML IdP metadata"
        ) from exc

    metadata = parse_saml_idp_metadata(
        response.text,
        expected_entity_id=getattr(legacy_idp, "entity_id", None),
    )
    return _metadata_for_browser_redirects(metadata)


def build_saml_authn_request_xml(
    legacy_idp: Any,
    *,
    request_id: str,
    destination: str,
    issue_instant: datetime | None = None,
) -> str:
    requested_context = getattr(legacy_idp, "requested_authn_context", None)
    requested_context_xml = ""
    if requested_context:
        comparison = getattr(
            legacy_idp, "requested_authn_context_comparison", None
        ) or "exact"
        requested_context_xml = (
            f'<samlp:RequestedAuthnContext Comparison="{escape(comparison)}">'
            f"<saml:AuthnContextClassRef>{escape(requested_context)}</saml:AuthnContextClassRef>"
            "</samlp:RequestedAuthnContext>"
        )

    sp_entity_id = getattr(legacy_idp, "sp_entity_id", None)
    acs_url = getattr(legacy_idp, "acs_url", None)
    nameid_format = getattr(legacy_idp, "expected_nameid_format", None)
    if not sp_entity_id or not acs_url or not nameid_format:
        raise HTTPException(
            status_code=500, detail="SAML service provider settings are incomplete"
        )

    return (
        f'<samlp:AuthnRequest xmlns:samlp="{SAML_PROTOCOL_NS}" '
        f'xmlns:saml="{SAML_ASSERTION_NS}" '
        f'ID="{escape(request_id)}" Version="2.0" '
        f'IssueInstant="{_format_saml_time(issue_instant)}" '
        f'Destination="{escape(destination)}" '
        f'ProtocolBinding="{HTTP_POST_BINDING}" '
        f'AssertionConsumerServiceURL="{escape(acs_url)}">'
        f"<saml:Issuer>{escape(sp_entity_id)}</saml:Issuer>"
        f'<samlp:NameIDPolicy Format="{escape(nameid_format)}" '
        f'SPNameQualifier="{escape(sp_entity_id)}" AllowCreate="true"/>'
        f"{requested_context_xml}"
        "</samlp:AuthnRequest>"
    )


def encode_saml_redirect_request(authn_request_xml: str) -> str:
    compressor = zlib.compressobj(wbits=-15)
    compressed = compressor.compress(authn_request_xml.encode("utf-8"))
    compressed += compressor.flush()
    return base64.b64encode(compressed).decode("ascii")


def build_saml_redirect_url(
    *,
    sso_url: str,
    authn_request_xml: str,
    relay_state: str,
) -> str:
    separator = "&" if "?" in sso_url else "?"
    query = urlencode(
        {
            "SAMLRequest": encode_saml_redirect_request(authn_request_xml),
            "RelayState": relay_state,
        }
    )
    return f"{sso_url}{separator}{query}"


async def build_saml_login_redirect_url(
    legacy_idp: Any,
    *,
    request_id: str,
    relay_state: str,
) -> str:
    metadata = await load_saml_idp_metadata(legacy_idp)
    authn_request_xml = build_saml_authn_request_xml(
        legacy_idp,
        request_id=request_id,
        destination=metadata.sso_url,
    )
    simulator_login_url = getattr(legacy_idp, "simulator_login_url", None)
    if simulator_login_url:
        _ensure_simulator_login_url_is_local(simulator_login_url)
    return build_saml_redirect_url(
        sso_url=simulator_login_url or metadata.sso_url,
        authn_request_xml=authn_request_xml,
        relay_state=relay_state,
    )


def build_sp_metadata_xml(
    *,
    entity_id: str,
    acs_url: str,
    logout_url: str | None = None,
) -> str:
    logout_xml = ""
    if logout_url:
        logout_xml = (
            f'<md:SingleLogoutService Binding="{HTTP_REDIRECT_BINDING}" '
            f'Location="{escape(logout_url)}"/>'
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<md:EntityDescriptor xmlns:md="{SAML_METADATA_NS}" '
        f'entityID="{escape(entity_id)}">'
        '<md:SPSSODescriptor AuthnRequestsSigned="false" '
        'WantAssertionsSigned="true" '
        'protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">'
        f"{logout_xml}"
        f'<md:AssertionConsumerService Binding="{HTTP_POST_BINDING}" '
        f'Location="{escape(acs_url)}" index="0" isDefault="true"/>'
        "</md:SPSSODescriptor>"
        "</md:EntityDescriptor>"
    )


def _decode_saml_response(saml_response: str) -> bytes:
    compact = _normalize_saml_response_b64(saml_response)
    try:
        return base64.b64decode(compact, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid SAMLResponse") from exc


def parse_saml_response_payload(saml_response: str) -> ParsedSamlResponse:
    try:
        root = ET.fromstring(_decode_saml_response(saml_response))
    except ET.ParseError as exc:
        raise HTTPException(status_code=400, detail="SAMLResponse is not valid XML") from exc

    assertion = root.find(".//saml:Assertion", NAMESPACES)
    issuer_element = None
    if assertion is not None:
        issuer_element = assertion.find("saml:Issuer", NAMESPACES)
    if issuer_element is None:
        issuer_element = root.find("saml:Issuer", NAMESPACES)

    nameid_element = root.find(".//saml:Subject/saml:NameID", NAMESPACES)
    if nameid_element is None:
        nameid_element = root.find(".//saml:NameID", NAMESPACES)

    authn_statement = root.find(".//saml:AuthnStatement", NAMESPACES)
    attributes: dict[str, list[str]] = {}
    for attribute in root.findall(".//saml:Attribute", NAMESPACES):
        name = attribute.attrib.get("Name") or attribute.attrib.get("FriendlyName")
        if not name:
            continue
        values = []
        for value in attribute.findall("saml:AttributeValue", NAMESPACES):
            text = _first_text(value)
            if text is not None:
                values.append(text)
        attributes[name] = values

    return ParsedSamlResponse(
        issuer=_first_text(issuer_element),
        nameid=_first_text(nameid_element),
        nameid_format=(
            nameid_element.attrib.get("Format") if nameid_element is not None else None
        ),
        session_index=(
            authn_statement.attrib.get("SessionIndex")
            if authn_statement is not None
            else None
        ),
        attributes=attributes,
    )


def normalize_saml_identity(
    parsed_response: ParsedSamlResponse,
    legacy_idp: Any,
) -> SamlIdentity:
    expected_entity_id = getattr(legacy_idp, "entity_id", None)
    if expected_entity_id and parsed_response.issuer != expected_entity_id:
        raise HTTPException(
            status_code=400, detail="SAML issuer does not match configured provider"
        )

    expected_nameid_format = getattr(legacy_idp, "expected_nameid_format", None)
    if expected_nameid_format and parsed_response.nameid_format != expected_nameid_format:
        raise HTTPException(status_code=400, detail="Unexpected SAML NameID format")

    expected_legacy_provider = getattr(legacy_idp, "expected_legacy_provider", None)
    legacy_provider_values = parsed_response.attributes.get("legacy_provider", [])
    if expected_legacy_provider and expected_legacy_provider not in legacy_provider_values:
        raise HTTPException(status_code=400, detail="Unexpected SAML legacy provider")

    legacy_pai = parsed_response.nameid
    if not legacy_pai and getattr(legacy_idp, "allow_local_fallback_identifier", False):
        fallback_attribute = getattr(
            legacy_idp, "local_fallback_identifier_attribute", None
        )
        if fallback_attribute:
            legacy_pai_values = parsed_response.attributes.get(fallback_attribute, [])
            legacy_pai = legacy_pai_values[0] if legacy_pai_values else None

    if not legacy_pai:
        raise HTTPException(status_code=400, detail="SAML NameID is required")

    provider_key = getattr(legacy_idp, "provider_key", None) or getattr(
        legacy_idp, "client_name", ""
    )
    provider_name = getattr(legacy_idp, "client_name", provider_key)
    return SamlIdentity(
        provider_key=provider_key,
        provider_name=provider_name,
        legacy_pai=legacy_pai,
        nameid_format=parsed_response.nameid_format,
        session_index=parsed_response.session_index,
        attributes=parsed_response.attributes,
    )


def _build_onelogin_request_data(
    request: Request,
    *,
    saml_response: str,
    relay_state: str | None,
) -> dict[str, Any]:
    request_url = str(getattr(request, "url", "") or "")
    parsed = urlparse(request_url)
    if not parsed.scheme or not parsed.netloc:
        parsed = urlparse(request.scope.get("path", "")) if hasattr(request, "scope") else parsed

    scheme = parsed.scheme or "http"
    port = parsed.port or (443 if scheme == "https" else 80)
    http_host = parsed.netloc or "localhost"
    normalized_saml_response = _normalize_saml_response_b64(saml_response)
    return {
        "https": "on" if scheme == "https" else "off",
        "http_host": http_host,
        "server_port": str(port),
        "script_name": parsed.path or "",
        "get_data": {},
        "post_data": {
            "SAMLResponse": normalized_saml_response,
            "RelayState": relay_state or "",
        },
    }


def _build_onelogin_settings(
    legacy_idp: Any,
    metadata: SamlIdpMetadata,
) -> dict[str, Any]:
    if not metadata.x509cert:
        raise HTTPException(
            status_code=502, detail="SAML IdP metadata missing signing certificate"
        )

    requested_context = getattr(legacy_idp, "requested_authn_context", None)
    security: dict[str, Any] = {
        "nameIdEncrypted": False,
        "authnRequestsSigned": False,
        "logoutRequestSigned": False,
        "logoutResponseSigned": False,
        "signMetadata": False,
        "wantMessagesSigned": False,
        "wantAssertionsSigned": True,
        "wantAssertionsEncrypted": False,
        "wantNameId": True,
        "wantNameIdEncrypted": False,
        "wantAttributeStatement": False,
        "requestedAuthnContext": [requested_context] if requested_context else False,
        "requestedAuthnContextComparison": getattr(
            legacy_idp, "requested_authn_context_comparison", None
        )
        or "exact",
        "signatureAlgorithm": XMLDSIG_RSA_SHA256,
        "digestAlgorithm": XMLENC_SHA256,
    }

    settings: dict[str, Any] = {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": getattr(legacy_idp, "sp_entity_id", None),
            "assertionConsumerService": {
                "url": getattr(legacy_idp, "acs_url", None),
                "binding": HTTP_POST_BINDING,
            },
            "NameIDFormat": getattr(legacy_idp, "expected_nameid_format", None),
        },
        "idp": {
            "entityId": metadata.entity_id,
            "singleSignOnService": {
                "url": metadata.sso_url,
                "binding": metadata.sso_binding,
            },
            "x509cert": metadata.x509cert,
        },
        "security": security,
    }
    if metadata.slo_url:
        settings["idp"]["singleLogoutService"] = {
            "url": metadata.slo_url,
            "binding": HTTP_REDIRECT_BINDING,
        }
    return settings


def _saml_response_validation_summary(saml_response: str) -> dict[str, Any]:
    try:
        root = ET.fromstring(_decode_saml_response(saml_response))
    except Exception:
        return {"parseable": False}

    assertion = root.find(".//saml:Assertion", NAMESPACES)
    conditions = root.find(".//saml:Conditions", NAMESPACES)
    confirmation_data = root.find(".//saml:SubjectConfirmationData", NAMESPACES)
    audience = root.find(".//saml:Audience", NAMESPACES)
    issuer = root.find("saml:Issuer", NAMESPACES)
    response_signature = root.find("ds:Signature", NAMESPACES)
    assertion_signature = (
        assertion.find("ds:Signature", NAMESPACES) if assertion is not None else None
    )
    signatures = root.findall(".//ds:Signature", NAMESPACES)
    references = root.findall(".//ds:Reference", NAMESPACES)
    response_cert = (
        _first_text(response_signature.find(".//ds:X509Certificate", NAMESPACES))
        if response_signature is not None
        else None
    )
    assertion_cert = (
        _first_text(assertion_signature.find(".//ds:X509Certificate", NAMESPACES))
        if assertion_signature is not None
        else None
    )

    return {
        "parseable": True,
        "response_id": root.attrib.get("ID"),
        "assertion_id": assertion.attrib.get("ID") if assertion is not None else None,
        "issuer": _first_text(issuer),
        "destination": root.attrib.get("Destination"),
        "response_in_response_to": root.attrib.get("InResponseTo"),
        "subject_recipient": (
            confirmation_data.attrib.get("Recipient")
            if confirmation_data is not None
            else None
        ),
        "subject_in_response_to": (
            confirmation_data.attrib.get("InResponseTo")
            if confirmation_data is not None
            else None
        ),
        "audience": _first_text(audience),
        "conditions_not_before": (
            conditions.attrib.get("NotBefore") if conditions is not None else None
        ),
        "conditions_not_on_or_after": (
            conditions.attrib.get("NotOnOrAfter") if conditions is not None else None
        ),
        "response_signature_count": len(root.findall("ds:Signature", NAMESPACES)),
        "assertion_signature_count": len(
            root.findall(".//saml:Assertion/ds:Signature", NAMESPACES)
        ),
        "signature_methods": _unique_values(
            [
                element.attrib.get("Algorithm")
                for signature in signatures
                for element in signature.findall(".//ds:SignatureMethod", NAMESPACES)
            ]
        ),
        "digest_methods": _unique_values(
            [
                element.attrib.get("Algorithm")
                for signature in signatures
                for element in signature.findall(".//ds:DigestMethod", NAMESPACES)
            ]
        ),
        "canonicalization_methods": _unique_values(
            [
                element.attrib.get("Algorithm")
                for signature in signatures
                for element in signature.findall(
                    ".//ds:CanonicalizationMethod", NAMESPACES
                )
            ]
        ),
        "transform_methods": _unique_values(
            [
                element.attrib.get("Algorithm")
                for signature in signatures
                for element in signature.findall(".//ds:Transform", NAMESPACES)
            ]
        ),
        "reference_uris": _unique_values(
            [reference.attrib.get("URI") for reference in references]
        ),
        "response_cert_sha256": _cert_fingerprint(response_cert),
        "assertion_cert_sha256": _cert_fingerprint(assertion_cert),
        "assertion_present": assertion is not None,
    }


def _saml_settings_trace_summary(
    legacy_idp: Any,
    metadata: SamlIdpMetadata,
    settings: dict[str, Any],
) -> dict[str, Any]:
    security = settings.get("security", {})
    return {
        "strict": settings.get("strict"),
        "sp_entity_id": getattr(legacy_idp, "sp_entity_id", None),
        "sp_acs_url": getattr(legacy_idp, "acs_url", None),
        "idp_entity_id": metadata.entity_id,
        "idp_sso_url": metadata.sso_url,
        "metadata_cert_sha256": _cert_fingerprint(metadata.x509cert),
        "want_messages_signed": security.get("wantMessagesSigned"),
        "want_assertions_signed": security.get("wantAssertionsSigned"),
        "requested_authn_context": security.get("requestedAuthnContext"),
        "requested_authn_context_comparison": security.get(
            "requestedAuthnContextComparison"
        ),
        "signature_algorithm": security.get("signatureAlgorithm"),
        "digest_algorithm": security.get("digestAlgorithm"),
    }


def validate_saml_response_with_onelogin(
    request: Request,
    *,
    saml_response: str,
    relay_state: str | None,
    request_id: str,
    legacy_idp: Any,
    metadata: SamlIdpMetadata,
) -> None:
    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="SAML support requires the python3-saml dependency",
        ) from exc

    try:
        request_data = _build_onelogin_request_data(
            request,
            saml_response=saml_response,
            relay_state=relay_state,
        )
        settings = _build_onelogin_settings(legacy_idp, metadata)
        transport_summary = _saml_response_transport_summary(saml_response)
        response_summary = _saml_response_validation_summary(saml_response)
        settings_summary = _saml_settings_trace_summary(
            legacy_idp, metadata, settings
        )
        logger.info(
            "SAML validation trace started: request_url=%s; expected_request_id=%s; "
            "relay_state_sha256=%s; transport=%s; response=%s; settings=%s",
            str(getattr(request, "url", "") or ""),
            request_id,
            _trace_hash(relay_state),
            transport_summary,
            response_summary,
            settings_summary,
        )
        auth = OneLogin_Saml2_Auth(
            request_data,
            old_settings=settings,
        )
        auth.process_response(request_id=request_id)
    except Exception as exc:
        logger.error(
            "SAML response validation raised exception: request_url=%s; "
            "expected_request_id=%s; relay_state_sha256=%s; transport=%s; "
            "response=%s; settings=%s",
            str(getattr(request, "url", "") or ""),
            request_id,
            _trace_hash(relay_state),
            _saml_response_transport_summary(saml_response),
            _saml_response_validation_summary(saml_response),
            _saml_settings_trace_summary(
                legacy_idp,
                metadata,
                _build_onelogin_settings(legacy_idp, metadata),
            ),
            exc_info=True,
        )
        raise HTTPException(status_code=400, detail="SAML response validation failed") from exc

    errors = auth.get_errors()
    if errors:
        logger.error(
            "SAML response validation errors: %s; reason=%s; request_url=%s; "
            "expected_request_id=%s; expected_acs_url=%s; relay_state_sha256=%s; "
            "transport=%s; response=%s; settings=%s",
            errors,
            auth.get_last_error_reason(),
            str(getattr(request, "url", "") or ""),
            request_id,
            getattr(legacy_idp, "acs_url", None),
            _trace_hash(relay_state),
            transport_summary,
            response_summary,
            settings_summary,
        )
        raise HTTPException(
            status_code=400,
            detail=f"SAML response validation failed: {', '.join(errors)}",
        )
    if not auth.is_authenticated():
        raise HTTPException(status_code=400, detail="SAML response is not authenticated")
    logger.info(
        "SAML validation trace succeeded: request_url=%s; expected_request_id=%s; "
        "relay_state_sha256=%s; transport=%s; response=%s; settings=%s",
        str(getattr(request, "url", "") or ""),
        request_id,
        _trace_hash(relay_state),
        transport_summary,
        response_summary,
        settings_summary,
    )


async def resolve_saml_identity(
    request: Request,
    *,
    legacy_idp: Any,
    saml_response: str,
    relay_state: str | None,
    request_id: str,
) -> SamlIdentity:
    metadata = await load_saml_idp_metadata(legacy_idp)
    validate_saml_response_with_onelogin(
        request,
        saml_response=saml_response,
        relay_state=relay_state,
        request_id=request_id,
        legacy_idp=legacy_idp,
        metadata=metadata,
    )
    parsed_response = parse_saml_response_payload(saml_response)
    return normalize_saml_identity(parsed_response, legacy_idp)
