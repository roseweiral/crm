"""Focused selection must not be blocked by unrelated test categories."""

from types import SimpleNamespace

import pytest

from . import run_tests

pytestmark = pytest.mark.contract


@pytest.mark.parametrize(
    "codes,expected", [([5, 0, 5], 0), ([5, 5, 5], 5), ([0, 1], 1), ([2], 2)]
)
def test_category_runner_handles_empty_selections_and_failures(
    monkeypatch, codes, expected
):
    calls = []
    remaining = iter(codes)

    def run(command, check):
        calls.append(command)
        return SimpleNamespace(returncode=next(remaining))

    monkeypatch.setattr(run_tests.subprocess, "run", run)
    assert (
        run_tests.run_categories(["smoke", "contract", "regression"], ["-k", "target"])
        == expected
    )
    assert len(calls) == len(codes)
