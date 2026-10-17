"""Command-line entry point for the Dune planning workflow.

This is the command the GitHub Actions workflow runs:
    python -m zaviq.cli --prompt-file INPUT_PATH --output OUTPUT_PATH

Exit codes:
    0  a plan was produced, validated, and written
    1  planning failed (model error, timeout, or output that does not match the schema)
    2  invalid input or arguments (empty or unreadable prompt, unsafe output path)
    3  configuration is missing or the model client could not be created
    4  the output file could not be written

Nothing is written when planning fails. Messages never include the API key,
the prompt text, or raw model output.
"""

import argparse
import asyncio
import inspect
import json
import os
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from zaviq.dune import DunePlanningError, describe_validation_error, plan_project
from zaviq.llm_client import (
    MODEL_ENV,
    GeminiStructuredClient,
    LLMConfigError,
    StructuredModelClient,
)
from zaviq.schemas import DunePlan, DuneRequest

EXIT_OK = 0
EXIT_PLANNING_FAILED = 1
EXIT_INVALID_INPUT = 2
EXIT_CONFIG = 3
EXIT_WRITE_FAILED = 4

OUTPUT_FORMAT = "zaviq.dune_plan.v1"
MAX_INPUT_BYTES = 16 * 1024


class CliInputError(Exception):
    """The arguments or input cannot be used. The message is safe to print."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m zaviq.cli",
        description="Turn a project idea into a validated Dune plan saved as JSON.",
    )
    parser.add_argument(
        "--prompt-file",
        required=True,
        help="UTF-8 text file that contains the project idea",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="JSON file to create inside the working directory, e.g. outputs/dune-plan.json",
    )
    return parser


def _read_prompt(prompt_file: str) -> str:
    path = Path(prompt_file)
    try:
        if path.stat().st_size > MAX_INPUT_BYTES:
            raise CliInputError(f"prompt file is larger than {MAX_INPUT_BYTES} bytes")
        raw = path.read_bytes()
    except OSError as exc:
        raise CliInputError(f"cannot read prompt file '{prompt_file}'") from exc
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CliInputError("prompt file must be UTF-8 text") from exc


def _make_request(text: str) -> DuneRequest:
    try:
        return DuneRequest(prompt=text)
    except ValidationError as exc:
        raise CliInputError(f"invalid project idea: {describe_validation_error(exc)}") from exc


def _resolve_output_path(raw_output: str) -> Path:
    """Resolve the output path and refuse anything outside the working directory."""
    workdir = Path.cwd().resolve()
    candidate = Path(raw_output)
    if not candidate.is_absolute():
        candidate = workdir / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(workdir):
        raise CliInputError("output must be inside the working directory")
    if resolved.suffix != ".json":
        raise CliInputError("output file name must end with .json")
    if resolved.is_dir():
        raise CliInputError("output path points to a directory")
    return resolved


def _build_document(plan: DunePlan, model_name: str) -> str:
    document = {
        "format": OUTPUT_FORMAT,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model_name,
        "plan": plan.model_dump(mode="json"),
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def _write_atomically(path: Path, text: str) -> None:
    """Write to a temporary file first, so an interrupted run never leaves a half-written plan."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


async def _close_client(client: Any) -> None:
    close = getattr(client, "aclose", None)
    if close is None:
        return
    result = close()
    if inspect.isawaitable(result):
        await result


async def _plan_then_close(request: DuneRequest, client: StructuredModelClient) -> DunePlan:
    try:
        return await plan_project(request, client=client)
    finally:
        await _close_client(client)


def main(
    argv: list[str] | None = None,
    *,
    client_factory: Callable[[], StructuredModelClient] | None = None,
) -> int:
    """Run the workflow and return an exit code. Tests pass a fake client factory."""
    args = _build_parser().parse_args(argv)

    try:
        request = _make_request(_read_prompt(args.prompt_file))
        output_path = _resolve_output_path(args.output)
    except CliInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    factory = client_factory or GeminiStructuredClient.from_env
    try:
        client = factory()
    except LLMConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    except Exception as exc:
        print(f"error: could not create the model client ({type(exc).__name__})", file=sys.stderr)
        return EXIT_CONFIG

    print("status: sending the project idea to the model")
    try:
        plan = asyncio.run(_plan_then_close(request, client))
    except DunePlanningError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_PLANNING_FAILED
    except Exception as exc:  # last resort: report the exception type only
        print(f"error: unexpected {type(exc).__name__} during planning", file=sys.stderr)
        return EXIT_PLANNING_FAILED

    print(
        f"status: plan validated ({len(plan.milestones)} milestones, "
        f"{len(plan.proposed_files)} proposed files)"
    )

    model_name = os.environ.get(MODEL_ENV, "").strip() or "unknown"
    try:
        _write_atomically(output_path, _build_document(plan, model_name))
    except OSError as exc:
        print(f"error: could not write the output file ({type(exc).__name__})", file=sys.stderr)
        return EXIT_WRITE_FAILED

    print(f"status: wrote {os.path.relpath(output_path)}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
