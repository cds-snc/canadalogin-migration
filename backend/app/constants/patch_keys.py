from enum import Enum


class PatchKeys(str, Enum):
    LEGACY_PAI_DATA_KEY = "legacypaidata"
    AUDIT_DATA_KEY = "auditdata"
    PROCESSING_DATA_KEY = "processingdata"
