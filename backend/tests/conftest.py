import os


# Provide required IBM Verify settings for imports during test collection.
os.environ.setdefault("IBM_VERIFY_TENANT_URL", "https://example.test")
os.environ.setdefault("IBM_VERIFY_MIGRATION_API_CLIENT_ID", "test-client-id")
os.environ.setdefault("IBM_VERIFY_MIGRATION_API_SECRET", "test-client-secret")
os.environ.setdefault("IBM_VERIFY_MIGRATION_CLIENT_ID", "test-profile-client-id")
os.environ.setdefault("IBM_VERIFY_MIGRATION_SECRET", "test-profile-client-secret")
