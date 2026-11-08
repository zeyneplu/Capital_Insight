"use server";

import { redirect } from "next/navigation";
import { getDataProvider } from "@/lib/data";

/** Clears all session-local demo state (connections, applications, pending codes). */
export async function resetDemoAction(): Promise<void> {
  await getDataProvider().resetDemo();
  redirect("/");
}
