"use client";
import {useEffect,useState} from "react";
import {previewGoalAction,saveGoalAction} from "@/lib/actions/planning";
import type {GoalInput,GoalRecord,GoalKind,GoalProjection} from "@/lib/planning-types";
import {Alert,Button,Card} from "@/components/ui/primitives";
import {Input,Select} from "@/components/ui/form";
import {formatMoney} from "@/lib/format";
import {ForecastChart} from "./forecast-chart";
import {GOAL_TEMPLATES} from "@/lib/planning-goals";

export { GOAL_TEMPLATES };

export function newGoal(kind:GoalKind):GoalInput {
  const template=GOAL_TEMPLATES.find(item=>item.kind===kind)??GOAL_TEMPLATES[0];
  return {name:template.name,kind,target_amount:template.amount,saved_amount:"0",monthly_contribution:"200",months:template.months,annual_return_pct:"0",target_score:kind==="credit"?740:null,target_utilization_pct:30,show_on_dashboard:true};
}

export function GoalEditor({initial,onSaved,onCancel}:{initial:GoalInput|GoalRecord;onSaved:()=>void;onCancel:()=>void}) {
  const [form,setForm]=useState<GoalInput>(initial);
  const [preview,setPreview]=useState<GoalProjection|null>(null);
  const [error,setError]=useState("");const [busy,setBusy]=useState(false);
  const set=<K extends keyof GoalInput>(key:K,value:GoalInput[K])=>setForm(previous=>({...previous,[key]:value}));
  useEffect(()=>{
    let current=true;
    const timer=setTimeout(async()=>{const result=await previewGoalAction(form);if(current&&result.ok)setPreview(result.data);},400);
    return ()=>{current=false;clearTimeout(timer);};
  },[form]);
  async function save(event:React.FormEvent){event.preventDefault();setBusy(true);setError("");const result=await saveGoalAction("id" in initial?String(initial.id):null,form);setBusy(false);if(!result.ok){setError(result.error);return;}onSaved();}
  return <Card title={"id" in initial?"Customize your goal":"Make it yours"} action={<Button variant="ghost" onClick={onCancel}>Close</Button>} className="border-primary/40">
    <form onSubmit={save} className="space-y-5">
      <label className="block text-sm">Goal name<Input value={form.name} maxLength={100} required onChange={event=>set("name",event.target.value)} className="mt-1"/></label>
      <div className="grid gap-4 sm:grid-cols-2">
        {form.kind!=="credit"?<><label className="block text-sm">Target amount ($)<Input type="number" min="1" max="100000000" step="0.01" value={form.target_amount} onChange={event=>set("target_amount",event.target.value)} required className="mt-1"/></label><label className="block text-sm">Already earmarked ($)<Input type="number" min="0" max="100000000" step="0.01" value={form.saved_amount} onChange={event=>set("saved_amount",event.target.value)} required className="mt-1"/><span className="text-xs text-muted">Manual allocation, not a bank transfer.</span></label></>:<label className="block text-sm">Aspirational credit score<Input type="number" min="300" max="850" value={form.target_score??740} onChange={event=>set("target_score",Number(event.target.value))} required className="mt-1"/></label>}
        <label className="block text-sm">Monthly allocation ($)<Input type="number" min="0" max="1000000" step="0.01" value={form.monthly_contribution} onChange={event=>set("monthly_contribution",event.target.value)} required className="mt-1"/></label>
        <label className="block text-sm">Timeline <strong className="float-right text-primary">{form.months} months</strong><input type="range" min="1" max={form.kind==="retirement"?600:120} value={form.months} onChange={event=>set("months",Number(event.target.value))} className="mt-4 w-full accent-primary"/></label>
      </div>
      {form.kind==="credit"?<><label className="block text-sm">Target credit utilization <strong className="float-right text-primary">{form.target_utilization_pct}%</strong><input type="range" min="1" max="100" value={form.target_utilization_pct} onChange={event=>set("target_utilization_pct",Number(event.target.value))} className="mt-3 w-full accent-amber-400"/></label><Alert tone="info">A score target is a personal aspiration. Sam can plan payments and utilization, but cannot predict a score or guarantee an increase in {form.months} months.</Alert></>:<label className="block text-sm">Assumed annual return <strong className="float-right text-primary">{form.annual_return_pct}%</strong><input type="range" min="0" max="15" step="0.5" value={form.annual_return_pct} onChange={event=>set("annual_return_pct",event.target.value)} className="mt-3 w-full accent-emerald-400"/><span className="text-xs text-muted">An adjustable scenario assumption, not an expected or guaranteed market return. Default is 0%.</span></label>}
      {preview?.points?<div className="rounded-xl bg-primary-soft/40 p-4"><ForecastChart points={preview.points} label="Goal savings scenario" color={GOAL_TEMPLATES.find(item=>item.kind===form.kind)?.color}/><p className="mt-2 text-sm">Calculated monthly contribution to reach your target: <strong>{formatMoney(preview.required_monthly??"0")}</strong></p></div>:null}
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.show_on_dashboard} onChange={event=>set("show_on_dashboard",event.target.checked)} className="accent-primary"/>Show this goal on my dashboard</label>
      {error?<Alert tone="bad" role="alert">{error}</Alert>:null}
      <div className="flex gap-2"><Button type="submit" disabled={busy}>{busy?"Saving...":"Save goal"}</Button><Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button></div>
    </form>
  </Card>;
}
