import Image from "next/image";
import Link from "next/link";
import { SavingsSlider } from "./savings-slider";

const FEATURES = [
  { title: "Every account, one view", body: "Checking, savings, cards, loans and your mortgage from multiple institutions, with net worth calculated to the cent.", color: "#38bdf8", icon: "M3 9l9-6 9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 21h18" },
  { title: "Goals that feel real", body: "College, your next car, an emergency fund or retirement. Drag sliders and watch the plan update.", color: "#a78bfa", icon: "M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18zM12 17a5 5 0 1 1 0-10 5 5 0 0 1 0 10zM12 13a1 1 0 1 1 0-2 1 1 0 0 1 0 2z" },
  { title: "A path to a better score", body: "Pick a target score and timeline. Get the utilization goal and the monthly card payments that support it.", color: "#fbbf24", icon: "M4 19h16M6 15l4-4 3 3 5-6" },
  { title: "Subscriptions & overspending", body: "Repeating charges are flagged for review, and you get a nudge when spending runs past your budget.", color: "#fb7185", icon: "M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" },
  { title: "Cash-flow forecast", body: "See where your unallocated cash is heading over the next 3 to 24 months, after your goal contributions.", color: "#34d399", icon: "M3 17l6-6 4 4 8-8M14 7h7v7" },
  { title: "Sam, your money coach", body: "Ask in plain English. Sam explains your numbers with NVIDIA Nemotron and stays strictly on personal finance.", color: "#818cf8", icon: "M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" },
];

const STEPS = [
  { title: "Verify your email", body: "A one-time code proves the inbox is yours. No passwords, no SSN." },
  { title: "Link your institutions", body: "Authorize each bank or lender separately. Tokens stay encrypted on our server." },
  { title: "Plan with Sam", body: "Set goals, review alerts and ask Sam what to do next." },
];

const TRUST = [
  "Bank tokens encrypted at rest and never sent to the browser",
  "TLS everywhere, including the managed PostgreSQL database",
  "Sam refuses off-topic or unsafe requests and never sees account numbers",
  "Calculations are exact; the AI explains numbers, it never invents them",
  "No money moves. This is a planning tool, not a payment app",
];

function Icon({ path, color }: { path: string; color: string }) {
  return (
    <span aria-hidden="true" className="grid size-11 place-items-center rounded-xl" style={{ background: color + "1f", color }}>
      <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round">
        <path d={path} />
      </svg>
    </span>
  );
}

/** Illustrative product preview built from markup; it is not anyone's data. */
function ProductPreview() {
  return (
    <div className="relative mx-auto w-full max-w-md sm:pb-28 lg:max-w-none" aria-label="Illustrative product preview" role="img">
      <div aria-hidden="true" className="absolute -inset-6 rounded-[2.5rem] bg-gradient-to-tr from-sky-500/30 via-indigo-500/20 to-fuchsia-500/30 blur-2xl" />
      <div aria-hidden="true" className="landing-float relative rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-2xl backdrop-blur">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] uppercase tracking-widest text-slate-400">Net worth</p>
            <p className="text-2xl font-semibold tabular-nums text-white">$48,210.55</p>
          </div>
          <span className="rounded-full bg-emerald-400/15 px-2.5 py-1 text-xs font-semibold text-emerald-300">▲ 4.2% this quarter</span>
        </div>
        <svg viewBox="0 0 300 70" className="mt-3 w-full">
          <defs>
            <linearGradient id="lp-area" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stopColor="#38bdf8" stopOpacity="0.45" />
              <stop offset="1" stopColor="#38bdf8" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d="M0,55 C30,52 45,40 70,42 S115,30 140,32 S190,18 215,22 S265,8 300,6 L300,70 L0,70 Z" fill="url(#lp-area)" />
          <path d="M0,55 C30,52 45,40 70,42 S115,30 140,32 S190,18 215,22 S265,8 300,6" fill="none" stroke="#38bdf8" strokeWidth="2.5" />
        </svg>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <div className="rounded-2xl bg-white/5 p-3">
            <p className="text-[11px] text-slate-400">Credit score</p>
            <p className="mt-1 text-xl font-semibold text-white">734 <span className="text-sm text-amber-300">→ 760</span></p>
            <div className="mt-2 h-1.5 rounded-full bg-gradient-to-r from-rose-400 via-amber-300 to-emerald-400" />
          </div>
          <div className="rounded-2xl bg-white/5 p-3">
            <p className="text-[11px] text-slate-400">Card utilization</p>
            <p className="mt-1 text-xl font-semibold text-white">18%</p>
            <p className="mt-1 text-[11px] text-emerald-300">Target 25% ✓</p>
          </div>
        </div>
        <div className="mt-3 space-y-2.5 rounded-2xl bg-white/5 p-3">
          {[
            ["College fund", "#a78bfa", 62],
            ["Next car", "#38bdf8", 41],
            ["Emergency cushion", "#fb7185", 78],
          ].map(([label, color, pct]) => (
            <div key={label as string}>
              <div className="flex justify-between text-[11px] text-slate-300"><span>{label}</span><span>{pct}%</span></div>
              <div className="mt-1 h-1.5 rounded-full bg-white/10"><div className="h-full rounded-full" style={{ width: `${pct}%`, background: color as string }} /></div>
            </div>
          ))}
        </div>
      </div>
      <div aria-hidden="true" className="landing-float-delayed absolute bottom-0 -left-4 hidden w-64 rounded-2xl border border-white/10 bg-slate-900/90 p-3 shadow-xl backdrop-blur sm:block lg:-left-10">
        <div className="flex items-center gap-2">
          <span className="grid size-7 place-items-center rounded-full bg-gradient-to-br from-sky-400 via-indigo-500 to-violet-500 text-xs font-bold text-white">S</span>
          <p className="text-xs font-semibold text-white">Sam</p>
        </div>
        <p className="mt-2 text-xs leading-relaxed text-slate-300">2 possible subscriptions found. Still using them? Cancelling one frees about <span className="font-semibold text-emerald-300">$31/mo</span> for your car goal.</p>
      </div>
    </div>
  );
}

export function Landing() {
  return (
    <div className="-mt-6 space-y-20 pb-6 lg:-mt-8 sm:space-y-24">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-[2rem] bg-slate-950 px-6 py-12 text-white sm:px-10 sm:py-16 lg:px-14">
        <div aria-hidden="true" className="landing-glow absolute -left-24 -top-24 size-96 rounded-full bg-sky-500/25 blur-3xl" />
        <div aria-hidden="true" className="landing-glow absolute -bottom-32 right-0 size-[28rem] rounded-full bg-fuchsia-500/20 blur-3xl [animation-delay:-4s]" />
        <div aria-hidden="true" className="absolute inset-0 bg-[radial-gradient(rgba(255,255,255,0.07)_1px,transparent_1px)] [background-size:22px_22px]" />
        <div className="relative grid items-center gap-12 lg:grid-cols-[1.05fr_1fr]">
          <div className="landing-rise">
            <div className="mb-6 flex items-center gap-3">
              <Image src="/logo-mark.png" alt="Capital Insight logo" width={56} height={56} priority className="size-14 rounded-2xl shadow-lg shadow-indigo-500/40" />
              <span className="text-lg font-semibold tracking-tight">Capital Insight</span>
            </div>
            <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-medium text-sky-200">
              <span className="size-1.5 animate-pulse rounded-full bg-emerald-400" /> HackUTD 2026 · AI by NVIDIA Nemotron
            </p>
            <h1 className="mt-5 text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">
              All your money.
              <span className="block bg-gradient-to-r from-sky-300 via-indigo-300 to-fuchsia-300 bg-clip-text text-transparent">One clear plan.</span>
            </h1>
            <p className="mt-5 max-w-xl text-base leading-relaxed text-slate-300 sm:text-lg">
              Capital Insight brings your banks, cards, loans and mortgage together, then helps you act on them: goals you can see, a path to a better credit score, and Sam, an AI coach that explains every number.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link href="/sign-in" className="rounded-xl bg-white px-5 py-3 text-sm font-semibold text-slate-950 shadow-lg shadow-sky-500/20 transition hover:-translate-y-0.5 hover:bg-sky-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300">
                Get started free →
              </Link>
              <a href="#features" className="rounded-xl border border-white/20 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10">
                See what it does
              </a>
            </div>
            <dl className="mt-10 grid max-w-lg grid-cols-3 gap-4 border-t border-white/10 pt-6">
              {[["6", "institutions in one view"], ["100%", "exact-cent math"], ["$0", "ever moved for you"]].map(([value, label]) => (
                <div key={label}>
                  <dt className="sr-only">{label}</dt>
                  <dd className="text-2xl font-semibold">{value}</dd>
                  <dd className="text-xs text-slate-400">{label}</dd>
                </div>
              ))}
            </dl>
          </div>
          <ProductPreview />
        </div>
      </section>

      {/* Features */}
      <section id="features" aria-labelledby="features-title" className="scroll-mt-8">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-primary">Everything in one place</p>
          <h2 id="features-title" className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">From scattered accounts to a plan you trust</h2>
          <p className="mt-3 text-muted">Banking apps show balances. Capital Insight shows what to do next.</p>
        </div>
        <ul className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <li key={feature.title} className="group relative overflow-hidden rounded-2xl border border-border bg-surface p-6 transition duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-black/5">
              <div aria-hidden="true" className="absolute inset-x-0 top-0 h-1 opacity-0 transition group-hover:opacity-100" style={{ background: feature.color }} />
              <Icon path={feature.icon} color={feature.color} />
              <h3 className="mt-4 font-semibold">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{feature.body}</p>
            </li>
          ))}
        </ul>
      </section>

      {/* Interactive goal */}
      <section aria-labelledby="try-title" className="grid items-center gap-10 lg:grid-cols-[0.8fr_1.2fr]">
        <div>
          <p className="text-sm font-semibold uppercase tracking-widest text-primary">Try it now</p>
          <h2 id="try-title" className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Small moves, visible progress</h2>
          <p className="mt-3 leading-relaxed text-muted">
            Pick a goal and drag the sliders. Inside the app, goals use your real cash flow, appear on your dashboard if you want them there, and Sam can turn them into a step-by-step plan.
          </p>
          <Link href="/sign-in" className="mt-6 inline-block text-sm font-semibold text-primary">Save goals to your dashboard →</Link>
        </div>
        <SavingsSlider />
      </section>

      {/* Sam */}
      <section aria-labelledby="sam-title" className="relative overflow-hidden rounded-[2rem] bg-gradient-to-br from-indigo-950 via-slate-950 to-slate-900 px-6 py-12 text-white sm:px-10 lg:px-14">
        <div aria-hidden="true" className="absolute -right-20 top-10 size-80 rounded-full bg-indigo-500/25 blur-3xl" />
        <div className="relative grid items-center gap-10 lg:grid-cols-2">
          <div>
            <p className="text-sm font-semibold uppercase tracking-widest text-indigo-300">Meet Sam</p>
            <h2 id="sam-title" className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Ask anything about your money</h2>
            <p className="mt-3 leading-relaxed text-slate-300">
              &ldquo;Would a new car be smart right now?&rdquo; &ldquo;How do I raise my score?&rdquo; Sam reads a private summary of your accounts and answers in clear steps.
            </p>
            <ul className="mt-6 space-y-3 text-sm">
              {["Finance-only: off-topic and unsafe requests are refused", "Uses calculated figures and never changes them", "No guarantees about scores, returns or approvals"].map((item) => (
                <li key={item} className="flex gap-3"><span aria-hidden="true" className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-emerald-400/20 text-xs text-emerald-300">✓</span>{item}</li>
              ))}
            </ul>
          </div>
          <figure className="space-y-3 rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur" aria-label="Example conversation with Sam">
            <figcaption className="text-[11px] uppercase tracking-widest text-slate-400">Example conversation</figcaption>
            <p className="ml-auto max-w-[85%] rounded-2xl rounded-tr-sm bg-sky-400 px-4 py-2.5 text-sm text-slate-950">Would it be smart to buy a new car right now?</p>
            <div className="flex gap-3">
              <span aria-hidden="true" className="grid size-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-sky-400 via-indigo-500 to-violet-500 text-xs font-bold">S</span>
              <div className="space-y-2 rounded-2xl rounded-tl-sm bg-slate-900/80 p-4 text-sm text-slate-200">
                <p>Maybe not yet. Your monthly room is tight, and a new loan would push total debt payments past a comfortable share of income.</p>
                <ol className="space-y-1.5">
                  {["Grow your car fund to a 20% down payment first", "Pay card utilization below 30%", "Compare a certified used model with the same payment"].map((step, index) => (
                    <li key={step} className="flex gap-2"><span className="grid size-5 shrink-0 place-items-center rounded-full bg-indigo-400/20 text-[11px] font-semibold text-indigo-200">{index + 1}</span>{step}</li>
                  ))}
                </ol>
              </div>
            </div>
          </figure>
        </div>
      </section>

      {/* How it works */}
      <section aria-labelledby="how-title">
        <h2 id="how-title" className="text-center text-3xl font-semibold tracking-tight sm:text-4xl">Up and running in three steps</h2>
        <ol className="mt-10 grid gap-4 md:grid-cols-3">
          {STEPS.map((step, index) => (
            <li key={step.title} className="relative rounded-2xl border border-border bg-surface p-6">
              <span className="grid size-10 place-items-center rounded-full bg-gradient-to-br from-sky-400 to-indigo-500 text-sm font-bold text-white">{index + 1}</span>
              <h3 className="mt-4 font-semibold">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Trust + CTA */}
      <section aria-labelledby="trust-title" className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-3xl border border-border bg-surface p-7 sm:p-9">
          <h2 id="trust-title" className="text-2xl font-semibold tracking-tight">Built to be trusted</h2>
          <ul className="mt-5 space-y-3">
            {TRUST.map((item) => (
              <li key={item} className="flex gap-3 text-sm"><span aria-hidden="true" className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-good-soft text-xs text-good">✓</span>{item}</li>
            ))}
          </ul>
        </div>
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-sky-500 via-indigo-500 to-fuchsia-500 p-7 text-white sm:p-9">
          <div aria-hidden="true" className="absolute -right-10 -top-10 size-48 rounded-full border-[28px] border-white/15" />
          <Image src="/logo-mark.png" alt="" width={48} height={48} className="relative mb-4 size-12 rounded-xl ring-2 ring-white/40" />
          <h2 className="relative text-2xl font-semibold tracking-tight sm:text-3xl">Your plan starts with one code.</h2>
          <p className="relative mt-3 text-sm text-white/85">Verify your email, link an institution, and see your whole financial picture in minutes.</p>
          <Link href="/sign-in" className="relative mt-6 inline-block rounded-xl bg-white px-5 py-3 text-sm font-semibold text-indigo-700 shadow-lg transition hover:-translate-y-0.5">
            Sign in to Capital Insight →
          </Link>
          <p className="relative mt-4 text-xs text-white/75">Judging HackUTD? Use the tester login shared by the team.</p>
        </div>
      </section>

      <p className="text-center text-xs text-muted">
        HackUTD 2026 project. Institutions and records are fictional and synthetic. Previews on this page are illustrative. Capital Insight is not a bank and does not give licensed financial advice.
      </p>
    </div>
  );
}
