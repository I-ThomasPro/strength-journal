"""Exporting the OpenAPI schema for the frontend's generated client"""

import json
from pathlib import Path

import pytest
from fastapi import FastAPI

from app import openapi
from app.main import app


def test_writes_the_schema_as_stable_json(tmp_path: Path) -> None:
    path = tmp_path / "openapi.json"

    assert openapi.main([str(path)]) == 0

    text = path.read_text(encoding="utf-8")
    assert json.loads(text) == app.openapi()
    assert text.endswith("}\n")
    assert text == openapi.schema_json()


def test_prints_the_schema_without_a_path(capsys: pytest.CaptureFixture[str]) -> None:
    assert openapi.main([]) == 0

    assert capsys.readouterr().out == openapi.schema_json()


def test_check_passes_for_a_current_file(tmp_path: Path) -> None:
    path = tmp_path / "openapi.json"
    path.write_text(openapi.schema_json(), encoding="utf-8")

    assert openapi.main(["--check", str(path)]) == 0


@pytest.mark.parametrize("stale", ["{}\n", None], ids=["stale", "missing"])
def test_check_fails_for_a_stale_or_missing_file_and_changes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], stale: str | None
) -> None:
    path = tmp_path / "openapi.json"
    if stale is not None:
        path.write_text(stale, encoding="utf-8")

    assert openapi.main(["--check", str(path)]) == 1

    assert "run `make openapi`" in capsys.readouterr().err
    assert (path.read_text(encoding="utf-8") if path.exists() else None) == stale


def test_check_notices_a_route_change(tmp_path: Path) -> None:
    path = tmp_path / "openapi.json"
    before = FastAPI(title="Strength Journal")
    path.write_text(openapi.schema_json(before), encoding="utf-8")
    after = FastAPI(title="Strength Journal")

    @after.get("/api/new")
    def new() -> dict[str, str]:
        return {}

    assert openapi.main(["--check", str(path)], app=before) == 0
    assert openapi.main(["--check", str(path)], app=after) == 1


def test_check_needs_a_path() -> None:
    with pytest.raises(SystemExit) as exit_info:
        openapi.main(["--check"])
    assert exit_info.value.code == 2
