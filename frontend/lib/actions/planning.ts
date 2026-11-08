"use server";
import {revalidatePath} from "next/cache";
import {authToken,coreRequest,requireVerifiedUser} from "@/lib/auth";
import type {GoalInput,GoalRecord,PlanningOverview,PlanningPreferences,SamAnswer,SamTurn,GoalProjection} from "@/lib/planning-types";

type Result<T>={ok:true;data:T}|{ok:false;error:string};
async function call<T>(path:string,method="GET",body?:unknown):Promise<Result<T>> {
  await requireVerifiedUser();
  try {
    const response=await coreRequest("/v1/planning"+path,{method,body,token:await authToken()});
    if(!response.ok) {
      const data=await response.json().catch(()=>({}));
      const detail=data.detail;
      return {ok:false,error:typeof detail==="string"?detail:Array.isArray(detail)?detail.map((item:{msg:string})=>item.msg).join(" "):"This request could not be completed."};
    }
    return {ok:true,data:response.status===204?undefined as T:await response.json() as T};
  } catch { return {ok:false,error:"The planning service is unavailable. Try again shortly."}; }
}
function refresh(){revalidatePath("/", "layout");}
export async function loadPlanningAction(){return call<PlanningOverview>("/overview");}
export async function savePreferencesAction(input:PlanningPreferences){const result=await call<PlanningPreferences>("/preferences","PUT",input);if(result.ok)refresh();return result;}
export async function saveGoalAction(id:string|null,input:GoalInput){const result=await call<GoalRecord>(id?`/goals/${encodeURIComponent(id)}`:"/goals",id?"PUT":"POST",input);if(result.ok)refresh();return result;}
export async function deleteGoalAction(id:string){const result=await call<void>(`/goals/${encodeURIComponent(id)}`,"DELETE");if(result.ok)refresh();return result;}
export async function previewGoalAction(input:GoalInput){return call<GoalProjection>("/preview","POST",input);}
export async function generateGoalPlanAction(id:string){const result=await call<GoalRecord>(`/goals/${encodeURIComponent(id)}/plan`,"POST");if(result.ok)refresh();return result;}
export async function askSamAction(message:string,requestId:string){return call<SamAnswer>("/sam/chat","POST",{message,request_id:requestId});}
export async function samHistoryAction(){return call<SamTurn[]>("/sam/history");}
export async function clearSamAction(){return call<void>("/sam/history","DELETE");}
