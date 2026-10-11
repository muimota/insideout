import json
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from .config import Settings
from .models import Agent


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AsyncOpenAI(
            api_key=settings.api_key, base_url=settings.base_url
        )

    async def run_turn(
        self,
        agent: Agent,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict],
        timeout: float,
    ) -> AsyncIterator[dict[str, Any]]:
        model = agent.model or self.settings.model
        stream = await self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=tools,
            stream=True,
            temperature=0.7,
            timeout=timeout + 10,
        )
        tool_calls: dict[int, dict] = {}
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta is None:
                continue
            if delta.content:
                yield {"type": "thought_token", "text": delta.content}
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    acc = tool_calls.setdefault(
                        tc.index, {"id": "", "name": "", "arguments": ""}
                    )
                    if tc.id:
                        acc["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            acc["name"] = tc.function.name
                        if tc.function.arguments:
                            acc["arguments"] += tc.function.arguments

        calls: list[dict] = []
        for acc in tool_calls.values():
            name = acc.get("name")
            if name not in ("propose_output", "abstain_output"):
                continue
            try:
                args = json.loads(acc["arguments"] or "{}")
            except json.JSONDecodeError:
                continue
            if isinstance(args, dict):
                if name == "abstain_output":
                    args["valor"] = "ABSTAIN"
                calls.append(args)
        yield {"type": "turn_complete", "tool_calls": calls}
