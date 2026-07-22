import { createFileRoute } from "@tanstack/react-router";
import { Github } from "lucide-react";
import { Shell } from "@/components/trainwatch/Shell";
import { FAULTS, SENSORS } from "@/lib/trainwatch/config";

export const Route = createFileRoute("/about")({
  head: () => ({
    meta: [
      { title: "About · TrainWatch" },
      {
        name: "description",
        content:
          "How TrainWatch generates synthetic train telemetry, detects anomalies and scores fleet health.",
      },
      { property: "og:title", content: "About · TrainWatch" },
      {
        property: "og:description",
        content:
          "Data generation, anomaly detection and alert episodes behind the TrainWatch predictive-maintenance demo.",
      },
    ],
  }),
  component: About,
});

function About() {
  return (
    <Shell>
      <div className="mx-auto max-w-3xl">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          About
        </div>
        <h1 className="mt-1 text-2xl font-semibold">TrainWatch</h1>
        <p className="mt-3 text-sm text-muted-foreground">
          A predictive-maintenance dashboard for a small train fleet, built on
          synthetic sensor data. This frontend is a browser port of the Python
          pipeline in{" "}
          <a
            className="text-primary hover:underline"
            href="https://github.com/ctanya-rani/predictive-maintenance"
            target="_blank"
            rel="noreferrer"
          >
            ctanya-rani/predictive-maintenance
          </a>
          : same fleet, same fault narratives, same detector ideas.
        </p>

        <a
          href="https://github.com/ctanya-rani/predictive-maintenance"
          target="_blank"
          rel="noreferrer"
          className="mt-4 inline-flex items-center gap-2 rounded-md border border-border bg-panel px-3 py-1.5 text-sm hover:bg-muted"
        >
          <Github className="h-4 w-4" /> View source on GitHub
        </a>

        <section className="mt-8">
          <h2 className="text-lg font-semibold">What runs in the browser</h2>
          <ol className="mt-3 space-y-3 text-sm text-muted-foreground">
            <li>
              <span className="font-medium text-foreground">1. Synthetic telemetry.</span>{" "}
              8 trains × 4 channels × 14 days at a 30-minute cadence, driven by a seeded
              PRNG. Each series has a daily duty cycle (morning/evening peaks),
              per-train character offsets and gaussian noise.
            </li>
            <li>
              <span className="font-medium text-foreground">2. Injected faults.</span>{" "}
              Four failure narratives are seeded into the fleet — see the table below.
            </li>
            <li>
              <span className="font-medium text-foreground">3. Anomaly detection.</span>{" "}
              Seasonal robust z-score for spikes, EWMA drift tracker for slow trends,
              rolling variance for a stuck transducer, and conventional engineering
              limits.
            </li>
            <li>
              <span className="font-medium text-foreground">4. Alert episodes.</span>{" "}
              Consecutive anomalous samples are merged into flicker-bridged episodes
              carrying severity, detector kind, peak reading and a maintenance
              recommendation.
            </li>
            <li>
              <span className="font-medium text-foreground">5. Health scores.</span>{" "}
              Each train starts at 100. Active criticals penalise heaviest, with
              diminishing penalties for repeat episodes on the same channel.
            </li>
          </ol>
        </section>

        <section className="mt-8">
          <h2 className="text-lg font-semibold">Sensors</h2>
          <div className="mt-3 overflow-hidden rounded-lg border border-border bg-panel">
            <table className="w-full text-sm">
              <thead className="text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="px-3 py-2">Channel</th>
                  <th className="px-3 py-2">Unit</th>
                  <th className="px-3 py-2">Warn</th>
                  <th className="px-3 py-2">Critical</th>
                </tr>
              </thead>
              <tbody className="font-mono text-xs">
                {Object.values(SENSORS).map((s) => (
                  <tr key={s.key} className="border-b border-border last:border-none">
                    <td className="px-3 py-2 text-foreground">{s.label}</td>
                    <td className="px-3 py-2 text-muted-foreground">{s.unit}</td>
                    <td className="px-3 py-2 text-watch">
                      {s.warnLow ?? "—"} / {s.warnHigh ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-critical">
                      {s.critLow ?? "—"} / {s.critHigh ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mt-8">
          <h2 className="text-lg font-semibold">Seeded faults</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {FAULTS.map((f) => (
              <li
                key={f.trainId + f.sensor}
                className="rounded-lg border border-border bg-panel p-3"
              >
                <div className="flex flex-wrap items-baseline gap-x-3">
                  <span className="font-mono font-semibold">{f.trainId}</span>
                  <span className="text-muted-foreground">{SENSORS[f.sensor].label}</span>
                  <span className="ml-auto font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    {f.kind} · from day {f.startDay}
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{f.description}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-8 rounded-lg border border-border bg-panel p-4 text-sm">
          <h2 className="text-base font-semibold">Note on GitHub sync</h2>
          <p className="mt-2 text-muted-foreground">
            This is a fresh browser frontend built in Lovable — Lovable cannot push
            commits directly into the existing{" "}
            <span className="font-mono text-foreground">predictive-maintenance</span>{" "}
            repo. To ship it back:
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
            <li>
              Connect this Lovable project to a new repo like{" "}
              <span className="font-mono text-foreground">
                predictive-maintenance-frontend
              </span>{" "}
              via the GitHub integration, or
            </li>
            <li>
              Download the code from Lovable and drop it into the existing repo as a{" "}
              <span className="font-mono text-foreground">frontend/</span> folder.
            </li>
          </ul>
        </section>
      </div>
    </Shell>
  );
}
