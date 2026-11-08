"""Test doubles."""

import json
from types import SimpleNamespace
from typing import Any

# --- Fake LLM: replays scripted responses in the shape of the OpenAI SDK --------


def tool_call(call_id: str, name: str, args: dict[str, Any] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(args or {})),
    )


def reply(content: str | None = None, tool_calls: list | None = None) -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeLLM:
    def __init__(self, script: list[SimpleNamespace]) -> None:
        self._script = list(script)
        self.requests: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(kwargs)
        # Repeat the last scripted reply forever (used by the step-cap test).
        return self._script.pop(0) if len(self._script) > 1 else self._script[0]
