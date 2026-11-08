import test from "node:test";
import assert from "node:assert/strict";
import { normalizePlaidAccount, normalizePlaidTransaction, type PlaidAccountSnapshot } from "./plaid-normalize.ts";

const institution = {id:"item-1",name:"Linked bank",service:"plaid" as const};
const raw: PlaidAccountSnapshot = {
  id:"item-1:checking",connection_id:"item-1",source_account_id:"checking",source_account_type:"depository",
  account_type:"checking",account_name:"Checking",currency:"USD",balance:"123.45",balance_kind:"asset",
};

test("Plaid accounts preserve ownership and do not invent opening balances",()=>{
  const account=normalizePlaidAccount(raw,institution,"2026-11-08T10:00:00Z")!;
  assert.equal(account.balance,"123.45");
  assert.equal(account.openingBalance,null);
  assert.equal(account.id,"item-1:checking");
  assert.equal(account.institution.service,"plaid");
});
test("Plaid sub-cent balances round exactly before entering cents-only portfolio math",()=>{
  for (const [balance, expected] of [["23631.9805","23631.98"],["1.005","1.01"],["-1.005","-1.01"],["9007199254740993.125","9007199254740993.13"]])
    assert.equal(normalizePlaidAccount({...raw,balance},institution,"2026-11-08")!.balance,expected);
});
test("Plaid investments and other debts have the correct classification",()=>{
  assert.equal(normalizePlaidAccount({...raw,source_account_type:"investment",account_type:"brokerage"},institution,"2026-11-08")!.type,"investment");
  const debt=normalizePlaidAccount({...raw,source_account_type:"loan",account_type:"student",balance_kind:"liability"},institution,"2026-11-08")!;
  assert.equal(debt.type,"other_liability");
  assert.equal(debt.classification,"liability");
});
test("Unknown and non-USD balances stay out of USD portfolio totals",()=>{
  for(const change of [{balance:null},{currency:"CAD"},{balance_kind:"unknown" as const}])
    assert.equal(normalizePlaidAccount({...raw,...change},institution,"2026-11-08"),null);
});
test("Plaid credits and debits retain their direction and money values",()=>{
  const account=normalizePlaidAccount(raw,institution,"2026-11-08")!;
  const transaction=normalizePlaidTransaction({id:"tx-1",account_id:raw.id,transaction_date:"2026-11-07",description:"Income",merchant:null,category:"income",amount:"2500.00",direction:"credit"},account);
  assert.equal(transaction.category,"salary");
  assert.equal(transaction.amount,"2500.00");
  assert.equal(transaction.balanceEffect,"increase");
});
