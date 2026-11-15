import { ImportButton } from "@/components/persistence/PackageControls";
import { SavedMissions } from "@/components/persistence/SavedMissions";
import { LearningCheck } from "@/components/learning/LearningCheck";
import { ScenarioGrid } from "@/components/scenario/ScenarioGrid";

/** Mission Hangar: the entry point (scenarios, saved architectures, packages). */
export default function Home() {
  return (
    <div className="space-y-12">
      <section className="panel relative isolate overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 bg-background-2/90 px-4 py-2">
          <span className="label-caps text-primary">{"// Command centre"}</span>
          <span className="label-caps text-muted">Educational mission-design console · engine-computed results</span>
        </div>
        <div aria-hidden className="hud-grid absolute inset-0 -z-10 opacity-60" />
        <div aria-hidden className="absolute inset-x-0 bottom-0 -z-10 h-40 bg-[url('/backdrops/orbital-layers.svg')] bg-cover bg-bottom bg-no-repeat opacity-60 grayscale" />
        <div aria-hidden className="absolute bottom-10 right-16 -z-10 hidden h-44 w-44 border border-border sm:block">
          <div className="absolute inset-0 m-auto h-28 w-28 rounded-full border border-dashed border-faint" />
          <div className="absolute left-1/2 top-0 h-full w-px bg-border" />
          <div className="absolute left-0 top-1/2 h-px w-full bg-border" />
        </div>
        <div className="px-6 py-10 sm:px-10 sm:py-14">
          <p className="flex items-center gap-2">
            <span aria-hidden className="h-1.5 w-1.5 bg-signal" />
            <span className="label-caps text-muted">Mission design game</span>
          </p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-6xl">MISSIONFORGE</h1>
          <p className="mt-4 max-w-2xl text-lg text-muted">
            Design a space mission, stress-test it against uncertainty, and fly it in a simulated mission control. Every
            number comes from the Python engine; this interface only presents the results.
          </p>
          <p className="label-caps mt-6 text-primary">Design it · Stress it · Fly it · Learn why</p>
        </div>
      </section>

      <section aria-labelledby="continue-heading" className="space-y-4">
        <h2 id="continue-heading" className="label-caps text-sm text-primary">
          {"// Continue a mission"}
        </h2>
        <SavedMissions limit={6} />
      </section>

      <section aria-labelledby="scenarios-heading" className="space-y-4">
        <h2 id="scenarios-heading" className="label-caps text-sm text-primary">
          {"// Choose a scenario"}
        </h2>
        <ScenarioGrid />
      </section>
      <LearningCheck phase="pre" />
      <section aria-labelledby="import-heading" className="space-y-3">
        <h2 id="import-heading" className="label-caps text-sm text-primary">
          {"// Continue from a package"}
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
