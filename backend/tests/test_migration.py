from typing import Final
import pytest

from app.users.services.custom_attributes import get_custom_attribute
from app.users.schemas import MeResponse

# User Attributes
LEGACY_PAI_DATA: Final[str] = "legacypaidata"
AUDIT_DATA: Final[str] = "auditdata"
PROCESSING_DATA: Final[str] = "processingdata"


@pytest.fixture
def mock_ibm_user_data():
    return {
        "emails": [{"type": "work", "value": "jane.doe@example.com"}],
        "preferredLanguage": "en-ca",
        "meta": {
            "created": "2025-07-02T21:16:28Z",
            "location": "https://cds-gcsignin-dev.verify.ibm.com/v2.0/Users/123456A0BC",
            "lastModified": "2025-11-17T13:34:54Z",
            "resourceType": "User",
        },
        "schemas": [
            "urn:ietf:params:scim:schemas:core:2.0:User",
            "urn:ietf:params:scim:schemas:extension:ibm:2.0:User",
        ],
        "urn:ietf:params:scim:schemas:extension:ibm:2.0:User": {
            "lastLogin": "2025-11-17T13:34:54Z",
            "lastLoginRealm": "cloudIdentityRealm",
            "lastMFA": [
                {"type": "signatures", "value": "2025-11-14T19:02:50Z"},
                {"type": "smsotp", "value": "2025-11-10T15:38:39Z"},
            ],
            "userCategory": "regular",
            "twoFactorAuthentication": False,
            "realm": "cloudIdentityRealm",
            "pwdChangedTime": "2025-07-04T11:38:09Z",
            "customAttributes": [
                {
                    "values": [
                        '{"client_id": "35505dc7-8937-4743-9510-e797dd4eca7d", "pai": "e5b61cf1-1024-42be-93e1-52b26fd7f967"}',
                        '{"client_id": "35505dc7-8937-4743-9510-e797dd4eca7d", "pai": "e5b61cf1-1024-42be-93e1-52b26fd7f967"}',
                    ],
                    "name": "legacypaidata",
                },
                {
                    "values": [
                        '{"client_id": "35505dc7-8937-4743-9510-e797dd4eca7d", "legacy_idp": "", "timestamp": "2025-11-17 13:54:25", "status": "LINKED"}'
                    ],
                    "name": "auditdata",
                },
                {
                    "values": [
                        '{"client_id": "35505dc7-8937-4743-9510-e797dd4eca7d", "retry_count": 3, "timestamp": "2025-11-17 13:54:24"}'
                    ],
                    "name": "processingdata",
                },
            ],
            "lastLoginType": "user_password",
        },
        "name": {"formatted": "Jane Doe", "familyName": "Doe", "givenName": "Jane"},
        "active": True,
        "id": "123456A0BC",
        "userName": "jane.doe@example.com",
    }


@pytest.mark.asyncio
async def test_get_legacypaidata(mock_ibm_user_data):

    mock_response_data = MeResponse(**mock_ibm_user_data)
    mock_custom_attributes = mock_response_data.ibm_extension.custom_attributes

    mock_legacy_pai_array = await get_custom_attribute(
        LEGACY_PAI_DATA, mock_custom_attributes
    )

    assert mock_legacy_pai_array is not None
    assert mock_legacy_pai_array == [
        '{"client_id": "35505dc7-8937-4743-9510-e797dd4eca7d", "pai": "e5b61cf1-1024-42be-93e1-52b26fd7f967"}',
        '{"client_id": "35505dc7-8937-4743-9510-e797dd4eca7d", "pai": "e5b61cf1-1024-42be-93e1-52b26fd7f967"}',
    ]


@pytest.mark.asyncio
async def test_get_auditdata(mock_ibm_user_data):

    mock_response_data = MeResponse(**mock_ibm_user_data)
    mock_custom_attributes = mock_response_data.ibm_extension.custom_attributes

    mock_audit_data_array = await get_custom_attribute(
        AUDIT_DATA, mock_custom_attributes
    )

    assert mock_audit_data_array is not None
    assert mock_audit_data_array == [
        '{"client_id": "35505dc7-8937-4743-9510-e797dd4eca7d", "legacy_idp": "", "timestamp": "2025-11-17 13:54:25", "status": "LINKED"}'
    ]


@pytest.mark.asyncio
async def test_get_processingdata(mock_ibm_user_data):

    mock_response_data = MeResponse(**mock_ibm_user_data)
    mock_custom_attributes = mock_response_data.ibm_extension.custom_attributes

    mock_processing_data_array = await get_custom_attribute(
        PROCESSING_DATA, mock_custom_attributes
    )

    assert mock_processing_data_array is not None
    assert mock_processing_data_array == [
        '{"client_id": "35505dc7-8937-4743-9510-e797dd4eca7d", "retry_count": 3, "timestamp": "2025-11-17 13:54:24"}'
    ]
