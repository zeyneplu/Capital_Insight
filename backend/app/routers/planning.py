import asyncio
from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select, func, delete
from sqlalchemy.exc import IntegrityError

from ..database import utcnow
from ..dependencies import SessionDep, VerifiedUserDep
from ..models import FinancialGoal, PlanningPreferences, SamTurn
from ..planning_schemas import PreferencesIn, GoalIn, ChatIn
from ..planning_math import goal_projection, credit_payment_plan, money
from ..financial_context import build_snapshot, model_context
from ..sam import infer, finance_request, REFUSAL

router=APIRouter(prefix="/v1/planning",tags=["Goals, forecasts and Sam"])


def preferences(session,user):
    record=session.get(PlanningPreferences,user.id)
    return PreferencesIn.model_validate(record.settings if record else {}).model_dump(mode="json")


def goals(session,user):
    return session.scalars(select(FinancialGoal).where(FinancialGoal.user_id==user.id).order_by(FinancialGoal.created_at)).all()


def goal_out(goal,snapshot=None):
    data={"id":goal.id,"name":goal.name,"kind":goal.kind,**goal.parameters,"ai_plan":goal.ai_plan,"updated_at":goal.updated_at.isoformat()}
    data["projection"]=credit_payment_plan(snapshot["cards"],goal.parameters["months"],goal.parameters["target_utilization_pct"]) if goal.kind=="credit" and snapshot else goal_projection(goal.parameters) if goal.kind!="credit" else None
    return data


def owned_goal(session,user,goal_id):
    goal=session.scalar(select(FinancialGoal).where(FinancialGoal.id==goal_id,FinancialGoal.user_id==user.id))
    if goal is None: raise HTTPException(404,"Goal not found")
    return goal


def forecast(snapshot,prefs,items):
    free=snapshot["cash_flow"]["monthly_free_cash"]
    if free is None:
        return {"available":False,"points":[],"reason":"Connect transaction history with at least 30 days of coverage to calculate a cash-flow scenario."}
    contributions=sum(Decimal(str(goal.parameters["monthly_contribution"])) for goal in items)
    initial=Decimal(snapshot["totals"]["liquid_cash"])
    earmarked=sum(Decimal(str(goal.parameters["saved_amount"])) for goal in items if goal.kind!="credit")
    points=[{"month":month,"cash":money(initial+Decimal(free)*month),
        "unallocated":money(initial-earmarked+(Decimal(free)-contributions)*month)} for month in range(prefs["forecast_months"]+1)]
    return {"available":True,"points":points,"goal_contributions":money(contributions),
        "overallocated":contributions>max(Decimal(0),Decimal(free)),
        "assumptions":["Constant estimated income, spending and known debt payments; USD only", "Goal allocations reduce spendable cash, not total cash; no actual transfers occur", "Missing accounts, taxes and irregular expenses can change the outcome"]}


@router.get("/preferences")
def get_preferences(session:SessionDep,user:VerifiedUserDep):
    return preferences(session,user)


@router.put("/preferences")
def save_preferences(body:PreferencesIn,session:SessionDep,user:VerifiedUserDep):
    record=session.get(PlanningPreferences,user.id)
    if record is None:
        record=PlanningPreferences(user_id=user.id,settings=body.model_dump(mode="json"));session.add(record)
    else: record.settings=body.model_dump(mode="json")
    session.commit()
    return record.settings


@router.get("/goals")
def list_goals(session:SessionDep,user:VerifiedUserDep):
    return [goal_out(goal) for goal in goals(session,user)]


@router.post("/goals",status_code=201)
def create_goal(body:GoalIn,session:SessionDep,user:VerifiedUserDep):
    if session.scalar(select(func.count()).select_from(FinancialGoal).where(FinancialGoal.user_id==user.id))>=20:
        raise HTTPException(422,"Keep up to 20 active goals; remove one before adding another")
    goal=FinancialGoal(user_id=user.id,name=body.name,kind=body.kind,parameters=body.model_dump(mode="json",exclude={"name","kind"}))
    session.add(goal);session.commit()
    return goal_out(goal)


@router.put("/goals/{goal_id}")
def update_goal(goal_id:str,body:GoalIn,session:SessionDep,user:VerifiedUserDep):
    goal=owned_goal(session,user,goal_id)
    goal.name,goal.kind,goal.parameters=body.name,body.kind,body.model_dump(mode="json",exclude={"name","kind"})
    goal.ai_plan=None;goal.updated_at=utcnow();session.commit()
    return goal_out(goal)


@router.delete("/goals/{goal_id}",status_code=204)
def remove_goal(goal_id:str,session:SessionDep,user:VerifiedUserDep):
    session.delete(owned_goal(session,user,goal_id));session.commit()


@router.post("/preview")
def preview(body:GoalIn,user:VerifiedUserDep):
    return goal_projection(body.model_dump(mode="json")) if body.kind!="credit" else {"aspirational_score":body.target_score,"message":"Score targets are aspirations, not forecasts. Save the goal to calculate utilization and payment scenarios from connected cards."}


@router.get("/overview")
async def overview(request:Request,session:SessionDep,user:VerifiedUserDep):
    prefs=preferences(session,user);items=goals(session,user)
    snapshot=await build_snapshot(request,session,user,prefs)
    return {"preferences":prefs,"goals":[goal_out(goal,snapshot) for goal in items],"snapshot":snapshot,
        "forecast":forecast(snapshot,prefs,items),"ai_configured":bool(request.app.state.settings.nvidia_api_key),
        "model":request.app.state.settings.nvidia_model}


def require_ai(session,user,request):
    if not preferences(session,user)["ai_enabled"]:
        raise HTTPException(403,"Enable Sam's use of your aggregated financial data in Planning first")
    if not request.app.state.settings.nvidia_api_key:
        raise HTTPException(503,"Add NVIDIA_API_KEY to backend/.env and restart the core API to enable Sam")


def rate_limit(session,user):
    count=session.scalar(select(func.count()).select_from(SamTurn).where(SamTurn.user_id==user.id,SamTurn.created_at>utcnow()-timedelta(minutes=1)))
    if count>=6: raise HTTPException(429,"Give Sam a moment. Try again in a minute.",headers={"Retry-After":"60"})


MISUSE_WINDOW=timedelta(minutes=15)
MISUSE_LIMIT=3


def misuse_lock(session,user):
    """After repeated off-topic or unsafe requests, Sam stops responding for a while."""
    recent=session.scalars(select(SamTurn).where(SamTurn.user_id==user.id,SamTurn.created_at>utcnow()-MISUSE_WINDOW)
        .order_by(SamTurn.created_at.desc()).limit(20)).all()
    if sum(1 for turn in recent if (turn.response or {}).get("source")=="policy")>=MISUSE_LIMIT:
        raise HTTPException(429,"Sam has paused this conversation after repeated off-topic or unsafe requests. "
            "Come back in 15 minutes with a personal-finance question.",headers={"Retry-After":"900"})


@router.get("/sam/history")
def history(session:SessionDep,user:VerifiedUserDep):
    turns=session.scalars(select(SamTurn).where(SamTurn.user_id==user.id).order_by(SamTurn.created_at.desc()).limit(20)).all()
    return [{"id":turn.id,"message":turn.message,"response":turn.response,"created_at":turn.created_at.isoformat()} for turn in reversed(turns)]


@router.delete("/sam/history",status_code=204)
def clear_history(session:SessionDep,user:VerifiedUserDep):
    session.execute(delete(SamTurn).where(SamTurn.user_id==user.id));session.commit()


@router.post("/sam/chat")
async def chat(body:ChatIn,request:Request,session:SessionDep,user:VerifiedUserDep):
    require_ai(session,user,request)
    prior=session.scalar(select(SamTurn).where(SamTurn.user_id==user.id,SamTurn.request_id==body.request_id))
    if prior:
        if prior.message!=body.message: raise HTTPException(409,"Use a new request ID for a new question")
        if prior.response is None: raise HTTPException(409,"Sam is still responding to this question")
        return prior.response
    misuse_lock(session,user)
    rate_limit(session,user)
    recent=session.scalars(select(SamTurn).where(SamTurn.user_id==user.id,SamTurn.response.is_not(None)).order_by(SamTurn.created_at.desc()).limit(6)).all()
    if not finance_request(body.message,bool(recent)):
        answer={"allowed":False,"answer":REFUSAL,"steps":[],"questions":[],"source":"policy"}
        session.add(SamTurn(user_id=user.id,request_id=body.request_id,message=body.message,response=answer));session.commit()
        return answer
    turn=SamTurn(user_id=user.id,request_id=body.request_id,message=body.message)
    session.add(turn)
    try: session.commit()
    except IntegrityError:
        session.rollback();raise HTTPException(409,"This question is already being processed") from None
    try:
        prefs=preferences(session,user);items=goals(session,user)
        snapshot=await build_snapshot(request,session,user,prefs)
        context=model_context(snapshot,items,prefs)
        context["calculated_goal_plans"]=[{"kind":goal.kind,"calculation":goal_out(goal,snapshot)["projection"]} for goal in items]
        session.rollback()
        answer=await infer(request,context,body.message,list(reversed(recent)))
        stored=session.get(SamTurn,turn.id);stored.response=answer;session.commit()
        return answer
    except HTTPException:
        session.rollback()
        stored=session.get(SamTurn,turn.id)
        if stored: session.delete(stored);session.commit()
        raise


@router.post("/goals/{goal_id}/plan")
async def generate_plan(goal_id:str,request:Request,session:SessionDep,user:VerifiedUserDep):
    require_ai(session,user,request);rate_limit(session,user)
    goal=owned_goal(session,user,goal_id)
    prefs=preferences(session,user);items=goals(session,user)
    snapshot=await build_snapshot(request,session,user,prefs)
    context=model_context(snapshot,items,prefs)
    context["selected_goal"]={"kind":goal.kind,**goal.parameters,"calculated_plan":goal_out(goal,snapshot)["projection"]}
    answer=await infer(request,context,"Explain a practical personal-finance plan for the selected goal. Use the calculated amounts, assess affordability, and explain uncertainty. Do not guarantee score changes or investment returns.")
    goal.ai_plan={**answer,"generated_at":utcnow().isoformat()};session.commit()
    # Plan requests count against the same inference budget as chat.
    session.add(SamTurn(user_id=user.id,request_id="plan-"+goal.id+"-"+str(int(utcnow().timestamp()*1000)),message="Generate saved goal plan",response=answer));session.commit()
    return goal_out(goal,snapshot)
