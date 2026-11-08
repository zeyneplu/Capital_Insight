import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { AccountCard } from "@/components/accounts/account-card";
import { Money } from "@/components/ui/money";
import { Alert, ButtonLink, EmptyState, LoadingBlock, PageHeader, Skeleton, TextLink, cx } from "@/components/ui/primitives";
import { getDataProvider } from "@/lib/data";
import { sumMoney } from "@/lib/finance/money";
import { ACCOUNT_TYPE_LABELS } from "@/lib/format";
import { firstParam, type SearchParams } from "@/lib/search-params";
import { ACCOUNT_TYPES, type Account, type AccountType } from "@/lib/types";

export const metadata: Metadata = { title: "Accounts" };

function TypeFilter({ accounts, active }: { accounts: Account[]; active: AccountType | undefined }) {
  const present = ACCOUNT_TYPES.filter((type) => accounts.some((account) => account.type === type));
  const chip = (selected: boolean) =>
    cx(
      "inline-flex min-h-9 items-center gap-1.5 rounded-full border px-3 text-sm font-medium",
      selected ? "border-primary bg-primary text-primary-contrast" : "border-border-strong bg-surface hover:bg-surface-muted",
    );
  return (
    <nav aria-label="Filter by account type" className="-mx-1 overflow-x-auto px-1 pb-1">
      <ul className="flex gap-2">
        <li>
          <Link href="/accounts" className={chip(!active)} aria-current={!active ? "page" : undefined}>
            All <span className="tabular-nums opacity-80">{accounts.length}</span>
          </Link>
        </li>
        {present.map((type) => (
          <li key={type}>
            <Link href={`/accounts?type=${type}`} className={chip(active === type)} aria-current={active === type ? "page" : undefined}>
              {ACCOUNT_TYPE_LABELS[type]}{" "}
              <span className="tabular-nums opacity-80">{accounts.filter((account) => account.type === type).length}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

async function AccountsContent({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const rawType = firstParam(params, "type");
  const accounts = await getDataProvider().listAccounts();

  if (accounts.length === 0) {
    return (
      <EmptyState
        title="No bank accounts connected"
        description="Connect a mock bank to see its accounts here."
        action={<ButtonLink href="/connect">Connect an institution</ButtonLink>}
      />
    );
  }

  const validType = rawType === undefined || (ACCOUNT_TYPES as readonly string[]).includes(rawType);
  const type = validType ? (rawType as AccountType | undefined) : undefined;
  const visible = type ? accounts.filter((account) => account.type === type) : accounts;
  const institutions = [...new Map(visible.map((account) => [account.institution.id, account.institution])).values()];

  return (
    <div className="space-y-6">
      <TypeFilter accounts={accounts} active={type} />
      {!validType ? (
        <Alert tone="warn" role="alert" title="Unknown account type">
          “{rawType}” is not a supported account type. Showing all accounts instead. <TextLink href="/accounts">Clear filter</TextLink>
        </Alert>
      ) : null}
      {visible.length === 0 ? (
        <EmptyState
          title={`No ${ACCOUNT_TYPE_LABELS[type!].toLowerCase()} accounts`}
          description="None of your connected institutions report this account type."
          action={<ButtonLink href="/accounts" variant="secondary">Show all accounts</ButtonLink>}
        />
      ) : (
        institutions.map((institution) => {
          const own = visible.filter((account) => account.institution.id === institution.id);
          const assets = own.filter((account) => account.classification === "asset");
          const liabilities = own.filter((account) => account.classification === "liability");
          return (
            <section key={institution.id} aria-labelledby={`institution-${institution.id}`}>
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                <h2 id={`institution-${institution.id}`} className="text-lg font-semibold">
                  {institution.name}
                </h2>
                <p className="text-xs text-muted">
                  {assets.length ? (
                    <>
                      Balances <Money value={sumMoney(assets.map((a) => a.balance))} />
                    </>
                  ) : null}
                  {assets.length && liabilities.length ? " · " : null}
                  {liabilities.length ? (
                    <>
                      Owed <Money value={sumMoney(liabilities.map((a) => a.balance))} />
                    </>
                  ) : null}
                </p>
              </div>
              <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {own.map((account) => (
                  <li key={account.id}>
                    <AccountCard account={account} />
                  </li>
                ))}
              </ul>
            </section>
          );
        })
      )}
    </div>
  );
}

function AccountsSkeleton() {
  return (
    <LoadingBlock label="Loading accounts">
      <div className="space-y-6">
        <Skeleton className="h-9 w-80 max-w-full" />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((key) => (
            <Skeleton key={key} className="h-40" />
          ))}
        </div>
      </div>
    </LoadingBlock>
  );
}

export default function AccountsPage({ searchParams }: PageProps<"/accounts">) {
  return (
    <>
      <PageHeader
        title="Accounts"
        description="Every account from your connected banks. Open a mock account to simulate deposits, purchases, transfers and payments."
        actions={<ButtonLink href="/connect" variant="secondary">Connect more</ButtonLink>}
      />
      <Suspense fallback={<AccountsSkeleton />}>
        <AccountsContent searchParams={searchParams} />
      </Suspense>
    </>
  );
}
