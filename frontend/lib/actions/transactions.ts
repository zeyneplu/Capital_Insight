"use server";
import { randomUUID } from "node:crypto";
import { revalidatePath } from "next/cache";
import { requireVerifiedUser } from "@/lib/auth";
import { dataSourceKind, getDataProvider } from "@/lib/data";
import type { TransactionInput } from "@/lib/types";

export interface TransactionFormState { requestId:string; message?:string; error?:string; values?:Record<string,string> }

export async function postTransactionAction(previous: TransactionFormState, form: FormData): Promise<TransactionFormState> {
  if (dataSourceKind() !== "http") return {...previous,error:"Use the live mock services to simulate transactions."};
  await requireVerifiedUser();
  const read = (key:string,max:number) => String(form.get(key) ?? "").slice(0,max).trim();
  const input: TransactionInput = {
    request_id:read("request_id",64), operation:read("operation",24) as TransactionInput["operation"],
    amount:read("amount",32),
    ...(read("counterparty_account_id",128) ? {counterparty_account_id:read("counterparty_account_id",128)} : {}),
    ...(read("category",32) ? {category:read("category",32)} : {}),
    ...(read("merchant",120) ? {merchant:read("merchant",120)} : {}),
    ...(read("description",200) ? {description:read("description",200)} : {}),
  };
  const values = Object.fromEntries(Object.entries(input).map(([key,value])=>[key,String(value)]));
  try {
    const result = await getDataProvider().postTransaction(read("account_id",128),input);
    if (!result.ok) return {requestId:previous.requestId,error:result.message,values};
    revalidatePath("/", "layout");
    return {requestId:randomUUID(),message:result.replayed ? "This transaction was already recorded; no duplicate was created." : "Simulated transaction recorded. Balances and history are updated."};
  } catch { return {requestId:previous.requestId,error:"Could not confirm this transaction. Retry without changing its fields; the same request cannot be posted twice.",values}; }
}
