import type {GoalKind} from "@/lib/planning-types";

/** Goal presets shared by Server and Client Components. */
export const GOAL_TEMPLATES:{kind:GoalKind;name:string;caption:string;color:string;amount:string;months:number}[]=[
  {kind:"education",name:"My undergraduate education",caption:"Tuition, books and your next chapter",color:"#a78bfa",amount:"20000",months:36},
  {kind:"car",name:"My next car",caption:"Build a down payment before you buy",color:"#38bdf8",amount:"12000",months:24},
  {kind:"retirement",name:"My retirement",caption:"Explore a long-term saving scenario",color:"#34d399",amount:"500000",months:360},
  {kind:"credit",name:"Healthier credit habits",caption:"Plan utilization and monthly payments",color:"#fbbf24",amount:"0",months:8},
  {kind:"emergency",name:"My emergency cushion",caption:"Give unexpected costs a place to land",color:"#fb7185",amount:"10000",months:18},
  {kind:"investment",name:"My investment fund",caption:"Keep investing separate from spending",color:"#818cf8",amount:"25000",months:60},
];
