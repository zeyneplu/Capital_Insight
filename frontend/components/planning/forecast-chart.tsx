"use client";
import {formatMoney} from "@/lib/format";

export function ForecastChart({points,label="Projected balance",color="#38bdf8"}:{points:{month:number;amount:string}[];label?:string;color?:string}) {
  if(!points.length)return <p className="text-sm text-muted">A forecast appears when enough data is available.</p>;
  const values=points.map(point=>Number(point.amount));
  const low=Math.min(0,...values),high=Math.max(1,...values),span=high-low||1;
  const coords=points.map((point,index)=>`${35+index/Math.max(1,points.length-1)*530},${175-(Number(point.amount)-low)/span*140}`);
  const last=points[points.length-1];
  return <figure className="space-y-2"><div className="flex flex-wrap items-end justify-between gap-2"><figcaption className="text-xs text-muted">{label} · scenario, not a guarantee</figcaption><strong className="text-xl tabular-nums">{formatMoney(last.amount)}<span className="ml-2 text-xs font-normal text-muted">month {last.month}</span></strong></div>
    <svg viewBox="0 0 600 210" role="img" aria-label={`${label}: ${formatMoney(points[0].amount)} now to ${formatMoney(last.amount)} in ${last.month} months`} className="w-full overflow-visible">
      {[0,0.5,1].map(value=><g key={value}><line x1="35" y1={175-value*140} x2="565" y2={175-value*140} stroke="currentColor" opacity="0.12"/><text x="35" y={167-value*140} fontSize="10" fill="currentColor" opacity="0.65">{formatMoney(String(Math.round(low+value*span)))}</text></g>)}
      <path d={`M${coords.join(" L")}`} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx="565" cy={175-(Number(last.amount)-low)/span*140} r="5" fill={color}/>
      <text x="35" y="203" fontSize="11" fill="currentColor">Now</text><text x="565" y="203" textAnchor="end" fontSize="11" fill="currentColor">Month {last.month}</text>
    </svg>
    <details className="text-xs text-muted"><summary className="cursor-pointer">View forecast values</summary><div className="mt-2 grid grid-cols-2 gap-1 sm:grid-cols-3">{points.map(point=><span key={point.month}>Month {point.month}: {formatMoney(point.amount)}</span>)}</div></details>
  </figure>;
}
