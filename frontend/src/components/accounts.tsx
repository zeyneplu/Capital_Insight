import type { SWRResponse } from "swr";

import type { ApiError, Schemas } from "@/lib/api";
import { accountTypeLabel, formatMoney, formatMoneyWhole } from "@/lib/format";

import { Empty, ErrorNotice, Skeleton } from "./states";

type Account = Schemas["Account"];
const DEBT_TYPES = new Set<Account["type"]>(["credit_card", "loan", "mortgage"]);

function groupByBank(accounts: Account[]): [string, Account[]][] {
  const groups = new Map<string, Account[]>();
  for (const account of accounts) {
    groups.set(account.institution, [...(groups.get(account.institution) ?? []), account]);
  }
  return [...groups.entries()];
}

function AccountRow({ account }: { account: Account }) {
  const isDebt = DEBT_TYPES.has(account.type);
  const limit = account.credit_limit;
  return (
    <li className="grid grid-cols-[1fr_auto] gap-x-6 py-3">
      <div>
        <p className="font-medium">{account.nickname}</p>
        <p className="text-sm text-ink-3">{accountTypeLabel(account.type)}</p>
      </div>
      <div className="text-right">
        <p className="font-semibold">{formatMoney(account.balance)}</p>
        <p className="text-sm text-ink-3">
          {isDebt ? (limit ? `owed of ${formatMoneyWhole(limit)} limit` : "owed") : "available"}
        </p>
        {limit && (
          // Visual meter only; the exact utilization comes from the backend's report.
          <span className="mt-1.5 ml-auto block h-1.5 w-28 rounded-full bg-accent-soft" aria-hidden="true">
            <span
              className="block h-full rounded-full bg-accent"
              style={{ width: `${Math.min((Number(account.balance) / Number(limit)) * 100, 100)}%` }}
            />
          </span>
        )}
      </div>
    </li>
  );
}

export function Accounts({ profile }: { profile: SWRResponse<Schemas["FinancialProfile"], ApiError> }) {
  return (
    <section aria-labelledby="accounts-heading">
      <h2 id="accounts-heading" className="text-xl font-semibold">
        Accounts
      </h2>
      <div className="mt-4">
        {profile.error ? (
          <ErrorNotice error={profile.error} onRetry={() => void profile.mutate()} />
        ) : !profile.data ? (
          <Skeleton lines={3} />
        ) : profile.data.accounts.length === 0 ? (
          <Empty>No accounts yet. Connect a bank to get started.</Empty>
        ) : (
          <div className="grid gap-x-12 gap-y-8 md:grid-cols-2">
            {groupByBank([...profile.data.accounts]).map(([bank, accounts]) => (
              <div key={bank}>
                <h3 className="text-sm font-semibold text-ink-2">{bank}</h3>
                <ul className="mt-1 divide-y divide-line border-y border-line">
                  {accounts.map((a) => (
                    <AccountRow key={a.id} account={a} />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
