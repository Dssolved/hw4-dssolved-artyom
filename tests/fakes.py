"""A fake OpenAI client for testing the loop without an API key."""
import json
import types

NS = types.SimpleNamespace


def tool_call(call_id, name, arguments):
    return NS(id=call_id, type="function", function=NS(name=name, arguments=arguments))


def reply(content=None, calls=None, prompt=100, completion=10):
    msg = NS(content=content, tool_calls=calls)
    return NS(choices=[NS(message=msg)], usage=NS(prompt_tokens=prompt, completion_tokens=completion))


class FakeClient:
    """Returns the scripted replies one by one and records every request it received."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        # keep a deep copy: the loop keeps adding to the same list afterwards
        self.requests.append(json.loads(json.dumps(kwargs, default=str)))
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
