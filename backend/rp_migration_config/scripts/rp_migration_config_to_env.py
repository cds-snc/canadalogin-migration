#!/usr/bin/env python3
"""Build RP migration config JSON and emit one-line env var content."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import shlex
import sys
from pathlib import Path
from typing import Any


CONFIG_ENV_VAR = "RP_MIGRATION_CONFIG"
LIST_WRAPPER_KEYS = ("rp_configs", "data", "configs")
SCRIPT_DIR = Path(__file__).resolve().parent
TOOLING_DIR = SCRIPT_DIR.parent
BACKEND_DIR = TOOLING_DIR.parent
CONFIG_DIR = TOOLING_DIR / "config"
DEFAULT_LEGACY_INPUT = TOOLING_DIR / "samples" / "rp_migration_config.sample.json"
DEFAULT_BASE_INPUT = CONFIG_DIR / "base" / "rp_migration_config.json"
DEFAULT_ENV_DIR = CONFIG_DIR / "env"
DEFAULT_ENV_RP_CONFIG_FILENAME = "rp_migration_config.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        help=(
            "Path to complete RP migration config JSON (legacy mode). "
            f"Default: {DEFAULT_LEGACY_INPUT}"
        ),
    )
    parser.add_argument(
        "--env-input",
        type=Path,
        help=(
            "Optional path to env config JSON. Merge mode defaults to "
            f"{DEFAULT_ENV_DIR}/<env>/{DEFAULT_ENV_RP_CONFIG_FILENAME}"
        ),
    )
    parser.add_argument(
        "--env",
        help=(
            "Environment key for SIC openid_configuration and redirect_uris "
            "(required for merge mode)."
        ),
    )
    parser.add_argument(
        "--rp-overrides-input",
        type=Path,
        help=(
            "Path to RP overrides JSON (secrets/client IDs). "
            "Use for merge mode when you don't pass overrides via stdin/json."
        ),
    )
    parser.add_argument(
        "--rp-overrides-json",
        help=(
            "RP overrides JSON as a string (merge mode). "
            "Avoid if shell history/process list exposure is a concern."
        ),
    )
    parser.add_argument(
        "--rp-overrides-stdin",
        action="store_true",
        help=(
            "Read RP overrides JSON from stdin (merge mode). "
            "Recommended for temporary secret handling."
        ),
    )
    parser.add_argument(
        "--run-id",
        help="Optional tracking value printed to stderr for audit/log correlation.",
    )
    parser.add_argument(
        "--rp-config-id",
        help=(
            "Optional filter: emit output for only one RP that matches this "
            "`rp_config_id`."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("dotenv", "value", "single-value"),
        default="dotenv",
        help=(
            "`dotenv`: RP_MIGRATION_CONFIG='...'; "
            "`value`: raw compact JSON array; "
            "`single-value`: raw compact JSON object (requires exactly one RP)."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output file path. If omitted, prints to stdout.",
    )
    return parser.parse_args()


def load_json(input_path: Path) -> Any:
    return json.loads(input_path.read_text(encoding="utf-8"))


def normalize_json_payload(payload: Any) -> list:
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


def load_json_payload(input_path: Path) -> list:
    return normalize_json_payload(load_json(input_path))


def load_json_object(input_path: Path) -> dict[str, Any]:
    payload = load_json(input_path)
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object for env-specific input.")
    return payload


def load_json_from_string(raw_json: str, context: str) -> Any:
    try:
        return json.loads(raw_json)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON for {context}: {error}") from error


def load_json_from_stdin(context: str) -> Any:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError(f"No stdin data provided for {context}.")
    return load_json_from_string(raw, context)


def resolve_env_name(cli_env: str | None) -> str:
    if cli_env:
        env_name = cli_env.strip()
        if env_name:
            return env_name
    raise ValueError("Missing environment. Provide --env.")


def resolve_env_input_path(args: argparse.Namespace, env_name: str) -> Path:
    if args.env_input:
        return args.env_input.resolve()

    default_env_input = (
        DEFAULT_ENV_DIR / env_name / DEFAULT_ENV_RP_CONFIG_FILENAME
    ).resolve()
    if default_env_input.is_file():
        return default_env_input

    # Backward compatibility with previous `config/env/<env>.json` style.
    legacy_env_input = (DEFAULT_ENV_DIR / f"{env_name}.json").resolve()
    if legacy_env_input.is_file():
        return legacy_env_input

    available_env_dirs = sorted(
        path.name
        for path in DEFAULT_ENV_DIR.iterdir()
        if path.is_dir() and (path / DEFAULT_ENV_RP_CONFIG_FILENAME).is_file()
    )
    available_env_files = sorted(
        path.stem for path in DEFAULT_ENV_DIR.glob("*.json") if path.is_file()
    )
    raise ValueError(
        f"No default env config found for --env `{env_name}`. "
        f"Tried {default_env_input} and {legacy_env_input}. "
        f"Available env directories: {', '.join(available_env_dirs) or 'none'}. "
        f"Available legacy env files: {', '.join(available_env_files) or 'none'}."
    )


def normalize_rp_overrides(raw_overrides: Any) -> dict[str, dict[str, Any]]:
    # Convenience: accept a single override object instead of requiring a list/map.
    if isinstance(raw_overrides, dict):
        has_override_identity = (
            isinstance(raw_overrides.get("rp_config_id"), str)
            or isinstance(raw_overrides.get("rp_client_name"), str)
        )
        has_override_content = any(
            field in raw_overrides
            for field in (
                "idp",
                "rp_client_id",
                "rp_redirect_uri",
                "dependentClientIds",
                "dependent_client_ids",
                "acr_values",
                "rp_client_name_en",
                "rp_client_name_fr",
            )
        )
        looks_like_single_override = has_override_identity and has_override_content
        if looks_like_single_override:
            raw_overrides = [raw_overrides]

    if isinstance(raw_overrides, dict):
        normalized: dict[str, dict[str, Any]] = {}
        for override_key, override in raw_overrides.items():
            if not isinstance(override_key, str) or not override_key.strip():
                raise ValueError("rp_overrides keys must be non-empty strings.")
            if not isinstance(override, dict):
                raise ValueError(
                    f"rp_overrides['{override_key}'] must be an object of override values."
                )
            normalized[override_key] = override
        return normalized

    if isinstance(raw_overrides, list):
        normalized = {}
        for idx, override in enumerate(raw_overrides):
            if not isinstance(override, dict):
                raise ValueError(f"rp_overrides[{idx}] must be an object.")

            override_key = override.get("rp_config_id")
            if not isinstance(override_key, str) or not override_key.strip():
                override_key = override.get("rp_client_name")

            if not isinstance(override_key, str) or not override_key.strip():
                raise ValueError(
                    f"rp_overrides[{idx}] requires non-empty `rp_config_id` or `rp_client_name`."
                )
            if override_key in normalized:
                raise ValueError(f"Duplicate rp_overrides entry for `{override_key}`.")
            normalized[override_key] = override
        return normalized

    raise ValueError("`rp_overrides` must be either an object or a list of objects.")


def resolve_rp_overrides_payload(
    args: argparse.Namespace, env_payload: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    explicit_sources = []
    if args.rp_overrides_input:
        explicit_sources.append("input")
    if args.rp_overrides_json:
        explicit_sources.append("json")
    if args.rp_overrides_stdin:
        explicit_sources.append("stdin")

    if len(explicit_sources) > 1:
        source_csv = ", ".join(explicit_sources)
        raise ValueError(
            "Provide only one RP overrides source: "
            f"--rp-overrides-input, --rp-overrides-json, or --rp-overrides-stdin (got {source_csv})."
        )

    if args.rp_overrides_input:
        overrides_payload = load_json(args.rp_overrides_input.resolve())
        return normalize_rp_overrides(overrides_payload)

    if args.rp_overrides_json:
        overrides_payload = load_json_from_string(
            args.rp_overrides_json, context="--rp-overrides-json"
        )
        return normalize_rp_overrides(overrides_payload)

    if args.rp_overrides_stdin:
        overrides_payload = load_json_from_stdin(context="--rp-overrides-stdin")
        return normalize_rp_overrides(overrides_payload)

    if "rp_overrides" not in env_payload:
        raise ValueError(
            "Missing rp_overrides. Provide one of: --rp-overrides-input, "
            "--rp-overrides-json, --rp-overrides-stdin, or include `rp_overrides` in env input."
        )

    return normalize_rp_overrides(env_payload.get("rp_overrides"))


def get_env_value(
    mapping: Any,
    env_name: str,
    field_name: str,
    expected_type: type[str] | type[list],
) -> Any:
    if not isinstance(mapping, dict):
        raise ValueError(f"`sic.{field_name}` must be an object keyed by environment.")

    value = mapping.get(env_name)
    if value is None:
        available = ", ".join(sorted(str(key) for key in mapping.keys()))
        raise ValueError(
            f"`sic.{field_name}` has no value for environment `{env_name}`. "
            f"Available: {available or 'none'}."
        )

    if not isinstance(value, expected_type):
        raise ValueError(
            f"`sic.{field_name}.{env_name}` must be a "
            f"{'string' if expected_type is str else 'list'}."
        )

    return value


def resolve_sic_values(
    env_payload: dict[str, Any],
    env_name: str,
) -> tuple[str, list[str]]:
    sic_config = env_payload.get("sic")
    if not isinstance(sic_config, dict):
        raise ValueError("Env input requires a top-level `sic` object.")

    # New format: one file per environment.
    openid_configuration = sic_config.get("openid_configuration")
    redirect_uris = sic_config.get("redirect_uris")
    if isinstance(openid_configuration, str) and isinstance(redirect_uris, list):
        if not openid_configuration.strip():
            raise ValueError("`sic.openid_configuration` must be a non-empty string.")
        if not all(isinstance(uri, str) and uri.strip() for uri in redirect_uris):
            raise ValueError("`sic.redirect_uris` must be a list of non-empty strings.")
        return openid_configuration, list(redirect_uris)

    # Backward-compatible format: one file containing values keyed by environment.
    sic_openid_configuration = get_env_value(
        sic_config.get("openid_configuration"),
        env_name,
        "openid_configuration",
        str,
    )
    sic_redirect_uris = get_env_value(
        sic_config.get("redirect_uris"),
        env_name,
        "redirect_uris",
        list,
    )
    if not all(isinstance(uri, str) and uri.strip() for uri in sic_redirect_uris):
        raise ValueError(
            f"`sic.redirect_uris.{env_name}` must be a list of non-empty strings."
        )
    return sic_openid_configuration, list(sic_redirect_uris)


def get_sic_idp_entry(rp: dict[str, Any]) -> dict[str, Any]:
    rp_name = rp.get("rp_client_name", "<unknown>")
    idp_entries = rp.get("IDP")

    if not isinstance(idp_entries, list) or not idp_entries:
        raise ValueError(f"Base RP `{rp_name}` must define a non-empty IDP list.")

    for idp in idp_entries:
        if isinstance(idp, dict) and idp.get("client_name") == "SIC":
            return idp

    raise ValueError(f"Base RP `{rp_name}` must define a SIC entry under IDP.")


def get_base_rp_override_keys(base_rp: dict[str, Any], idx: int) -> list[str]:
    rp_name = base_rp.get("rp_client_name")
    if not isinstance(rp_name, str) or not rp_name.strip():
        raise ValueError(
            f"Base RP at index {idx} is missing non-empty `rp_client_name`."
        )

    keys: list[str] = []
    rp_config_id = base_rp.get("rp_config_id")
    if isinstance(rp_config_id, str) and rp_config_id.strip():
        keys.append(rp_config_id.strip())

    keys.append(rp_name)
    return keys


def apply_rp_overrides(
    base_rp: dict[str, Any],
    rp_override: dict[str, Any],
    sic_openid_configuration: str | None,
    sic_redirect_uris: list[str] | None,
) -> dict[str, Any]:
    rp_name = base_rp.get("rp_client_name", "<unknown>")
    base_sic_idp = get_sic_idp_entry(base_rp)

    idp_override = rp_override.get("idp")
    if idp_override is None:
        idp_override = {}
    if not isinstance(idp_override, dict):
        raise ValueError(f"rp_overrides['{rp_name}'].idp must be an object.")

    final_rp_client_id = rp_override.get("rp_client_id", base_rp.get("rp_client_id"))
    final_rp_redirect_uri = rp_override.get(
        "rp_redirect_uri", base_rp.get("rp_redirect_uri")
    )
    final_idp_client_id = idp_override.get("client_id", base_sic_idp.get("client_id"))
    final_idp_client_secret = idp_override.get(
        "client_secret", base_sic_idp.get("client_secret")
    )

    missing_fields = []
    if not isinstance(final_rp_client_id, str) or not final_rp_client_id.strip():
        missing_fields.append("rp_client_id")
    if not isinstance(final_rp_redirect_uri, str) or not final_rp_redirect_uri.strip():
        missing_fields.append("rp_redirect_uri")
    if not isinstance(final_idp_client_id, str) or not final_idp_client_id.strip():
        missing_fields.append("idp.client_id")
    if not isinstance(final_idp_client_secret, str) or not final_idp_client_secret.strip():
        missing_fields.append("idp.client_secret")

    if missing_fields:
        missing_csv = ", ".join(missing_fields)
        raise ValueError(
            f"rp_overrides['{rp_name}'] is missing required values: {missing_csv}"
        )

    merged = deepcopy(base_rp)

    for key in (
        "rp_client_id",
        "rp_redirect_uri",
        "rp_client_name",
        "rp_client_name_en",
        "rp_client_name_fr",
        "acr_values",
    ):
        if key in rp_override:
            merged[key] = rp_override[key]

    if "dependentClientIds" in rp_override:
        merged["dependentClientIds"] = rp_override["dependentClientIds"]
    elif "dependent_client_ids" in rp_override:
        merged["dependentClientIds"] = rp_override["dependent_client_ids"]

    sic_idp = get_sic_idp_entry(merged)
    for key, value in idp_override.items():
        if key in ("openid_configuration", "redirect_uris"):
            continue
        sic_idp[key] = value

    if sic_openid_configuration is not None:
        sic_idp["openid_configuration"] = sic_openid_configuration
    if sic_redirect_uris is not None:
        sic_idp["redirect_uris"] = list(sic_redirect_uris)

    assert isinstance(final_rp_client_id, str)
    assert isinstance(final_rp_redirect_uri, str)
    assert isinstance(final_idp_client_id, str)
    assert isinstance(final_idp_client_secret, str)
    merged["rp_client_id"] = final_rp_client_id
    merged["rp_redirect_uri"] = final_rp_redirect_uri
    sic_idp["client_id"] = final_idp_client_id
    sic_idp["client_secret"] = final_idp_client_secret

    return merged


def merge_base_with_overrides(
    base_payload: list,
    rp_overrides: dict[str, dict[str, Any]],
    allow_extra_overrides: bool = False,
    sic_openid_configuration: str | None = None,
    sic_redirect_uris: list[str] | None = None,
) -> list:
    merged_payload = []
    seen_base_rp_names: set[str] = set()
    used_override_keys: set[str] = set()
    seen_rp_config_ids: set[str] = set()

    for idx, base_rp in enumerate(base_payload):
        if not isinstance(base_rp, dict):
            raise ValueError(f"Base RP at index {idx} must be an object.")

        rp_name = base_rp.get("rp_client_name")
        if not isinstance(rp_name, str) or not rp_name.strip():
            raise ValueError(f"Base RP at index {idx} is missing non-empty `rp_client_name`.")
        if rp_name in seen_base_rp_names:
            raise ValueError(f"Duplicate base RP `rp_client_name`: {rp_name}")
        seen_base_rp_names.add(rp_name)

        override_keys = get_base_rp_override_keys(base_rp, idx)
        if len(override_keys) > 1:
            rp_config_id = override_keys[0]
            if rp_config_id in seen_rp_config_ids:
                raise ValueError(f"Duplicate base RP `rp_config_id`: {rp_config_id}")
            seen_rp_config_ids.add(rp_config_id)

        matching_override_keys = [key for key in override_keys if key in rp_overrides]
        if not matching_override_keys:
            key_hint = " or ".join(override_keys)
            raise ValueError(
                f"Missing rp_overrides entry for base RP `{rp_name}` (expected key `{key_hint}`)."
            )
        if len(matching_override_keys) > 1:
            key_csv = ", ".join(matching_override_keys)
            raise ValueError(
                f"Multiple rp_overrides keys matched base RP `{rp_name}`: {key_csv}. "
                "Provide only one key per RP."
            )

        selected_override_key = matching_override_keys[0]
        used_override_keys.add(selected_override_key)
        rp_override = rp_overrides[selected_override_key]

        merged_rp = apply_rp_overrides(
            base_rp=base_rp,
            rp_override=rp_override,
            sic_openid_configuration=sic_openid_configuration,
            sic_redirect_uris=sic_redirect_uris,
        )
        merged_payload.append(merged_rp)

    if not allow_extra_overrides:
        unknown_overrides = sorted(set(rp_overrides.keys()) - used_override_keys)
        if unknown_overrides:
            unknown_csv = ", ".join(unknown_overrides)
            raise ValueError(
                "rp_overrides contains entries not present in base config: "
                f"{unknown_csv}"
            )

    return merged_payload


def merge_base_with_env(
    base_payload: list,
    env_payload: dict[str, Any],
    env_name: str,
    rp_overrides: dict[str, dict[str, Any]],
    allow_extra_overrides: bool = False,
) -> list:
    sic_openid_configuration, sic_redirect_uris = resolve_sic_values(
        env_payload, env_name
    )
    return merge_base_with_overrides(
        base_payload=base_payload,
        rp_overrides=rp_overrides,
        allow_extra_overrides=allow_extra_overrides,
        sic_openid_configuration=sic_openid_configuration,
        sic_redirect_uris=sic_redirect_uris,
    )


def filter_base_payload_by_rp_config_id(
    base_payload: list,
    requested_rp_config_id: str | None,
) -> list:
    if not requested_rp_config_id:
        return base_payload

    rp_config_id = requested_rp_config_id.strip()
    if not rp_config_id:
        raise ValueError("--rp-config-id cannot be blank.")

    matches: list[dict[str, Any]] = []
    available_ids: list[str] = []

    for idx, item in enumerate(base_payload):
        if not isinstance(item, dict):
            raise ValueError(f"Base RP at index {idx} must be an object.")

        item_rp_config_id = item.get("rp_config_id")
        if not isinstance(item_rp_config_id, str) or not item_rp_config_id.strip():
            continue

        normalized_item_id = item_rp_config_id.strip()
        available_ids.append(normalized_item_id)
        if normalized_item_id == rp_config_id:
            matches.append(item)

    if not matches:
        available_csv = ", ".join(sorted(set(available_ids)))
        raise ValueError(
            f"No base RP found for rp_config_id `{rp_config_id}`. "
            f"Available rp_config_id values: {available_csv or 'none'}."
        )

    if len(matches) > 1:
        raise ValueError(
            f"Multiple base RP entries found for rp_config_id `{rp_config_id}`. "
            "Each rp_config_id must be unique."
        )

    return matches


def filter_payload_by_rp_config_id(
    payload: list,
    requested_rp_config_id: str | None,
) -> list:
    if not requested_rp_config_id:
        return payload

    rp_config_id = requested_rp_config_id.strip()
    if not rp_config_id:
        raise ValueError("--rp-config-id cannot be blank.")

    matches = []
    available_ids: list[str] = []

    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"RP entry at index {idx} must be an object.")

        item_rp_config_id = item.get("rp_config_id")
        if not isinstance(item_rp_config_id, str) or not item_rp_config_id.strip():
            continue

        normalized_item_id = item_rp_config_id.strip()
        available_ids.append(normalized_item_id)
        if normalized_item_id == rp_config_id:
            matches.append(item)

    if not matches:
        available_csv = ", ".join(sorted(set(available_ids)))
        raise ValueError(
            f"No RP found for rp_config_id `{rp_config_id}`. "
            f"Available rp_config_id values: {available_csv or 'none'}."
        )

    if len(matches) > 1:
        raise ValueError(
            f"Multiple RP entries found for rp_config_id `{rp_config_id}`. "
            "Each rp_config_id must be unique."
        )

    return matches


def validate_and_normalize(payload: list) -> list:
    backend_dir = BACKEND_DIR
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    from app.rp.schemas import RPSchema  # pylint: disable=import-outside-toplevel

    return [
        RPSchema.model_validate(item).model_dump(by_alias=True, exclude_none=True)
        for item in payload
    ]


def build_output(payload: list, output_format: str) -> str:
    if output_format == "single-value":
        if len(payload) != 1:
            raise ValueError(
                "--format single-value requires exactly one RP in output. "
                "Use --rp-config-id to select one RP."
            )
        return json.dumps(payload[0], separators=(",", ":"), ensure_ascii=False)

    compact_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    if output_format == "value":
        return compact_json
    return f"{CONFIG_ENV_VAR}={shlex.quote(compact_json)}"


def main() -> int:
    args = parse_args()
    try:
        if args.run_id:
            print(f"[rp_migration_config_to_env] run_id={args.run_id}", file=sys.stderr)

        merge_mode_requested = bool(
            args.env_input
            or args.env
            or args.rp_overrides_input
            or args.rp_overrides_json
            or args.rp_overrides_stdin
        )

        if args.input and merge_mode_requested:
            raise ValueError(
                "Use either --input (legacy mode) or merge-mode options "
                "(--env-input/--env/--rp-overrides-*)."
            )

        if merge_mode_requested and not args.env:
            raise ValueError("--env is required in merge mode.")

        if merge_mode_requested:
            env_name = resolve_env_name(args.env)
            env_input_path = resolve_env_input_path(args, env_name)
            merge_source_payload = load_json(env_input_path)

            env_payload: dict[str, Any] = {}
            try:
                # Preferred format: full per-env RP config payload.
                base_payload = normalize_json_payload(merge_source_payload)
                base_payload = filter_base_payload_by_rp_config_id(
                    base_payload, args.rp_config_id
                )
                rp_overrides = resolve_rp_overrides_payload(args, env_payload)
                payload = merge_base_with_overrides(
                    base_payload=base_payload,
                    rp_overrides=rp_overrides,
                    allow_extra_overrides=bool(args.rp_config_id),
                )
            except ValueError:
                # Backward-compatible format: env SIC values payload.
                env_payload = load_json_object(env_input_path)
                rp_overrides = resolve_rp_overrides_payload(args, env_payload)
                base_payload = load_json_payload(DEFAULT_BASE_INPUT.resolve())
                base_payload = filter_base_payload_by_rp_config_id(
                    base_payload, args.rp_config_id
                )
                payload = merge_base_with_env(
                    base_payload,
                    env_payload,
                    env_name,
                    rp_overrides,
                    allow_extra_overrides=bool(args.rp_config_id),
                )
        else:
            input_path = (args.input or DEFAULT_LEGACY_INPUT).resolve()
            payload = load_json_payload(input_path)

        payload = filter_payload_by_rp_config_id(payload, args.rp_config_id)
        validated = validate_and_normalize(payload)
        output_text = build_output(validated, args.format)
    except (ValueError, json.JSONDecodeError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if args.output:
        output_path = args.output.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{output_text}\n", encoding="utf-8")
    else:
        print(output_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
