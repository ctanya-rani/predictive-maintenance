import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { Activity, Github, Info } from "lucide-react";

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-panel/60 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] items-center justify-between gap-4 px-6 py-4">
          <Link to="/" className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/15 text-primary">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-semibold leading-tight">TrainWatch</div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                Predictive maintenance · demo
              </div>
            </div>
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            <Link
              to="/"
              activeOptions={{ exact: true }}
              className="rounded-md px-3 py-1.5 text-muted-foreground transition hover:bg-muted hover:text-foreground [&.active]:bg-muted [&.active]:text-foreground"
              activeProps={{ className: "active" }}
            >
              Fleet
            </Link>
            <Link
              to="/about"
              className="rounded-md px-3 py-1.5 text-muted-foreground transition hover:bg-muted hover:text-foreground [&.active]:bg-muted [&.active]:text-foreground"
              activeProps={{ className: "active" }}
            >
              <span className="inline-flex items-center gap-1.5">
                <Info className="h-3.5 w-3.5" /> About
              </span>
            </Link>
            <a
              href="https://github.com/ctanya-rani/predictive-maintenance"
              target="_blank"
              rel="noreferrer"
              className="ml-2 inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground transition hover:text-foreground"
            >
              <Github className="h-3.5 w-3.5" /> Source
            </a>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-[1400px] px-6 py-6">{children}</main>
      <footer className="mx-auto max-w-[1400px] px-6 pb-10 pt-4">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Synthetic telemetry · deterministic seed 20260717 · no live data
        </p>
      </footer>
    </div>
  );
}
