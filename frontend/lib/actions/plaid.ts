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
    revalidatePath("/banks");
    revalidatePath("/connect");
    return {ok:true};
  } catch { return {ok:false,error:"Could not save the bank connection. Please try again."}; }
}
