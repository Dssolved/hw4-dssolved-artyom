"""Tests for the loop (S3) with a fake model. No API key needed."""
import json

import strategies
from fakes import FakeClient, reply, tool_call


def q09_script():
    """What the real model is expected to do for Q-09 (see A3 in SUBMISSION.md)."""
    return [
        reply(calls=[tool_call("c1", "lookup", '{"district": "Brightwater", "field": "population_2025"}'),
                     tool_call("c2", "lookup", '{"district": "Brightwater", "field": "area_km2"}'),
                     tool_call("c3", "lookup", '{"district": "Millbrook", "field": "population_2025"}'),
                     tool_call("c4", "lookup", '{"district": "Millbrook", "field": "area_km2"}')]),
        reply(calls=[tool_call("c5", "calculate", '{"expression": "37203 / 758.6 - 44675 / 921.4", "decimals": 3}')]),
        reply(content="Millbrook is denser.\nANSWER: Millbrook | 0.556", prompt=300, completion=20),
    ]


def test_q09_flow_every_tool_call_id_is_answered_and_the_answer_is_read():
    client = FakeClient(q09_script())
    out = strategies.run_s3(client, "Which district has the higher population density ...?")
    assert out["answer"] == {"name": "Millbrook", "number": 0.556}
    assert out["rounds"] == 3 and out["calls"] == 3 and not out["unanswered"]
    # second request: the assistant message with its tool_calls, then one tool message per id
    second = client.requests[1]["messages"]
    assistant = second[2]
    assert [tc["id"] for tc in assistant["tool_calls"]] == ["c1", "c2", "c3", "c4"]
    answered = [m["tool_call_id"] for m in second if m["role"] == "tool"]
    assert answered == ["c1", "c2", "c3", "c4"]
    brightwater_area = json.loads(second[4]["content"])
    assert brightwater_area["value"] == 921.4                      # the corrected area reached the model
    # the tools were sent to the model
    assert [t["function"]["name"] for t in client.requests[0]["tools"]] == ["lookup", "calculate"]
    # the log: every call with inputs, result and time
    calls = [c for r in out["trace"] for c in r["tool_calls"]]
    assert len(calls) == 5 and all({"id", "name", "arguments", "result", "seconds"} <= set(c) for c in calls)


def test_tokens_are_added_up_over_all_rounds():
    out = strategies.run_s3(FakeClient(q09_script()), "q")
    assert out["prompt_tokens"] == 100 + 100 + 300 and out["completion_tokens"] == 10 + 10 + 20


def test_bad_arguments_get_an_error_with_the_same_id_and_the_loop_goes_on():
    script = [
        reply(calls=[tool_call("a", "lookup", "{not json"),
                     tool_call("b", "lookup", '{"district": "Ossford", "field": "area_km2"}'),
                     tool_call("c", "no_such_tool", "{}")]),
        reply(content="ANSWER: Ossford | 846.2"),
    ]
    client = FakeClient(script)
    out = strategies.run_s3(client, "q")
    tool_msgs = [m for m in client.requests[1]["messages"] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["a", "b", "c"]
    assert "not valid JSON" in json.loads(tool_msgs[0]["content"])["error"]
    assert json.loads(tool_msgs[1]["content"])["value"] == 846.2
    assert "unknown tool" in json.loads(tool_msgs[2]["content"])["error"]
    assert out["answer"]["number"] == 846.2


def test_round_limit_marks_the_question_unanswered():
    forever = [reply(calls=[tool_call("x", "calculate", '{"expression": "1+1"}')])]
    client = FakeClient(forever)
    out = strategies.run_s3(client, "q", max_rounds=4)
    assert out["unanswered"] and out["answer"] is None and out["round_limit_reached"]
    assert len(client.requests) == 4 and out["rounds"] == 4


def test_reply_without_the_final_line_is_unanswered_but_not_a_limit_problem():
    out = strategies.run_s3(FakeClient([reply(content="I think it is Millbrook.")]), "q")
    assert out["answer"] is None and out["unanswered"] and not out["round_limit_reached"]


def test_s1_and_s2_send_all_documents_and_s3_sends_none():
    s1, s2 = FakeClient([reply(content="ANSWER: yes | 5")]), FakeClient([reply(content="ANSWER: yes | 5")])
    strategies.run_s1(s1, "q")
    out2 = strategies.run_s2(s2, "q", k=3)
    for client in (s1, s2):
        system = client.requests[0]["messages"][0]["content"]
        assert "[NR-16]" in system and "[NR-13]" in system and "tools" not in client.requests[0]
    assert len(s2.requests) == 3 and out2["calls"] == 3                 # k separate calls
    s3 = FakeClient([reply(content="ANSWER: yes | 5")])
    strategies.run_s3(s3, "q")
    assert "[NR-16]" not in s3.requests[0]["messages"][0]["content"]
    # the question is passed word for word, and the format rules are the same text in all three
    assert s3.requests[0]["messages"][1]["content"] == "q"
    for client in (s1, s3):
        assert strategies.FORMAT_RULES in client.requests[0]["messages"][0]["content"]


def test_every_call_of_every_strategy_uses_the_same_reasoning_setting():
    clients = [FakeClient([reply(content="ANSWER: yes | 5")]) for _ in range(3)]
    strategies.run_s1(clients[0], "q")
    strategies.run_s2(clients[1], "q", k=2)
    strategies.run_s3(clients[2], "q")
    for client in clients:
        for request in client.requests:
            assert request["model"] == "gpt-5.6-luna"
            assert request["reasoning_effort"] == "none"          # the API needs it for tools; kept for all
            assert "temperature" not in request and "max_tokens" not in request
