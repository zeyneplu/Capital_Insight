"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { NavLinks, StaticNavLinks } from "./nav-links";

/** Phone navigation: a disclosure button that closes on navigation and on Escape. */
export function MobileMenu() {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="lg:hidden">
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-controls="mobile-navigation"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-border-strong px-3 text-sm font-medium"
      >
        <span aria-hidden="true">{open ? "✕" : "☰"}</span>
        Menu
      </button>
      {open ? (
        <nav id="mobile-navigation" aria-label="Main" className="absolute inset-x-0 top-full z-20 border-b border-border bg-surface p-3 shadow-lg">
          <Suspense fallback={<StaticNavLinks />}>
            <NavLinks onNavigate={() => setOpen(false)} />
          </Suspense>
        </nav>
      ) : null}
    </div>
  );
}
