"""Tests for `calculate`. No API key needed."""
import os
import time

import pytest

from tools import calculate


def test_multiplication_is_right():
    r = calculate("48317 * 1.0947")
    assert r["result"] == pytest.approx(52892.6199)
    assert r["rounded"] is None


def test_order_of_operations_brackets_and_unary_minus():
    assert calculate("2 + 3 * 4")["result"] == 14
    assert calculate("(2 + 3) * 4")["result"] == 20
    assert calculate("-5 + 3")["result"] == -2
    assert calculate("10 - -2")["result"] == 12


def test_density_example_and_rounding():
    r = calculate("44675 / 921.4", decimals=3)
    assert r["result"] == pytest.approx(48.48599956587801)
    assert r["rounded"] == 48.486
    assert calculate("2.675", decimals=2)["rounded"] == 2.68                 # half up on the written number
    assert calculate("0.0348", decimals=3)["rounded"] == 0.035


def test_division_by_zero_is_an_error():
    assert calculate("1 / 0") == {"error": "division by zero"}
    assert "error" in calculate("5 / (3 - 3)")


@pytest.mark.parametrize("bad", ["__import__('os').system('echo hi')", "(1).__class__", "9**9**9"])
def test_dangerous_input_is_refused_and_never_run(bad, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the expression was run!")
    monkeypatch.setattr(os, "system", boom)
    start = time.perf_counter()
    r = calculate(bad)
    assert "error" in r and "result" not in r
    assert time.perf_counter() - start < 1.0                                 # no freezing (9**9**9 would take forever)


def test_refusal_messages_say_why():
    assert "function call" in calculate("__import__('os').system('echo hi')")["error"]
    assert "attribute" in calculate("(1).__class__")["error"]
    assert "**" in calculate("9**9**9")["error"]
    assert "name 'x'" in calculate("x + 1")["error"]
    assert "comma" in calculate("44,675 / 2")["error"]


def test_other_things_that_are_not_arithmetic_are_refused():
    for bad in ["'a' * 3", "True + 1", "[1, 2]", "1 if 1 else 2", "lambda: 1", "10 % 3", "10 // 3", "1 < 2", "abs(-1)"]:
        assert "error" in calculate(bad), bad


def test_limits():
    assert "longer" in calculate("1+" * 150 + "1")["error"]
    assert "too large" in calculate("99999999999999999999 + 1")["error"]
    assert "too large" in calculate("999999999999 * 999999999999")["error"]
    assert "error" in calculate("")
    assert "error" in calculate("   ")
    assert "cannot read" in calculate("2 +")["error"]
    assert "too complicated" in calculate("+".join(["1"] * 60))["error"]


def test_wrong_argument_types():
    assert "string" in calculate(123)["error"]
    assert "decimals" in calculate("1+1", decimals=-1)["error"]
    assert "decimals" in calculate("1+1", decimals=11)["error"]
    assert "decimals" in calculate("1+1", decimals=True)["error"]
    assert "decimals" in calculate("1+1", decimals="2")["error"]
