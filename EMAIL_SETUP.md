# Verify your own email, then connect financial accounts

Capital Insight now has a personal-email sign-in flow. A user verifies an inbox they control before authorizing any financial connections. Do not use an SSN as a database identifier. No SSNs are collected or stored.

## Database and ownership

- `users.email` is normalized to lowercase and unique. It is the user's sign-in identity.
- `users.id` remains a stable UUID primary key for foreign-key relationships; changing an email must not break account ownership.
- `users.email_verified_at` records successful verification. Existing users are migrated as unverified and must verify their email before financial access.
- `email_challenges.email` is the primary key of the verification table. Codes are encrypted, expire in five minutes, allow five attempts, are single use, and have a 30-second resend cooldown.
- Institution and Plaid connections reference `users.id`; tokens remain encrypted server-side. The frontend adapter now restores mock connections from this same persisted ownership store after sign-in. Logout invalidates the related frontend session as well.
- Startup adds the new nullable columns and verification table without dropping users, financial connections, or transactions. The SQLAlchemy models work with local SQLite and the PostgreSQL Compose setup. Back up deployed databases before schema upgrades.

## Gmail SMTP setup

A personal Gmail account is suitable for this low-volume demo. Enable [2-Step Verification](https://myaccount.google.com/security), then create a [Google app password](https://myaccount.google.com/apppasswords). Some managed or protected accounts do not offer app passwords. See [Google's instructions](https://support.google.com/accounts/answer/185833) and [SMTP settings](https://developers.google.com/workspace/gmail/imap/imap-smtp).

From the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/setup_email.py
```

Open the private root `.env.mail` and set:

```dotenv
AUTH_CODE_DELIVERY=smtp
MOCK_EMAIL_RECIPIENT_MODE=customer
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=your-sender@gmail.com
SMTP_PASSWORD=your_google_app_password_without_spaces
SMTP_FROM=your-sender@gmail.com
# Not required in customer mode. Only forwarded_demo uses a shared key.
```

The normal sign-in flow sends to each user's entered email. With `MOCK_EMAIL_RECIPIENT_MODE=customer` (the default), each institution sends its own consent code to the customer email stored in its own database. `AUTH_EMAIL_RECIPIENT` and `MOCK_SERVICE_API_KEY` are unused in this mode. Never commit `.env.mail`, print passwords, or put these settings in NEXT_PUBLIC_ variables. The setup script preserves existing credentials and only generates a missing internal key.

## Run and sign in

Restart the core API and mock services after saving mail settings. Stop previous instances of this project's servers first. From the repository root, using the project's virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts/dev.py --api-port 8007 --web-port 3001
```

The alternate ports avoid the other project on this machine. On a free machine, omit those arguments for ports 8000 and 3000. The launcher starts six mock services plus the API and frontend, and writes logs in logs/. Docker Compose also passes root mail settings to the API and mock containers; recreate containers after configuration changes.

1. Open http://localhost:3001/sign-in.
2. Enter your own email address, such as your personal Gmail. Do not enter a seeded customerN@example.test address here.
3. Retrieve the six-digit sign-in code from your own inbox and verify it.
4. The app signs in or creates the unique user for that email and takes you to Connections.
5. Choose Plaid for a bank authorization, or a clearly labeled mock institution for fictional demo data.

### Local testing without SMTP (`AUTH_CODE_DELIVERY=log`, the default)

With no `.env.mail` (or `AUTH_CODE_DELIVERY=log`) and `ENVIRONMENT` not set to `production`, the core API sends no email. It logs `DEVELOPMENT ONLY Capital Insight sign-in code for <email>: <code>` at WARNING level, `scripts/dev.py` highlights it on the console like mock consent codes, and the sign-in page says to copy the code from the terminal. With `ENVIRONMENT=production`, log delivery is refused (503) and codes are never logged; production must use `smtp`.

Application endpoints:

- POST `/v1/auth/request-email-code` with `{ "email": "you@example.com" }`.
- POST `/v1/auth/verify-email-code` with `{ "email": "you@example.com", "code": "123456" }`, using the actual code.
- Verification returns the app token and user metadata including email_verified_at. The Next.js app stores the token only in an HTTP-only cookie.
- Existing password registration/login endpoints remain available, but an unverified account cannot link institutions, access financial connections, or use Plaid. Verify the same email to keep its existing UUID and password.

No personal-email sign-in code is exposed in API responses or logs. SMTP configuration is required for real sign-in; it never silently falls back to a shared recipient or visible fixture code. Missing credentials or rejected email sends return 503. A failed send rolls back the challenge so it can be retried.

## Bank authorization versus email identity

Email verification proves control of a Capital Insight sign-in inbox. It does not prove ownership of any bank account. Bank access is authorized separately through Plaid Link. Capital Insight does not collect bank passwords or SSNs.

The Connections page launches Plaid Link using the configured backend credentials. The public token is exchanged on the backend and the encrypted Item token is owned by the verified user. `/banks` displays their Plaid accounts. Plaid defaults to Sandbox: this links test institutions/data, not actual bank accounts. Real bank access requires approved/configured Plaid production credentials. See backend/CORE_API.md and [Plaid Link](https://plaid.com/docs/link/).

The mock bank/loan/mortgage services contain fictional customers. Enter the customer email registered in the selected institution database; provision your own address using the command below. Each institution emails that address itself, verifies the returned code against its own challenge, and issues its own bearer token. Capital Insight stores the returned token encrypted. The institution rejects recipient overrides in customer mode, including requests with an internal key. Fictional authorization does not connect a real financial institution. The old key-protected redirection remains available only by explicitly setting `MOCK_EMAIL_RECIPIENT_MODE=forwarded_demo` on both the backend and institution.

The HTTP-mode frontend uses verified sign-in. Fixture-only mode remains a separate labeled UI demonstration and never sends real email.

## Checks

Automated tests use temporary databases and mocked SMTP/HTTP providers. They cover email uniqueness, ownership verification, expiry, attempts, replay, delivery failures, legacy database upgrades, anonymous/unverified linking denial, shared user ownership across API interfaces, protected recipient forwarding, persistence, logout, and Plaid authorization. They do not send real emails or connect real banks. Real SMTP delivery still requires your credentials and a user-initiated sign-in request.
# Add your own email to the local mock institutions

After starting the services once to initialize their databases, run from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/add_demo_customer.py --email you@example.com
```

This adds your email to the four local bank databases, loan database, mortgage database, and configured core database. Financial records are copied from each institution's first synthetic seed customer with separate IDs and ownership. Names and birth dates remain fictional. Existing customers are preserved, and rerunning does not duplicate accounts. Backup and obsolete database files are excluded. This targets the local development stack, not Docker volumes or external bank accounts.

Sign in with that email, verify the emailed code, then enter the same email when connecting each mock institution. SMTP configuration is required; provisioning does not mark the email verified or send a message. Local database files are ignored by Git, so teammates must run the command themselves after pulling.

