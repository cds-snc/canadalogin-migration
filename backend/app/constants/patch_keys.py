from enum import Enum


class PatchKeys(str, Enum):
    LEGACY_PAI_DATA_KEY = "gcsattributeslegacypaidata"
    AUDIT_DATA_KEY = "gcsattributeslegacypaiauditdata"
    PROCESSING_DATA_KEY = "gcsattributeslegacypaiprocessingdata"
