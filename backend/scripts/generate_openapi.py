#!/usr/bin/env python3
"""Generate or validate the checked-in OpenAPI specification."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
from pathlib import Path


REQUIRED_ENV_DEFAULTS = {
    "IBM_VERIFY_TENANT_URL": "https://example.test",
    "IBM_VERIFY_MIGRATION_API_CLIENT_ID": "openapi-client-id",
    "IBM_VERIFY_MIGRATION_API_SECRET": "openapi-client-secret",
    "IBM_VERIFY_MIGRATION_CLIENT_ID": "openapi-profile-client-id",
    "IBM_VERIFY_MIGRATION_SECRET": "openapi-profile-client-secret",
}


def normalize_openapi(document: dict) -> dict:
    """Normalize known FastAPI/Pydantic schema drift across environments."""
    schemas = document.get("components", {}).get("schemas", {})
    validation_error = schemas.get("ValidationError")
    if not isinstance(validation_error, dict):
        return document

    properties = validation_error.get("properties")
    if isinstance(properties, dict):
        properties.pop("ctx", None)
        properties.pop("input", None)

    required = validation_error.get("required")
    if isinstance(required, list):
        validation_error["required"] = [
            field for field in required if field not in {"ctx", "input"}
        ]
    return document


def build_openapi_document() -> dict:
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    for key, value in REQUIRED_ENV_DEFAULTS.items():
        os.environ.setdefault(key, value)

    from app.main import app  # pylint: disable=import-outside-toplevel

    return normalize_openapi(app.openapi())


def parse_args() -> argparse.Namespace:
    default_output = Path(__file__).resolve().parents[1] / "openapi" / "openapi.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output,
        help=f"Output file path (default: {default_output})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the checked-in spec does not match generated output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = args.output.resolve()
    content = json.dumps(build_openapi_document(), indent=2, sort_keys=True) + "\n"

    if args.check:
        if not output_path.exists():
            print(f"Missing OpenAPI file: {output_path}")
            return 1
        existing = output_path.read_text(encoding="utf-8")
        if existing != content:
            print("OpenAPI spec is out of date. Run `make generate-openapi`.")
            diff_lines = difflib.unified_diff(
                existing.splitlines(),
                content.splitlines(),
                fromfile=str(output_path),
                tofile="generated-openapi.json",
                lineterm="",
            )
            for idx, line in enumerate(diff_lines):
                if idx >= 200:
                    print("... diff truncated ...")
                    break
                print(line)
            return 1
        print(f"OpenAPI spec is up to date: {output_path}")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote OpenAPI spec: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
