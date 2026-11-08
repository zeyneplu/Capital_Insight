# Simulated bank transactions

Open **Accounts**, select a connected mock-bank account, and use **Simulate a transaction**. These actions update fictional records only. They do not send money, charge a card, contact an employer, or affect a real credit report.

| Account | Actions |
| --- | --- |
| Checking / savings | Deposit, salary/paycheck, purchase, bill payment, cash withdrawal, refund, transfer, interest received, fee |
| Credit card | Purchase, card payment, refund, fee, interest charge |
| Personal / auto / mortgage bank-loan account | Principal-only loan payment |
| CD, IRA, other investment, Plaid account | No simulated postings |

For a transfer, select the source cash account first and choose another checking/savings destination. For a card or loan payment, select the debt account first and choose the checking/savings account to fund it. Both accounts must belong to the same consenting customer, institution, and currency. Cross-bank and third-party transfers are not supported.

Cash credits increase assets; cash debits decrease assets. Liability debits increase the amount owed, and liability credits decrease it. Transfers and debt payments write two transaction rows and update both balances in one database transaction. Loan `outstanding_principal` is updated with its balance. Credit-card minimum-payment previews are refreshed. Payments cannot exceed the amount owed; cash accounts cannot overdraw and card charges cannot exceed their credit limit.

The current mock-loan and mock-mortgage services expose application decisions and projected schedules, not live loan servicing. Bank-account principal payments do not rewrite those separate application schedules, interest, taxes, insurance, or escrow. Historical application credit scores and the current synthetic credit profile are unchanged.

## API

Institution endpoint: `POST /v1/accounts/{account_id}/transactions` with the customer's institution bearer token.

Core frontend endpoint: `POST /api/v1/accounts/{raw_account_id}/transactions` with a verified app bearer and/or its bound adapter session. Core persistent endpoint: `POST /v1/accounts/{composite_account_id}/transactions` with a verified app bearer. The persistent endpoint accepts a counterparty composite ID from the same connection, or its raw upstream account ID.

```json
{
  "request_id": "b9411be8-2a4b-49e3-b86f-cf4894f27866",
  "operation": "salary",
  "amount": "2500.00",
  "merchant": "Example Employer",
  "description": "Demo monthly paycheck"
}
```

For `transfer`, `card_payment`, or `loan_payment`, include `counterparty_account_id`. For purchases, refunds, and bill payments, an optional spending `category` may be included. Other operation categories are derived by the server: salary, transfers, debt_payment, or other. Amounts must be positive, at most 1,000,000.00, with no fractional cents. Postings use the current UTC date and timestamp; backdating is not supported.

The response is `201` with `posting_id`, `transactions`, `simulated: true`, and `replayed`. Retrying the same customer/request ID and normalized payload returns the original posting without applying it again. Reusing that request ID for different data returns `409`. Idempotency records are persisted and survive restarts. SQLite `BEGIN IMMEDIATE` serializes posting checks and writes across processes. Every balance change and ledger row commits or rolls back together.

Unauthorized accounts return `404`; invalid action/product combinations return `422`; insufficient funds, overpayments, credit-limit violations, and conflicting request IDs return `409`. The frontend disables pending submissions, keeps a request ID across retries, and refreshes balances, history, and dashboard data after success.

Startup creates the new `postings` table without dropping or reseeding existing records. Fixture mode stays read-only; use the HTTP mock services for these actions. Plaid Link continues to provide read-only account and transaction imports, with no payment initiation added.
