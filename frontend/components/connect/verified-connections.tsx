import { currentAppUser } from "@/lib/auth";
import { Alert, ButtonLink, Card } from "@/components/ui/primitives";
import { PlaidConnect } from "./plaid-connect";
export async function VerifiedConnections() {
  const user = await currentAppUser();
  if (!user?.email_verified_at) return <Alert tone="info" title="Verify your email first"><p className="mb-3">Sign in with your own email before linking banks, loans, or mortgages.</p><ButtonLink href="/sign-in">Verify my email</ButtonLink></Alert>;
  return <Card className="space-y-3"><h2 className="font-semibold">Connect your bank</h2><p className="text-sm">Signed in as <strong>{user.email}</strong>. Bank authorization happens through Plaid; Capital Insight does not ask for your bank password or SSN.</p>
    <PlaidConnect/><ButtonLink href="/banks" variant="secondary">View linked bank accounts</ButtonLink>
    <p className="text-xs text-muted">Plaid defaults to Sandbox with test accounts. Real bank connections require configured Plaid production access. The mock institutions below contain fictional demo records.</p></Card>;
}
