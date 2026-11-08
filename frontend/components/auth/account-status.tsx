import Link from "next/link";
import { currentAppUser } from "@/lib/auth";
import { signOutAction } from "@/lib/actions/auth";
export async function AccountStatus() {
  const user = await currentAppUser();
  if (!user?.email_verified_at) return <Link href="/sign-in" className="text-sm font-medium text-primary">Sign in</Link>;
  return <div className="flex items-center gap-3 text-xs"><span className="max-w-44 truncate" title={user.email}>{user.email}</span>
    <form action={signOutAction}><button type="submit" className="text-primary">Sign out</button></form></div>;
}
