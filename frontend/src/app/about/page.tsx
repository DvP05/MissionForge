import { ConstraintBadge, type ConstraintStatus } from "@/components/common/ConstraintBadge";
import { FidelityBadge, type Fidelity } from "@/components/common/FidelityBadge";
import { ProvenancePopover, type Provenance } from "@/components/common/ProvenancePopover";

const CONSTRAINT_STATES: ConstraintStatus[] = ["pass", "warning", "fail", "not-modelled"];
const FIDELITIES: Fidelity[] = [
  "source-backed",
  "derived",
  "gameplay-estimate",
  "not-modelled",
];

// Demonstration record for the legend only; not a real catalogue value.
const EXAMPLE_PROVENANCE: Provenance = {
  fidelity: "gameplay-estimate",
  sourceName: "Example entry (legend only)",
  sourceVersion: "n/a",
  assumptions: ["Shown to explain what the provenance panel contains."],
};

export const metadata = { title: "About | MISSIONFORGE" };

export default function AboutPage() {
  return (
    <div className="space-y-10">
      <section className="max-w-2xl space-y-3">
        <h1 className="text-3xl font-semibold tracking-tight">About MISSIONFORGE</h1>
        <p className="text-muted">
          MISSIONFORGE is an independent educational prototype. The Python engine owns all
          engineering calculations; this interface presents results and how much to trust them.
        </p>
      </section>

      <section aria-labelledby="fidelity-legend" className="space-y-3">
        <h2 id="fidelity-legend" className="text-xl font-semibold">
          Value fidelity
        </h2>
        <ul className="flex flex-wrap items-center gap-3">
          {FIDELITIES.map((f) => (
            <li key={f}>
              <FidelityBadge fidelity={f} />
            </li>
          ))}
          <li className="flex items-center gap-2 text-sm text-muted">
            Example provenance panel
            <ProvenancePopover provenance={EXAMPLE_PROVENANCE} label="the example value" />
          </li>
        </ul>
      </section>

      <section aria-labelledby="constraint-legend" className="space-y-3">
        <h2 id="constraint-legend" className="text-xl font-semibold">
          Constraint results
        </h2>
        <ul className="flex flex-wrap gap-3">
          {CONSTRAINT_STATES.map((s) => (
            <li key={s}>
              <ConstraintBadge status={s} />
            </li>
          ))}
        </ul>
        <p className="text-sm text-muted">
          Every result carries an icon and a word, so meaning never depends on colour alone.
        </p>
      </section>
    </div>
  );
}
