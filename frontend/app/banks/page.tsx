import { Suspense } from "react";
import { authToken, coreRequest, requireVerifiedUser } from "@/lib/auth";
import { VerifiedConnections } from "@/components/connect/verified-connections";
import { Alert, Card, PageHeader } from "@/components/ui/primitives";
export const metadata = {title:"Linked banks"};
interface BankAccount { id:string;account_name:string;account_type:string;currency:string|null;balance:string|null;provider:string }
async function BankAccounts() {
  await requireVerifiedUser();
  const response = await coreRequest("/v1/accounts",{token:await authToken()});
  if (!response.ok) return <Alert tone="bad">Could not load linked bank accounts. Try again.</Alert>;
  const data = await response.json() as {items:BankAccount[];complete:boolean;errors:unknown[]};
  const accounts = data.items.filter(account=>account.provider === "plaid");
  return <div className="space-y-4"><VerifiedConnections/>
    {!data.complete ? <Alert tone="warn">Some providers could not be reached. The accounts shown may be incomplete.</Alert> : null}
    {accounts.length === 0 ? <Alert tone="info">No Plaid bank accounts are linked yet. Connect a bank above to authorize access.</Alert> : <div className="grid gap-3 sm:grid-cols-2">{accounts.map(account=><Card key={account.id}><h2 className="font-semibold">{account.account_name}</h2><p className="text-sm text-muted">{account.account_type.replaceAll("_"," ")}</p><p className="mt-2 font-mono">{account.balance === null ? "Balance unavailable" : `${account.currency ?? ""} ${account.balance}`}</p></Card>)}</div>}
  </div>;
}
export default function BanksPage() { return <><PageHeader title="Your linked banks" description="Accounts authorized through Plaid and owned by your verified Capital Insight identity."/><Suspense fallback={<p>Loading your bank accounts...</p>}><BankAccounts/></Suspense></>; }
