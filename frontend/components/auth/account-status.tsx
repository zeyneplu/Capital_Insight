import Link from "next/link";
import { currentAppUser } from "@/lib/auth";
import { signOutAction } from "@/lib/actions/auth";
import { dataSourceKind } from "@/lib/data";

/**
 * Header sign-in status. Accounts only exist in live mode (DATA_SOURCE=http),
 * so demo mode says so instead of offering a sign-in that cannot work.
 */
export async function AccountStatus() {
  if (dataSourceKind() !== "http") {
    return (
      <Link href="/sign-in" className="text-xs text-muted hover:text-text" title="Demo mode needs no account">
        Demo mode · no sign-in needed
      </Link>
    );
  }
  const user = await currentAppUser();
  if (!user?.email_verified_at) return <Link href="/sign-in" className="text-sm font-medium text-primary">Sign in</Link>;
  return <div className="flex items-center gap-3 text-xs"><span className="max-w-44 truncate" title={user.email}>{user.email}</span>
    <form action={signOutAction}><button type="submit" className="text-primary">Sign out</button></form></div>;
}
