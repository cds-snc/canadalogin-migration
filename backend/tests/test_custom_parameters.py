import base64
import json
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.constants.session_keys import SessionKeys
from app.utils.custom_parameters import (
    append_customparameters_to_url,
    get_rp_return_parameters_from_session,
    parse_customparameters,
    set_customparameters_in_session,
)


def _encode_payload(payload: dict[str, object]) -> str:
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("utf-8")
    return encoded.rstrip("=")


def test_parse_customparameters_decodes_pair_format():
    encoded = _encode_payload(
        {
            "paramOneName": "fakeparam1",
            "paramOne": "value-1",
            "paramTwoName": "fakeparam2",
            "paramTwo": "value-2",
        }
    )

    parsed = parse_customparameters(encoded)

    assert parsed == {"fakeparam1": "value-1", "fakeparam2": "value-2"}


def test_set_customparameters_in_session_clears_existing_value():
    request = MagicMock()
    request.session = {SessionKeys.CUSTOM_PARAMETERS.value: {"old": "value"}}

    set_customparameters_in_session(request, None)

    assert SessionKeys.CUSTOM_PARAMETERS.value not in request.session


def test_append_customparameters_to_url_merges_existing_query():
    redirect_url = append_customparameters_to_url(
        "https://rp.example.test/landing?existing=1",
        {"fakeparam1": "value-1"},
    )

    assert (
        redirect_url == "https://rp.example.test/landing?existing=1&fakeparam1=value-1"
    )


def test_get_rp_return_parameters_from_session_includes_normalized_lang():
    request = MagicMock()
    request.session = {
        SessionKeys.CUSTOM_PARAMETERS.value: {"fakeparam1": "value-1"},
        SessionKeys.CURRENT_LANGUAGE.value: "fr-CA",
    }

    assert get_rp_return_parameters_from_session(request) == {
        "fakeparam1": "value-1",
        "lang": "fr",
        "ui_locales": "fr-CA",
    }


def test_get_rp_return_parameters_from_session_ignores_invalid_lang():
    request = MagicMock()
    request.session = {
        SessionKeys.CUSTOM_PARAMETERS.value: {"fakeparam1": "value-1"},
        SessionKeys.CURRENT_LANGUAGE.value: "es",
    }

    assert get_rp_return_parameters_from_session(request) == {
        "fakeparam1": "value-1"
    }


def test_parse_customparameters_raises_for_invalid_payload():
    with pytest.raises(HTTPException) as raised:
        parse_customparameters("not-valid-base64")

    assert raised.value.status_code == 400
