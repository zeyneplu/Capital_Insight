import { ColumnChart } from "@/components/charts/bars";
import { Money } from "@/components/ui/money";
import { Pagination } from "@/components/ui/pagination";
import { Alert, Card, DetailList, StatTile, TextLink } from "@/components/ui/primitives";
import { groupScheduleByLoanYear, summarizeSchedule } from "@/lib/finance/amortization";
import { formatDate, formatInteger, formatMoney, formatRate, formatTerm } from "@/lib/format";
import type { Installment, LoanApplication, MortgageApplication } from "@/lib/types";

const ROWS_PER_PAGE = 12;

export function ScheduleView({
  application,
  rows,
  page,
  path,
}: {
  application: LoanApplication | MortgageApplication;
  rows: Installment[];
  page: number;
  path: string;
}) {
  const totals = summarizeSchedule(rows);
  const years = groupScheduleByLoanYear(rows);
  const pageCount = Math.ceil(rows.length / ROWS_PER_PAGE);
  const current = Math.min(page, pageCount);
  const visible = rows.slice((current - 1) * ROWS_PER_PAGE, current * ROWS_PER_PAGE);
  const servicing = application.servicing;
  const nextIndex = servicing?.nextDueDate ? rows.findIndex((row) => row.due_date === servicing.nextDueDate) : -1;
  const nextPage = nextIndex >= 0 ? Math.floor(nextIndex / ROWS_PER_PAGE) + 1 : null;

  return (
    <div className="space-y-6">
      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Monthly principal + interest" value={formatMoney(application.monthlyPayment)} hint={`${formatRate(application.apr)} APR, ${formatTerm(application.termMonths)}`} />
        <StatTile label="Amount financed" value={formatMoney(application.amount)} hint="Original amount, not a current balance" />
        <StatTile label="Total interest" value={formatMoney(totals.totalInterest)} hint={`Over ${formatInteger(rows.length)} payments`} />
        <StatTile label="Final payment" value={totals.finalDueDate ? formatDate(totals.finalDueDate) : "—"} hint={`Total paid ${formatMoney(totals.totalPayments)}`} />
      </dl>

      {servicing ? (
        <Alert tone="demo" title="Demo servicing snapshot">
          <p>
            As of {formatDate(servicing.asOf)}, this demo assumes {formatInteger(servicing.installmentsAssumedPaid)} scheduled{" "}
            {servicing.installmentsAssumedPaid === 1 ? "payment was" : "payments were"} made, leaving an estimated{" "}
            <Money value={servicing.estimatedOutstanding} className="font-semibold" /> of principal.{" "}
            {servicing.nextDueDate && servicing.nextPayment ? (
              <>
                Next installment {formatMoney(servicing.nextPayment)} on {formatDate(servicing.nextDueDate)}.
              </>
            ) : null}
          </p>
          <p className="mt-1 text-xs">The lender API reports the original amount and this projected schedule only, never a live balance or payment history.</p>
        </Alert>
      ) : null}

      <Card title="Principal and interest by loan year" description="Early payments are mostly interest; later payments are mostly principal.">
        <ColumnChart
          mode="stacked"
          caption="Principal and interest paid in each loan year"
          seriesA="Principal"
          seriesB="Interest"
          labelEvery={years.length > 12 ? 5 : 1}
          data={years.map((year) => ({
            key: String(year.loanYear),
            label: `Year ${year.loanYear}`,
            axisLabel: years.length > 12 ? `Y${year.loanYear}` : `Year ${year.loanYear}`,
            a: year.principal,
            b: year.interest,
            note: `Balance after: ${formatMoney(year.endingBalance)}`,
          }))}
        />
      </Card>

      <Card
        title="Projected repayment schedule"
        description={
          application.kind === "mortgage"
            ? "Principal and interest only. Excludes property taxes, insurance, PMI, escrow and closing costs."
            : "Scheduled principal and interest. This is a projection, not a record of payments."
        }
        action={nextPage && nextPage !== current ? <TextLink href={`${path}?page=${nextPage}`} scroll={false} className="text-sm">Jump to next installment</TextLink> : undefined}
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[34rem] text-right text-sm">
            <caption className="sr-only">
              Installments {visible[0]?.installment} to {visible.at(-1)?.installment} of {rows.length}
            </caption>
            <thead>
              <tr className="border-b border-border text-xs text-muted">
                <th scope="col" className="py-2 pr-3 text-left font-medium">#</th>
                <th scope="col" className="py-2 pr-3 text-left font-medium">Due date</th>
                <th scope="col" className="py-2 pr-3 font-medium">Payment</th>
                <th scope="col" className="py-2 pr-3 font-medium">Principal</th>
                <th scope="col" className="py-2 pr-3 font-medium">Interest</th>
                <th scope="col" className="py-2 font-medium">Remaining</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {visible.map((row) => {
                const isNext = row.due_date === servicing?.nextDueDate;
                return (
                  <tr key={row.installment} className={isNext ? "bg-primary-soft" : "border-b border-border last:border-0"}>
                    <th scope="row" className="py-2 pr-3 text-left font-normal text-muted">{row.installment}</th>
                    <td className="py-2 pr-3 text-left whitespace-nowrap">
                      {formatDate(row.due_date)}
                      {isNext ? <span className="ml-2 text-xs font-medium text-primary">Next</span> : null}
                    </td>
                    <td className="py-2 pr-3">{formatMoney(row.payment)}</td>
                    <td className="py-2 pr-3">{formatMoney(row.principal)}</td>
                    <td className="py-2 pr-3">{formatMoney(row.interest)}</td>
                    <td className="py-2">{formatMoney(row.remaining_balance)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="mt-4">
          <Pagination label="Schedule pages" path={path} params={{}} page={current} pageCount={pageCount} />
        </div>
      </Card>

      <Card title="Application details" headingLevel={2}>
        <DetailList
          items={[
            { label: "Lender", value: application.lender.name },
            { label: "Submitted", value: formatDate(application.createdAt) },
            application.kind === "mortgage" ? { label: "Property value", value: formatMoney(application.propertyValue) } : null,
            application.kind === "mortgage" ? { label: "Down payment", value: formatMoney(application.downPayment) } : null,
            application.kind === "mortgage" ? { label: "Loan-to-value", value: formatRate(application.loanToValue) } : null,
            { label: "Reported annual income", value: formatMoney(application.applicant.annualIncome) },
            { label: "Existing monthly debt", value: formatMoney(application.applicant.existingMonthlyDebt) },
            { label: "Credit score (self-reported)", value: String(application.applicant.creditScore) },
            { label: "Decision", value: application.decisionReason },
          ]}
        />
        <p className="mt-5 border-t border-border pt-3 font-mono text-[11px] text-muted break-all">
          Source: {application.source.service} · {application.source.institutionId} · {application.source.recordId}
        </p>
      </Card>
    </div>
  );
}
