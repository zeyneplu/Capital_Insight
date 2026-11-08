"use server";
import { authToken, coreRequest, requireVerifiedUser } from "@/lib/auth";
import { revalidatePath } from "next/cache";
async function plaidError(response: Response) {
  const data = await response.json().catch(()=>({}));
  return typeof data.detail === "string" ? data.detail : "Bank linking failed. Please try again.";
}
export async function createPlaidLinkAction(): Promise<{ok:true;linkToken:string}|{ok:false;error:string}> {
  await requireVerifiedUser();
  try {
    const response = await coreRequest("/v1/plaid/link-token",{method:"POST",token:await authToken()});
    if (!response.ok) return {ok:false,error:await plaidError(response)};
    const data = await response.json() as {link_token:string};
    return {ok:true,linkToken:data.link_token};
  } catch { return {ok:false,error:"The bank-linking service is unavailable."}; }
}
export async function exchangePlaidAction(publicToken: string): Promise<{ok:true}|{ok:false;error:string}> {
  await requireVerifiedUser();
  if (!publicToken || publicToken.length > 2048) return {ok:false,error:"Invalid bank authorization token."};
  try {
    const response = await coreRequest("/v1/plaid/exchange-public-token",{method:"POST",body:{public_token:publicToken},token:await authToken()});
    if (!response.ok) return {ok:false,error:await plaidError(response)};
    const saved = await response.json() as {id:string};
    // The Item is saved even when Plaid is still preparing transaction history.
    await coreRequest(`/v1/plaid/connections/${encodeURIComponent(saved.id)}/sync`, {
      method:"POST", token:await authToken(),
    }).catch(()=>undefined);
    revalidatePath("/banks");
    revalidatePath("/connect");
    revalidatePath("/", "layout");
    return {ok:true};
  } catch { return {ok:false,error:"Could not save the bank connection. Please try again."}; }
}

export async function refreshPlaidAction(): Promise<{message?:string;error?:string}> {
  await requireVerifiedUser();
  const token = await authToken();
  try {
    const response = await coreRequest("/v1/connections", {token});
    if (!response.ok) return {error:"Could not load saved bank connections."};
    const links = (await response.json() as {id:string;kind:string}[]).filter(link => link.kind === "plaid");
    const results = await Promise.all(links.map(link => coreRequest(`/v1/plaid/connections/${encodeURIComponent(link.id)}/sync`, {method:"POST",token})));
    revalidatePath("/", "layout");
    if (results.some(result => !result.ok)) return {error:"Accounts were refreshed, but some transaction history is not ready or requires reconnection. Try again shortly."};
    return {message:"Bank data refreshed. Newly linked transaction history may take a little time to become available."};
  } catch { return {error:"Could not refresh bank data. Your saved connections are unchanged."}; }
}
