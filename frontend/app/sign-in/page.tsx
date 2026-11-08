import { EmailSignIn } from "@/components/auth/email-sign-in";
import { Alert, ButtonLink, Card, PageHeader } from "@/components/ui/primitives";
import { dataSourceKind } from "@/lib/data";

export const metadata = { title: "Sign in" };

export default function SignInPage() {
  if (dataSourceKind() !== "http") {
    return (
      <>
        <PageHeader title="Sign in" description="Accounts exist only when the app runs against the Capital Insight backend." />
        <Card className="max-w-xl">
          <Alert tone="demo" title="You are in demo mode">
            <p>Everything here uses fictional demo data, so no account is needed. Connect banks on the Connections page with the demo code 424242.</p>
            <p className="mt-2">
              To sign in with your email, start the live stack from the project folder with{" "}
              <code className="font-mono">python scripts/dev.py</code>. Email codes also need Gmail SMTP set up (see EMAIL_SETUP.md).
            </p>
          </Alert>
          <div className="mt-4 flex gap-2">
            <ButtonLink href="/">Go to overview</ButtonLink>
            <ButtonLink href="/connect" variant="secondary">Connect demo banks</ButtonLink>
          </div>
        </Card>
      </>
    );
  }
  return <><PageHeader title="Sign in with your email" description="Verify your own email first, then authorize the financial accounts you want to connect."/>
    <Card className="max-w-xl"><EmailSignIn/><p className="mt-5 text-xs text-muted">Your email identifies your Capital Insight account. We do not ask for or store your SSN. Email verification does not grant access to a bank; bank linking requires separate authorization.</p></Card></>;
}
