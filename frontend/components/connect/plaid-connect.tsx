"use client";
import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createPlaidLinkAction, exchangePlaidAction } from "@/lib/actions/plaid";
import { Alert, Button } from "@/components/ui/primitives";
interface LinkHandler { open:()=>void; destroy:()=>void }
declare global { interface Window { Plaid?: {create:(options:{token:string;onSuccess:(publicToken:string)=>void;onExit:(error:{display_message?:string}|null)=>void})=>LinkHandler} } }
export function PlaidConnect() {
  const [ready,setReady] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const handler = useRef<LinkHandler|null>(null);
  const router = useRouter();
  useEffect(()=>()=>handler.current?.destroy(),[]);
  async function open() {
    setBusy(true); setError("");
    const result = await createPlaidLinkAction();
    if (!result.ok) { setBusy(false); setError(result.error); return; }
    if (!window.Plaid) { setBusy(false);setError("Plaid did not load. Refresh and try again.");return; }
    handler.current?.destroy();
    handler.current = window.Plaid.create({token:result.linkToken,
      onSuccess:async publicToken=>{
        const saved = await exchangePlaidAction(publicToken);
        setBusy(false);
        if (!saved.ok) {setError(saved.error);return;}
        router.push("/banks");router.refresh();
      },
      onExit:err=>{setBusy(false);if(err)setError(err.display_message ?? "Bank linking was interrupted. Try again.");},
    });
    handler.current.open();
  }
  return <div className="space-y-3">
    <Script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js" strategy="afterInteractive" onReady={()=>setReady(true)} onError={()=>setError("Could not load Plaid. Check your connection and refresh.")}/>
    <Button type="button" onClick={open} disabled={!ready || busy}>{busy ? "Connecting..." : ready ? "Connect a bank with Plaid" : "Loading bank connection..."}</Button>
    {error ? <Alert tone="bad" role="alert">{error}</Alert> : null}
  </div>;
}
