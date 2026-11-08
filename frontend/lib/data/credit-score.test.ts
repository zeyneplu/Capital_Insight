import test from "node:test";
import assert from "node:assert/strict";
import { syntheticCreditScore, creditScoreLabel } from "./credit-score.ts";

test("credit scores match the independent Python service policy",()=>{
  assert.equal(syntheticCreditScore("alice@example.test"),762);
  assert.equal(syntheticCreditScore("test@example.com"),787);
  assert.equal(syntheticCreditScore("demo-user@capital-insight.example.test"),774);
  assert.equal(syntheticCreditScore(" Alice@Example.test "),762);
});
test("current demo credit scores are stable, bounded and not institution-specific",()=>{
  for(let i=0;i<100;i++) {
    const email=`person${i}@example.test`;
    assert.equal(syntheticCreditScore(email),syntheticCreditScore(email));
    assert.ok(syntheticCreditScore(email)>=300 && syntheticCreditScore(email)<=850);
  }
  assert.equal(creditScoreLabel(762),"Very good");
});
