import base64
import binascii
import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import HTTPException, Request

from app.constants.session_keys import SessionKeys

PAIR_PARAMETER_KEYS = (
    ("paramOneName", "paramOne"),
    ("paramTwoName", "paramTwo"),
)


def _decode_customparameters_payload(customparameters: str) -> dict[str, object]:
    candidate = customparameters.strip()
    padding = "=" * (-len(candidate) % 4)

    try:
        decoded_payload = base64.urlsafe_b64decode(f"{candidate}{padding}")
        payload = json.loads(decoded_payload.decode("utf-8"))
    except (
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        binascii.Error,
    ) as exc:
        raise HTTPException(status_code=400, detail="Invalid customparameters") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid customparameters")

    return payload


def _normalize_parameter_value(value: object) -> str:
    if value is None:
        return ""

    if isinstance(value, (str, int, float, bool)):
        return str(value)

    raise HTTPException(status_code=400, detail="Invalid customparameters")


def normalize_customparameters(payload: dict[str, object]) -> dict[str, str]:
    uses_pair_format = any(
        key in payload
        for parameter_keys in PAIR_PARAMETER_KEYS
        for key in parameter_keys
    )

    if not uses_pair_format:
        normalized_parameters: dict[str, str] = {}
        for parameter_name, parameter_value in payload.items():
            if not isinstance(parameter_name, str) or not parameter_name.strip():
                raise HTTPException(status_code=400, detail="Invalid customparameters")
            normalized_parameters[parameter_name.strip()] = _normalize_parameter_value(
                parameter_value
            )
        return normalized_parameters

    normalized_parameters = {}
    for parameter_name_key, parameter_value_key in PAIR_PARAMETER_KEYS:
        parameter_name = payload.get(parameter_name_key)
        parameter_value = payload.get(parameter_value_key)

        if parameter_name is None and parameter_value is None:
            continue

        if not isinstance(parameter_name, str) or not parameter_name.strip():
            raise HTTPException(status_code=400, detail="Invalid customparameters")

        normalized_parameters[parameter_name.strip()] = _normalize_parameter_value(
            parameter_value
        )

    return normalized_parameters


def parse_customparameters(customparameters: str | None) -> dict[str, str]:
    if not customparameters:
        return {}

    payload = _decode_customparameters_payload(customparameters)
    return normalize_customparameters(payload)


def set_customparameters_in_session(
    request: Request, customparameters: str | None
) -> None:
    if not customparameters:
        request.session.pop(SessionKeys.CUSTOM_PARAMETERS.value, None)
        return

    request.session[SessionKeys.CUSTOM_PARAMETERS.value] = parse_customparameters(
        customparameters
    )


def get_customparameters_from_session(request: Request) -> dict[str, str]:
    custom_parameters = request.session.get(SessionKeys.CUSTOM_PARAMETERS.value, {})

    if not isinstance(custom_parameters, dict):
        return {}

    return {
        str(parameter_name): str(parameter_value)
        for parameter_name, parameter_value in custom_parameters.items()
    }


def append_customparameters_to_url(
    url: str, custom_parameters: dict[str, str] | None
) -> str:
    if not custom_parameters:
        return url

    parsed_url = urlsplit(url)
    query_parameters = dict(parse_qsl(parsed_url.query, keep_blank_values=True))
    query_parameters.update(custom_parameters)

    return urlunsplit(parsed_url._replace(query=urlencode(query_parameters)))
