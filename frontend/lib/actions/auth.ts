"use server";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { AUTH_COOKIE, ADAPTER_COOKIE, coreRequest, authToken } from "@/lib/auth";

export interface SignInState { step: "email" | "code"; email: string; message?: string; error?: string }
const read = (form: FormData, key: string, max: number) => String(form.get(key) ?? "").slice(0, max).trim();
async function errorMessage(response: Response) {
  const data = await response.json().catch(() => ({}));
  return typeof data.detail === "string" ? data.detail : "Please check the email and six-digit code.";
}

export async function signInAction(previous: SignInState, form: FormData): Promise<SignInState> {
  const intent = read(form, "intent", 16);
  const email = read(form, "email", 254).toLowerCase();
  if (intent === "restart") return {step:"email",email};
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return {...previous,error:"Enter your own email address."};
  try {
    if (intent === "request") {
      const response = await coreRequest("/v1/auth/request-email-code", {method:"POST",body:{email}});
      if (!response.ok) return {step:previous.step,email,error:await errorMessage(response)};
      return {step:"code",email,message:"Check your inbox for your Capital Insight sign-in code."};
    }
    if (intent !== "verify") return {...previous,error:"Choose an action."};
    const code = read(form,"code",6);
    const response = await coreRequest("/v1/auth/verify-email-code", {method:"POST",body:{email,code}});
    if (!response.ok) return {step:"code",email,error:await errorMessage(response)};
    const result = await response.json() as {access_token:string;expires_in:number};
    const session = await coreRequest("/api/v1/sessions", {method:"POST",token:result.access_token});
    if (!session.ok) return {step:"code",email,error:"Sign-in succeeded, but the connection session could not be created. Request a new code."};
    const {session_id} = await session.json() as {session_id:string};
    const jar = await cookies();
    const options = {httpOnly:true,sameSite:"lax" as const,secure:process.env.NODE_ENV === "production",path:"/",maxAge:result.expires_in};
    jar.set(AUTH_COOKIE,result.access_token,options);
    jar.set(ADAPTER_COOKIE,session_id,options);
  } catch {
    // Say what is wrong, so the user can fix it instead of retrying blindly.
    const base = process.env.BACKEND_API_URL;
    const error = !base
      ? "Sign-in needs the live backend: start the app with python scripts/dev.py (demo mode has no accounts)."
      : `Cannot reach the Capital Insight backend at ${base}. Is python scripts/dev.py running?`;
    return {step:previous.step,email,error};
  }
  redirect("/connect");
}

export async function signOutAction() {
  const token = await authToken();
  if (token) await coreRequest("/v1/auth/logout",{method:"POST",token});
  const jar = await cookies();
  jar.delete(AUTH_COOKIE);
  jar.delete(ADAPTER_COOKIE);
  redirect("/sign-in");
}
