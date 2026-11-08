import test from "node:test";
import assert from "node:assert/strict";
import {transactionOperations,pairedOperation} from "./transaction-operations.ts";

test("transaction controls match cash, card and principal-only loan products",()=>{
  assert.ok(transactionOperations("checking").includes("salary"));
  assert.ok(transactionOperations("savings").includes("transfer"));
  assert.ok(!transactionOperations("credit_card").includes("deposit"));
  assert.ok(transactionOperations("credit_card").includes("card_payment"));
  assert.deepEqual(transactionOperations("mortgage"),["loan_payment"]);
  assert.deepEqual(transactionOperations("ira"),[]);
  assert.deepEqual(transactionOperations("cd"),[]);
});
test("transfers and debt payments require another owned cash account",()=>{
  assert.ok(pairedOperation("transfer"));
  assert.ok(pairedOperation("card_payment"));
  assert.ok(pairedOperation("loan_payment"));
  assert.ok(!pairedOperation("salary"));
});
