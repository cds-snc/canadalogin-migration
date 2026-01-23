import os


# Provide required IBM Verify settings for imports during test collection.
os.environ.setdefault("IBM_VERIFY_TENANT_URL", "https://example.test")
os.environ.setdefault("IBM_VERIFY_MIGRATION_API_CLIENT_ID", "test-client-id")
os.environ.setdefault("IBM_VERIFY_MIGRATION_API_SECRET", "test-client-secret")
os.environ.setdefault("IBM_VERIFY_MIGRATION_CLIENT_ID", "test-profile-client-id")
os.environ.setdefault("IBM_VERIFY_MIGRATION_SECRET", "test-profile-client-secret")

# Provide required RP (Relying Party) configuration for imports during test collection.
os.environ.setdefault("RP_CLIENT_ID", "test-rp-client-id")
os.environ.setdefault("RP_CLIENT_NAME", "Test RP Client")
os.environ.setdefault("RP_CLIENT_NAME_EN", "Test RP Client EN")
os.environ.setdefault("RP_CLIENT_NAME_FR", "Test RP Client FR")
os.environ.setdefault("RP_REDIRECT_URI", "http://localhost:3000/callback")
os.environ.setdefault("RP_REDIRECT_URI_EN", "http://localhost:3000/en/callback")
os.environ.setdefault("RP_REDIRECT_URI_FR", "http://localhost:3000/fr/callback")
