export type GoalKind="education"|"retirement"|"car"|"emergency"|"investment"|"credit"|"custom";
export interface PlanningPreferences {
  ai_enabled:boolean;show_forecast:boolean;show_subscriptions:boolean;show_spending:boolean;
  monthly_income:string|null;monthly_budget:string|null;forecast_months:number;
  stocks_pct:number;bonds_pct:number;cash_pct:number;
}
export interface GoalInput {
  name:string;kind:GoalKind;target_amount:string;saved_amount:string;monthly_contribution:string;
  months:number;annual_return_pct:string;target_score:number|null;target_utilization_pct:number;show_on_dashboard:boolean;
}
export interface SamAnswer {allowed:boolean;answer:string;steps:string[];questions:string[];source:string;model?:string;generated_at?:string}
export interface GoalProjection {
  projected_amount?:string;required_monthly?:string;shortfall?:string;on_track?:boolean;progress_pct?:number;
  points?:{month:number;amount:string}[];monthly_payment?:string;
  cards?:{account_ref:string;balance:string;credit_limit:string;utilization_pct:number;target_balance:string;monthly_payment:string;apr:string|null;apr_unknown:boolean}[];
  assumptions?:string[];
}
export interface GoalRecord extends GoalInput {id:string;updated_at:string;projection:GoalProjection|null;ai_plan:SamAnswer|null}
export interface PlanningSnapshot {
  as_of:string;currency:string;
  accounts:{ref:string;institution:string;type:string;balance:string;apr:string|null;credit_limit:string|null}[];
  totals:{liquid_cash:string;debt:string;credit_limit:string;card_balance:string;utilization_pct:number|null};
  cash_flow:{coverage_days:number;monthly_income:string|null;monthly_spending:string|null;known_debt_payments:string;monthly_free_cash:string|null;recent_spending:string;income_source:string};
  credit_score:{score:number;synthetic:boolean;model:string}|null;
  categories:{category:string;amount:string}[];
  subscriptions:{merchant:string;amount:string;monthly_estimate:string;cadence:string;occurrences:number;status:string}[];
  alerts:{kind:string;title:string;amount:string;detail:string}[];warnings:string[];
}
export interface PlanningOverview {
  preferences:PlanningPreferences;goals:GoalRecord[];snapshot:PlanningSnapshot;
  forecast:{available:boolean;reason?:string;points:{month:number;cash:string;unallocated:string}[];goal_contributions?:string;overallocated?:boolean;assumptions?:string[]};
  ai_configured:boolean;model:string;
}
export interface SamTurn {id:string;message:string;response:SamAnswer|null;created_at:string}
