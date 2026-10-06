"""The definitions in tools.py must be the ones written in Part A of SUBMISSION.md."""
import json
import re
from pathlib import Path

import pytest

import tools

SUBMISSION = Path(__file__).resolve().parent.parent / "SUBMISSION.md"


def part_a_definition(name):
    text = SUBMISSION.read_text(encoding="utf-8")
    section = text.split(f"#### `{name}`")[1]
    return json.loads(re.search(r"```json\n(.*?)```", section, re.S).group(1))


@pytest.mark.skipif(not SUBMISSION.exists(), reason="SUBMISSION.md not found")
def test_definitions_are_the_same_as_in_part_a():
    assert tools.LOOKUP_DEF == part_a_definition("lookup")
    assert tools.CALC_DEF == part_a_definition("calculate")


def test_definitions_have_the_required_shape():
    for d in tools.TOOLS:
        f = d["function"]
        assert d["type"] == "function" and f["name"] and f["description"]
        assert set(f["parameters"]["required"]) <= set(f["parameters"]["properties"])
        assert f["parameters"]["additionalProperties"] is False
