"""Export the API's OpenAPI schema, which the frontend generates its API client from:
`python -m app.openapi [PATH]` writes it to PATH (stdout without one), and
`python -m app.openapi --check PATH` fails if PATH doesn't match the current API"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from fastapi import FastAPI

from app.main import app as main_app

UPDATE_COMMAND = "make openapi"


def schema_json(app: FastAPI = main_app) -> str:
    """The schema as JSON with two-space indents and a trailing newline. The same API always
    gives the same text, so the committed file only changes when the API does"""
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main(argv: Sequence[str] | None = None, app: FastAPI = main_app) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.openapi", description="Export the API's OpenAPI schema as JSON"
    )
    parser.add_argument("path", nargs="?", type=Path, help="file to write (default: stdout)")
    parser.add_argument(
        "--check",
        action="store_true",
        help="change nothing; exit 1 if PATH doesn't match the current schema",
    )
    args = parser.parse_args(argv)
    schema = schema_json(app)

    if args.check:
        if args.path is None:
            parser.error("--check needs a PATH")
        current = args.path.read_text(encoding="utf-8") if args.path.exists() else None
        if current != schema:
            print(
                f"{args.path} doesn't match the API; run `{UPDATE_COMMAND}` and commit it",
                file=sys.stderr,
            )
            return 1
    elif args.path is None:
        sys.stdout.write(schema)
    else:
        args.path.write_text(schema, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
