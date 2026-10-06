"""Tests for reading the final line, voting, and my rule for a correct answer."""
import strategies
from run import is_correct


def test_parse_answer():
    assert strategies.parse_answer("blah\nANSWER: Millbrook | 0.556") == {"name": "Millbrook", "number": 0.556}
    assert strategies.parse_answer("ANSWER: yes | 14,069") == {"name": "yes", "number": 14069.0}
    assert strategies.parse_answer("ANSWER: **Harrowfield** | 1.6875")["name"] == "Harrowfield"
    assert strategies.parse_answer("ANSWER: A | 1\nlater\nANSWER: B | 2") == {"name": "B", "number": 2.0}  # the last one counts
    assert strategies.parse_answer("The answer is Millbrook, 0.6") is None
    assert strategies.parse_answer("ANSWER: Millbrook | about five") is None
    assert strategies.parse_answer("") is None and strategies.parse_answer(None) is None


def test_vote_takes_the_most_common_answer():
    a = lambda n, x: {"name": n, "number": x}
    v = strategies.vote([a("Millbrook", 0.556), a("Brightwater", 0.1), a("millbrook", 0.5561), None, a("Millbrook", 0.556)])
    assert v["name"] == "Millbrook" and v["votes"] == 3 and v["of"] == 4
    assert strategies.vote([None, None]) is None
    assert strategies.vote([a("A", 1), a("B", 2)])["name"] == "A"          # a tie: the first one


def test_my_rule_for_a_correct_answer():
    q = {"answer": "Millbrook", "value": 0.6, "decimals": 1}
    assert is_correct({"name": "Millbrook", "number": 0.556}, q)           # 0.556 rounds to 0.6
    assert is_correct({"name": "millbrook", "number": 0.6}, q)              # capital letters do not matter
    assert is_correct({"name": "Millbrook", "number": 0.7}, q)              # 1 in the last digit is allowed
    assert not is_correct({"name": "Millbrook", "number": 0.077}, q)        # the uncorrected-area answer (0.1)
    assert not is_correct({"name": "Brightwater", "number": 0.6}, q)        # the name must match
    assert not is_correct(None, q)
    big = {"answer": "Coldharbour", "value": 14235, "decimals": 0}
    assert is_correct({"name": "Coldharbour", "number": 14235.3145}, big)
    assert not is_correct({"name": "Coldharbour", "number": 14240}, big)
