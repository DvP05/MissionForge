import { ImportButton } from "@/components/persistence/PackageControls";
import { ScenarioGrid } from "@/components/scenario/ScenarioGrid";

export default function Home() {
  return (
    <div className="space-y-10">
      <section className="space-y-5">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-accent-amber">
          Mission design game
        </p>
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">MISSIONFORGE</h1>
        <p className="max-w-2xl text-lg text-muted">
          Design a space mission, stress-test it against uncertainty, and fly it in a
          simulated mission control. All analysis runs in the Python engine; this
          interface only presents the results.
        </p>
      </section>
      <section aria-labelledby="scenarios-heading" className="space-y-4">
        <h2 id="scenarios-heading" className="text-xl font-semibold">
          Choose a scenario
        </h2>
        <ScenarioGrid />
      </section>
      <section aria-labelledby="import-heading" className="space-y-3">
        <h2 id="import-heading" className="text-xl font-semibold">
          Continue from a package
        </h2>
        <p className="max-w-2xl text-sm text-muted">
          Import a mission package exported from MISSIONFORGE. The file is checked by the engine first; nothing you
          have saved changes unless it is accepted.
        </p>
        <ImportButton />
      </section>
    </div>
  );
}
