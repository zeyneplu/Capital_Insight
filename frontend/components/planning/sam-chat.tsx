"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Alert, Badge, Button, Card, cx } from "@/components/ui/primitives";
import { askSamAction, clearSamAction, savePreferencesAction } from "@/lib/actions/planning";
import { formatMoney } from "@/lib/format";
import type { PlanningOverview, SamAnswer, SamTurn } from "@/lib/planning-types";

const TOPICS = [
  { label: "Subscriptions check", color: "#a78bfa", prompt: "Review my possible recurring charges and subscriptions. Which ones should I double-check?" },
  { label: "Am I overspending?", color: "#fb7185", prompt: "Am I overspending compared with my income? Where could I cut back first?" },
  { label: "Raise my credit score", color: "#fbbf24", prompt: "How can I improve my credit score over the next 8 months? What utilization and monthly payments should I target?" },
  { label: "Buy a new car?", color: "#38bdf8", prompt: "Would it be a smart decision for me to buy a new car right now?" },
  { label: "Save for retirement", color: "#34d399", prompt: "How should I think about saving for retirement given my current cash flow?" },
  { label: "Pay for college", color: "#818cf8", prompt: "Help me plan to save for my undergraduate education." },
  { label: "Emergency fund", color: "#f472b6", prompt: "How big should my emergency fund be and how fast can I build it?" },
  { label: "Investing vs. debt", color: "#2dd4bf", prompt: "Should I invest extra money or pay down my debt first?" },
];

interface Message { id: string; question: string; answer: SamAnswer | null; pending?: boolean }

function SamAvatar({ size = "md" }: { size?: "sm" | "md" }) {
  return (
    <span
      aria-hidden="true"
      className={cx(
        "grid shrink-0 place-items-center rounded-full bg-gradient-to-br from-sky-400 via-indigo-500 to-violet-500 font-bold text-white shadow-md",
        size === "sm" ? "size-8 text-xs" : "size-12 text-base",
      )}
    >
      S
    </span>
  );
}

function Answer({ answer, onAsk, disabled }: { answer: SamAnswer; onAsk: (text: string) => void; disabled: boolean }) {
  if (!answer.allowed) {
    return (
      <div className="rounded-2xl rounded-tl-sm border border-border bg-surface-muted p-4 text-sm text-muted">
        <p>{answer.answer}</p>
      </div>
    );
  }
  return (
    <div className="space-y-3 rounded-2xl rounded-tl-sm border border-primary/20 bg-surface p-4 text-sm shadow-sm">
      <p className="whitespace-pre-wrap leading-relaxed">{answer.answer}</p>
      {answer.steps.length ? (
        <ol className="space-y-2">
          {answer.steps.map((step, index) => (
            <li key={index} className="flex gap-3">
              <span className="grid size-6 shrink-0 place-items-center rounded-full bg-primary-soft text-xs font-semibold text-primary">{index + 1}</span>
              <span className="pt-0.5">{step}</span>
            </li>
          ))}
        </ol>
      ) : null}
      {answer.questions.length ? (
        <div className="flex flex-wrap gap-2 pt-1">
          {answer.questions.map((question) => (
            <button
              key={question}
              type="button"
              disabled={disabled}
              onClick={() => onAsk(question)}
              className="rounded-full border border-primary/30 px-3 py-1 text-xs font-medium text-primary hover:bg-primary-soft disabled:opacity-50"
            >
              {question}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function SamChat({ overview, history, initialPrompt }: { overview: PlanningOverview; history: SamTurn[]; initialPrompt: string }) {
  const [prefs, setPrefs] = useState(overview.preferences);
  const [messages, setMessages] = useState<Message[]>(history.map((turn) => ({ id: turn.id, question: turn.message, answer: turn.response })));
  const [input, setInput] = useState(initialPrompt);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const ready = prefs.ai_enabled && overview.ai_configured;
  const { snapshot } = overview;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages]);

  async function ask(text: string) {
    const question = text.trim();
    if (!question || busy || !ready) return;
    const id = crypto.randomUUID();
    setBusy(true);
    setError("");
    setInput("");
    setMessages((old) => [...old, { id, question, answer: null, pending: true }]);
    const result = await askSamAction(question, id);
    if (result.ok) {
      setMessages((old) => old.map((message) => (message.id === id ? { ...message, answer: result.data, pending: false } : message)));
    } else {
      setMessages((old) => old.filter((message) => message.id !== id));
      setInput(question);
      setError(result.error);
    }
    setBusy(false);
    inputRef.current?.focus();
  }

  async function enable() {
    setBusy(true);
    setError("");
    const next = { ...prefs, ai_enabled: true };
    const result = await savePreferencesAction(next);
    if (result.ok) setPrefs(next);
    else setError(result.error);
    setBusy(false);
  }

  async function clear() {
    setBusy(true);
    const result = await clearSamAction();
    if (result.ok) setMessages([]);
    else setError(result.error);
    setBusy(false);
  }

  const facts = [
    { label: "Available cash", value: formatMoney(snapshot.totals.liquid_cash), color: "#38bdf8" },
    { label: "Total debt", value: formatMoney(snapshot.totals.debt), color: "#fb7185" },
    { label: "Monthly room", value: snapshot.cash_flow.monthly_free_cash == null ? "Need more history" : formatMoney(snapshot.cash_flow.monthly_free_cash), color: "#34d399" },
    { label: "Card utilization", value: snapshot.totals.utilization_pct == null ? "Unavailable" : `${snapshot.totals.utilization_pct}%`, color: "#fbbf24" },
    { label: "Synthetic credit score", value: snapshot.credit_score ? String(snapshot.credit_score.score) : "Unavailable", color: "#a78bfa" },
  ];

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
      <section aria-label="Conversation with Sam" className="flex min-h-[32rem] flex-col overflow-hidden rounded-2xl border border-border bg-surface">
        <header className="flex items-center gap-3 bg-gradient-to-r from-slate-950 via-blue-950 to-indigo-950 px-5 py-4 text-white">
          <SamAvatar />
          <div className="min-w-0 flex-1">
            <h2 className="font-semibold">Sam</h2>
            <p className="text-xs text-blue-200">
              {ready ? `Personal-finance assistant · ${overview.model.replace(/^nvidia\//, "")}` : "Personal-finance assistant · setup needed"}
            </p>
          </div>
          {messages.length ? (
            <Button variant="ghost" size="sm" onClick={() => void clear()} disabled={busy} className="text-blue-100 hover:bg-white/10">
              Clear chat
            </Button>
          ) : null}
        </header>

        <div className="flex-1 space-y-5 overflow-y-auto p-4 sm:p-5" aria-live="polite">
          {!overview.ai_configured ? (
            <Alert tone="info" title="Sam is almost ready">
              The backend needs an NVIDIA API key. Add <code>NVIDIA_API_KEY</code> to <code>backend/.env</code> and restart the core API. Goals and forecasts already work on the{" "}
              <Link href="/planning" className="font-medium text-primary underline">Plan & goals</Link> page.
            </Alert>
          ) : !prefs.ai_enabled ? (
            <div className="rounded-2xl border border-primary/30 bg-primary-soft p-5">
              <h3 className="font-semibold">Let Sam see your financial summary?</h3>
              <p className="mt-2 text-sm text-muted">
                Sam sends NVIDIA a summary of your balances, APRs, credit limits, spending categories and saved goals so answers fit your situation. Account numbers, credentials, your email and merchant names are left out. You can turn this off anytime in Plan & goals → Customize.
              </p>
              <Button className="mt-4" onClick={() => void enable()} disabled={busy}>
                Allow and start chatting
              </Button>
            </div>
          ) : messages.length === 0 ? (
            <div className="flex gap-3">
              <SamAvatar size="sm" />
              <div className="rounded-2xl rounded-tl-sm border border-primary/20 bg-surface p-4 text-sm shadow-sm">
                <p>Hi, I’m Sam. I can walk you through budgeting, subscriptions, debt, credit habits and saving goals, using the accounts you’ve linked. Pick a topic or ask me anything about your money.</p>
              </div>
            </div>
          ) : null}

          {messages.map((message) => (
            <div key={message.id} className="space-y-3">
              <div className="flex justify-end">
                <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-tr-sm bg-primary px-4 py-2.5 text-sm text-primary-contrast">{message.question}</p>
              </div>
              <div className="flex gap-3">
                <SamAvatar size="sm" />
                <div className="min-w-0 max-w-[90%] flex-1">
                  {message.pending ? (
                    <div className="inline-flex items-center gap-1.5 rounded-2xl rounded-tl-sm border border-border bg-surface px-4 py-3" role="status">
                      <span className="sr-only">Sam is thinking</span>
                      {[0, 150, 300].map((delay) => (
                        <span key={delay} aria-hidden="true" className="size-2 animate-bounce rounded-full bg-primary" style={{ animationDelay: `${delay}ms` }} />
                      ))}
                    </div>
                  ) : message.answer ? (
                    <Answer answer={message.answer} onAsk={(text) => void ask(text)} disabled={busy || !ready} />
                  ) : (
                    <p className="text-sm text-muted">No answer was saved for this question.</p>
                  )}
                </div>
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>

        {ready ? (
          <div className="flex gap-2 overflow-x-auto border-t border-border px-4 py-3" aria-label="Suggested topics">
            {TOPICS.map((topic) => (
              <button
                key={topic.label}
                type="button"
                disabled={busy}
                onClick={() => void ask(topic.prompt)}
                className="shrink-0 rounded-full border px-3 py-1.5 text-xs font-semibold transition hover:-translate-y-0.5 disabled:opacity-50"
                style={{ borderColor: topic.color + "66", color: topic.color, backgroundColor: topic.color + "14" }}
              >
                {topic.label}
              </button>
            ))}
          </div>
        ) : null}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void ask(input);
          }}
          className="border-t border-border p-3 sm:p-4"
        >
          {error ? (
            <Alert tone="bad" role="alert" className="mb-3">
              {error}
            </Alert>
          ) : null}
          <div className="flex items-end gap-2">
            <label htmlFor="sam-input" className="sr-only">
              Ask Sam a personal-finance question
            </label>
            <textarea
              id="sam-input"
              ref={inputRef}
              value={input}
              maxLength={2000}
              rows={2}
              disabled={!ready || busy}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void ask(input);
                }
              }}
              placeholder={ready ? "e.g. Would it be smart to buy a new car?" : "Sam is not enabled yet"}
              className="min-h-11 flex-1 resize-none rounded-xl border border-border-strong bg-background px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-primary disabled:opacity-60"
            />
            <Button type="submit" disabled={!ready || busy || !input.trim()}>
              {busy ? "Sending…" : "Send"}
            </Button>
          </div>
          <p className="mt-2 text-xs text-muted">
            Sam answers personal-finance questions only and gives education, not licensed advice. It can’t move money, cancel subscriptions or guarantee a score or return. Don’t share account numbers or passwords.
          </p>
        </form>
      </section>

      <aside className="space-y-4">
        <Card title="What Sam sees" description={`Aggregated summary as of ${snapshot.as_of}.`}>
          <dl className="space-y-3">
            {facts.map((fact) => (
              <div key={fact.label} className="flex items-center justify-between gap-3">
                <dt className="flex items-center gap-2 text-sm text-muted">
                  <span aria-hidden="true" className="size-2.5 rounded-full" style={{ background: fact.color }} />
                  {fact.label}
                </dt>
                <dd className="text-sm font-semibold tabular-nums">{fact.value}</dd>
              </div>
            ))}
          </dl>
          {snapshot.credit_score ? (
            <p className="mt-3 text-xs text-muted">
              <Badge tone="demo">Synthetic</Badge> The score comes from the mock services, not a credit bureau.
            </p>
          ) : null}
        </Card>
        {snapshot.alerts.length || snapshot.subscriptions.length ? (
          <Card title="Worth asking about">
            <ul className="space-y-2 text-sm">
              {snapshot.alerts.slice(0, 3).map((alert) => (
                <li key={alert.kind}>
                  <button type="button" disabled={!ready || busy} onClick={() => void ask(`${alert.title}. What should I do about it?`)} className="w-full rounded-lg bg-warn-soft p-3 text-left disabled:opacity-60">
                    <strong className="block text-warn">{alert.title}</strong>
                    <span className="text-xs text-muted">{formatMoney(alert.amount)} · ask Sam →</span>
                  </button>
                </li>
              ))}
              {snapshot.subscriptions.length ? (
                <li>
                  <button type="button" disabled={!ready || busy} onClick={() => void ask(TOPICS[0].prompt)} className="w-full rounded-lg bg-primary-soft p-3 text-left disabled:opacity-60">
                    <strong className="block text-primary">{snapshot.subscriptions.length} possible recurring charges</strong>
                    <span className="text-xs text-muted">Make sure you still need them · ask Sam →</span>
                  </button>
                </li>
              ) : null}
            </ul>
          </Card>
        ) : null}
        <Card title="Turn ideas into goals">
          <p className="text-sm text-muted">Save an education, car, retirement or credit goal and Sam can write a plan that uses its calculated numbers.</p>
          <Link href="/planning" className="mt-3 inline-block text-sm font-semibold text-primary">Open Plan & goals →</Link>
        </Card>
      </aside>
    </div>
  );
}
