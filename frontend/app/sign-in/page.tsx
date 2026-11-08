import { EmailSignIn } from "@/components/auth/email-sign-in";
import { Card, PageHeader } from "@/components/ui/primitives";
export const metadata = {title:"Sign in"};
export default function SignInPage() {
  return <><PageHeader title="Sign in with your email" description="Verify your own email first, then authorize the financial accounts you want to connect."/>
    <Card className="max-w-xl"><EmailSignIn/><p className="mt-5 text-xs text-muted">Your email identifies your Capital Insight account. We do not ask for or store your SSN. Email verification does not grant access to a bank; bank linking requires separate authorization.</p></Card></>;
}
