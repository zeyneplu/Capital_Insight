# Independent institution email verification

The default `MOCK_EMAIL_RECIPIENT_MODE=customer` supports separate servers. Each institution owns its customer database, email credentials, verification challenges, and token signing secret. Capital Insight does not need an institution's SMTP password or signing secret. No shared `MOCK_SERVICE_API_KEY` is required for this flow.

1. The user verifies their Capital Insight email to sign in to the app.
2. They choose an institution and enter the email registered at that institution.
3. The core calls the institution's `/v1/auth/request-code` over HTTPS with that email only.
4. The institution looks up its own customer and emails its own code to the stored customer address. Unknown customers receive the same generic API response but no email.
5. The user enters the code. The core forwards it to that institution's `/v1/auth/verify-code`.
6. The institution checks its stored code hash, expiry, attempts, and single-use state, then returns its own bearer token.
7. The core stores that token encrypted under the app user's connection and uses it to fetch institution data. The institution validates the bearer token on each protected request.

The app email and institution email may differ: authorization comes from completing that institution's challenge. Email verification is a simulated institution login here; actual banks must be connected through their supported authorization process, such as Plaid Link.

## Configure each server independently

Set these environment variables in each institution's hosting configuration, using that institution's own sender account:

```dotenv
AUTH_CODE_DELIVERY=smtp
MOCK_EMAIL_RECIPIENT_MODE=customer
DEMO_MODE=false
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=institution-sender@gmail.com
SMTP_FROM=institution-sender@gmail.com
SMTP_PASSWORD=that_senders_google_app_password
SMTP_TIMEOUT_SECONDS=10
```

Give each institution a separate persistent `DATABASE_URL`, institution ID (`BANK_ID` or `LENDER_ID`), and its own token signing secret (`SIGNING_SECRET`, or retain its database-generated secret). Maintain the customer's registered email in that institution database. There is no runtime database sharing or automatic synchronization with the core. The local provisioning script is only for local development data.

The core server needs its own SMTP configuration for app sign-in, `MOCK_EMAIL_RECIPIENT_MODE=customer`, its own database/encryption key, and the deployed HTTPS URLs:

```dotenv
CHASE_URL=https://chase.your-domain.example
AMEX_URL=https://amex.your-domain.example
PNC_URL=https://pnc.your-domain.example
DISCOVER_URL=https://discover.your-domain.example
LOANS_URL=https://loans.your-domain.example
MORTGAGES_URL=https://mortgages.your-domain.example
```

These hostnames are examples; replace them with deployed addresses. Set the frontend's server-only `BACKEND_API_URL` to the core URL. Restart or redeploy after configuration changes.

The shared root `.env.mail` is a local convenience. Separate deployments receive environment variables independently; no server reads a file from another server. For Docker, inject the same variable names into each container using its own deployment configuration.

`forwarded_demo` mode preserves the earlier shared-inbox demonstration. It requires explicitly configuring both parties and a shared key. Keep customer mode for independent institution verification.
