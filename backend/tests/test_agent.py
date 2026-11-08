import json

from app.agent.coach import run_coach
from app.agent.tools import ToolRegistry
from tests.fakes import FakeLLM, reply, tool_call


def test_registry_exposes_schemas_without_customer_id(alex):
    schemas = ToolRegistry(alex).schemas()
    names = {s["function"]["name"] for s in schemas}
    assert names == {
        "get_accounts",
        "get_health_report",
        "plan_credit_utilization_goal",
        "project_debt_payoff",
    }
    # Security property: the model can never pick whose data it reads.
    assert "customer_id" not in json.dumps(schemas)


def test_tool_call_returns_engine_numbers(alex):
    result = ToolRegistry(alex).call(
        "plan_credit_utilization_goal",
        json.dumps({"account_id": "pnc-cc-1", "target_utilization_percent": 10, "months": 6}),
    )
    assert result.ok
    assert result.payload["monthly_payment"] == "65.19"


def test_tool_errors_are_returned_to_the_model_not_raised(alex):
    reg = ToolRegistry(alex)
    assert not reg.call("transfer_money", "{}").ok
    assert not reg.call("plan_credit_utilization_goal", "not json").ok
    assert not reg.call("plan_credit_utilization_goal", '{"account_id": "x"}').ok
    bad_account = reg.call(
        "project_debt_payoff",
        json.dumps({"account_id": "c1-chk-1", "monthly_payment": 50, "months": 3}),
    )
    assert not bad_account.ok
    assert "not a credit card or loan" in bad_account.payload["error"]


async def test_coach_runs_multi_step_workflow(alex):
    llm = FakeLLM(
        [
            reply(tool_calls=[tool_call("1", "get_accounts")]),
            reply(
                tool_calls=[
                    tool_call(
                        "2",
                        "plan_credit_utilization_goal",
                        {"account_id": "pnc-cc-1", "target_utilization_percent": 10, "months": 6},
                    )
                ]
            ),
            reply(content="Pay $65.19/month for 6 months to reach 10% utilization."),
        ]
    )
    answer = await run_coach(llm, "test-model", alex, "How do I raise my credit score?")

    assert answer.completed
    assert [s.tool for s in answer.steps] == ["get_accounts", "plan_credit_utilization_goal"]
    assert answer.steps[1].result["monthly_payment"] == "65.19"
    # The tool result was fed back to the model on the final turn.
    last_messages = llm.requests[-1]["messages"]
    assert last_messages[-1]["role"] == "tool"
    assert '"65.19"' in last_messages[-1]["content"]


async def test_coach_stops_at_step_cap(alex):
    llm = FakeLLM([reply(tool_calls=[tool_call("x", "get_accounts")])])  # loops forever
    answer = await run_coach(llm, "test-model", alex, "loop", max_steps=3)
    assert not answer.completed
    assert len(llm.requests) == 3
