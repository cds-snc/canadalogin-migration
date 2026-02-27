#!/usr/bin/env python3
"""Validate RP migration config JSON and emit one-line env var content."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path


CONFIG_ENV_VAR = "RP_MIGRATION_CONFIG"
LIST_WRAPPER_KEYS = ("rp_configs", "data", "configs")


def parse_args() -> argparse.Namespace:
    default_input = (
        Path(__file__).resolve().parents[1] / "docs" / "rp_migration_config.sample.json"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=default_input,
        help=f"Path to RP migration config JSON (default: {default_input})",
    )
    parser.add_argument(
        "--format",
        choices=("dotenv", "value"),
        default="dotenv",
        help="`dotenv`: RP_MIGRATION_CONFIG='...'; `value`: raw compact JSON only.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output file path. If omitted, prints to stdout.",
    )
    return parser.parse_args()


def load_json_payload(input_path: Path) -> list:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in LIST_WRAPPER_KEYS:
            maybe_list = payload.get(key)
            if isinstance(maybe_list, list):
                return maybe_list
    raise ValueError(
        "Expected a JSON array of RP objects, or an object with a list under "
        f"one of: {', '.join(LIST_WRAPPER_KEYS)}."
    )


def validate_and_normalize(payload: list) -> list:
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    from app.rp.schemas import RPSchema  # pylint: disable=import-outside-toplevel

    return [
        RPSchema.model_validate(item).model_dump(by_alias=True, exclude_none=True)
        for item in payload
    ]


def build_output(payload: list, output_format: str) -> str:
    compact_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    if output_format == "value":
        return compact_json
    return f"{CONFIG_ENV_VAR}={shlex.quote(compact_json)}"


def main() -> int:
    args = parse_args()
    input_path = args.input.resolve()
    payload = load_json_payload(input_path)
    validated = validate_and_normalize(payload)
    output_text = build_output(validated, args.format)

    if args.output:
        output_path = args.output.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{output_text}\n", encoding="utf-8")
    else:
        print(output_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
