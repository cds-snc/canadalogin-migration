from enum import Enum


class AuditStatusKeys(str, Enum):
    LINKED_KEY = "LINKED"
    SKIPPED_KEY = "SKIPPED"
