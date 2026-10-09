"""Command line interface for ``opencode2others``."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .catalog import (
    DEFAULT_API_KEY_ENV,
    DEFAULT_BASE_URL,
    DEFAULT_PROVIDER_ID,
    DEFAULT_PROVIDER_NAME,
    Catalog,
    load_catalog,
)
from .credentials import discover_api_key, mask_secret
from .errors import OpenCode2OthersError
from .model import Model
from .targets import TARGETS, TARGET_CLASSES, Context, Target, write_auth_file
from .util import write_text

EPILOG = """\
examples:
  # write configs for every supported agent (merging into existing files)
  opencode2others --api-key sk-...

  # only Pi, and also store the key in ~/.pi/agent/auth.json
  opencode2others --target pi --api-key sk-... --write-auth

  # preview without touching any file
  opencode2others --target codex --dry-run

  # list models and the protocol each one speaks
  opencode2others --list

  # detect protocols with live 1-token requests instead of scraping the docs
  opencode2others --probe

Notes:
  * Credentials come from --api-key, otherwise from $OPENCODE_API_KEY.
  * Existing config files are merged and backed up to <file>.bak.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opencode2others",
        description=(
            "Generate configuration files for Pi, Claude Code, OpenAI Codex and "
            "ZCode from an OpenCode Go subscription."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    parser.add_argument(
        "--target",
        "-t",
        action="append",
        choices=[*TARGETS, "all"],
        default=None,
        metavar="TARGET",
        help="target to generate; repeatable, or 'all' (default: all)",
    )
    parser.add_argument("--list", action="store_true",
                        help="print the resolved model/protocol table and exit")
    parser.add_argument("--probe", action="store_true",
                        help="auto-detect each model's protocol with a live request "
                             "(requires a key; consumes a tiny amount of usage)")
    parser.add_argument("--merge", dest="merge", action="store_true",
                        help="merge into existing config files (default)")
    parser.add_argument("--no-merge", dest="merge", action="store_false",
                        help="overwrite existing config files")
    parser.set_defaults(merge=True)

    parser.add_argument("--api-key", default=None,
                        help="API key to embed (default: read $--api-key-env)")
    parser.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV,
                        help=f"env var that holds the key (default: {DEFAULT_API_KEY_ENV})")
    parser.add_argument("--no-key-discovery", action="store_true",
                        help="do not read the key from existing local configs")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help=f"OpenCode Go API base URL (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--provider-id", default=DEFAULT_PROVIDER_ID,
                        help=f"provider id in generated configs (default: {DEFAULT_PROVIDER_ID})")
    parser.add_argument("--provider-name", default=DEFAULT_PROVIDER_NAME,
                        help=f"provider display name (default: {DEFAULT_PROVIDER_NAME})")
    parser.add_argument("--model", "--default-model", dest="default_model", default=None,
                        metavar="MODEL_ID",
                        help="preferred default model id, e.g. deepseek-v4.1-flash "
                             "(applied to every target that supports its protocol)")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="HTTP timeout in seconds (default: 30)")

    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="output path override (only with a single target)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the generated files instead of writing them")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="print extra diagnostics")

    for target_cls in TARGET_CLASSES:
        target_cls.add_arguments(parser)

    return parser


def _resolve_target_names(names: list[str] | None) -> list[str]:
    if not names:
        names = ["all"]
    resolved: list[str] = []
    for name in names:
        candidates = list(TARGETS) if name == "all" else [name]
        for candidate in candidates:
            if candidate not in resolved:
                resolved.append(candidate)
    return resolved


def _resolve_path(
    target: Target,
    args: argparse.Namespace,
    *,
    single_target: bool,
) -> Path:
    per_target = {
        "pi": args.pi_output,
        "claude-code": args.claude_output,
        "codex": args.codex_output,
        "zcode": args.zcode_output,
    }.get(target.key)
    if per_target:
        return per_target
    if args.output is not None:
        if not single_target:
            raise OpenCode2OthersError(
                "--output can only be used with a single --target; "
                "use the per-target --<name>-output options instead"
            )
        return args.output
    return target.default_path()


def _print_table(models: list[Model]) -> None:
    print(f"{'MODEL ID':<30} {'PROTOCOL (Pi api)':<20} {'CTX':>9} {'OUT':>9}  NAME")
    print("-" * 90)
    for model in models:
        ctx = str(model.context_window) if model.context_window else "-"
        out = str(model.max_tokens) if model.max_tokens else "-"
        print(f"{model.id:<30} {model.protocol.value:<20} {ctx:>9} {out:>9}  {model.name}")


def _report(catalog: Catalog) -> None:
    if catalog.unresolved:
        print(
            f"[warn] {len(catalog.unresolved)} model(s) not in the endpoint table; "
            f"skipped: {', '.join(catalog.unresolved)}",
            file=sys.stderr,
        )
    if catalog.missing_metadata:
        print(
            f"[info] {len(catalog.missing_metadata)} model(s) without models.dev "
            f"metadata: {', '.join(catalog.missing_metadata)}"
        )
    counts = catalog.protocol_counts
    for protocol, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {count:>3}  {protocol.label:<18} -> {protocol.value}")


def _resolve_key(args: argparse.Namespace) -> tuple[str | None, str | None]:
    """Resolve the API key from flags, the environment, or existing configs."""
    if args.api_key:
        return args.api_key, "--api-key"
    env_value = os.environ.get(args.api_key_env, "").strip()
    if env_value:
        return env_value, f"${args.api_key_env}"
    if not args.no_key_discovery:
        return discover_api_key(args.provider_id, args.base_url, args.api_key_env)
    return None, None


def run(
    args: argparse.Namespace,
    catalog: Catalog,
    targets: list[Target],
    resolved_key: str | None,
) -> int:
    ctx = Context(
        provider_id=args.provider_id,
        provider_name=args.provider_name,
        base_url=args.base_url.rstrip("/"),
        api_key_env=args.api_key_env,
        resolved_key=resolved_key,
        merge=args.merge,
        verbose=args.verbose,
    )

    if args.write_auth and not resolved_key:
        raise OpenCode2OthersError(
            f"--write-auth needs a key: pass --api-key or set ${args.api_key_env}"
        )

    single_target = len(targets) == 1
    exit_code = 0
    for target in targets:
        path = _resolve_path(target, args, single_target=single_target)
        selected = target.filter(catalog.models)
        if not selected:
            print(f"[warn] {target.key}: no compatible models; skipping", file=sys.stderr)
            exit_code = 1
            continue

        try:
            content = target.render(catalog.models, ctx, path)
            extras = target.additional_files(catalog.models, ctx, path)
        except OpenCode2OthersError as exc:
            print(f"[error] {target.key}: {exc}", file=sys.stderr)
            exit_code = 1
            continue

        if args.dry_run:
            print(f"\n# ===== {target.key} -> {path} =====")
            print(content, end="" if content.endswith("\n") else "\n")
            for extra_path, extra_content in extras:
                print(f"\n# ===== {target.key} -> {extra_path} =====")
                print(extra_content, end="" if extra_content.endswith("\n") else "\n")
        else:
            write_text(path, content)
            print(f"[{target.key}] wrote {len(selected)} model(s) -> {path}")
            for extra_path, extra_content in extras:
                write_text(extra_path, extra_content)
                print(f"[{target.key}] wrote {extra_path}")

        if target.key == "pi" and args.write_auth:
            auth_path = args.pi_auth_file or target.default_auth_path()
            write_auth_file(auth_path, ctx.provider_id, resolved_key)
            print(f"[pi] stored credential for '{ctx.provider_id}' in {auth_path}")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    target_names = _resolve_target_names(args.target)
    targets = [TARGETS[name](args) for name in target_names]

    resolved_key, key_source = _resolve_key(args)
    if resolved_key:
        print(f"[info] using API key {mask_secret(resolved_key)} (from {key_source})")
    elif not args.list:
        print(
            f"[warn] no API key found; set ${args.api_key_env}, pass --api-key, "
            "or ensure an existing config holds it",
            file=sys.stderr,
        )

    try:
        catalog = load_catalog(
            args.base_url,
            timeout=args.timeout,
            probe=args.probe,
            api_key=resolved_key,
        )
    except OpenCode2OthersError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    if args.list:
        _print_table(catalog.models)
        _report(catalog)
        return 0

    print(f"[info] resolved {len(catalog.models)} model(s) from {args.base_url}")
    try:
        return run(args, catalog, targets, resolved_key)
    except OpenCode2OthersError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
