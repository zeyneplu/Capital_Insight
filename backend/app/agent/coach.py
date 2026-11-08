"""The Nemotron coach: a bounded plan -> call tools -> observe -> answer loop.

Why this is "beyond a chatbot" (NVIDIA track):
- The model decides which tools to call and in what order (multi-step workflow).
- Every number in the answer comes from a deterministic tool, not from the model.
- The full trace is returned, so the UI can show *how* the answer was reached.
"""

from typing import Any, Protocol

from pydantic import BaseModel

from app.agent.tools import ToolRegistry
from app.domain.models import FinancialProfile

MAX_STEPS = 6  # hard cap on model round-trips: bounds cost, latency and runaway loops

SYSTEM_PROMPT = """You are Capital Insight, a calm, encouraging financial coach.

Rules:
1. Never calculate numbers yourself. Get every number from a tool and quote it exactly.
2. Start with get_accounts unless you already have the account IDs you need.
3. For goals ("raise my credit score", "pay this off by June"), turn the goal into a
   concrete plan with plan_credit_utilization_goal or project_debt_payoff.
4. If spare cash could pay off high-interest debt faster, say so, citing get_health_report.
5. If data is missing, say what is missing. Do not guess.
6. Answer in under 150 words: the plan, the monthly amount, the timeline, one next step.
7. You give education, not professional financial advice. Say so once, briefly."""


class TraceStep(BaseModel):
    tool: str
    arguments: str
    ok: bool
    result: dict[str, Any]


class CoachAnswer(BaseModel):
    answer: str
    completed: bool  # False if the step cap was hit
    steps: list[TraceStep]


class ChatClient(Protocol):
    """The slice of openai.AsyncOpenAI we use. Lets tests pass a fake client."""

    @property
    def chat(self) -> Any: ...


async def run_coach(
    client: ChatClient,
    model: str,
    profile: FinancialProfile,
    question: str,
    max_steps: int = MAX_STEPS,
) -> CoachAnswer:
    registry = ToolRegistry(profile)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    trace: list[TraceStep] = []

    for _ in range(max_steps):
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=registry.schemas(),
            temperature=0.6,  # NVIDIA's recommended setting for tool calling
            top_p=0.95,
        )
        message = response.choices[0].message
        if not message.tool_calls:
            return CoachAnswer(answer=message.content or "", completed=True, steps=trace)

        # Echo the assistant's tool request back, then one "tool" message per call.
        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in message.tool_calls
                ],
            }
        )
        for call in message.tool_calls:
            result = registry.call(call.function.name, call.function.arguments)
            trace.append(
                TraceStep(
                    tool=call.function.name,
                    arguments=call.function.arguments or "{}",
                    ok=result.ok,
                    result=result.payload,
                )
            )
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result.to_message_content()}
            )

    return CoachAnswer(
        answer="I ran out of steps before finishing. Try a more specific question.",
        completed=False,
        steps=trace,
    )
