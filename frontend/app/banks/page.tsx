import { Suspense } from "react";
import { authToken, coreRequest, requireVerifiedUser } from "@/lib/auth";
import { VerifiedConnections } from "@/components/connect/verified-connections";
import { PlaidRefresh } from "@/components/connect/plaid-refresh";
import { Alert, Card, PageHeader } from "@/components/ui/primitives";
export const metadata = {title:"Linked banks"};
interface BankAccount { id:string;account_name:string;account_type:string;currency:string|null;balance:string|null;provider:string }
async function BankAccounts() {
  await requireVerifiedUser();
  const token = await authToken();
  const response = await coreRequest("/v1/connections",{token});
  if (!response.ok) return <Alert tone="bad">Could not load saved bank connections. Try again.</Alert>;
  const links = (await response.json() as {id:string;kind:string}[]).filter(link=>link.kind === "plaid");
  const results = await Promise.all(links.map(async link => {
    try {
      const result = await coreRequest(`/v1/plaid/connections/${encodeURIComponent(link.id)}/accounts`,{token});
      return {accounts:result.ok ? await result.json() as BankAccount[] : [],failed:!result.ok};
    } catch { return {accounts:[] as BankAccount[],failed:true}; }
  }));
  const accounts = results.flatMap(result=>result.accounts);
  return <div className="space-y-4"><VerifiedConnections/>
    {links.length ? <><p>{links.length} saved Plaid connection(s), {accounts.length} account(s) returned.</p><PlaidRefresh/><p className="text-xs text-muted">Overview and Accounts include USD accounts with known balances. This page shows every Plaid account, including other currencies and unavailable balances.</p></> : null}
    {results.some(result=>result.failed) ? <Alert tone="warn">A saved Plaid connection could not return accounts. Refresh or reconnect it; your other connections are retained.</Alert> : null}
    {accounts.length === 0 ? <Alert tone="info">{links.length ? "Your Plaid connection is saved, but no accounts are available yet. Refresh to try again." : "No Plaid bank accounts are linked yet. Connect a bank above to authorize access."}</Alert> : <div className="grid gap-3 sm:grid-cols-2">{accounts.map(account=><Card key={account.id}><h2 className="font-semibold">{account.account_name}</h2><p className="text-sm text-muted">{account.account_type.replaceAll("_"," ")}</p><p className="mt-2 font-mono">{account.balance === null ? "Balance unavailable" : `${account.currency ?? ""} ${account.balance}`}</p></Card>)}</div>}
  </div>;
}
export default function BanksPage() { return <><PageHeader title="Your linked banks" description="Accounts authorized through Plaid and owned by your verified Capital Insight identity."/><Suspense fallback={<p>Loading your bank accounts...</p>}><BankAccounts/></Suspense></>; }
